#!/usr/bin/env python3
"""Check image formats in test_prototype and across all campaigns."""

import cloudinary
import cloudinary.api
import os
from collections import Counter
from dotenv import load_dotenv

load_dotenv()

cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)

print("Fetching ALL resources to check formats...")
print("=" * 80)

all_resources = []
next_cursor = None

while True:
    params = {
        'type': 'upload',
        'max_results': 500,
        'resource_type': 'image'
    }
    if next_cursor:
        params['next_cursor'] = next_cursor

    result = cloudinary.api.resources(**params)
    all_resources.extend(result.get('resources', []))
    next_cursor = result.get('next_cursor')

    if not next_cursor:
        break

print(f"Total resources: {len(all_resources)}")

# Get format info for each with asset_folder
formats_by_folder = {}

for resource in all_resources:
    public_id = resource['public_id']

    # Skip samples
    if public_id.startswith('samples/') or public_id.startswith('sample'):
        continue

    try:
        # Fetch full details including asset_folder
        full = cloudinary.api.resource(public_id)

        asset_folder = full.get('asset_folder', 'NO_FOLDER')
        format_val = full.get('format', 'unknown')

        if asset_folder not in formats_by_folder:
            formats_by_folder[asset_folder] = []
        formats_by_folder[asset_folder].append(format_val)

    except Exception as e:
        print(f"Error fetching {public_id}: {e}")

# Report formats by folder
print("\n" + "=" * 80)
print("Image formats by asset_folder:")
print("=" * 80)

for folder in sorted(formats_by_folder.keys()):
    formats = formats_by_folder[folder]
    format_counts = Counter(formats)

    print(f"\n{folder}: {len(formats)} images")
    for fmt, count in format_counts.most_common():
        print(f"  {fmt}: {count}")

# Focus on test_prototype
if 'test_prototype' in formats_by_folder:
    test_formats = Counter(formats_by_folder['test_prototype'])
    print("\n" + "=" * 80)
    print("test_prototype format details:")
    print("=" * 80)
    for fmt, count in test_formats.most_common():
        print(f"{fmt}: {count} images")
