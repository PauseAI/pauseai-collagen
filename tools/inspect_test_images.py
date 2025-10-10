#!/usr/bin/env python3
"""Comprehensive inspection of test_prototype asset folder images."""

import cloudinary
import cloudinary.api
import os
import json
from dotenv import load_dotenv

load_dotenv()

cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)

# Get all images with asset_folder=test_prototype via search
# Search API is more reliable for filtering by asset_folder
print("Searching for images with asset_folder='test_prototype'...")
print("=" * 80)

search_result = cloudinary.Search() \
    .expression('asset_folder=test_prototype') \
    .with_field('context') \
    .with_field('tags') \
    .with_field('metadata') \
    .with_field('image_metadata') \
    .max_results(100) \
    .execute()

print(f"\nFound {len(search_result.get('resources', []))} images")
print("=" * 80)

# Also fetch moderation status separately since it's not in search results
all_info = []

for resource in search_result.get('resources', []):
    public_id = resource['public_id']

    # Fetch full details including moderation
    try:
        full_details = cloudinary.api.resource(
            public_id,
            moderation=True,
            context=True,
            tags=True,
            metadata=True
        )

        # Extract key info
        info = {
            'public_id': public_id,
            'asset_folder': resource.get('asset_folder'),
            'folder': resource.get('folder'),
            'moderation_status': 'none',
            'email': None,
            'tags': full_details.get('tags', []),
            'context': full_details.get('context', {}),
            'created_at': resource.get('created_at'),
            'uploaded_at': resource.get('uploaded_at')
        }

        # Get moderation status
        mod = full_details.get('moderation', [])
        if mod and len(mod) > 0:
            info['moderation_status'] = mod[0].get('status', 'none')

        # Get email from context
        if 'context' in full_details and 'custom' in full_details['context']:
            info['email'] = full_details['context']['custom'].get('email')

        all_info.append(info)

    except Exception as e:
        print(f"Error fetching {public_id}: {e}")

# Print summary
print(f"\nDetailed info for {len(all_info)} images:")
print("=" * 80)

for info in all_info:
    print(f"\nPublic ID: {info['public_id']}")
    print(f"  asset_folder: {info['asset_folder']}")
    print(f"  folder: {info['folder']}")
    print(f"  Moderation: {info['moderation_status']}")
    print(f"  Email: {info['email'] or 'NO EMAIL'}")
    if info['tags']:
        print(f"  Tags: {', '.join(info['tags'])}")

# Save to JSON for analysis
with open('test_prototype_images.json', 'w') as f:
    json.dump(all_info, f, indent=2)

print(f"\n\nSaved detailed info to test_prototype_images.json")

# Show unique values for key fields
asset_folders = set(info['asset_folder'] for info in all_info if info['asset_folder'])
folders = set(info['folder'] for info in all_info if info['folder'])
print(f"\nUnique asset_folder values: {asset_folders}")
print(f"Unique folder values: {folders}")
