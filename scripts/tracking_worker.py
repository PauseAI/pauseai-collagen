#!/usr/bin/env python3
"""
Tracking worker: Processes SQS messages for user tracking events.

Polls SQS queue for tracking events (open, validate, subscribe),
updates tracking.db, and logs all actions.
"""

import json
import logging
import os
import re
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

# Add lib/ to path for tracking module
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
from tracking import TrackingDB


# SQS configuration
QUEUE_NAME = "collagen-tracking-queue"
REGION = "us-east-1"
POLL_INTERVAL = 1  # seconds
MAX_MESSAGES = 10  # per poll

# S3 configuration
S3_BUCKET = "pauseai-collagen"

# Data directory
DATA_DIR = os.environ.get("COLLAGEN_DATA_DIR", "/mnt/efs")

# Logging
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)


def parse_tracking_path(path: str) -> dict:
    """
    Parse tracking URL path into components.

    Paths:
      /t/{campaign}/{uid}/{build_id}.jpg     → open event
      /t/{campaign}/{uid}/validate           → validate event
      /t/{campaign}/{uid}/subscribe          → subscribe event
      /t/{campaign}/{uid}/share/{platform}   → share event

    Returns:
        dict with keys: event_type, campaign, uid, build_id (if open event), platform (if share event)
        None if path doesn't match
    """
    # Open event
    match = re.match(r'/t/([^/]+)/([^/]+)/(.+)\.jpg$', path)
    if match:
        campaign, uid, build_id = match.groups()
        return {
            'event_type': 'open',
            'campaign': campaign,
            'uid': uid,
            'build_id': build_id
        }

    # Validate event
    match = re.match(r'/t/([^/]+)/([^/]+)/validate$', path)
    if match:
        campaign, uid = match.groups()
        return {
            'event_type': 'validate',
            'campaign': campaign,
            'uid': uid
        }

    # Subscribe event
    match = re.match(r'/t/([^/]+)/([^/]+)/subscribe$', path)
    if match:
        campaign, uid = match.groups()
        return {
            'event_type': 'subscribe',
            'campaign': campaign,
            'uid': uid
        }

    # Share event
    match = re.match(r'/t/([^/]+)/([^/]+)/share/([^/]+)$', path)
    if match:
        campaign, uid, platform = match.groups()
        return {
            'event_type': 'share',
            'campaign': campaign,
            'uid': uid,
            'platform': platform
        }

    return None


def handle_open_event(campaign: str, uid: str, build_id: str, event_time: 'datetime'):
    """Handle tracking pixel load event."""
    db = TrackingDB(campaign, DATA_DIR)
    user = db.get_user_by_uid(uid)

    if not user:
        logger.warning(f"OPEN: Unknown UID {uid} in campaign {campaign}")
        return

    updated = db.mark_opened(uid, event_time)
    if updated:
        logger.info(f"OPENED: {campaign}/{uid} (email={user['email']}, build={build_id})")
    else:
        logger.debug(f"OPENED (duplicate): {campaign}/{uid} (build={build_id})")


def handle_validate_event(campaign: str, uid: str, event_time: 'datetime'):
    """Handle validation (opt-out) event."""
    db = TrackingDB(campaign, DATA_DIR)
    user = db.get_user_by_uid(uid)

    if not user:
        logger.warning(f"VALIDATE: Unknown UID {uid} in campaign {campaign}")
        return

    updated = db.mark_validated(uid, event_time)
    if updated:
        logger.info(f"VALIDATED: {campaign}/{uid} (email={user['email']})")
    else:
        logger.debug(f"VALIDATED (duplicate): {campaign}/{uid}")


def handle_subscribe_event(campaign: str, uid: str, event_time: 'datetime'):
    """
    Handle subscription event.
    Records that user clicked subscribe link (intent to subscribe).
    User will complete actual subscription in their browser.
    """
    db = TrackingDB(campaign, DATA_DIR)
    user = db.get_user_by_uid(uid)

    if not user:
        logger.warning(f"SUBSCRIBE: Unknown UID {uid} in campaign {campaign}")
        return

    email = user['email']

    # Check if already subscribed
    if user.get('subscribed_at'):
        logger.debug(f"SUBSCRIBE (duplicate): {campaign}/{uid}")
        return

    # Mark as subscribed in our database (user clicked subscribe link)
    # Note: Actual Substack subscription happens in browser to avoid CloudFlare blocking
    db.mark_subscribed(uid, event_time)
    logger.info(f"SUBSCRIBE_INTENT: {campaign}/{uid} (email={email})")


def handle_share_event(campaign: str, uid: str, platform: str, event_time: 'datetime'):
    """
    Handle social share intent event with deduplication.
    Records when user clicked share link (redirected to social platform).
    Deduplicates: ignores repeat clicks within 60 seconds for same uid+platform.
    Uses SQS message timestamp (when queued) for accurate deduplication.
    Note: Does not confirm share was completed/posted.
    """
    db = TrackingDB(campaign, DATA_DIR)
    user = db.get_user_by_uid(uid)

    if not user:
        logger.warning(f"SHARE_INTENT: Unknown UID {uid} in campaign {campaign}")
        return

    email = user['email']

    # Check for recent duplicate (same uid+platform within last 60 seconds)
    # Use event_time (when message was queued) not processing time
    import sqlite3
    from datetime import datetime

    conn = sqlite3.connect(db.db_path)
    cursor = conn.execute('''
        SELECT shared_at FROM shares
        WHERE uid = ? AND platform = ?
        ORDER BY shared_at DESC LIMIT 1
    ''', (uid, platform))

    last_share = cursor.fetchone()
    if last_share:
        last_time = datetime.fromisoformat(last_share[0])
        time_diff = (event_time - last_time).total_seconds()
        if time_diff < 60:
            logger.info(f"SHARE_DUPLICATE: {campaign}/{uid} platform={platform} ({time_diff:.1f}s since last, ignored)")
            conn.close()
            return

    conn.close()

    # Record share intent with actual event time (from SQS message timestamp)
    db.record_share(uid, platform, event_time)
    logger.info(f"SHARE_INTENT: {campaign}/{uid} platform={platform} (email={email})")


def process_message(message: dict):
    """Process a single SQS message."""
    try:
        body = json.loads(message['Body'])
        path = body.get('path')

        if not path:
            logger.error(f"Message missing 'path' field: {body}")
            return

        # Extract message timestamp (when queued, not when processed)
        # SentTimestamp is in milliseconds since epoch
        attributes = message.get('Attributes', {})
        sent_timestamp_ms = attributes.get('SentTimestamp')

        if sent_timestamp_ms:
            from datetime import datetime, timezone
            event_time = datetime.fromtimestamp(int(sent_timestamp_ms) / 1000, tz=timezone.utc)
        else:
            # Fallback to now if timestamp missing (shouldn't happen)
            logger.warning("Message missing SentTimestamp, using current time")
            event_time = datetime.now(timezone.utc)

        # Parse path
        event = parse_tracking_path(path)
        if not event:
            logger.error(f"Invalid tracking path: {path}")
            return

        # Dispatch to handler
        event_type = event['event_type']
        campaign = event['campaign']
        uid = event['uid']

        if event_type == 'open':
            handle_open_event(campaign, uid, event['build_id'], event_time)
        elif event_type == 'validate':
            handle_validate_event(campaign, uid, event_time)
        elif event_type == 'subscribe':
            handle_subscribe_event(campaign, uid, event_time)
        elif event_type == 'share':
            handle_share_event(campaign, uid, event['platform'], event_time)

    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        raise  # Re-raise to prevent message deletion


def poll_queue(queue_url: str):
    """Poll SQS queue and process messages."""
    sqs = boto3.client('sqs', region_name=REGION)

    logger.info(f"Starting tracking worker (queue={queue_url})")

    while True:
        try:
            # Long polling (20s wait)
            response = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=MAX_MESSAGES,
                WaitTimeSeconds=20,
                AttributeNames=['All']
            )

            messages = response.get('Messages', [])
            if not messages:
                continue  # No messages, continue polling

            logger.debug(f"Received {len(messages)} messages")

            for message in messages:
                try:
                    process_message(message)

                    # Delete message on success
                    sqs.delete_message(
                        QueueUrl=queue_url,
                        ReceiptHandle=message['ReceiptHandle']
                    )
                except Exception as e:
                    logger.error(f"Failed to process message: {e}")
                    # Don't delete - let it retry after visibility timeout

        except KeyboardInterrupt:
            logger.info("Shutting down...")
            break
        except Exception as e:
            logger.error(f"Error polling queue: {e}", exc_info=True)
            time.sleep(POLL_INTERVAL)


def main():
    # Get queue URL
    sqs = boto3.client('sqs', region_name=REGION)

    try:
        response = sqs.get_queue_url(QueueName=QUEUE_NAME)
        queue_url = response['QueueUrl']
    except ClientError as e:
        logger.error(f"Failed to get queue URL: {e}")
        sys.exit(1)

    poll_queue(queue_url)


if __name__ == "__main__":
    main()
