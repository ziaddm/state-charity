import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

def send_temp_password_email(email: str, temp_password: str):
    """Send temp password to user via email"""
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    
    if not all([smtp_server, smtp_user, smtp_password]):
        print(f"Email not configured. Temp password for {email}: {temp_password}")
        return
    
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
        
        print(f"Email sent to {email}")
    
    except Exception as e:
        print(f"Failed to send email: {e}")