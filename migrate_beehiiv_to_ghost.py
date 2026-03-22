#!/usr/bin/env python3
"""
migrate_beehiiv_to_ghost.py — The Rockland Navigator

Migrates past newsletter posts from Beehiiv to Ghost.

Steps:
  1. Reads Beehiiv API key from config.yaml
  2. Auto-discovers your Beehiiv publication ID
  3. Fetches all published posts from Beehiiv
  4. Converts each post to Ghost format
  5. Imports them to Ghost via Admin API (as published posts, preserving dates)

Usage:
  python migrate_beehiiv_to_ghost.py

Run this once after setting up Ghost. It is safe to re-run — it checks for
existing posts by title and skips duplicates.

Requirements: fill in config.yaml with:
  - beehiiv.api_key      (your existing Beehiiv API key)
  - ghost.url            (e.g. https://rocklandnavigator.com)
  - ghost.admin_api_key  (from Ghost Admin → Settings → Integrations)
"""

import certifi
import os
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

import sys
import time
import hmac
import hashlib
import base64
import json
import requests
import logging
from datetime import datetime, timezone
from pathlib import Path
import yaml

# ─────────────────────────────────────────────
# Setup
# ─────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("migrate")

BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.yaml"

BEEHIIV_API_BASE = "https://api.beehiiv.com/v2"


# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────

def load_config() -> dict:
    if not CONFIG_FILE.exists():
        print("ERROR: config.yaml not found. Copy config.yaml.example and fill in your values.")
        sys.exit(1)
    with open(CONFIG_FILE, "r") as f:
        return yaml.safe_load(f)


# ─────────────────────────────────────────────
# Ghost JWT (stdlib only, no PyJWT needed)
# ─────────────────────────────────────────────

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def make_ghost_jwt(admin_api_key: str) -> str:
    """Generate a 5-minute JWT for the Ghost Admin API."""
    try:
        key_id, hex_secret = admin_api_key.split(":", 1)
    except ValueError:
        raise ValueError(
            "Ghost Admin API key must be in  id:secret  format.\n"
            "Find it in Ghost Admin → Settings → Integrations → your integration."
        )
    secret = bytes.fromhex(hex_secret)
    iat = int(time.time())
    header  = {"alg": "HS256", "typ": "JWT", "kid": key_id}
    payload = {"iat": iat, "exp": iat + 300, "aud": "/admin/"}
    h = _b64url(json.dumps(header,  separators=(",", ":")).encode())
    p = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(secret, f"{h}.{p}".encode(), hashlib.sha256).digest()
    return f"{h}.{p}.{_b64url(sig)}"


# ─────────────────────────────────────────────
# Beehiiv helpers
# ─────────────────────────────────────────────

def beehiiv_get(path: str, api_key: str, params: dict = None) -> dict:
    """Make a GET request to the Beehiiv API."""
    resp = requests.get(
        f"{BEEHIIV_API_BASE}{path}",
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        params=params or {},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def get_publication_id(api_key: str) -> str:
    """Auto-discover the publication ID from the Beehiiv API."""
    logger.info("Fetching Beehiiv publications...")
    data = beehiiv_get("/publications", api_key)
    pubs = data.get("data", [])
    if not pubs:
        print("\nERROR: No publications found on this Beehiiv account.")
        sys.exit(1)
    if len(pubs) == 1:
        pub = pubs[0]
        logger.info(f"Found publication: {pub.get('name', 'Unknown')} ({pub['id']})")
        return pub["id"]
    # Multiple publications — ask user to pick
    print("\nMultiple Beehiiv publications found:")
    for i, pub in enumerate(pubs):
        print(f"  [{i+1}] {pub.get('name', 'Unknown')} — {pub['id']}")
    choice = input("Enter the number of the publication to migrate: ").strip()
    return pubs[int(choice) - 1]["id"]


def fetch_beehiiv_posts(api_key: str, publication_id: str) -> list[dict]:
    """Fetch all published posts from Beehiiv, handling pagination."""
    posts = []
    page = 1
    logger.info(f"Fetching posts from Beehiiv publication {publication_id}...")

    while True:
        data = beehiiv_get(
            f"/publications/{publication_id}/posts",
            api_key,
            params={
                "status": "confirmed",  # published posts only
                "expand[]": ["free_email_content", "stats"],
                "limit": 10,
                "page": page,
            },
        )
        batch = data.get("data", [])
        if not batch:
            break
        posts.extend(batch)
        logger.info(f"  Page {page}: {len(batch)} posts (total so far: {len(posts)})")

        # Check if there are more pages
        total_pages = data.get("total_pages", 1)
        if page >= total_pages:
            break
        page += 1

    logger.info(f"Beehiiv: {len(posts)} published posts found")
    return posts


# ─────────────────────────────────────────────
# Conversion: Beehiiv → Ghost
# ─────────────────────────────────────────────

def beehiiv_post_to_ghost(post: dict) -> dict:
    """
    Convert a Beehiiv post dict to a Ghost Admin API post dict.

    Beehiiv content is stored in free_email_content (HTML) or content fields.
    We pass it directly as html — Ghost converts it to Lexical internally.
    """
    title = post.get("subject_line") or post.get("title") or "Untitled"
    subtitle = post.get("preview_text") or post.get("subtitle") or ""

    # Try to get HTML content from various Beehiiv fields
    html_content = (
        post.get("free_email_content")
        or post.get("content", {}).get("free", {}).get("email")
        or post.get("content", {}).get("free", {}).get("web")
        or post.get("free_web_content")
        or ""
    )

    if not html_content:
        logger.warning(f"  No HTML content found for post: {title!r} — importing title only")

    # Parse the publish date — Beehiiv returns Unix timestamps
    published_at_raw = post.get("publish_date") or post.get("created_at")
    if isinstance(published_at_raw, (int, float)):
        published_at = datetime.fromtimestamp(published_at_raw, tz=timezone.utc).isoformat()
    elif isinstance(published_at_raw, str):
        published_at = published_at_raw
    else:
        published_at = datetime.now(tz=timezone.utc).isoformat()

    # Beehiiv web URL — preserve as a meta field for reference
    beehiiv_url = post.get("web_url", "")

    ghost_post = {
        "title": title,
        "custom_excerpt": subtitle,
        "html": html_content,
        "status": "published",
        "published_at": published_at,
        "tags": [
            {"name": "Newsletter"},
            {"name": "Local News"},
            {"name": "Rockland County"},
        ],
    }

    # Store original Beehiiv URL as codeinjection_head comment (non-visible, for reference)
    if beehiiv_url:
        ghost_post["codeinjection_head"] = f"<!-- Migrated from Beehiiv: {beehiiv_url} -->"

    return ghost_post


# ─────────────────────────────────────────────
# Ghost helpers
# ─────────────────────────────────────────────

def ghost_post(path: str, admin_api_key: str, ghost_url: str, payload: dict) -> dict:
    """Make a POST request to the Ghost Admin API."""
    token = make_ghost_jwt(admin_api_key)
    resp = requests.post(
        f"{ghost_url.rstrip('/')}/ghost/api/admin{path}",
        json=payload,
        headers={
            "Authorization": f"Ghost {token}",
            "Content-Type": "application/json",
            "Accept-Version": "v5.0",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def ghost_get(path: str, admin_api_key: str, ghost_url: str, params: dict = None) -> dict:
    """Make a GET request to the Ghost Admin API."""
    token = make_ghost_jwt(admin_api_key)
    resp = requests.get(
        f"{ghost_url.rstrip('/')}/ghost/api/admin{path}",
        headers={
            "Authorization": f"Ghost {token}",
            "Accept-Version": "v5.0",
        },
        params=params or {},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def get_existing_ghost_titles(admin_api_key: str, ghost_url: str) -> set[str]:
    """Fetch titles of posts already in Ghost to detect duplicates."""
    try:
        data = ghost_get("/posts/", admin_api_key, ghost_url, params={"limit": "all", "fields": "title"})
        return {p["title"] for p in data.get("posts", [])}
    except Exception as e:
        logger.warning(f"Could not fetch existing Ghost posts: {e}")
        return set()


def import_post_to_ghost(ghost_post_data: dict, admin_api_key: str, ghost_url: str) -> dict:
    """Import a single post to Ghost."""
    result = ghost_post("/posts/", admin_api_key, ghost_url, {"posts": [ghost_post_data]})
    return result.get("posts", [{}])[0]


# ─────────────────────────────────────────────
# Main migration
# ─────────────────────────────────────────────

def migrate():
    print("\n" + "=" * 60)
    print("  Rockland Navigator — Beehiiv → Ghost Migration")
    print("=" * 60 + "\n")

    # ── Load config ───────────────────────────────────────────────────────────
    config = load_config()

    beehiiv_api_key = config.get("beehiiv", {}).get("api_key", "")
    ghost_cfg = config.get("ghost", {})
    ghost_url = ghost_cfg.get("url", "").rstrip("/")
    ghost_admin_key = ghost_cfg.get("admin_api_key", "")

    # Validate
    errors = []
    if not beehiiv_api_key:
        errors.append("beehiiv.api_key not set in config.yaml")
    if not ghost_url or ghost_url == "https://your-ghost-site.com":
        errors.append("ghost.url not set in config.yaml")
    if not ghost_admin_key or ghost_admin_key == "YOUR_GHOST_ADMIN_API_KEY":
        errors.append("ghost.admin_api_key not set in config.yaml")
    if errors:
        print("Configuration errors:")
        for e in errors:
            print(f"  ✗ {e}")
        sys.exit(1)

    logger.info(f"Ghost target: {ghost_url}")

    # ── Fetch from Beehiiv ────────────────────────────────────────────────────
    try:
        publication_id = get_publication_id(beehiiv_api_key)
        beehiiv_posts = fetch_beehiiv_posts(beehiiv_api_key, publication_id)
    except requests.HTTPError as e:
        print(f"\nERROR fetching from Beehiiv: {e}")
        print("Check your beehiiv.api_key in config.yaml.")
        sys.exit(1)

    if not beehiiv_posts:
        print("\nNo published posts found on Beehiiv. Nothing to migrate.")
        sys.exit(0)

    # ── Check Ghost for existing posts ────────────────────────────────────────
    logger.info("Checking Ghost for existing posts (to skip duplicates)...")
    try:
        existing_titles = get_existing_ghost_titles(ghost_admin_key, ghost_url)
        if existing_titles:
            logger.info(f"  Found {len(existing_titles)} existing post(s) in Ghost")
    except requests.HTTPError as e:
        print(f"\nERROR connecting to Ghost: {e.response.status_code} — {e.response.text[:200]}")
        print("Check ghost.url and ghost.admin_api_key in config.yaml.")
        sys.exit(1)

    # ── Migrate ───────────────────────────────────────────────────────────────
    print(f"\nMigrating {len(beehiiv_posts)} post(s) from Beehiiv → Ghost...\n")

    imported = 0
    skipped  = 0
    failed   = 0

    for i, post in enumerate(beehiiv_posts, 1):
        title = post.get("subject_line") or post.get("title") or f"Post {i}"
        print(f"  [{i}/{len(beehiiv_posts)}] {title[:70]}")

        # Skip duplicates
        if title in existing_titles:
            print(f"    ↳ Already exists in Ghost — skipping\n")
            skipped += 1
            continue

        # Convert
        ghost_data = beehiiv_post_to_ghost(post)

        # Import
        try:
            result = import_post_to_ghost(ghost_data, ghost_admin_key, ghost_url)
            post_id  = result.get("id", "?")
            post_url = result.get("url", "")
            print(f"    ✓ Imported — Ghost URL: {post_url or post_id}\n")
            imported += 1
            time.sleep(0.5)  # Be gentle with the API

        except requests.HTTPError as e:
            status = e.response.status_code
            body   = e.response.text[:300]
            print(f"    ✗ Failed ({status}): {body}\n")
            logger.error(f"Failed to import '{title}': {status} — {body}")
            failed += 1

        except Exception as e:
            print(f"    ✗ Unexpected error: {e}\n")
            logger.error(f"Unexpected error importing '{title}': {e}")
            failed += 1

    # ── Summary ───────────────────────────────────────────────────────────────
    print("=" * 60)
    print("  Migration complete")
    print("=" * 60)
    print(f"  ✓ Imported:  {imported}")
    print(f"  ↷ Skipped:   {skipped} (already existed)")
    print(f"  ✗ Failed:    {failed}")
    print()

    if imported > 0:
        print(f"  Posts are published in Ghost at: {ghost_url}")
        print(f"  Review them in Ghost Admin: {ghost_url}/ghost/#/posts")
        print()

    if failed > 0:
        print("  Some posts failed — check the output above for details.")
        print("  You can re-run this script safely; duplicates will be skipped.")
        print()

    # ── Next steps ────────────────────────────────────────────────────────────
    print("  NEXT STEPS:")
    print("  1. Review imported posts in Ghost Admin")
    print("  2. Point rocklandnavigator.com DNS to Ghost (see README)")
    print("  3. Submit your sitemap to Google Search Console:")
    print(f"     {ghost_url}/sitemap.xml")
    print("  4. Once DNS is live, cancel your Beehiiv subscription")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    migrate()
