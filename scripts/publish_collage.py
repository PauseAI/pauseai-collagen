#!/usr/bin/env python3
"""
Publish a collage: create user records in tracking DB and upload to S3.

This must be run before sending emails, as it creates the user UIDs needed for tracking.

Usage:
    ./scripts/publish_collage.py test_prototype 20251030T120019Z,12=4x3
    ./scripts/publish_collage.py sayno 20251024T230728Z,266=19x14

Environment variables:
    COLLAGEN_DATA_DIR: Data directory (default: /mnt/efs)
"""

import argparse
import json
import logging
import os
import sys
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# Add lib/ to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
from tracking import TrackingDB

# Configuration
DATA_DIR = os.environ.get("COLLAGEN_DATA_DIR", "/mnt/efs")

# Logging
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)


def publish_collage(campaign: str, build_id: str):
    """
    Publish a collage: record participation in tracking DB and upload to S3.

    Args:
        campaign: Campaign name
        build_id: Collage build ID
    """
    logger.info(f"Publishing collage: {campaign}/{build_id}")

    # Load manifest
    manifest_path = Path(DATA_DIR) / campaign / "collages" / build_id / "manifest.json"

    if not manifest_path.exists():
        logger.error(f"Manifest not found: {manifest_path}")
        sys.exit(1)

    with open(manifest_path) as f:
        manifest = json.load(f)

    # Check for warnings (blocks publish)
    if manifest.get('warnings'):
        logger.error("CANNOT PUBLISH - Manifest contains warnings:")
        logger.error(manifest['warnings'])
        logger.error("Fix the issues above and rebuild before publishing")
        sys.exit(1)

    # Check if already published
    if manifest.get('published_at'):
        logger.warning(f"Already published at {manifest['published_at']}")
        response = input("Republish anyway? (y/N): ").strip().lower()
        if response != 'y':
            logger.info("Aborted")
            sys.exit(0)

    # Initialize tracking DB
    db = TrackingDB(campaign, DATA_DIR)

    # Record participation for each tile
    tiles = manifest.get('tiles', [])
    logger.info(f"Recording participation for {len(tiles)} tiles in tracking DB")

    layout = manifest['layout']
    cols = layout['cols']

    users_created = 0
    for idx, tile_entry in enumerate(tiles):
        email = tile_entry.get('email')

        if not email:
            logger.debug(f"Skipping tile {tile_entry['filename']} (no email)")
            continue

        # Calculate grid position
        row = idx // cols
        col = idx % cols

        # Record participation (creates user if needed)
        uid = db.record_participation(email, build_id, row, col)

        # Check if this was a new user
        user = db.get_user_by_uid(uid)
        if user and not user.get('emailed_at'):
            users_created += 1

        logger.debug(f"Recorded: {email} at ({row},{col}) → UID {uid}")

    logger.info(f"✓ Created/updated user records ({users_created} new users)")

    # Update manifest with published timestamp
    manifest['published_at'] = datetime.now(timezone.utc).isoformat()

    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    logger.info(f"✓ Updated manifest with published_at")

    # Upload to S3
    logger.info("Uploading to S3...")

    upload_script = Path(__file__).parent / "upload_collage_to_s3.py"
    result = subprocess.run(
        ["python3", str(upload_script), campaign, build_id],
        env={**os.environ, "COLLAGEN_DATA_DIR": DATA_DIR}
    )

    if result.returncode != 0:
        logger.error("S3 upload failed")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("✅ PUBLISH COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Build: {campaign}/{build_id}")
    logger.info(f"Users in tracking DB: {users_created} new, {len(tiles) - users_created} existing")
    logger.info(f"Next: Send emails with ./scripts/send_notifications.py {campaign} {build_id}")
    logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Publish collage: create tracking DB records and upload to S3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("campaign", help="Campaign name (e.g. sayno, test_prototype)")
    parser.add_argument("build_id", help="Collage build ID (e.g. 20251024T230728Z,266=19x14)")
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    publish_collage(args.campaign, args.build_id)


if __name__ == "__main__":
    main()
