"""
Curator for The Rockland Navigator.

Uses the Anthropic Claude API to draft the newsletter from scraped stories,
following the system prompt and newsletter template.
"""

import logging
import os
from datetime import datetime

import anthropic
import yaml

logger = logging.getLogger(__name__)

# Path helpers (relative to this file's location)
_HERE = os.path.dirname(os.path.abspath(__file__))
SYSTEM_PROMPT_PATH = os.path.join(_HERE, "system_prompt.txt")
TEMPLATE_PATH = os.path.join(_HERE, "newsletter_template.yaml")

# Claude model to use
CLAUDE_MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 4096


def _load_system_prompt() -> str:
    """Load the editorial system prompt from disk."""
    with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read().strip()


def _load_template() -> dict:
    """Load the newsletter template YAML."""
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _build_section_guide(template: dict) -> str:
    """Format the template sections into plain-text instructions for the prompt."""
    sections = template.get("newsletter", {})
    newsletter_name = sections.get("name", "The Rockland Navigator")
    target_words = template.get("newsletter", {}).get("target_word_count", 800)

    lines = [
        f"NEWSLETTER: {newsletter_name}",
        f"TARGET LENGTH: approximately {target_words} words total",
        "",
        "SECTIONS TO WRITE (in order):",
    ]

    for sec in template.get("sections", []):
        name = sec.get("name", "")
        desc = sec.get("description", "")
        wc = sec.get("word_count", "")
        fmt = sec.get("format", "prose")
        count = sec.get("count", "")
        subsections = sec.get("subsections", [])

        lines.append(f"\n## {name}")
        lines.append(f"Description: {desc}")
        if wc:
            lines.append(f"Target word count: {wc}")
        if fmt == "bullets" and count:
            lines.append(f"Format: {count} bullet points")
        if subsections:
            lines.append(f"Subsections: {', '.join(subsections)}")

    return "\n".join(lines)


def _build_story_list(stories: list[dict]) -> str:
    """Format scraped stories into a numbered list for the prompt."""
    if not stories:
        return "No stories were scraped. Write a brief placeholder newsletter."

    lines = [f"AVAILABLE STORIES ({len(stories)} total):", ""]
    for i, story in enumerate(stories, 1):
        title = story.get("title", "Untitled")
        source = story.get("source", "unknown")
        published = story.get("published", "")
        summary = story.get("summary", "")
        url = story.get("url", "")

        lines.append(f"{i}. [{source}] {title}")
        if published:
            lines.append(f"   Published: {published}")
        if summary:
            lines.append(f"   Summary: {summary[:300]}")
        if url:
            lines.append(f"   URL: {url}")
        lines.append("")

    return "\n".join(lines)


def curate_newsletter(stories: list[dict], api_key: str) -> str:
    """
    Draft the full newsletter using Claude.

    Args:
        stories: Deduplicated list of story dicts from scrapers.
        api_key: Anthropic API key.

    Returns:
        Drafted newsletter as a plain-text string (markdown-friendly).
    """
    system_prompt = _load_system_prompt()
    template = _load_template()

    section_guide = _build_section_guide(template)
    story_list = _build_story_list(stories)
    today = datetime.now().strftime("%A, %B %-d, %Y")

    user_message = f"""Today is {today}.

Please draft the full edition of The Rockland Navigator newsletter using the stories provided below.

{section_guide}

---

{story_list}

---

INSTRUCTIONS:
- Write every section defined above. Do not skip any section.
- Select and prioritize the most relevant, recent, and locally impactful stories.
- Follow the voice and editorial standards from the system prompt exactly.
- For Quick Hits, write exactly 5 bullet points.
- Include story URLs as plain links (e.g., "Read more: https://...") at the end of each story blurb.
- If a section has no good matching stories, write a brief note that there were no major developments.
- Do not use markdown headers with # symbols — use ALL CAPS section headers instead (e.g., TOP STORIES).
- Write in warm, conversational prose as defined in the system prompt.
"""

    logger.info(f"Sending {len(stories)} stories to Claude for curation...")

    client = anthropic.Anthropic(api_key=api_key)

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_message}
        ],
    )

    draft = message.content[0].text
    logger.info(
        f"Claude draft complete: ~{len(draft.split())} words, "
        f"{message.usage.input_tokens} input tokens, "
        f"{message.usage.output_tokens} output tokens"
    )
    return draft
