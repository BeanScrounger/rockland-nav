# The Rockland Navigator — Newsletter Automation (Ghost edition)

Automated pipeline for generating, reviewing, and publishing *The Rockland Navigator*, a hyperlocal newsletter covering Rockland County, NY.

> **Branch:** `ghost` — publishes to [Ghost](https://ghost.org) instead of Beehiiv.
> For the original Beehiiv version, see the `main` branch.

---

## How It Works

Every Tuesday and Friday, the system:
1. Scrapes local news from RSS feeds, Reddit, and town/county websites
2. Removes duplicate stories
3. Optionally opens a browser UI so you can pick which stories to include (`--select`)
4. Drafts the newsletter using Claude AI, following your template and voice guide
5. Emails you an HTML preview
6. Opens a browser window where you can approve or reject the draft
7. If approved, publishes the draft to Ghost automatically — then opens the Ghost editor so you can review before hitting Publish

---

## Prerequisites

- **Python 3.9 or newer** — check with `python3 --version`
- **pip** — usually included with Python
- A **Gmail account** with an App Password (see step 3 below)
- An **Anthropic account** with an API key (for Claude AI)
- A **Ghost site** — either self-hosted or on [Ghost(Pro)](https://ghost.org/pricing/)

---

## 1. Installation

Open Terminal, navigate to this folder, and run:

```bash
python3 -m venv venv
source venv/bin/activate
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

### Ghost URL + Admin API Key
1. Log in to your Ghost Admin panel (e.g. `https://yoursite.com/ghost`)
2. Go to **Settings → Integrations**
3. Click **Add custom integration** and give it a name (e.g. "Rockland Navigator")
4. Copy the **Admin API Key** — it looks like `64abc123...:def456...` (id:secret format)
5. Paste it as `ghost.admin_api_key` in `config.yaml`
6. Set `ghost.url` to your Ghost site's root URL (e.g. `https://yoursite.com`)

### Gmail App Password
1. Go to your Google Account → **Security**
2. Under "How you sign in to Google," click **2-Step Verification** (must be enabled first)
3. Scroll to the bottom and click **App passwords**
4. Create a new app password for "Mail"
5. Copy the 16-character password (with spaces) into `email.app_password`

---

## 3. First Run (Dry Run)

Test everything without sending email or publishing:

```bash
python main.py --dry-run
```

Scrapes stories, drafts the newsletter with Claude, and saves the HTML. No emails sent, nothing published.

---

## 4. Full Run

```bash
python main.py
```

A browser window opens showing the draft. Click **Approve & Publish** to post to Ghost as a draft, or **Reject** to cancel. After approving, Ghost editor opens automatically so you can review and hit Publish when ready.

---

## 5. Selecting Stories Manually

When you want editorial control over which scraped articles Claude uses:

```bash
python main.py --select
```

Opens a browser UI showing all ~100 scraped articles grouped by source with checkboxes. Uncheck anything irrelevant, click **Continue**, and Claude drafts from only your selection. Combine with `--dry-run` to preview without publishing:

```bash
python main.py --select --dry-run
```

---

## 6. Auto-Scheduling

To run automatically every Tuesday and Friday at 7 AM:

```bash
python scheduler.py
```

Keep the Terminal window open. It triggers `main.py` at the configured times.

---

## 7. Customizing the Newsletter Format

Edit `newsletter_template.yaml` to change section names, word counts, source priorities, and publishing days. Changes take effect on the next run.

---

## 8. Customizing the AI Voice

Edit `system_prompt.txt` to adjust tone, editorial priorities, and formatting preferences. The AI reads this file on every run.

---

## 9. Adding Manual Content

Paste story tips, events, or corrections into `manual_input.txt` before running:

```
STORY: The Nyack Farmers Market opens for the season on April 5th at Memorial Park.
EVENT: Clarkstown Town Board meeting, Monday March 24 at 7pm, Town Hall.
```

Clear the file after each run if you don't want items repeated.

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
| `story_selector.py` | Browser UI for picking stories (used with `--select`) |
| `publisher.py` | Ghost Admin API integration |
| `scheduler.py` | Auto-schedules Tuesday/Friday runs |

---

## Troubleshooting

**"Authentication failed" on email send:** Double-check your Gmail App Password in `config.yaml`. Make sure 2-Step Verification is enabled on your Google account.

**Ghost API returns 401:** Your Admin API key is wrong or expired. Regenerate it in Ghost Admin → Settings → Integrations.

**Ghost API returns 404:** Your `ghost.url` in `config.yaml` is incorrect. It should be the root of your site (e.g. `https://yoursite.com`), not the Ghost admin URL.

**Scraper returns no stories:** Some local news sites block scrapers or change their RSS URLs. Check the URLs in `scrapers/rss_scraper.py` are still valid. Add stories manually via `manual_input.txt`.

**AI draft is poor quality:** Add more context in `manual_input.txt`, adjust `system_prompt.txt`, or use `--select` to manually choose the best stories before drafting.

**SSL certificate errors on RSS feeds:** Run this in your venv to fix: `pip install certifi` then add these two lines at the top of `main.py`:
```python
import certifi, os
os.environ['SSL_CERT_FILE'] = certifi.where()
```
