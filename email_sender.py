"""
Email sender for The Rockland Navigator.

Sends the HTML newsletter draft as a preview email via Gmail SMTP
so the editor can review it before approving publication.
"""

import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def send_preview_email(
    html_content: str,
    email_config: dict,
    edition_date: str | None = None,
) -> bool:
    """
    Send the HTML newsletter as a preview email via Gmail SMTP.

    Args:
        html_content: Full HTML string of the formatted newsletter.
        email_config: Dict with keys:
            smtp_server, smtp_port, sender, app_password, preview_recipient
        edition_date: Human-readable date for the subject line.
                      Defaults to today.

    Returns:
        True if the email was sent successfully, False otherwise.
    """
    if edition_date is None:
        edition_date = datetime.now().strftime("%B %-d, %Y")

    smtp_server = email_config.get("smtp_server", "smtp.gmail.com")
    smtp_port = int(email_config.get("smtp_port", 587))
    sender = email_config["sender"]
    app_password = email_config["app_password"]
    recipient = email_config["preview_recipient"]

    subject = f"PREVIEW: The Rockland Navigator — {edition_date}"

    # Build the MIME message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"The Rockland Navigator <{sender}>"
    msg["To"] = recipient

    # Plain-text fallback
    plain_text = (
        f"The Rockland Navigator Preview — {edition_date}\n\n"
        "Your email client doesn't support HTML. "
        "Please open the approval server in your browser to review the newsletter."
    )
    msg.attach(MIMEText(plain_text, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        logger.info(f"Connecting to {smtp_server}:{smtp_port} ...")
        with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender, app_password)
            server.sendmail(sender, [recipient], msg.as_string())

        logger.info(f"Preview email sent to {recipient}")
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error(
            "Gmail authentication failed. "
            "Check your app password in config.yaml. "
            "Make sure 2-Step Verification is enabled on your Google account."
        )
        return False
    except smtplib.SMTPException as exc:
        logger.error(f"SMTP error while sending preview email: {exc}")
        return False
    except Exception as exc:
        logger.error(f"Unexpected error sending preview email: {exc}")
        return False
