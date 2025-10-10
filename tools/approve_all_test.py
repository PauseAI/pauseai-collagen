#!/usr/bin/env python3
"""Approve all test_prototype asset_folder images."""

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

# Get all images with asset_folder=test_prototype
search_result = cloudinary.Search() \
    .expression('asset_folder=test_prototype') \
    .max_results(100) \
    .execute()

test_ids = [r['public_id'] for r in search_result.get('resources', [])]

print(f"Approving {len(test_ids)} test_prototype images...")

for i, public_id in enumerate(test_ids, 1):
    print(f"  [{i}/{len(test_ids)}] {public_id}")
    cloudinary.api.update(public_id, moderation_status='approved')
    time.sleep(0.5)

print(f"\n✓ Approved {len(test_ids)} images")
print("Webhooks will sync them to /mnt/efs/test_prototype/approved/")
