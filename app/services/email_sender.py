import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path

logger = logging.getLogger(__name__)


def send_report_email(
    recipient_email: str,
    recipient_name: str,
    company_name: str,
    html_report_path: Path,
    pdf_report_path: Path | None = None,
) -> dict:
    """
    Sends the generated report to the prospect via email.

    Reads SMTP config from environment variables:
        SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SENDER_EMAIL

    Returns:
        {"success": True} or {"success": False, "error": "..."}
    """
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    sender_email = os.getenv("SENDER_EMAIL", smtp_user)

    if not all([smtp_host, smtp_user, smtp_pass]):
        logger.warning(
            "SMTP not configured (SMTP_HOST/SMTP_USER/SMTP_PASS missing). "
            "Skipping email delivery."
        )
        return {
            "success": False,
            "error": "SMTP not configured — email not sent."
        }

    subject = f"Your Personalized Business Insight Report — {company_name}"

    # Plain-text fallback body
    text_body = (
        f"Hi {recipient_name},\n\n"
        f"Thank you for submitting your details.\n\n"
        f"Please find your personalized business insight report for {company_name} attached.\n\n"
        f"We look forward to connecting with you.\n\n"
        f"Best regards,\nThe SimplifIQ Team"
    )

    # Rich HTML email body
    html_body = f"""
    <html><body style="font-family:Inter,Arial,sans-serif;color:#111827;padding:32px;">
      <h2 style="color:#0f172a;">Hi {recipient_name},</h2>
      <p>Thank you for reaching out. We've prepared a personalized business insight report
         for <strong>{company_name}</strong> based on your submitted details and our research.</p>
      <p>The report is attached to this email. It includes:</p>
      <ul>
        <li>Executive Summary &amp; Company Snapshot</li>
        <li>Key Observations from publicly available data</li>
        <li>Identified Business Opportunities</li>
        <li>Strategic Recommendations tailored to your goals</li>
        <li>A personalized outreach summary</li>
      </ul>
      <p>We'd love to discuss these insights further. Feel free to reply to this email
         or schedule a quick call.</p>
      <p style="margin-top:24px;">Best regards,<br><strong>The SimplifIQ Team</strong></p>
    </body></html>
    """

    msg = MIMEMultipart("mixed")
    msg["From"] = sender_email
    msg["To"] = recipient_email
    msg["Subject"] = subject

    # Attach text + HTML
    alt_part = MIMEMultipart("alternative")
    alt_part.attach(MIMEText(text_body, "plain"))
    alt_part.attach(MIMEText(html_body, "html"))
    msg.attach(alt_part)

    # Attach HTML report file
    if html_report_path and html_report_path.exists():
        _attach_file(msg, html_report_path, "text/html")

    # Attach PDF report if available
    if pdf_report_path and pdf_report_path.exists():
        _attach_file(msg, pdf_report_path, "application/pdf")

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(sender_email, recipient_email, msg.as_string())

        logger.info(f"Email sent to {recipient_email}")
        return {"success": True}

    except smtplib.SMTPAuthenticationError:
        error = "SMTP authentication failed. Check SMTP_USER and SMTP_PASS."
        logger.error(error)
        return {"success": False, "error": error}

    except smtplib.SMTPException as e:
        error = f"SMTP error: {e}"
        logger.error(error)
        return {"success": False, "error": error}

    except Exception as e:
        error = f"Unexpected email error: {e}"
        logger.error(error)
        return {"success": False, "error": error}


def _attach_file(msg: MIMEMultipart, file_path: Path, mime_type: str) -> None:
    """Attaches a file to a MIMEMultipart message."""
    main_type, sub_type = mime_type.split("/", 1)
    with open(file_path, "rb") as f:
        part = MIMEBase(main_type, sub_type)
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header(
        "Content-Disposition",
        "attachment",
        filename=file_path.name
    )
    msg.attach(part)
