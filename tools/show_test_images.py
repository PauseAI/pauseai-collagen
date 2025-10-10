#!/usr/bin/env python3
"""Show test_prototype rejected images with display names."""

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

rejected = cloudinary.api.resources_by_moderation(
    'manual', 'rejected',
    prefix='test_prototype/',
    max_results=50,
    context=True
)

print("REJECTED test_prototype images (with emails):")
print("-" * 80)
for r in rejected.get('resources', []):
    email = r.get('context', {}).get('custom', {}).get('email')
    if email:  # Only show ones with emails
        # Get display name - could be filename or last part of public_id
        display_name = r.get('original_filename', r['public_id'].split('/')[-1])
        print(f"Display: {display_name}")
        print(f"  Email: {email}")
        print(f"  Public ID: {r['public_id']}")
        print()
