"""
Deduplicator for The Rockland Navigator.

Uses SequenceMatcher to find near-duplicate stories across sources,
keeping the one from the higher-priority source.
"""

import logging
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# Similarity threshold above which two stories are considered duplicates
SIMILARITY_THRESHOLD = 0.7

# Source priority order — lower index = higher priority (kept over duplicates)
SOURCE_PRIORITY = [
    "manual",
    "rockland_report",
    "rockland_news",
    "daily_voice_new_city",
    "daily_voice_monsey",
    "daily_voice_stony_point",
    "daily_voice_spring_valley",
    "daily_voice_haverstraw",
    "daily_voice_pearl_river",
    "daily_voice_suffern",
    "daily_voice_nanuet",
    "lohud",
    "rockland_times",
    "nyack_news",
    "mid_hudson_news",
    "monsey_scoop",
    "county_gov",
    "orangetown",
    "nyack_gov",
    "suffern",
    "reddit",
]


def _source_priority(source: str) -> int:
    """Return numeric priority for a source (lower = higher priority)."""
    try:
        return SOURCE_PRIORITY.index(source)
    except ValueError:
        return len(SOURCE_PRIORITY)  # Unknown sources get lowest priority


def _title_similarity(title_a: str, title_b: str) -> float:
    """Return similarity ratio between two story titles."""
    a = title_a.lower().strip()
    b = title_b.lower().strip()
    return SequenceMatcher(None, a, b).ratio()


def deduplicate(stories: list[dict]) -> list[dict]:
    """
    Remove near-duplicate stories from the list.

    For each pair with title similarity > SIMILARITY_THRESHOLD,
    the story from the higher-priority source is kept and the other
    is discarded.

    Args:
        stories: List of story dicts (each must have 'title' and 'source' keys)

    Returns:
        Deduplicated list of story dicts.
    """
    if not stories:
        return []

    original_count = len(stories)

    # Sort by source priority so that when we iterate we prefer high-priority
    # stories when resolving conflicts.
    sorted_stories = sorted(stories, key=lambda s: _source_priority(s.get("source", "")))

    kept: list[dict] = []
    dropped_indices: set[int] = set()

    for i, story_a in enumerate(sorted_stories):
        if i in dropped_indices:
            continue

        kept.append(story_a)

        for j in range(i + 1, len(sorted_stories)):
            if j in dropped_indices:
                continue

            story_b = sorted_stories[j]
            sim = _title_similarity(story_a["title"], story_b["title"])

            if sim >= SIMILARITY_THRESHOLD:
                # story_a has higher (or equal) priority — drop story_b
                logger.debug(
                    f"Duplicate dropped (sim={sim:.2f}): "
                    f"'{story_b['title'][:60]}' "
                    f"(kept '{story_a['title'][:60]}' from {story_a['source']})"
                )
                dropped_indices.add(j)

    logger.info(
        f"Deduplication: {original_count} stories → {len(kept)} "
        f"({original_count - len(kept)} duplicates removed)"
    )
    return kept
