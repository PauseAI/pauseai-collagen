#!/usr/bin/env python3
"""Toggle an approved test_prototype image to re-trigger webhook."""

import cloudinary
import cloudinary.api
import os
import time
from dotenv import load_dotenv

load_dotenv()
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)

# Use the image with email for better testing
public_id = 'test_prototype/bs8psp5fvlylptdqmxmh'

print(f"Re-toggling: {public_id}")
print("=" * 80)

# Check current status
resource = cloudinary.api.resource(public_id, moderation=True, context=True)
current_status = resource.get('moderation', [{}])[0].get('status', 'none')
email = resource.get('context', {}).get('custom', {}).get('email')
asset_folder = resource.get('asset_folder')

print(f"Current status: {current_status}")
print(f"Email: {email}")
print(f"Asset folder: {asset_folder}")
print()

# Step 1: Set to pending
print("Step 1: Setting to pending...")
cloudinary.api.update(public_id, moderation_status='pending')
print("  ✓ Set to pending (webhook fired, processor will ignore)")
time.sleep(1)

# Step 2: Set back to approved
print("\nStep 2: Setting back to approved...")
cloudinary.api.update(public_id, moderation_status='approved')
print("  ✓ Set to approved (webhook fired, processor should sync)")

print("\n" + "=" * 80)
print("Toggle complete!")
print(f"Processor should download and save to:")
print(f"  /mnt/efs/test_prototype/approved/test_prototype_bs8psp5fvlylptdqmxmh.jpg")
print(f"With EXIF UserComment: {email}")
