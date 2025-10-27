#!/usr/bin/env python3
"""
Test SMTP sending from sayno@pauseai.info

Usage:
    ./tools/test_smtp.py <recipient_email>

Example:
    ./tools/test_smtp.py collagen-test+initial@antb.me
"""

import os
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv()

def send_test_email(recipient_email):
    """Send a test email via Google Workspace SMTP"""

    # SMTP configuration
    smtp_server = "smtp.gmail.com"
    smtp_port = 587  # TLS
    smtp_user = os.getenv("SAYNO_SMTP_USER")
    smtp_password = os.getenv("SAYNO_SMTP_PASSWORD")

    # Validate credentials
    if not smtp_user or not smtp_password:
        print("❌ Error: SAYNO_SMTP_USER and SAYNO_SMTP_PASSWORD must be set in .env")
        sys.exit(1)

    # Create message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Collagen SMTP Test - " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg["From"] = smtp_user
    msg["To"] = recipient_email

    # Plain text version
    text_body = f"""
Hello!

This is a test email from the Collagen email system.

Configuration:
- From: {smtp_user}
- SMTP Server: {smtp_server}:{smtp_port}
- Authentication: App Password (DKIM enabled)
- Timestamp: {datetime.now().isoformat()}

If you're reading this, SMTP is working correctly! ✅

--
Collagen Email System
PauseAI
"""

    # HTML version
    html_body = f"""
<html>
<body>
<p>Hello!</p>

<p>This is a test email from the <strong>Collagen email system</strong>.</p>

<h3>Configuration:</h3>
<ul>
<li><strong>From:</strong> {smtp_user}</li>
<li><strong>SMTP Server:</strong> {smtp_server}:{smtp_port}</li>
<li><strong>Authentication:</strong> App Password (DKIM enabled)</li>
<li><strong>Timestamp:</strong> {datetime.now().isoformat()}</li>
</ul>

<p>If you're reading this, SMTP is working correctly! ✅</p>

<hr>
<p><em>Collagen Email System<br>PauseAI</em></p>
</body>
</html>
"""

    # Attach both versions
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    # Send email
    print(f"📧 Sending test email...")
    print(f"   From: {smtp_user}")
    print(f"   To: {recipient_email}")
    print(f"   Server: {smtp_server}:{smtp_port}")

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()  # Upgrade to TLS
            server.login(smtp_user, smtp_password)
            server.send_message(msg)

        print("✅ Email sent successfully!")
        print(f"\nCheck {recipient_email} inbox (and spam folder)")

    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Authentication failed: {e}")
        print("\nTroubleshooting:")
        print("1. Verify SAYNO_SMTP_PASSWORD is the correct app password (16 chars)")
        print("2. Ensure 2FA is enabled on sayno@pauseai.info")
        print("3. Try regenerating the app password")
        sys.exit(1)

    except smtplib.SMTPException as e:
        print(f"❌ SMTP error: {e}")
        sys.exit(1)

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: ./tools/test_smtp.py <recipient_email>")
        print("\nExample:")
        print("  ./tools/test_smtp.py collagen-test+initial@antb.me")
        sys.exit(1)

    recipient = sys.argv[1]

    # Basic email validation
    if "@" not in recipient or "." not in recipient:
        print(f"❌ Invalid email address: {recipient}")
        sys.exit(1)

    send_test_email(recipient)
