"""
Publisher for The Rockland Navigator.

Attempts to publish to Beehiiv via API. If the API is unavailable
(e.g. not on Enterprise plan), falls back to saving the HTML locally
and opening the Beehiiv new-post page so you can paste it in manually.
"""

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

BEEHIIV_NEW_POST_URL = "https://app.beehiiv.com/posts/new"


def _load_config() -> dict:
    with open(CONFIG_FILE, "r") as f:
        return yaml.safe_load(f)


def _load_template() -> dict:
    with open(TEMPLATE_FILE, "r") as f:
        return yaml.safe_load(f)


def _manual_publish_fallback(html_content: str, date_str: str) -> bool:
    """
    Fallback when Beehiiv API publishing is unavailable.

    Saves the finished HTML to output/latest_newsletter.html (already done
    by main.py, but we re-save a clearly named copy), then opens the
    Beehiiv new-post page in the browser with instructions.
    """
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Save a clearly named copy for easy reference
    dated_filename = f"newsletter_{date_str.replace(' ', '_').replace(',', '')}.html"
    dated_path = OUTPUT_DIR / dated_filename
    dated_path.write_text(html_content, encoding="utf-8")

    template = _load_template()
    newsletter_name = template.get("newsletter", {}).get("name", "The Rockland Navigator")
    tagline = template.get("newsletter", {}).get("tagline", "Your hyperlocal guide to Rockland County, NY")
    title = f"{newsletter_name} — {date_str}"

    print("\n" + "=" * 60)
    print("  MANUAL PUBLISH — 4 easy steps")
    print("=" * 60)
    print()
    print("  Step 1 — Copy these into Beehiiv when prompted:")
    print(f"    Title:    {title}")
    print(f"    Subtitle: {tagline}")
    print()
    print("  Step 2 — Your newsletter is opening in your browser.")
    print("           Press Cmd+A to select all, then Cmd+C to copy.")
    print()
    print("  Step 3 — Beehiiv's new post page is also opening.")
    print("           Click into the content area and press Cmd+V to paste.")
    print("           (Beehiiv accepts the formatted text directly.)")
    print()
    print("  Step 4 — Fill in the title/subtitle above, then")
    print("           Save as Draft or hit Send.")
    print()
    print(f"  HTML file also saved at: {dated_path}")
    print("=" * 60 + "\n")

    logger.info(f"Manual publish fallback: HTML saved to {dated_path}")
    logger.info(f"Opening newsletter preview and Beehiiv new-post page")

    # Open the newsletter in the browser first (so user can Cmd+A, Cmd+C)
    webbrowser.open(dated_path.as_uri())
    # Then open Beehiiv new post (slight delay so both tabs appear)
    import time
    time.sleep(1)
    webbrowser.open(BEEHIIV_NEW_POST_URL)
    return True


def publish_to_beehiiv(html_content: str, date_str: str = None) -> bool:
    """
    Publish the newsletter to Beehiiv.

    First attempts the Beehiiv v2 API. If the API returns a plan-restriction
    error (403 Enterprise), automatically falls back to the manual publish
    flow: saves HTML locally and opens Beehiiv in the browser.

    Args:
        html_content: The formatted HTML newsletter content.
        date_str: Date string for the post title.

    Returns:
        True on success or successful fallback, False on hard failure.
    """
    if date_str is None:
        date_str = datetime.now().strftime("%B %d, %Y")

    config = _load_config()
    template = _load_template()

    beehiiv = config.get("beehiiv", {})
    api_key = beehiiv.get("api_key", "")
    publication_id = beehiiv.get("publication_id", "")
    base_url = beehiiv.get("base_url", "https://api.beehiiv.com/v2")

    newsletter_name = template.get("newsletter", {}).get("name", "The Rockland Navigator")
    tagline = template.get("newsletter", {}).get("tagline", "Your hyperlocal guide to Rockland County")

    # ── Attempt API publish ───────────────────────────────────────────────────
    if api_key and publication_id and publication_id != "YOUR_BEEHIIV_PUBLICATION_ID":
        endpoint = f"{base_url}/publications/{publication_id}/posts"
        title = f"{newsletter_name} — {date_str}"

        payload = {
            "title": title,
            "subtitle": tagline,
            "status": "draft",
            "content_tags": ["rockland", "local-news", "newsletter"],
            "content": {"free": html_content},
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        logger.info(f"Attempting Beehiiv API publish: {endpoint}")
        try:
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=30)

            if resp.status_code in (200, 201):
                data = resp.json()
                post_id = data.get("data", {}).get("id", "unknown")
                post_url = data.get("data", {}).get("web_url", "")
                logger.info(f"Beehiiv API publish successful — Post ID: {post_id}")
                print(f"\n✅ Newsletter published to Beehiiv as a draft!")
                print(f"   Post ID: {post_id}")
                if post_url:
                    print(f"   URL: {post_url}")
                print("   Log in to Beehiiv to review, edit, and schedule.\n")
                return True

            elif resp.status_code == 403:
                # Plan restriction — fall back gracefully
                logger.warning(
                    f"Beehiiv API not available on current plan (403). "
                    f"Falling back to manual publish."
                )
                return _manual_publish_fallback(html_content, date_str)

            elif resp.status_code == 401:
                logger.error("Beehiiv API authentication failed. Check api_key in config.yaml.")
                return _manual_publish_fallback(html_content, date_str)

            elif resp.status_code == 404:
                logger.error(
                    f"Beehiiv publication not found (404). "
                    f"Check publication_id in config.yaml (current: '{publication_id}')."
                )
                return _manual_publish_fallback(html_content, date_str)

            else:
                logger.error(f"Beehiiv API error {resp.status_code}: {resp.text[:300]}")
                return _manual_publish_fallback(html_content, date_str)

        except requests.exceptions.ConnectionError:
            logger.error("Could not connect to Beehiiv API. Falling back to manual publish.")
            return _manual_publish_fallback(html_content, date_str)
        except requests.exceptions.Timeout:
            logger.error("Beehiiv API timed out. Falling back to manual publish.")
            return _manual_publish_fallback(html_content, date_str)
        except Exception as e:
            logger.error(f"Unexpected Beehiiv error: {e}. Falling back to manual publish.")
            return _manual_publish_fallback(html_content, date_str)

    # ── No API credentials configured — go straight to manual ────────────────
    else:
        logger.info("Beehiiv API not configured — using manual publish flow.")
        return _manual_publish_fallback(html_content, date_str)
