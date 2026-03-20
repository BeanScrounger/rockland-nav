#!/usr/bin/env python3
"""
The Rockland Navigator — Main Pipeline

Usage:
    python main.py            # Full run: scrape → draft → email → approve → publish
    python main.py --dry-run  # Print draft only; skip email, approval, and publish
"""

import argparse
import logging
import os
import sys
from datetime import datetime

import yaml

# ─────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────
HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.yaml")
TEMPLATE_PATH = os.path.join(HERE, "newsletter_template.yaml")


# ─────────────────────────────────────────────
# Logging setup
# ─────────────────────────────────────────────
def setup_logging(log_level: str = "INFO", log_file: str = "rockland_navigator.log"):
    level = getattr(logging, log_level.upper(), logging.INFO)
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(HERE, log_file), encoding="utf-8"),
    ]
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )


# ─────────────────────────────────────────────
# Config loader
# ─────────────────────────────────────────────
def load_config(path: str = CONFIG_PATH) -> dict:
    if not os.path.exists(path):
        print(
            f"ERROR: config.yaml not found at {path}\n"
            "Copy config.yaml.example to config.yaml and fill in your credentials."
        )
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_template(path: str = TEMPLATE_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ─────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────
def main(dry_run: bool = False):
    # 1. Load config
    config = load_config()
    template = load_template()

    setup_logging(
        log_level=config.get("logging", {}).get("level", "INFO"),
        log_file=config.get("logging", {}).get("file", "rockland_navigator.log"),
    )
    logger = logging.getLogger("main")

    edition_date = datetime.now().strftime("%B %-d, %Y")
    logger.info(f"{'='*60}")
    logger.info(f"The Rockland Navigator — {edition_date}")
    logger.info(f"Mode: {'DRY RUN' if dry_run else 'FULL RUN'}")
    logger.info(f"{'='*60}")

    # 2. Scrape all sources
    logger.info("Step 1/7: Scraping news sources...")
    from scrapers.rss_scraper import scrape_rss_feeds
    from scrapers.reddit_scraper import scrape_reddit
    from scrapers.html_scraper import scrape_html_sources
    from scrapers.manual_scraper import scrape_manual_input

    rss_stories = scrape_rss_feeds()
    reddit_stories = scrape_reddit()
    html_stories = scrape_html_sources()
    manual_stories = scrape_manual_input()

    # 3. Combine all stories
    all_stories = rss_stories + reddit_stories + html_stories + manual_stories
    logger.info(
        f"Scraping complete: {len(all_stories)} total stories "
        f"(RSS: {len(rss_stories)}, Reddit: {len(reddit_stories)}, "
        f"HTML: {len(html_stories)}, Manual: {len(manual_stories)})"
    )

    if not all_stories:
        logger.warning(
            "No stories were scraped from any source. "
            "Check your internet connection or add content to manual_input.txt."
        )

    # 4. Deduplicate
    logger.info("Step 2/7: Deduplicating stories...")
    from deduplicator import deduplicate
    stories = deduplicate(all_stories)

    # 5. Curate (AI draft)
    logger.info("Step 3/7: Drafting newsletter with Claude AI...")
    anthropic_key = config.get("anthropic", {}).get("api_key", "")
    if not anthropic_key or anthropic_key == "YOUR_ANTHROPIC_API_KEY":
        logger.error(
            "Anthropic API key is not set. "
            "Add your key to config.yaml under anthropic.api_key"
        )
        sys.exit(1)

    from curator import curate_newsletter
    draft_text = curate_newsletter(stories, api_key=anthropic_key)

    # 6. Format as HTML
    logger.info("Step 4/7: Formatting newsletter as HTML...")
    from formatter import format_newsletter
    html_content = format_newsletter(draft_text, edition_date=edition_date)

    # ── DRY RUN: stop here ──
    if dry_run:
        print("\n" + "=" * 60)
        print("  DRY RUN — Newsletter Draft")
        print("=" * 60)
        print(draft_text)
        print("\n" + "=" * 60)
        print("  Dry run complete. No email sent, nothing published.")
        print("=" * 60 + "\n")
        return

    # 7. Send preview email
    logger.info("Step 5/7: Sending preview email...")
    from email_sender import send_preview_email
    email_sent = send_preview_email(
        html_content=html_content,
        email_config=config.get("email", {}),
        edition_date=edition_date,
    )
    if not email_sent:
        logger.warning(
            "Preview email failed — continuing to approval server anyway. "
            "Review the draft in the browser window."
        )

    # 8. Start approval server
    logger.info("Step 6/7: Opening approval server...")
    from approval_server import run_approval_server
    port = config.get("approval", {}).get("port", 8765)
    approved = run_approval_server(html_content, port=port)

    # 9. Handle decision
    if approved:
        logger.info("Step 7/7: Publishing to Beehiiv...")
        from publisher import publish_to_beehiiv
        success = publish_to_beehiiv(
            html_content=html_content,
            beehiiv_config=config.get("beehiiv", {}),
            edition_date=edition_date,
        )
        if success:
            logger.info("Pipeline complete — newsletter published to Beehiiv as draft.")
        else:
            logger.error(
                "Beehiiv publish failed. Check your credentials and try again."
            )
            sys.exit(1)
    else:
        print(
            "\n✗ Newsletter rejected.\n"
            "  Add notes or extra content to manual_input.txt and re-run:\n"
            "      python main.py\n"
        )
        logger.info("Newsletter rejected by editor. Pipeline stopped.")


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="The Rockland Navigator — Newsletter Automation"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scrape and draft the newsletter without sending email or publishing.",
    )
    args = parser.parse_args()
    main(dry_run=args.dry_run)
