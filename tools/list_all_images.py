#!/usr/bin/env python3
"""List ALL images in the account with comprehensive metadata."""

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

print("Fetching ALL resources (paginated)...")
print("=" * 80)

all_resources = []
next_cursor = None

# Paginate through ALL resources
while True:
    params = {
        'type': 'upload',
        'max_results': 500,
        'tags': True,
        'context': True,
        'moderation': True
    }

    if next_cursor:
        params['next_cursor'] = next_cursor

    result = cloudinary.api.resources(**params)

    all_resources.extend(result.get('resources', []))
    next_cursor = result.get('next_cursor')

    print(f"Fetched {len(result.get('resources', []))} resources (total: {len(all_resources)})")

    if not next_cursor:
        break

print(f"\nTotal resources fetched: {len(all_resources)}")
print("=" * 80)

# Now get detailed info for each (including asset_folder which isn't in basic listing)
detailed_info = []

for i, resource in enumerate(all_resources):
    public_id = resource['public_id']

    # Skip cloudinary demo assets
    if public_id.startswith('samples/') or public_id.startswith('sample'):
        continue

    try:
        # Fetch full details including asset_folder
        full = cloudinary.api.resource(
            public_id,
            context=True,
            tags=True,
            moderation=True
        )

        info = {
            'public_id': public_id,
            'asset_folder': full.get('asset_folder'),
            'folder': full.get('folder'),
            'moderation_status': 'none',
            'email': None,
            'tags': full.get('tags', []),
            'created_at': full.get('created_at'),
        }

        # Extract moderation status
        mod = full.get('moderation', [])
        if mod and len(mod) > 0:
            info['moderation_status'] = mod[0].get('status', 'none')

        # Extract email
        context = full.get('context', {})
        if 'custom' in context:
            info['email'] = context['custom'].get('email')

        detailed_info.append(info)

        if (i + 1) % 50 == 0:
            print(f"Processed {i + 1} resources...")

    except Exception as e:
        print(f"Error processing {public_id}: {e}")

print(f"\n\nProcessed {len(detailed_info)} non-sample resources")
print("=" * 80)

# Group by asset_folder
by_folder = {}
for info in detailed_info:
    folder = info['asset_folder'] or 'NO_FOLDER'
    if folder not in by_folder:
        by_folder[folder] = []
    by_folder[folder].append(info)

print("\nBreakdown by asset_folder:")
for folder in sorted(by_folder.keys()):
    images = by_folder[folder]
    with_email = sum(1 for img in images if img['email'])

    # Count by moderation status
    approved = sum(1 for img in images if img['moderation_status'] == 'approved')
    pending = sum(1 for img in images if img['moderation_status'] == 'pending')
    rejected = sum(1 for img in images if img['moderation_status'] == 'rejected')
    none_status = sum(1 for img in images if img['moderation_status'] == 'none')

    print(f"\n{folder}: {len(images)} images")
    print(f"  Emails: {with_email}")
    print(f"  Moderation: approved={approved}, pending={pending}, rejected={rejected}, none={none_status}")

# Show test_prototype tagged images in sayno
print("\n\nImages in sayno/ with 'test_prototype' tag:")
print("-" * 80)
sayno_test_images = [
    info for info in detailed_info
    if info['asset_folder'] == 'sayno' and 'test_prototype' in info['tags']
]
for info in sayno_test_images:
    print(f"{info['public_id']}")
    print(f"  Moderation: {info['moderation_status']}")
    print(f"  Email: {info['email'] or 'NO EMAIL'}")
    print(f"  Tags: {', '.join(info['tags'])}")
    print()

# Save everything
with open('all_images_detailed.json', 'w') as f:
    json.dump(detailed_info, f, indent=2)

print(f"\nSaved all details to all_images_detailed.json")
