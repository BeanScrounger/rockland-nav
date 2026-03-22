#!/usr/bin/env python3
"""
The Rockland Navigator — Newsletter Automation System
Main entry point. Runs the full pipeline: scrape → deduplicate → draft → preview → approve → publish.

Usage:
    python main.py              # Full run (scrape, draft, email, approve, publish)
    python main.py --dry-run    # Generate newsletter only, no email or publishing
"""

import certifi
import os
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

import argparse
import logging
import sys
import yaml
from datetime import datetime
from pathlib import Path

# ── Setup paths ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

CONFIG_FILE = BASE_DIR / "config.yaml"


def setup_logging(config: dict):
    """Configure logging to both console and file."""
    log_config = config.get("logging", {})
    level_str = log_config.get("level", "INFO").upper()
    level = getattr(logging, level_str, logging.INFO)
    log_file = BASE_DIR / log_config.get("file", "navigator.log")

    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding="utf-8"),
    ]

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )


def load_config() -> dict:
    try:
        with open(CONFIG_FILE, "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"ERROR: config.yaml not found at {CONFIG_FILE}")
        print("Please copy config.yaml and fill in your API keys.")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"ERROR: Invalid YAML in config.yaml: {e}")
        sys.exit(1)


def run_scrapers() -> list:
    """Run all scrapers and return combined story list."""
    from scrapers.rss_scraper import fetch_all_rss
    from scrapers.reddit_scraper import fetch_reddit
    from scrapers.html_scraper import fetch_all_html
    from scrapers.manual_scraper import fetch_manual

    logger = logging.getLogger("main")
    all_stories = []

    logger.info("=" * 50)
    logger.info("STEP 1: Scraping all sources")
    logger.info("=" * 50)

    # RSS feeds
    rss_stories = fetch_all_rss()
    logger.info(f"RSS feeds: {len(rss_stories)} stories")
    all_stories.extend(rss_stories)

    # Reddit
    reddit_stories = fetch_reddit()
    logger.info(f"Reddit: {len(reddit_stories)} stories")
    all_stories.extend(reddit_stories)

    # HTML sources
    html_stories = fetch_all_html()
    logger.info(f"HTML scraping: {len(html_stories)} stories")
    all_stories.extend(html_stories)

    # Manual input
    manual_stories = fetch_manual()
    if manual_stories:
        logger.info(f"Manual input: {len(manual_stories)} item(s)")
    all_stories.extend(manual_stories)

    logger.info(f"TOTAL SCRAPED: {len(all_stories)} raw stories")
    return all_stories


def run_pipeline(dry_run: bool = False, select: bool = False):
    """Run the full newsletter pipeline."""
    logger = logging.getLogger("main")
    date_str = datetime.now().strftime("%B %d, %Y")

    print("\n" + "🗺️ " * 10)
    print("  THE ROCKLAND NAVIGATOR — Newsletter Automation")
    print("🗺️ " * 10 + "\n")

    # ── Step 1: Scrape ────────────────────────────────────────────────────────
    all_stories = run_scrapers()

    if not all_stories:
        logger.error("No stories found from any source. Exiting.")
        print("\n⚠️  No stories were found. Check your internet connection and try again.")
        sys.exit(1)

    # ── Step 2: Deduplicate ───────────────────────────────────────────────────
    logger.info("=" * 50)
    logger.info("STEP 2: Deduplicating stories")
    logger.info("=" * 50)

    from deduplicator import deduplicate
    unique_stories = deduplicate(all_stories)
    logger.info(f"After deduplication: {len(unique_stories)} unique stories")

    # ── Step 2b: Story selection (optional) ──────────────────────────────────
    if select:
        logger.info("=" * 50)
        logger.info("STEP 2b: Story selection")
        logger.info("=" * 50)
        from story_selector import select_stories
        unique_stories = select_stories(unique_stories)
        logger.info(f"Stories after selection: {len(unique_stories)}")
        if not unique_stories:
            print("\n⚠️  No stories selected. Exiting.")
            sys.exit(0)

    # ── Step 3: Generate newsletter with Claude ───────────────────────────────
    logger.info("=" * 50)
    logger.info("STEP 3: Generating newsletter with Claude AI")
    logger.info("=" * 50)

    from curator import generate_newsletter
    try:
        raw_html = generate_newsletter(unique_stories)
    except ValueError as e:
        logger.error(str(e))
        print(f"\n❌ Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error generating newsletter: {e}")
        print(f"\n❌ Failed to generate newsletter: {e}")
        sys.exit(1)

    # ── Step 4: Format HTML ───────────────────────────────────────────────────
    logger.info("=" * 50)
    logger.info("STEP 4: Formatting newsletter HTML")
    logger.info("=" * 50)

    from formatter import format_email
    full_html = format_email(raw_html, date_str)

    # Save to output directory
    output_file = OUTPUT_DIR / "latest_newsletter.html"
    output_file.write_text(full_html, encoding="utf-8")
    logger.info(f"Newsletter saved to: {output_file}")
    print(f"\n📄 Newsletter HTML saved to: {output_file}")

    # ── Dry run: stop here ────────────────────────────────────────────────────
    if dry_run:
        logger.info("Dry run complete. No email sent, nothing published.")
        print("\n✅ Dry run complete!")
        print(f"   Open {output_file} in your browser to preview the newsletter.")
        print("   Run without --dry-run to send email and publish.\n")
        return

    # ── Step 5: Send email preview ────────────────────────────────────────────
    logger.info("=" * 50)
    logger.info("STEP 5: Sending email preview")
    logger.info("=" * 50)

    from email_sender import send_preview
    email_ok = send_preview(full_html, date_str)
    if email_ok:
        config = load_config()
        recipient = config.get("gmail", {}).get("preview_recipient", "your email")
        print(f"📧 Preview email sent to {recipient}")
    else:
        print("⚠️  Email preview failed (check logs). Continuing to approval server...")

    # ── Step 6: Approval server ───────────────────────────────────────────────
    logger.info("=" * 50)
    logger.info("STEP 6: Starting approval server")
    logger.info("=" * 50)

    from publisher import publish_to_beehiiv

    def on_approve():
        logger.info("Publishing to Beehiiv...")
        success = publish_to_beehiiv(full_html, date_str)
        if not success:
            logger.error("Publishing to Beehiiv failed. Check logs.")

    from approval_server import run_approval_server
    approved = run_approval_server(full_html, on_approve_callback=on_approve)

    # ── Result ────────────────────────────────────────────────────────────────
    if approved:
        logger.info("Pipeline complete — newsletter approved and published.")
        print("\n🎉 Done! Newsletter approved and sent to Beehiiv.")
    else:
        logger.info("Pipeline complete — newsletter rejected.")
        print("\n📝 Newsletter rejected.")
        print("   Add your notes to manual_input.txt and re-run: python main.py")


def main():
    parser = argparse.ArgumentParser(
        description="The Rockland Navigator — Newsletter Automation System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                       # Full automatic run
  python main.py --dry-run             # Draft only, no email or publishing
  python main.py --select              # Pick stories before drafting, then full run
  python main.py --select --dry-run    # Pick stories, draft only, no email or publishing
        """,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate newsletter only — no email preview, no publishing to Beehiiv",
    )
    parser.add_argument(
        "--select",
        action="store_true",
        help="Open story selector before drafting — choose which scraped articles to include",
    )
    args = parser.parse_args()

    config = load_config()
    setup_logging(config)

    try:
        run_pipeline(dry_run=args.dry_run, select=args.select)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Exiting.")
        sys.exit(0)
    except Exception as e:
        logging.getLogger("main").exception(f"Unexpected error: {e}")
        print(f"\n❌ Unexpected error: {e}")
        print("Check navigator.log for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
