"""
HTML scraper for The Rockland Navigator.
Scrapes news headlines from local government and news websites that
don't provide RSS feeds or whose RSS feeds are incomplete.

All scrapers are fault-tolerant: they catch all exceptions and return
an empty list on failure so the pipeline can continue.
"""

import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; RocklandNavigator/1.0; "
        "+https://rocklandnavigator.com)"
    )
}


def _fetch_soup(url: str) -> BeautifulSoup | None:
    """Fetch a URL and return a BeautifulSoup object, or None on failure."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as exc:
        logger.error(f"Failed to fetch {url}: {exc}")
        return None


def _make_story(title: str, url: str, summary: str, source: str) -> dict:
    """Construct a standard story dict."""
    return {
        "title": title.strip(),
        "url": url.strip(),
        "summary": summary.strip()[:500],
        "published": datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000"),
        "source": source,
    }


# ─────────────────────────────────────────────
# Individual site scrapers
# ─────────────────────────────────────────────

def scrape_rockland_county_gov() -> list[dict]:
    """Scrape Rockland County government latest news page."""
    url = "https://rocklandcountyny.gov/government/latest-news"
    stories = []
    try:
        soup = _fetch_soup(url)
        if not soup:
            return []

        # Look for news headlines in h2/h3 tags
        for tag in soup.find_all(["h2", "h3"]):
            text = tag.get_text(strip=True)
            if not text or len(text) < 10:
                continue

            # Try to find an associated link
            link = tag.find("a")
            if not link:
                link = tag.find_parent("a")
            href = link["href"] if link and link.get("href") else url

            # Resolve relative URLs
            if href.startswith("/"):
                href = "https://rocklandcountyny.gov" + href

            # Try to grab a brief description from a sibling <p>
            summary = ""
            sibling = tag.find_next_sibling("p")
            if sibling:
                summary = sibling.get_text(strip=True)

            stories.append(_make_story(text, href, summary, "county_gov"))

        logger.info(f"county_gov: {len(stories)} stories")
    except Exception as exc:
        logger.error(f"county_gov scraper error: {exc}")
    return stories


def scrape_lohud() -> list[dict]:
    """Scrape lohud.com Rockland section for visible (non-paywalled) headlines."""
    url = "https://www.lohud.com/news/rockland/"
    stories = []
    try:
        soup = _fetch_soup(url)
        if not soup:
            return []

        # lohud uses article cards — look for <a> tags with headline text
        seen = set()
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            # Filter for article links (contain a year pattern or /story/)
            if "/story/" not in href and not any(
                f"/{y}/" in href for y in ["2024", "2025", "2026"]
            ):
                continue

            title = a_tag.get_text(strip=True)
            if not title or len(title) < 15 or title in seen:
                continue
            seen.add(title)

            if href.startswith("/"):
                href = "https://www.lohud.com" + href

            stories.append(_make_story(title, href, "", "lohud"))

        logger.info(f"lohud: {len(stories)} stories")
    except Exception as exc:
        logger.error(f"lohud scraper error: {exc}")
    return stories[:10]  # Cap at 10


def scrape_orangetown() -> list[dict]:
    """Scrape Orangetown official website for news/announcements."""
    url = "https://www.orangetown.com"
    stories = []
    try:
        soup = _fetch_soup(url)
        if not soup:
            return []

        # Look for news/announcements section
        for section_keyword in ["news", "announcement", "alert", "update"]:
            for tag in soup.find_all(
                ["h2", "h3", "h4", "li", "a"],
                string=lambda s: s and section_keyword in s.lower() if s else False,
            ):
                title = tag.get_text(strip=True)
                link = tag if tag.name == "a" else tag.find("a")
                href = link["href"] if link and link.get("href") else url
                if href.startswith("/"):
                    href = "https://www.orangetown.com" + href
                if title and len(title) > 10:
                    stories.append(_make_story(title, href, "", "orangetown"))

        # Also try generic headline search
        if not stories:
            for tag in soup.find_all(["h2", "h3"]):
                text = tag.get_text(strip=True)
                if not text or len(text) < 10:
                    continue
                link = tag.find("a")
                href = link["href"] if link and link.get("href") else url
                if href.startswith("/"):
                    href = "https://www.orangetown.com" + href
                stories.append(_make_story(text, href, "", "orangetown"))

        logger.info(f"orangetown: {len(stories)} stories")
    except Exception as exc:
        logger.error(f"orangetown scraper error: {exc}")
    return stories[:8]


def scrape_nyack_gov() -> list[dict]:
    """Scrape Nyack Village official website for news."""
    url = "https://nyack-ny.gov"
    stories = []
    try:
        soup = _fetch_soup(url)
        if not soup:
            return []

        for tag in soup.find_all(["h2", "h3", "h4"]):
            text = tag.get_text(strip=True)
            if not text or len(text) < 10:
                continue
            link = tag.find("a")
            href = link["href"] if link and link.get("href") else url
            if href.startswith("/"):
                href = "https://nyack-ny.gov" + href

            summary = ""
            sibling = tag.find_next_sibling("p")
            if sibling:
                summary = sibling.get_text(strip=True)

            stories.append(_make_story(text, href, summary, "nyack_gov"))

        logger.info(f"nyack_gov: {len(stories)} stories")
    except Exception as exc:
        logger.error(f"nyack_gov scraper error: {exc}")
    return stories[:8]


def scrape_suffern() -> list[dict]:
    """Scrape Suffern Village official website for news."""
    url = "https://suffernvillage.com"
    stories = []
    try:
        soup = _fetch_soup(url)
        if not soup:
            return []

        for tag in soup.find_all(["h2", "h3", "h4"]):
            text = tag.get_text(strip=True)
            if not text or len(text) < 10:
                continue
            link = tag.find("a")
            href = link["href"] if link and link.get("href") else url
            if href.startswith("/"):
                href = "https://suffernvillage.com" + href

            summary = ""
            sibling = tag.find_next_sibling("p")
            if sibling:
                summary = sibling.get_text(strip=True)

            stories.append(_make_story(text, href, summary, "suffern"))

        logger.info(f"suffern: {len(stories)} stories")
    except Exception as exc:
        logger.error(f"suffern scraper error: {exc}")
    return stories[:8]


# ─────────────────────────────────────────────
# Combined runner
# ─────────────────────────────────────────────

SCRAPERS = [
    scrape_rockland_county_gov,
    scrape_lohud,
    scrape_orangetown,
    scrape_nyack_gov,
    scrape_suffern,
]


def scrape_html_sources() -> list[dict]:
    """
    Run all HTML scrapers and return combined list of stories.
    Each individual scraper is wrapped in error handling.
    """
    all_stories = []
    for scraper_fn in SCRAPERS:
        try:
            stories = scraper_fn()
            all_stories.extend(stories)
        except Exception as exc:
            logger.error(f"Unexpected error in {scraper_fn.__name__}: {exc}")

    logger.info(f"HTML scraping complete: {len(all_stories)} total stories")
    return all_stories
