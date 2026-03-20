#!/usr/bin/env python3
"""
Scheduler for The Rockland Navigator.

Automatically runs the newsletter pipeline every Tuesday and Friday at 7:00 AM.

Usage:
    python scheduler.py

Leave this running in a terminal or set it up as a background process.
"""

import logging
import sys
import time
from datetime import datetime

import schedule

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("scheduler")


def run_newsletter():
    """Trigger the full newsletter pipeline."""
    logger.info("=" * 60)
    logger.info(f"Scheduled run triggered — {datetime.now().strftime('%A, %B %-d, %Y %H:%M')}")
    logger.info("=" * 60)
    try:
        from main import main
        main(dry_run=False)
    except SystemExit as e:
        # main() may call sys.exit on errors — catch so the scheduler keeps running
        logger.error(f"Pipeline exited with code {e.code}")
    except Exception as exc:
        logger.error(f"Unexpected error during newsletter run: {exc}", exc_info=True)


def main():
    logger.info("The Rockland Navigator Scheduler starting...")
    logger.info("Scheduled: Tuesday and Friday at 7:00 AM")
    logger.info("Press Ctrl+C to stop.\n")

    # Schedule Tuesday and Friday runs at 7:00 AM
    schedule.every().tuesday.at("07:00").do(run_newsletter)
    schedule.every().friday.at("07:00").do(run_newsletter)

    # Show next scheduled run
    next_run = schedule.next_run()
    if next_run:
        logger.info(f"Next run: {next_run.strftime('%A, %B %-d, %Y at %H:%M')}")

    try:
        while True:
            schedule.run_pending()
            time.sleep(30)  # Check every 30 seconds
    except KeyboardInterrupt:
        logger.info("\nScheduler stopped by user.")


if __name__ == "__main__":
    main()
