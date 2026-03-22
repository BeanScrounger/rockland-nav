"""
Publisher for The Rockland Navigator — Ghost edition.

Posts the approved newsletter to Ghost as a draft post via the Ghost Admin API.
Ghost Admin API docs: https://ghost.org/docs/admin-api/

Authentication uses a JWT generated from your Ghost Admin API key.
The key format is:  id:secret  (found in Ghost Admin → Settings → Integrations → Add custom integration)
"""

import time
import hmac
import hashlib
import base64
import json
import webbrowser
import requests
import logging
from datetime import datetime
from pathlib import Path
import yaml

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.yaml"
TEMPLATE_FILE = BASE_DIR / "newsletter_template.yaml"
OUTPUT_DIR = BASE_DIR / "output"


def _load_config() -> dict:
    with open(CONFIG_FILE, "r") as f:
        return yaml.safe_load(f)


def _load_template() -> dict:
    with open(TEMPLATE_FILE, "r") as f:
        return yaml.safe_load(f)


# ─────────────────────────────────────────────
# Ghost JWT auth (no external library needed)
# ─────────────────────────────────────────────

def _b64url(data: bytes) -> str:
    """Base64-url encode without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _make_ghost_jwt(admin_api_key: str) -> str:
    """
    Generate a short-lived JWT for the Ghost Admin API.

    Ghost Admin API key format:  {key_id}:{hex_secret}
    JWT is valid for 5 minutes.
    """
    try:
        key_id, hex_secret = admin_api_key.split(":", 1)
    except ValueError:
        raise ValueError(
            "Ghost Admin API key must be in the format  id:secret\n"
            "Find it in Ghost Admin → Settings → Integrations → Add custom integration."
        )

    secret_bytes = bytes.fromhex(hex_secret)
    iat = int(time.time())
    exp = iat + 300  # 5 minutes

    header  = {"alg": "HS256", "typ": "JWT", "kid": key_id}
    payload = {"iat": iat, "exp": exp, "aud": "/admin/"}

    header_b64  = _b64url(json.dumps(header,  separators=(",", ":")).encode())
    payload_b64 = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode()

    sig = hmac.new(secret_bytes, signing_input, hashlib.sha256).digest()
    return f"{header_b64}.{payload_b64}.{_b64url(sig)}"


# ─────────────────────────────────────────────
# Manual fallback
# ─────────────────────────────────────────────

def _manual_publish_fallback(html_content: str, date_str: str, ghost_url: str = "") -> bool:
    """Open the rendered newsletter + Ghost editor when API publish fails."""
    OUTPUT_DIR.mkdir(exist_ok=True)

    template = _load_template()
    newsletter_name = template.get("newsletter", {}).get("name", "The Rockland Navigator")
    tagline = template.get("newsletter", {}).get("tagline", "Your hyperlocal guide to Rockland County, NY")
    title = f"{newsletter_name} — {date_str}"

    dated_filename = f"newsletter_{date_str.replace(' ', '_').replace(',', '')}.html"
    dated_path = OUTPUT_DIR / dated_filename
    dated_path.write_text(html_content, encoding="utf-8")

    new_post_url = f"{ghost_url.rstrip('/')}/ghost/#/editor/post" if ghost_url else ""

    print("\n" + "=" * 60)
    print("  MANUAL PUBLISH — 4 easy steps")
    print("=" * 60)
    print()
    print("  Step 1 — Copy these into Ghost when prompted:")
    print(f"    Title:   {title}")
    print(f"    Excerpt: {tagline}")
    print()
    print("  Step 2 — Your newsletter is opening in your browser.")
    print("           Press Cmd+A to select all, then Cmd+C to copy.")
    print()
    print("  Step 3 — Ghost's new post editor is also opening.")
    print("           Click into the content area and press Cmd+V to paste.")
    print()
    print("  Step 4 — Fill in the title above, then Save Draft or Publish.")
    print()
    print(f"  HTML file saved at: {dated_path}")
    print("=" * 60 + "\n")

    logger.info(f"Manual publish fallback — HTML saved to {dated_path}")
    webbrowser.open(dated_path.as_uri())
    if new_post_url:
        time.sleep(1)
        webbrowser.open(new_post_url)
    return True


# ─────────────────────────────────────────────
# Main publish function
# ─────────────────────────────────────────────

def publish_to_ghost(html_content: str, date_str: str = None) -> bool:
    """
    Publish the newsletter to Ghost as a draft post.

    Uses the Ghost Admin API v5. On any API failure, falls back to the
    manual publish flow (saves HTML, opens Ghost editor in browser).

    Args:
        html_content: Full HTML string of the formatted newsletter.
        date_str: Human-readable date for the post title.

    Returns:
        True on success or graceful fallback, False on hard failure.
    """
    if date_str is None:
        date_str = datetime.now().strftime("%B %d, %Y")

    config = _load_config()
    template = _load_template()

    ghost_cfg = config.get("ghost", {})
    admin_api_key = ghost_cfg.get("admin_api_key", "")
    ghost_url = ghost_cfg.get("url", "").rstrip("/")

    newsletter_name = template.get("newsletter", {}).get("name", "The Rockland Navigator")
    tagline = template.get("newsletter", {}).get("tagline", "Your hyperlocal guide to Rockland County, NY")
    title = f"{newsletter_name} — {date_str}"

    # ── Validate config ───────────────────────────────────────────────────────
    if not ghost_url or ghost_url == "https://your-ghost-site.com":
        logger.error("Ghost URL not set in config.yaml (ghost.url)")
        return _manual_publish_fallback(html_content, date_str)

    if not admin_api_key or admin_api_key == "YOUR_GHOST_ADMIN_API_KEY":
        logger.error("Ghost Admin API key not set in config.yaml (ghost.admin_api_key)")
        return _manual_publish_fallback(html_content, date_str, ghost_url)

    # ── Build request ─────────────────────────────────────────────────────────
    endpoint = f"{ghost_url}/ghost/api/admin/posts/"

    try:
        token = _make_ghost_jwt(admin_api_key)
    except ValueError as e:
        logger.error(f"Ghost API key format error: {e}")
        return _manual_publish_fallback(html_content, date_str, ghost_url)

    headers = {
        "Authorization": f"Ghost {token}",
        "Content-Type": "application/json",
        "Accept-Version": "v5.0",
    }

    # Ghost accepts HTML directly and converts to its internal Lexical format
    payload = {
        "posts": [
            {
                "title": title,
                "custom_excerpt": tagline,
                "html": html_content,
                "status": "draft",
                "tags": [
                    {"name": "Newsletter"},
                    {"name": "Local News"},
                    {"name": "Rockland County"},
                ],
            }
        ]
    }

    # ── POST to Ghost ─────────────────────────────────────────────────────────
    logger.info(f"Publishing to Ghost: {endpoint}")
    try:
        resp = requests.post(endpoint, json=payload, headers=headers, timeout=30)

        if resp.status_code in (200, 201):
            data = resp.json()
            post = data.get("posts", [{}])[0]
            post_id  = post.get("id", "unknown")
            post_url = post.get("url", "")
            edit_url = f"{ghost_url}/ghost/#/editor/post/{post_id}"

            logger.info(f"Ghost publish successful — Post ID: {post_id}")
            print(f"\n✅ Newsletter published to Ghost as a draft!")
            print(f"   Post ID: {post_id}")
            if post_url:
                print(f"   Preview: {post_url}")
            print(f"   Edit:    {edit_url}")
            print("   Opening Ghost editor to review before publishing.\n")
            webbrowser.open(edit_url)
            return True

        elif resp.status_code == 401:
            logger.error("Ghost authentication failed (401). Check admin_api_key in config.yaml.")
            return _manual_publish_fallback(html_content, date_str, ghost_url)

        elif resp.status_code == 403:
            logger.error("Ghost permission denied (403). Make sure your integration can create posts.")
            return _manual_publish_fallback(html_content, date_str, ghost_url)

        elif resp.status_code == 404:
            logger.error(f"Ghost Admin API not found (404). Check ghost.url in config.yaml — current: '{ghost_url}'")
            return _manual_publish_fallback(html_content, date_str, ghost_url)

        else:
            logger.error(f"Ghost API error {resp.status_code}: {resp.text[:300]}")
            return _manual_publish_fallback(html_content, date_str, ghost_url)

    except requests.exceptions.ConnectionError:
        logger.error(f"Could not connect to Ghost at {ghost_url}. Check ghost.url in config.yaml.")
        return _manual_publish_fallback(html_content, date_str, ghost_url)
    except requests.exceptions.Timeout:
        logger.error("Ghost API request timed out.")
        return _manual_publish_fallback(html_content, date_str, ghost_url)
    except Exception as e:
        logger.error(f"Unexpected error publishing to Ghost: {e}")
        return _manual_publish_fallback(html_content, date_str, ghost_url)


# Alias so main.py requires no changes
publish_to_beehiiv = publish_to_ghost
