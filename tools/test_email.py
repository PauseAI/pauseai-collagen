#!/usr/bin/env python3
"""Send test email to verify safe address format."""

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Email config (from send-collage-notifications.ts)
SENDER_EMAIL = 'anthony@pauseai.info'
SENDER_NAME = 'Anthony Bailey (PauseAI)'

# Test recipient (safe format)
test_recipient = 'collagen-test+test-example-com@antb.me'

# Create message
msg = MIMEMultipart('alternative')
msg['Subject'] = 'Collagen: Test email format verification'
msg['From'] = f'{SENDER_NAME} <{SENDER_EMAIL}>'
msg['To'] = test_recipient

body = """Test email from collagen processor - verifying safe email format works.

Original would have been: test@example.com
Sanitized to: collagen-test+test-example-com@antb.me

If you receive this, the format works!"""

msg.attach(MIMEText(body, 'plain'))

# Get Gmail app password from environment
password = os.getenv('GMAIL_APP_PASSWORD')

if not password:
    print("❌ GMAIL_APP_PASSWORD not set")
    print("Set it with: export GMAIL_APP_PASSWORD='your-16-char-password'")
    exit(1)

# Send via Gmail SMTP
print(f"Sending test email to: {test_recipient}")

with smtplib.SMTP('smtp.gmail.com', 587) as server:
    server.starttls()
    server.login(SENDER_EMAIL, password)
    server.send_message(msg)

print(f"✓ Email sent to {test_recipient}")
print("Check your inbox at antb.me")
