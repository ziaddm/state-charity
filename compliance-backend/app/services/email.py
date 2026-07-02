import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def send_temp_password_email(email: str, temp_password: str) -> bool:
    """
    Send a temporary password to a new user.

    Returns True if the email was sent, False otherwise. The password is never
    logged; when this returns False the caller is responsible for delivering
    the password through another secure channel.
    """
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")

    if not all([smtp_server, smtp_user, smtp_password]):
        logger.warning(f"SMTP not configured — could not email temp password to {email}")
        return False

    try:
        msg = MIMEMultipart()
        msg["From"] = smtp_user
        msg["To"] = email
        msg["Subject"] = "Your Charity Care Portal Account"

        body = f"""
Hello,

Your account has been created on the Charity Care Portal.

Temporary Password: {temp_password}

Please log in and change your password immediately.

Best regards,
Charity Care Portal Admin
"""

        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)

        logger.info(f"Temp password email sent to {email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send temp password email to {email}: {e}")
        return False
