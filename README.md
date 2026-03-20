# The Rockland Navigator — Newsletter Automation

Automated pipeline for generating, reviewing, and publishing *The Rockland Navigator*, a hyperlocal newsletter covering Rockland County, NY.

---

## How It Works

Every Tuesday and Friday, the system:
1. Scrapes local news from RSS feeds, Reddit, and town/county websites
2. Removes duplicate stories
3. Drafts the newsletter using Claude AI, following your template and voice guide
4. Emails you an HTML preview
5. Opens a browser window where you can approve or reject the draft
6. If approved, publishes the draft to Beehiiv automatically

---

## Prerequisites

- **Python 3.9 or newer** — check with `python3 --version`
- **pip** — usually included with Python
- A **Gmail account** with an App Password (see step 3 below)
- An **Anthropic account** with an API key (for Claude AI)
- A **Beehiiv account** with your newsletter publication set up

---

## 1. Installation

Open Terminal, navigate to this folder, and run:

```bash
pip install -r requirements.txt
```

---

## 2. Configuration

Copy the example config file:

```bash
cp config.yaml.example config.yaml
```

Open `config.yaml` in any text editor and fill in your values:

### Anthropic API Key
1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Click **API Keys** in the left sidebar
3. Click **Create Key**, give it a name, copy the key
4. Paste it as the value for `anthropic.api_key`

### Beehiiv Publication ID
1. Log in to [beehiiv.com](https://www.beehiiv.com)
2. Open your newsletter publication
3. Go to **Settings → Publication**
4. Look at the URL — it will contain something like `/publications/pub_xxxxxxxx`
5. Copy everything after `/publications/` (e.g. `pub_xxxxxxxx`)
6. Paste it as the value for `beehiiv.publication_id`

### Gmail App Password
If you haven't already set one up:
1. Go to your Google Account → **Security**
2. Under "How you sign in to Google," click **2-Step Verification** (must be enabled)
3. Scroll to the bottom and click **App passwords**
4. Create a new app password for "Mail"
5. Copy the 16-character password (with spaces) into `email.app_password`

---

## 3. First Run (Dry Run)

Test everything without sending email or publishing:

```bash
python main.py --dry-run
```

This will scrape stories, draft the newsletter, and print the result to the terminal. No emails sent, nothing published.

---

## 4. Full Run

To run the full pipeline — scrape, draft, email preview, approve, and publish:

```bash
python main.py
```

A browser window will open showing the draft. Click **Approve & Publish** to post to Beehiiv, or **Reject** to cancel. If you reject, add notes or extra content to `manual_input.txt` and run again.

---

## 5. Auto-Scheduling

To have the newsletter run automatically every Tuesday and Friday at 7 AM, leave this running in the background:

```bash
python scheduler.py
```

Keep the Terminal window open (or run it as a background process). It will trigger `main.py` at the configured times.

---

## 6. Customizing the Newsletter Format

Edit `newsletter_template.yaml` to change:
- Section names and descriptions
- Word counts per section
- Which sources are prioritized for each section
- Publishing days

After editing, the AI will follow the new structure on the next run.

---

## 7. Customizing the AI Voice

Edit `system_prompt.txt` to adjust:
- Tone and writing style
- Editorial priorities
- Formatting preferences

The AI reads this file on every run, so changes take effect immediately.

---

## 8. Adding Manual Content

Paste any content into `manual_input.txt` — story tips, community announcements, events, corrections. The curator will incorporate this into the newsletter alongside scraped content.

Format example:
```
STORY: The Nyack Farmers Market opens for the season on April 5th at Memorial Park.
EVENT: Clarkstown Town Board meeting, Monday March 24 at 7pm, Town Hall.
```

Clear the file after each run if you don't want the same content repeated.

---

## File Reference

| File | Purpose |
|------|---------|
| `config.yaml` | Your credentials and settings (never commit this) |
| `config.yaml.example` | Safe template to share/commit |
| `newsletter_template.yaml` | Section structure and word counts |
| `system_prompt.txt` | AI voice and editorial guidelines |
| `manual_input.txt` | Add tips and extra content here |
| `main.py` | Run this to generate a newsletter |
| `scheduler.py` | Run this to auto-schedule Tuesday/Friday runs |

---

## Troubleshooting

**"Authentication failed" on email send:** Double-check your Gmail App Password in `config.yaml`. Make sure 2-Step Verification is enabled on your Google account.

**Scraper returns no stories:** Some local news sites may block scrapers or change their RSS URLs. Check the URLs in `scrapers/rss_scraper.py` are still valid.

**Beehiiv publish fails:** Confirm your `publication_id` is correct — it should look like `pub_xxxxxxxx`. Check the Beehiiv API key hasn't expired.

**AI draft is poor quality:** Add more context in `manual_input.txt`, adjust `system_prompt.txt`, or run with `--dry-run` to see what stories were collected.
