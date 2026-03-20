"""
Reddit scraper for The Rockland Navigator.
Pulls community posts from r/rocklandcounty.
"""

import logging
import requests
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

REDDIT_URL = "https://www.reddit.com/r/rocklandcounty/new.json"
REDDIT_HEADERS = {"User-Agent": "RocklandNavigator/1.0"}
MAX_POSTS = 20
MIN_SCORE = 5
MIN_COMMENTS = 3


def scrape_reddit() -> list[dict]:
    """
    Pull top posts from r/rocklandcounty and return filtered story dicts.

    Filters for posts with score > MIN_SCORE OR comments > MIN_COMMENTS
    to ensure some level of community engagement.

    Returns:
        List of story dicts with keys: title, url, summary, published, source
    """
    stories = []
    try:
        logger.info(f"Scraping Reddit: {REDDIT_URL}")
        response = requests.get(
            REDDIT_URL,
            headers=REDDIT_HEADERS,
            params={"limit": MAX_POSTS},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()

        posts = data.get("data", {}).get("children", [])
        for post in posts:
            post_data = post.get("data", {})

            score = post_data.get("score", 0)
            num_comments = post_data.get("num_comments", 0)

            # Filter low-engagement posts
            if score <= MIN_SCORE and num_comments <= MIN_COMMENTS:
                continue

            title = post_data.get("title", "").strip()
            permalink = post_data.get("permalink", "")
            url = f"https://www.reddit.com{permalink}" if permalink else ""
            selftext = post_data.get("selftext", "").strip()

            # Build a summary: prefer selftext, fall back to external URL
            if selftext:
                summary = selftext[:400]
            else:
                external_url = post_data.get("url", "")
                summary = f"Link: {external_url}" if external_url else ""

            # Convert UTC timestamp to readable string
            created_utc = post_data.get("created_utc", 0)
            try:
                published = datetime.fromtimestamp(
                    created_utc, tz=timezone.utc
                ).strftime("%a, %d %b %Y %H:%M:%S +0000")
            except Exception:
                published = ""

            if title and url:
                stories.append(
                    {
                        "title": title,
                        "url": url,
                        "summary": summary,
                        "published": published,
                        "source": "reddit",
                        "score": score,
                        "num_comments": num_comments,
                    }
                )

        logger.info(f"Reddit scraping complete: {len(stories)} posts passed filter")

    except requests.RequestException as exc:
        logger.error(f"Reddit request failed: {exc}")
    except Exception as exc:
        logger.error(f"Reddit scraping error: {exc}")

    return stories
