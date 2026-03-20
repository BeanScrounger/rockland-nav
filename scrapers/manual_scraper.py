"""
Manual input scraper for The Rockland Navigator.
Reads story tips, community announcements, and extra content
from manual_input.txt and returns them as story dicts.

Format in manual_input.txt (any line starting with STORY:, EVENT:, TIP:, etc.
is treated as a story item):

    STORY: The Nyack Farmers Market opens April 5th at Memorial Park.
    EVENT: Clarkstown Town Board meeting Monday March 24 at 7pm, Town Hall.
    TIP: Route 9W road closure between Piermont and Grand View starting Monday.

Blank lines and lines starting with # are ignored.
"""

import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

MANUAL_INPUT_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "manual_input.txt")

# Keywords that signal the start of a manual story line
STORY_PREFIXES = ("STORY:", "EVENT:", "TIP:", "NOTE:", "ITEM:", "ALERT:", "UPDATE:")


def scrape_manual_input(filepath: str | None = None) -> list[dict]:
    """
    Read manual_input.txt and return a list of story dicts.

    Args:
        filepath: Path to the manual input file. Defaults to manual_input.txt
                  in the project root directory.

    Returns:
        List of story dicts with source = "manual"
    """
    if filepath is None:
        filepath = MANUAL_INPUT_FILE

    stories = []

    if not os.path.exists(filepath):
        logger.info(f"No manual input file found at {filepath} — skipping")
        return []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()

        published = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")

        for line in lines:
            line = line.strip()

            # Skip blanks and comments
            if not line or line.startswith("#"):
                continue

            # Check for known prefixes (case-insensitive)
            upper_line = line.upper()
            matched_prefix = None
            for prefix in STORY_PREFIXES:
                if upper_line.startswith(prefix):
                    matched_prefix = prefix
                    break

            if matched_prefix:
                content = line[len(matched_prefix):].strip()
                label = matched_prefix.rstrip(":")
            else:
                # Treat any non-blank, non-comment line as content
                content = line
                label = "MANUAL"

            if not content:
                continue

            # Use the first sentence as the "title"
            title = content.split(".")[0].strip()
            if len(title) > 120:
                title = title[:120] + "…"

            stories.append(
                {
                    "title": f"[{label}] {title}",
                    "url": "",
                    "summary": content,
                    "published": published,
                    "source": "manual",
                }
            )

        logger.info(f"Manual input: {len(stories)} items loaded from {filepath}")

    except Exception as exc:
        logger.error(f"Failed to read manual input file {filepath}: {exc}")

    return stories
