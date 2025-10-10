#!/usr/bin/env python3
"""Find HEIC images."""

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

print("Searching for HEIC images...")

all_resources = []
next_cursor = None

while True:
    params = {
        'type': 'upload',
        'max_results': 500,
    }
    if next_cursor:
        params['next_cursor'] = next_cursor

    result = cloudinary.api.resources(**params)
    all_resources.extend(result.get('resources', []))
    next_cursor = result.get('next_cursor')
    if not next_cursor:
        break

# Find HEIC files
heic_files = []
for r in all_resources:
    if r.get('format') == 'heic':
        try:
            full = cloudinary.api.resource(r['public_id'])
            heic_files.append({
                'public_id': r['public_id'],
                'asset_folder': full.get('asset_folder'),
                'created_at': full.get('created_at'),
                'uploaded_at': r.get('uploaded_at'),
                'format': 'heic',
                'bytes': r.get('bytes'),
                'width': r.get('width'),
                'height': r.get('height')
            })
        except Exception as e:
            print(f"Error fetching {r['public_id']}: {e}")

print(f"\nFound {len(heic_files)} HEIC images:\n")
print("=" * 80)
for img in heic_files:
    print(f"Public ID: {img['public_id']}")
    print(f"  Asset folder: {img['asset_folder']}")
    print(f"  Created: {img['created_at']}")
    print(f"  Uploaded: {img['uploaded_at']}")
    print(f"  Size: {img['bytes']:,} bytes ({img['width']}x{img['height']})")
    print()
