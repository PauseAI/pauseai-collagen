#!/usr/bin/env python3
"""
Webhook processor for Collagen - handles image sync from Cloudinary to EFS.

Downloads approved images, embeds email metadata in EXIF, and saves to campaign-specific
directories. Deletes rejected images from approved storage.
"""

import os
import re
import json
import logging
import subprocess
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor

import cloudinary
import cloudinary.api
import requests
from dotenv import load_dotenv

from campaign_logger import CampaignLogger

# Load environment variables
load_dotenv()

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)

# Configuration
EFS_BASE = Path('/mnt/efs')
DEV_CAMPAIGN = 'test_prototype'  # Phase 1: Only process dev campaign

logger = logging.getLogger(__name__)


def sanitize_public_id(public_id: str) -> str:
    """
    Convert Cloudinary public_id to safe filename.

    Examples:
        'sayno/selfie_abc123' -> 'sayno_selfie_abc123'
        'test_prototype/photo' -> 'test_prototype_photo'
    """
    # Replace forward slashes and other unsafe chars with underscores
    safe_name = re.sub(r'[/\\:*?"<>|]', '_', public_id)
    return safe_name


def sanitize_test_email(email: str) -> str:
    """
    Transform email to safe test address for test_prototype campaign.

    Prevents accidental emails to real users during testing.

    Examples:
        'user@example.com' -> 'collagen-test+user-example-com@antb.me'
        'test@antb.me' -> 'collagen-test+test-antb-me@antb.me'
    """
    if not email:
        return email

    # Convert email to safe format: user@domain.com -> user-domain-com
    safe_token = email.replace('@', '-').replace('.', '-')

    # Return safe address
    return f'collagen-test+{safe_token}@antb.me'


def thumb_for_approved(approved_path: Path) -> Path:
    """
    Convert approved/ path to corresponding thumbnails/ path.
    Works for both files and directories.

    Convention:
        - approved/photo_abc.jpg → thumbnails/photo_abc.png (file)
        - campaign/approved/ → campaign/thumbnails/ (directory)

    Args:
        approved_path: Path in approved/ directory (file or directory)

    Returns:
        Corresponding path in thumbnails/
    """
    # Replace 'approved' with 'thumbnails' in path
    thumb_str = str(approved_path).replace('/approved', '/thumbnails')
    thumb_path = Path(thumb_str)

    # If it's a file (or looks like one), change extension to .png
    if approved_path.suffix or (not approved_path.exists() and '.' in approved_path.name):
        thumb_path = thumb_path.with_suffix('.png')

    return thumb_path


def fetch_resource_info(public_id: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Fetch resource metadata from Cloudinary API.

    Returns:
        Tuple of (asset_folder, email) or (None, None) on failure
    """
    try:
        resource = cloudinary.api.resource(public_id, context=True)

        asset_folder = resource.get('asset_folder')
        email = resource.get('context', {}).get('custom', {}).get('email')

        logger.info(f"Fetched metadata for {public_id}: asset_folder={asset_folder}, email={email or 'NO EMAIL'}")
        return (asset_folder, email)

    except Exception as e:
        logger.error(f"Failed to fetch metadata for {public_id}: {e}")
        return (None, None)


def download_image_to_temp(secure_url: str) -> Optional[str]:
    """
    Download image from Cloudinary CDN to temporary file as JPG.

    Always requests f_jpg format from Cloudinary to ensure consistent JPG output
    regardless of source format (PNG, HEIC, WEBP, etc.).

    Returns:
        Path to temp JPG file, or None on failure
    """
    try:
        # Always request JPG format from Cloudinary
        # This converts PNG/HEIC/WEBP to JPG on delivery, and is a no-op for existing JPGs
        jpg_url = secure_url.replace('/upload/', '/upload/f_jpg/')

        response = requests.get(jpg_url, timeout=30)
        response.raise_for_status()

        # Create temp file (always .jpg)
        temp_fd, temp_path = tempfile.mkstemp(suffix='.jpg', prefix='collagen_', dir='/tmp')

        # Write image bytes
        with os.fdopen(temp_fd, 'wb') as f:
            f.write(response.content)

        logger.info(f"Downloaded image to temp as JPG: {temp_path}")
        return temp_path

    except Exception as e:
        logger.error(f"Failed to download image from {jpg_url if 'jpg_url' in locals() else secure_url}: {e}")
        return None


def embed_exif_email(image_path: str, email: str) -> bool:
    """
    Embed email address in EXIF UserComment field of JPG file using exiftool.
    Modifies the file in place.

    Args:
        image_path: Path to JPG file
        email: Email address to embed

    Returns:
        True if successful, False otherwise
    """
    try:
        result = subprocess.run(
            ['exiftool', '-UserComment=' + email, '-overwrite_original', image_path],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            logger.info(f"Embedded email in EXIF: {image_path}")
            return True
        else:
            logger.error(f"exiftool failed: {result.stderr}")
            return False

    except FileNotFoundError:
        logger.error("exiftool not found - install with: apt-get install libimage-exiftool-perl")
        return False
    except Exception as e:
        logger.error(f"Failed to embed EXIF: {e}")
        return False


def generate_thumbnail(approved_path: Path) -> bool:
    """
    Generate 300×400 PNG thumbnail from approved JPEG.

    Uses convention: approved/photo.jpg → thumbnails/photo.png (via thumb_for_approved)

    Args:
        approved_path: Path to approved JPEG image

    Returns:
        True if successful, False otherwise
    """
    try:
        thumbnail_path = thumb_for_approved(approved_path)
        thumbnail_path.parent.mkdir(parents=True, exist_ok=True)

        result = subprocess.run(
            ['convert', str(approved_path), '-resize', '300x400!', str(thumbnail_path)],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            logger.info(f"Generated thumbnail: {thumbnail_path}")
            return True
        else:
            logger.error(f"Thumbnail generation failed: {result.stderr}")
            return False

    except FileNotFoundError:
        logger.error("convert (ImageMagick) not found")
        return False
    except Exception as e:
        logger.error(f"Failed to generate thumbnail: {e}")
        return False


def process_webhook(webhook_data: Dict[str, Any]) -> None:
    """
    Main webhook processor - orchestrates image sync based on moderation status.

    Phase 1 filtering: Only process test_prototype campaign

    Format handling: Always downloads as JPG via Cloudinary's f_jpg transformation,
    regardless of source format (PNG, HEIC, WEBP, etc.). This ensures:
    - Consistent format for collage generation
    - Simple EXIF embedding (JPG only)
    - Universal ImageMagick compatibility

    Flow:
        1. Parallel: fetch metadata + download to temp as JPG
        2. Check asset_folder matches campaign filter
        3. Embed EXIF in temp JPG file
        4. Move temp file to final EFS location (always .jpg extension)
        5. Return success (or fail and cleanup temp)

    Logic:
        - approved: Sync image with EXIF to approved/
        - rejected/pending: Delete from approved/ if exists
    """
    public_id = webhook_data.get('public_id')
    moderation_status = webhook_data.get('moderation_status')
    secure_url = webhook_data.get('secure_url')

    if not public_id:
        logger.error("No public_id in webhook data")
        return

    logger.info(f"Processing webhook: {public_id} ({moderation_status})")

    if moderation_status == 'approved':
        if not secure_url:
            logger.error(f"No secure_url in webhook for {public_id}")
            return

        temp_path = None
        try:
            # Parallel requests: API for metadata + CDN for image bytes to temp
            with ThreadPoolExecutor(max_workers=2) as executor:
                metadata_future = executor.submit(fetch_resource_info, public_id)
                download_future = executor.submit(download_image_to_temp, secure_url)

                # Wait for both
                asset_folder, email = metadata_future.result()
                temp_path = download_future.result()

            # Check if we got metadata
            if not asset_folder:
                logger.error(f"Failed to fetch asset_folder for {public_id}")
                if temp_path:
                    os.unlink(temp_path)
                return

            # Phase 1: Filter for dev campaign only
            if asset_folder != DEV_CAMPAIGN:
                logger.debug(f"Skipping {public_id} - not in {DEV_CAMPAIGN} campaign (asset_folder: {asset_folder})")
                if temp_path:
                    os.unlink(temp_path)
                return

            # Create campaign-specific logger for persistent file logging
            campaign_log = CampaignLogger(asset_folder, EFS_BASE)

            # Check if download succeeded
            if not temp_path:
                logger.error(f"Failed to download image for {public_id}")
                return

            # Sanitize email for test campaigns (prevent accidental emails to real users)
            email_for_exif = email
            if email and asset_folder == 'test_prototype':
                email_for_exif = sanitize_test_email(email)
                logger.info(f"Sanitized test email: {email} → {email_for_exif}")

            # Embed email in EXIF (modifies temp file in place)
            if email_for_exif:
                if not embed_exif_email(temp_path, email_for_exif):
                    logger.error(f"Failed to embed EXIF for {public_id} - aborting")
                    os.unlink(temp_path)
                    return
            else:
                logger.warning(f"No email found for {public_id} - saving without EXIF")

            # Setup directories (creates both approved/ and thumbnails/)
            approved_dir = EFS_BASE / asset_folder / 'approved'
            approved_dir.mkdir(parents=True, exist_ok=True)
            thumb_for_approved(approved_dir).mkdir(parents=True, exist_ok=True)

            # Move full-size to approved/
            safe_filename = sanitize_public_id(public_id)
            final_path = approved_dir / f"{safe_filename}.jpg"

            shutil.move(temp_path, final_path)
            temp_path = None  # Moved successfully

            # Generate 300×400 PNG thumbnail (uses convention to find path)
            if not generate_thumbnail(final_path):
                logger.error(f"Failed to generate thumbnail for {public_id} - aborting")
                final_path.unlink()  # Remove approved image
                return

            logger.info(f"✓ Synced approved image: {public_id} -> {final_path}")
            logger.info(f"  + thumbnail: {thumb_for_approved(final_path)}")
            campaign_log.info(f"SYNCED: {public_id} (email: {email_for_exif or 'none'})")

        except Exception as e:
            logger.error(f"Error processing approved image {public_id}: {e}", exc_info=True)
            if 'campaign_log' in locals():
                campaign_log.error(f"ERROR: Failed to sync {public_id}: {str(e)}")
            # Cleanup temp file on error
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
            raise  # Re-raise to signal failure to webhook receiver

    elif moderation_status == 'rejected':
        # For rejected, delete from EFS (pending is ignored - it's a limbo state, not rejection)
        asset_folder, _ = fetch_resource_info(public_id)

        if not asset_folder:
            logger.warning(f"Could not determine asset_folder for {public_id}, cannot delete")
            return

        # Create campaign-specific logger
        campaign_log = CampaignLogger(asset_folder, EFS_BASE)

        # Remove both approved image and thumbnail (using convention)
        approved_dir = EFS_BASE / asset_folder / 'approved'
        safe_filename = sanitize_public_id(public_id)
        image_path = approved_dir / f"{safe_filename}.jpg"
        thumbnail_path = thumb_for_approved(image_path)

        deleted_any = False

        if image_path.exists():
            image_path.unlink()
            logger.info(f"✓ Deleted {moderation_status} image: {image_path}")
            deleted_any = True

        if thumbnail_path.exists():
            thumbnail_path.unlink()
            logger.info(f"✓ Deleted {moderation_status} thumbnail: {thumbnail_path}")
            deleted_any = True

        if deleted_any:
            campaign_log.info(f"DELETED: {public_id} (status: {moderation_status})")
        else:
            logger.debug(f"Image not in approved dir (already removed or never approved): {public_id}")

    elif moderation_status == 'pending':
        # Pending is a limbo state (not yet moderated) - do nothing
        logger.debug(f"Ignoring pending webhook for {public_id}")

    else:
        logger.warning(f"Unknown moderation status: {moderation_status}")


def log_webhook_to_file(webhook_data: Dict[str, Any], campaign: str) -> None:
    """
    Log webhook to campaign-specific log directory.

    Format: /mnt/efs/{campaign}/logs/webhooks/YYYYMMDD/HHMMSS.{status}.{public_id}.json
    """
    try:
        public_id = webhook_data.get('public_id', 'unknown')
        status = webhook_data.get('moderation_status', 'unknown')

        now = datetime.utcnow()
        date_dir = now.strftime('%Y%m%d')
        timestamp = now.strftime('%H%M%S')

        safe_id = sanitize_public_id(public_id)
        filename = f"{timestamp}.{status}.{safe_id}.json"

        log_dir = EFS_BASE / campaign / 'logs' / 'webhooks' / date_dir
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / filename
        with open(log_file, 'w') as f:
            json.dump({
                'timestamp': now.isoformat(),
                'webhook_data': webhook_data
            }, f, indent=2)

        logger.debug(f"Logged webhook to {log_file}")

    except Exception as e:
        logger.error(f"Failed to log webhook: {e}")
