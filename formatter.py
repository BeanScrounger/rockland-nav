"""
Formatter for The Rockland Navigator.

Converts the plain-text newsletter draft into a clean,
responsive HTML email suitable for preview and Beehiiv publishing.
"""

import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

# Brand colors
COLOR_DARK_GREEN = "#1a4a2e"
COLOR_LIGHT_GREEN = "#2d7a4f"
COLOR_ACCENT = "#4caf50"
COLOR_BG = "#f5f5f0"
COLOR_CARD = "#ffffff"
COLOR_TEXT = "#2c2c2c"
COLOR_MUTED = "#666666"
COLOR_BORDER = "#e0e0d8"


def _text_to_html_paragraphs(text: str) -> str:
    """
    Convert plain text to HTML paragraphs and basic formatting.
    - Double newlines become paragraph breaks
    - Lines starting with '•' or '-' become list items
    - URLs become clickable links
    - ALL CAPS section headers get special treatment
    """
    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Split on double newlines to get blocks
    blocks = re.split(r"\n{2,}", text.strip())
    html_parts = []

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        lines = block.split("\n")

        # Check if this is an ALL CAPS section header (e.g., "TOP STORIES")
        if (
            len(lines) == 1
            and lines[0].isupper()
            and len(lines[0]) > 3
            and len(lines[0]) < 80
        ):
            html_parts.append(
                f'<h2 style="color:{COLOR_DARK_GREEN}; font-family: Georgia, serif; '
                f'font-size: 18px; font-weight: bold; margin: 32px 0 12px 0; '
                f'padding-bottom: 6px; border-bottom: 2px solid {COLOR_ACCENT};">'
                f"{_linkify(lines[0])}</h2>"
            )
            continue

        # Check if block is a bullet list
        bullet_lines = [
            l for l in lines if l.strip().startswith(("•", "-", "*", "–"))
        ]
        if len(bullet_lines) >= len(lines) * 0.6 and len(bullet_lines) > 1:
            items_html = ""
            for line in lines:
                stripped = line.strip().lstrip("•-*– ").strip()
                if stripped:
                    items_html += (
                        f'<li style="margin-bottom: 8px; line-height: 1.6;">'
                        f"{_linkify(stripped)}</li>"
                    )
            html_parts.append(
                f'<ul style="padding-left: 20px; margin: 12px 0;">{items_html}</ul>'
            )
            continue

        # Regular paragraph
        para_text = " ".join(lines)
        html_parts.append(
            f'<p style="margin: 0 0 16px 0; line-height: 1.7; color: {COLOR_TEXT};">'
            f"{_linkify(para_text)}</p>"
        )

    return "\n".join(html_parts)


def _linkify(text: str) -> str:
    """Convert bare URLs in text to HTML anchor tags."""
    url_pattern = re.compile(
        r"(https?://[^\s\)\]\>,\"\']+)"
    )
    return url_pattern.sub(
        lambda m: (
            f'<a href="{m.group(1)}" '
            f'style="color: {COLOR_LIGHT_GREEN}; text-decoration: underline;">'
            f"{m.group(1)}</a>"
        ),
        text,
    )


def format_newsletter(draft_text: str, edition_date: str | None = None) -> str:
    """
    Wrap plain-text newsletter draft in a responsive HTML email template.

    Args:
        draft_text: The raw newsletter text from the curator.
        edition_date: Date string for the edition header. Defaults to today.

    Returns:
        Full HTML string ready for email and Beehiiv.
    """
    if edition_date is None:
        edition_date = datetime.now().strftime("%B %-d, %Y")

    body_html = _text_to_html_paragraphs(draft_text)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>The Rockland Navigator — {edition_date}</title>
  <style>
    /* Reset */
    body, table, td, p, a, li, blockquote {{
      -webkit-text-size-adjust: 100%;
      -ms-text-size-adjust: 100%;
      margin: 0;
      padding: 0;
    }}
    body {{
      background-color: {COLOR_BG};
      font-family: Georgia, 'Times New Roman', Times, serif;
      color: {COLOR_TEXT};
    }}
    a {{ color: {COLOR_LIGHT_GREEN}; }}
    @media only screen and (max-width: 600px) {{
      .email-container {{ width: 100% !important; }}
      .email-body {{ padding: 20px 16px !important; }}
    }}
  </style>
</head>
<body style="background-color: {COLOR_BG}; margin: 0; padding: 20px 0;">

  <!-- Outer wrapper -->
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
    <tr>
      <td align="center" style="padding: 20px 10px;">

        <!-- Email container -->
        <table class="email-container" role="presentation" width="600"
               cellpadding="0" cellspacing="0" border="0"
               style="max-width: 600px; width: 100%;">

          <!-- ── HEADER ── -->
          <tr>
            <td style="background-color: {COLOR_DARK_GREEN}; padding: 36px 40px 28px 40px;
                        border-radius: 8px 8px 0 0; text-align: center;">
              <h1 style="font-family: Georgia, serif; color: #ffffff;
                          font-size: 32px; font-weight: bold; margin: 0 0 8px 0;
                          letter-spacing: -0.5px;">
                The Rockland Navigator
              </h1>
              <p style="color: rgba(255,255,255,0.75); font-size: 14px;
                          margin: 0 0 12px 0; font-style: italic;">
                Your hyperlocal guide to Rockland County, NY
              </p>
              <p style="color: rgba(255,255,255,0.9); font-size: 13px; margin: 0;">
                {edition_date}
              </p>
            </td>
          </tr>

          <!-- ── BODY ── -->
          <tr>
            <td class="email-body"
                style="background-color: {COLOR_CARD}; padding: 36px 40px;
                        border-left: 1px solid {COLOR_BORDER};
                        border-right: 1px solid {COLOR_BORDER};">
              {body_html}
            </td>
          </tr>

          <!-- ── FOOTER ── -->
          <tr>
            <td style="background-color: {COLOR_DARK_GREEN}; padding: 24px 40px;
                        border-radius: 0 0 8px 8px; text-align: center;">
              <p style="color: rgba(255,255,255,0.8); font-size: 12px; margin: 0 0 6px 0;">
                The Rockland Navigator · Rockland County, NY
              </p>
              <p style="color: rgba(255,255,255,0.55); font-size: 11px; margin: 0;">
                You received this because you subscribed to local news from The Rockland Navigator.
              </p>
            </td>
          </tr>

        </table>
        <!-- /Email container -->

      </td>
    </tr>
  </table>

</body>
</html>"""

    logger.info("Newsletter formatted as HTML")
    return html
