"""
RSS feed scraper for The Rockland Navigator.
Pulls stories from local Rockland County news sources.
"""

import logging
import feedparser
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

RSS_FEEDS = {
    "rockland_report": "https://rocklandreport.com/feed/",
    "rockland_news": "https://rocklandnews.com/feed/",
    "monsey_scoop": "https://monseyscoop.com/feed/",
    "mid_hudson_news": "https://midhudsonnews.com/category/news/rockland-county/feed/",
    "rockland_times": "https://rocklandtimes.com/feed/",
    "nyack_news": "https://nyacknewsandviews.com/feed/",
    "daily_voice_new_city": "https://dailyvoice.com/new-york/rockland-new-city/rss/",
    "daily_voice_monsey": "https://dailyvoice.com/new-york/rockland-monsey/rss/",
    "daily_voice_stony_point": "https://dailyvoice.com/new-york/rockland-stony-point/rss/",
    "daily_voice_spring_valley": "https://dailyvoice.com/new-york/rockland-spring-valley/rss/",
    "daily_voice_haverstraw": "https://dailyvoice.com/new-york/rockland-haverstraw/rss/",
    "daily_voice_pearl_river": "https://dailyvoice.com/new-york/rockland-pearl-river/rss/",
    "daily_voice_suffern": "https://dailyvoice.com/new-york/rockland-suffern/rss/",
    "daily_voice_nanuet": "https://dailyvoice.com/new-york/rockland-nanuet/rss/",
}

# Maximum number of stories to pull per feed
MAX_STORIES_PER_FEED = 10


def _parse_published(entry) -> str:
    """Extract a human-readable publish date from a feed entry."""
    if hasattr(entry, "published"):
        return entry.published
    if hasattr(entry, "updated"):
        return entry.updated
    return datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")


def _extract_summary(entry) -> str:
    """Extract a plain-text summary from a feed entry."""
    summary = ""
    if hasattr(entry, "summary"):
        summary = entry.summary
    elif hasattr(entry, "description"):
        summary = entry.description

    # Strip basic HTML tags that feedparser may leave in summaries
    import re
    summary = re.sub(r"<[^>]+>", " ", summary)
    summary = " ".join(summary.split())  # Normalize whitespace
    return summary[:500]  # Cap at 500 chars


def scrape_feed(source_name: str, feed_url: str) -> list[dict]:
    """
    Scrape a single RSS feed and return a list of story dicts.

    Each story dict has keys:
        title, url, summary, published, source
    """
    stories = []
    try:
        logger.info(f"Scraping RSS feed: {source_name} ({feed_url})")
        feed = feedparser.parse(feed_url)

        if feed.bozo and feed.bozo_exception:
            logger.warning(
                f"Feed parse warning for {source_name}: {feed.bozo_exception}"
            )

        entries = feed.entries[:MAX_STORIES_PER_FEED]
        for entry in entries:
            title = getattr(entry, "title", "").strip()
            url = getattr(entry, "link", "").strip()
            if not title or not url:
                continue

            stories.append(
                {
                    "title": title,
                    "url": url,
                    "summary": _extract_summary(entry),
                    "published": _parse_published(entry),
                    "source": source_name,
                }
            )

        logger.info(f"  → {len(stories)} stories from {source_name}")

    except Exception as exc:
        logger.error(f"Failed to scrape {source_name}: {exc}")

    return stories


def scrape_rss_feeds(feeds: dict | None = None) -> list[dict]:
    """
    Scrape all configured RSS feeds and return combined list of stories.

    Args:
        feeds: Optional override dict of {source_name: url}.
               Defaults to the built-in RSS_FEEDS.

    Returns:
        List of story dicts sorted newest-first (best effort).
    """
    if feeds is None:
        feeds = RSS_FEEDS

    all_stories = []
    for source_name, feed_url in feeds.items():
        stories = scrape_feed(source_name, feed_url)
        all_stories.extend(stories)

    logger.info(f"RSS scraping complete: {len(all_stories)} total stories")
    return all_stories
