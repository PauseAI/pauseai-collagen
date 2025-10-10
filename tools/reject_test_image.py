#!/usr/bin/env python3
"""Reject a test_prototype image to test deletion from EFS."""

import cloudinary
import cloudinary.api
import os
from dotenv import load_dotenv

load_dotenv()
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)

# Use the same image we just approved
public_id = 'test_prototype/bs8psp5fvlylptdqmxmh'

print(f"Rejecting: {public_id}")
print("=" * 80)

# Check current status
resource = cloudinary.api.resource(public_id, moderation=True)
current_status = resource.get('moderation', [{}])[0].get('status', 'none')

print(f"Current status: {current_status}")
print()

# Set to rejected
print("Setting to rejected...")
cloudinary.api.update(public_id, moderation_status='rejected')
print("  ✓ Set to rejected (webhook fired)")

print("\n" + "=" * 80)
print("Rejection complete!")
print(f"Processor should delete:")
print(f"  /mnt/efs/test_prototype/approved/test_prototype_bs8psp5fvlylptdqmxmh.jpg")
