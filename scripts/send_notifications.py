#!/usr/bin/env python3
"""
Send notification emails to first-time collage contributors.

Usage:
    # Dry-run (show what would be sent, don't actually send)
    ./scripts/send_notifications.py test_prototype 20251023T160502Z,20=5x4 --dry-run

    # Send to single UID for testing
    ./scripts/send_notifications.py test_prototype 20251023T160502Z,20=5x4 --uid abc12345

    # Send to all first-time contributors
    ./scripts/send_notifications.py sayno 20251024T230728Z,266=19x14

Environment variables:
    COLLAGEN_DATA_DIR: Data directory (default: /mnt/efs)
    SAYNO_SMTP_USER: SMTP username (sayno@pauseai.info)
    SAYNO_SMTP_PASSWORD: SMTP app password
"""

import argparse
import json
import logging
import os
import smtplib
import sys
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import List, Dict, Optional

# Add lib/ to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
from tracking import TrackingDB
from email_template import generate_email

# Load environment variables
from dotenv import load_dotenv
load_dotenv()


# Configuration
DATA_DIR = os.environ.get("COLLAGEN_DATA_DIR", "/mnt/efs")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = os.getenv("SAYNO_SMTP_USER")
SMTP_PASSWORD = os.getenv("SAYNO_SMTP_PASSWORD")
RATE_LIMIT_SECONDS = 2  # Delay between sends (from bootstrap #500 success)

# Bootstrap emails file (one-time use, will delete after production send)
BOOTSTRAP_EMAILS_FILE = Path(__file__).parent / "bootstrap_emails.txt"

# Allowlist file (optional - if present, only send to these emails)
ALLOWLIST_EMAILS_FILE = Path(__file__).parent / "allowlist_emails.txt"

# Logging
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)


def load_manifest(campaign: str, build_id: str) -> Dict:
    """Load collage manifest JSON."""
    manifest_path = Path(DATA_DIR) / campaign / "collages" / build_id / "manifest.json"

    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    with open(manifest_path) as f:
        return json.load(f)


def get_first_time_contributors(manifest: Dict, db: TrackingDB) -> List[Dict]:
    """
    Get list of first-time contributors (not yet emailed).

    Returns:
        List of dicts with keys: email, uid (from tracking DB)
    """
    contributors = []

    for entry in manifest.get('tiles', []):
        email = entry.get('email')
        if not email:
            logger.warning(f"Tile {entry.get('filename')} has no email, skipping")
            continue

        # Check if already emailed
        user = db.get_user_by_email(email)
        if user and user.get('emailed_at'):
            logger.debug(f"Already emailed: {email} (uid={user['uid']})")
            continue

        # Add to contributors list
        if user:
            # User exists (participated in collage) but not yet emailed
            contributors.append({
                'email': email,
                'uid': user['uid']
            })
        else:
            # Should not happen - publish workflow creates user records
            logger.error(f"User not in tracking DB: {email} (run publish workflow first)")

    return contributors


def send_email(recipient: str, email_content: Dict[str, str], dry_run: bool = False) -> bool:
    """
    Send notification email via SMTP.

    Args:
        recipient: Email address
        email_content: Dict with keys: subject, plain, html
        dry_run: If True, log but don't actually send

    Returns:
        True if sent successfully, False otherwise
    """
    if dry_run:
        logger.info(f"[DRY-RUN] Would send to {recipient}")
        logger.debug(f"[DRY-RUN] Subject: {email_content['subject']}")
        logger.debug(f"[DRY-RUN] Plain text length: {len(email_content['plain'])} chars")
        logger.debug(f"[DRY-RUN] HTML length: {len(email_content['html'])} chars")
        return True

    # Validate SMTP credentials
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.error("SMTP credentials not set (SAYNO_SMTP_USER, SAYNO_SMTP_PASSWORD)")
        return False

    # Create message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = email_content['subject']
    msg["From"] = SMTP_USER
    msg["To"] = recipient

    # Attach both versions (email clients will prefer HTML)
    msg.attach(MIMEText(email_content['plain'], "plain"))
    msg.attach(MIMEText(email_content['html'], "html"))

    # Send email
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)

        logger.info(f"✓ Sent email to {recipient}")
        return True

    except smtplib.SMTPException as e:
        logger.error(f"✗ SMTP error sending to {recipient}: {e}")
        return False

    except Exception as e:
        logger.error(f"✗ Unexpected error sending to {recipient}: {e}")
        return False


def load_bootstrap_emails() -> set:
    """Load bootstrap email list (users who got manual notification)."""
    if not BOOTSTRAP_EMAILS_FILE.exists():
        return set()

    with open(BOOTSTRAP_EMAILS_FILE) as f:
        return {line.strip().lower() for line in f if line.strip()}


def load_allowlist_emails() -> Optional[set]:
    """
    Load allowlist email addresses (optional).
    If file exists, only send to these emails.
    Returns None if file doesn't exist (no filtering).
    """
    if not ALLOWLIST_EMAILS_FILE.exists():
        return None

    with open(ALLOWLIST_EMAILS_FILE) as f:
        return {line.strip().lower() for line in f if line.strip()}


def send_notifications(
    campaign: str,
    build_id: str,
    dry_run: bool = False,
    single_uid: Optional[str] = None
):
    """
    Send notification emails to first-time contributors.

    Args:
        campaign: Campaign name
        build_id: Collage build ID
        dry_run: If True, show what would be sent but don't send
        single_uid: If provided, only send to this UID (for testing)
    """
    logger.info(f"Starting email notifications for {campaign}/{build_id}")
    logger.info(f"Mode: {'DRY-RUN' if dry_run else 'LIVE SEND'}")
    if single_uid:
        logger.info(f"Single UID mode: {single_uid}")

    # Load bootstrap emails list
    bootstrap_emails = load_bootstrap_emails()
    if bootstrap_emails:
        logger.info(f"Loaded {len(bootstrap_emails)} bootstrap email addresses")

    # Load allowlist (optional - restricts who gets emails)
    allowlist_emails = load_allowlist_emails()
    if allowlist_emails:
        logger.info(f"ALLOWLIST MODE: Only sending to {len(allowlist_emails)} specified emails")

    # Load manifest
    try:
        manifest = load_manifest(campaign, build_id)
        logger.info(f"Loaded manifest with {len(manifest.get('tiles', []))} tiles")
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)

    # Check for warnings in manifest (blocks publish)
    if manifest.get('warnings'):
        logger.error("CANNOT SEND EMAILS - Manifest contains warnings:")
        logger.error(manifest['warnings'])
        logger.error("Fix the issues above, rebuild the collage, then retry email send")
        sys.exit(1)

    # Initialize tracking DB
    db = TrackingDB(campaign, DATA_DIR)

    # Get first-time contributors
    contributors = get_first_time_contributors(manifest, db)
    logger.info(f"Found {len(contributors)} first-time contributors to notify")

    # Filter to allowlist if present
    if allowlist_emails:
        original_count = len(contributors)
        contributors = [c for c in contributors if c['email'].lower() in allowlist_emails]
        logger.info(f"Allowlist filtered: {original_count} → {len(contributors)} recipients")

    if len(contributors) == 0:
        logger.info("No first-time contributors to email. Done!")
        return

    # Filter to single UID if requested
    if single_uid:
        contributors = [c for c in contributors if c['uid'] == single_uid]
        if len(contributors) == 0:
            logger.error(f"UID {single_uid} not found in first-time contributors")
            sys.exit(1)
        logger.info(f"Filtered to single UID: {single_uid} ({contributors[0]['email']})")

    # Send emails
    success_count = 0
    fail_count = 0

    for i, contributor in enumerate(contributors, 1):
        email = contributor['email']
        uid = contributor['uid']

        logger.info(f"[{i}/{len(contributors)}] Processing {email} (uid={uid})")

        # Check if this is a bootstrap user
        is_bootstrap = email.lower() in bootstrap_emails

        # Generate personalized email
        email_content = generate_email(campaign, uid, email, build_id, is_bootstrap_user=is_bootstrap)

        # Show content if allowlist is being used (testing mode)
        if allowlist_emails and dry_run:
            print(f"\n[ALLOWLIST TEST] Email for {email}:")
            print("=" * 60)
            import json
            print(json.dumps(email_content, indent=2))
            print("=" * 60)

        # Send email
        success = send_email(recipient=email, email_content=email_content, dry_run=dry_run)

        if success:
            success_count += 1

            # Mark as emailed in tracking DB (skip in dry-run)
            if not dry_run:
                db.mark_emailed(uid)
                logger.debug(f"Marked {uid} as emailed in tracking DB")

            # Rate limiting (skip for last email)
            if i < len(contributors):
                time.sleep(RATE_LIMIT_SECONDS)
        else:
            fail_count += 1

    # Summary
    logger.info("=" * 60)
    logger.info(f"Email send complete!")
    logger.info(f"  Success: {success_count}")
    logger.info(f"  Failed: {fail_count}")
    logger.info(f"  Total: {len(contributors)}")
    logger.info("=" * 60)

    if fail_count > 0:
        logger.warning(f"{fail_count} emails failed - check logs above")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Send notification emails to first-time collage contributors",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("campaign", help="Campaign name (e.g. sayno, test_prototype)")
    parser.add_argument("build_id", help="Collage build ID (e.g. 20251024T230728Z,266=19x14)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be sent without actually sending"
    )
    parser.add_argument(
        "--uid",
        help="Send to single UID only (for testing)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging"
    )

    args = parser.parse_args()

    # Set log level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate SMTP credentials (unless dry-run)
    if not args.dry_run:
        if not SMTP_USER or not SMTP_PASSWORD:
            logger.error("SMTP credentials not set!")
            logger.error("Set SAYNO_SMTP_USER and SAYNO_SMTP_PASSWORD environment variables")
            sys.exit(1)

    # Send notifications
    send_notifications(
        campaign=args.campaign,
        build_id=args.build_id,
        dry_run=args.dry_run,
        single_uid=args.uid
    )


if __name__ == "__main__":
    main()
