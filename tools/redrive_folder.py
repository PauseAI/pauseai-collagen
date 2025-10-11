#!/usr/bin/env python3
"""
Redrive all images in a folder to re-trigger webhooks.

For each image in the specified asset_folder:
1. Get current moderation status M
2. Toggle to pending (triggers webhook, ignored by processor)
3. Toggle back to M (triggers webhook, processed)

This re-syncs all approved images to EFS.
"""

import cloudinary
import cloudinary.api
import os
import time
import sys
from dotenv import load_dotenv

load_dotenv()

cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)


def redrive_folder(asset_folder: str, delay: float = 0.5, limit: int = None):
    """
    Redrive all images in an asset_folder by toggling moderation status.

    Args:
        asset_folder: Folder name (e.g., 'test_prototype', 'sayno')
        delay: Seconds to wait between API calls (rate limiting)
        limit: Max number of images to process (None = all)
    """
    print(f"Redriving asset_folder: {asset_folder}")
    print("=" * 80)

    # Get all images in folder
    search_result = cloudinary.Search() \
        .expression(f'asset_folder={asset_folder}') \
        .max_results(500) \
        .execute()

    all_images = search_result.get('resources', [])
    images = all_images[:limit] if limit else all_images

    print(f"Found {len(all_images)} images in {asset_folder}")
    if limit:
        print(f"Processing first {len(images)} images (--limit {limit})")

    if not images:
        print("No images to redrive")
        return

    print()

    # Process each image
    for i, resource in enumerate(images, 1):
        public_id = resource['public_id']

        # Get current moderation status
        try:
            full = cloudinary.api.resource(public_id, moderation=True)
            mod = full.get('moderation', [])

            if mod:
                original_status = mod[0].get('status')
                print(f"[{i}/{len(images)}] {public_id} (currently: {original_status})")

                # Toggle: original → pending → original
                print(f"  → pending", end="", flush=True)
                cloudinary.api.update(public_id, moderation_status='pending')
                time.sleep(delay)

                print(f" → {original_status}", end="", flush=True)
                cloudinary.api.update(public_id, moderation_status=original_status)
                time.sleep(delay)

                print(" ✓")
            else:
                print(f"[{i}/{len(images)}] {public_id} - NO MODERATION (skipping)")

        except Exception as e:
            print(f"[{i}/{len(images)}] {public_id} - ERROR: {e}")

    print()
    print(f"✓ Redriven {len(images)} images in {asset_folder}")
    print("Check EFS for synced files")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Redrive images in an asset_folder to re-trigger webhooks')
    parser.add_argument('asset_folder', help='Folder name (e.g., test_prototype, sayno)')
    parser.add_argument('--limit', type=int, help='Process only first N images (for testing)')
    parser.add_argument('--delay', type=float, default=0.5, help='Delay between API calls (default: 0.5s)')

    args = parser.parse_args()
    redrive_folder(args.asset_folder, delay=args.delay, limit=args.limit)
