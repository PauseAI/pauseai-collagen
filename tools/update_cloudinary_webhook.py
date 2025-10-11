#!/usr/bin/env python3
"""
Update Cloudinary webhook URL

Usage:
    python3 tools/update_cloudinary_webhook.py NEW_URL
"""

import sys
import os
import requests
from dotenv import load_dotenv

load_dotenv()

CLOUD_NAME = os.getenv('CLOUDINARY_CLOUD_NAME')
API_KEY = os.getenv('CLOUDINARY_API_KEY')
API_SECRET = os.getenv('CLOUDINARY_API_SECRET')

# From CLAUDE.md
WEBHOOK_ID = '0784a23497ead91ace28a2564f2fdb130fe17df07b2e786a36900af404860ab7'

def update_webhook(new_url):
    """Update Cloudinary webhook URL via Settings API"""

    # Cloudinary Settings API endpoint
    url = f'https://api.cloudinary.com/v1_1/{CLOUD_NAME}/notifications/{WEBHOOK_ID}'

    auth = (API_KEY, API_SECRET)
    data = {
        'notification_url': new_url
    }

    print(f"Updating webhook {WEBHOOK_ID[:16]}...")
    print(f"New URL: {new_url}")

    response = requests.put(url, auth=auth, data=data)

    if response.status_code == 200:
        result = response.json()
        print("\n✓ Webhook updated successfully!")
        print(f"  URL: {result.get('notification_url', 'N/A')}")
        print(f"  Status: {result.get('status', 'N/A')}")
        return True
    else:
        print(f"\n✗ Failed to update webhook")
        print(f"  Status: {response.status_code}")
        print(f"  Response: {response.text}")
        return False

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python3 tools/update_cloudinary_webhook.py NEW_URL")
        print("\nExample:")
        print("  python3 tools/update_cloudinary_webhook.py https://mjs5ar0xn4.execute-api.us-east-1.amazonaws.com/webhook/moderation")
        sys.exit(1)

    new_url = sys.argv[1]

    if not all([CLOUD_NAME, API_KEY, API_SECRET]):
        print("ERROR: Missing Cloudinary credentials in .env")
        sys.exit(1)

    success = update_webhook(new_url)
    sys.exit(0 if success else 1)
