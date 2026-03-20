"""
Publisher for The Rockland Navigator.

Posts the approved newsletter to Beehiiv as a draft post via the Beehiiv v2 API.
"""

import logging
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

BEEHIIV_API_BASE = "https://api.beehiiv.com/v2"


def publish_to_beehiiv(
    html_content: str,
    beehiiv_config: dict,
    edition_date: str | None = None,
) -> bool:
    """
    Create a draft post on Beehiiv with the newsletter content.

    The post is created as a DRAFT so you can review it in Beehiiv's
    editor before sending to subscribers. You can change this to
    "confirmed" if you want to publish immediately.

    Args:
        html_content: Full HTML string of the formatted newsletter.
        beehiiv_config: Dict with keys: api_key, publication_id
        edition_date: Human-readable date for the post title.
                      Defaults to today.

    Returns:
        True if published successfully, False otherwise.
    """
    if edition_date is None:
        edition_date = datetime.now().strftime("%B %-d, %Y")

    api_key = beehiiv_config.get("api_key", "")
    publication_id = beehiiv_config.get("publication_id", "")

    if not api_key or api_key == "YOUR_BEEHIIV_API_KEY":
        logger.error("Beehiiv API key is not set in config.yaml")
        return False

    if not publication_id or publication_id == "YOUR_PUBLICATION_ID":
        logger.error(
            "Beehiiv publication_id is not set in config.yaml. "
            "Go to beehiiv.com → Settings → Publication to find your ID."
        )
        return False

    endpoint = f"{BEEHIIV_API_BASE}/publications/{publication_id}/posts"
    subject_line = f"The Rockland Navigator — {edition_date}"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    payload = {
        "subject_line": subject_line,
        "content_html": html_content,
        "status": "draft",
        # Beehiiv v2 post fields
        "newsletter_id": publication_id,
    }

    try:
        logger.info(f"Publishing to Beehiiv: {endpoint}")
        response = requests.post(
            endpoint,
            json=payload,
            headers=headers,
            timeout=30,
        )

        if response.status_code in (200, 201):
            data = response.json()
            post_data = data.get("data", {})
            post_id = post_data.get("id", "")
            post_url = (
                post_data.get("web_url")
                or f"https://app.beehiiv.com/posts/{post_id}"
            )

            print("\n" + "=" * 60)
            print("  ✓ PUBLISHED TO BEEHIIV (as draft)")
            print(f"  Post: {subject_line}")
            print(f"  URL:  {post_url}")
            print("  Review and send it from your Beehiiv dashboard.")
            print("=" * 60 + "\n")

            logger.info(f"Beehiiv post created: {post_url}")
            return True

        else:
            logger.error(
                f"Beehiiv API error: HTTP {response.status_code} — {response.text[:500]}"
            )
            print(f"\n✗ Beehiiv publish failed (HTTP {response.status_code}):")
            print(f"  {response.text[:300]}")
            print("  Check your API key and publication ID in config.yaml.\n")
            return False

    except requests.RequestException as exc:
        logger.error(f"Beehiiv request error: {exc}")
        return False
    except Exception as exc:
        logger.error(f"Unexpected error publishing to Beehiiv: {exc}")
        return False
