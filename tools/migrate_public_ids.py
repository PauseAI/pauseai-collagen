#!/usr/bin/env python3
"""
Migrate mismatched public_ids: rename test_prototype/... to sayno/... for images in sayno asset_folder.

This ensures public_id prefix matches asset_folder for campaign-based routing.
"""

import cloudinary
import cloudinary.uploader
import cloudinary.api
from dotenv import load_dotenv
import os
import json
import sys
import time

load_dotenv('.env')

cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)

# Load backup file
BACKUP_FILE = 'archive/migration-backup-20251010085050.json'

def test_single_rename():
    """Test rename on first image to see what metadata is preserved."""

    with open(BACKUP_FILE) as f:
        images = json.load(f)

    test_image = images[0]
    old_id = test_image['public_id']

    # Extract suffix after test_prototype/
    suffix = old_id.split('/', 1)[1]
    new_id = f"sayno/{suffix}"

    print(f"Testing rename on 1 image:")
    print(f"  From: {old_id}")
    print(f"  To:   {new_id}")
    print()

    print("Before rename:")
    print(f"  Tags: {test_image['tags']}")
    print(f"  Email: {test_image.get('email')}")
    print(f"  Moderation: {test_image['moderation_status']}")
    print()

    # Perform rename
    try:
        result = cloudinary.uploader.rename(old_id, new_id)
        print(f"✓ Rename API call succeeded")
        print(f"  New public_id: {result.get('public_id')}")
        print()
    except Exception as e:
        print(f"✗ Rename failed: {e}")
        sys.exit(1)

    # Fetch renamed resource to check preserved metadata
    time.sleep(1)
    renamed = cloudinary.api.resource(new_id, tags=True, context=True, moderation=True)

    print("After rename:")
    print(f"  Tags: {renamed.get('tags', [])}")
    print(f"  Context: {renamed.get('context', {}).get('custom', {})}")
    print(f"  Moderation: {renamed.get('moderation', [{}])[0].get('status')}")
    print(f"  Created: {renamed.get('created_at')}")
    print()

    # Compare
    preserved = []
    lost = []

    if set(renamed.get('tags', [])) == set(test_image['tags']):
        preserved.append("tags")
    else:
        lost.append(f"tags (had {test_image['tags']}, now {renamed.get('tags', [])})")

    email_before = test_image.get('email')
    email_after = renamed.get('context', {}).get('custom', {}).get('email')
    if email_before == email_after:
        preserved.append("email")
    else:
        lost.append(f"email (had {email_before}, now {email_after})")

    mod_before = test_image['moderation_status']
    mod_after = renamed.get('moderation', [{}])[0].get('status')
    if mod_before == mod_after:
        preserved.append("moderation_status")
    else:
        lost.append(f"moderation_status (had {mod_before}, now {mod_after})")

    print("=" * 80)
    print(f"PRESERVED: {', '.join(preserved) if preserved else 'NOTHING'}")
    print(f"LOST: {', '.join(lost) if lost else 'NOTHING'}")
    print("=" * 80)

    return {
        'new_public_id': new_id,
        'preserved': preserved,
        'lost': lost,
        'needs_restoration': len(lost) > 0
    }

def migrate_remaining():
    """Migrate the remaining 25 images."""

    with open(BACKUP_FILE) as f:
        images = json.load(f)

    # Skip first (already migrated)
    remaining = images[1:]

    print(f"Migrating remaining {len(remaining)} images...")
    print("=" * 80)

    migrated = 0
    failed = []

    for img in remaining:
        old_id = img['public_id']
        suffix = old_id.split('/', 1)[1]
        new_id = f"sayno/{suffix}"

        print(f"\n[{migrated + 1}/{len(remaining)}] {old_id}")
        print(f"  → {new_id}")

        try:
            result = cloudinary.uploader.rename(old_id, new_id)
            print(f"  ✓ Success")
            migrated += 1
            time.sleep(0.5)  # Rate limiting

        except Exception as e:
            print(f"  ✗ Failed: {e}")
            failed.append({'old_id': old_id, 'new_id': new_id, 'error': str(e)})

    print()
    print("=" * 80)
    print(f"Migration complete!")
    print(f"  Migrated: {migrated}/{len(remaining)}")
    print(f"  Failed: {len(failed)}")

    if failed:
        print()
        print("Failed migrations:")
        for f in failed:
            print(f"  {f['old_id']} → {f['new_id']}: {f['error']}")

    return migrated, failed

if __name__ == '__main__':
    if '--test' in sys.argv:
        test_single_rename()
    elif '--migrate' in sys.argv:
        migrate_remaining()
    else:
        print("Usage:")
        print("  python3 migrate_public_ids.py --test      # Test rename on 1 image")
        print("  python3 migrate_public_ids.py --migrate   # Migrate remaining 25 images")
