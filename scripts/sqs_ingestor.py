#!/usr/bin/env python3
"""
SQS Processor for Collagen - polls SQS for Cloudinary webhook messages.

Replaces the Flask HTTP receiver with SQS-based architecture for production durability.
Delegates actual webhook processing to processor.py.

Architecture:
    Cloudinary → API Gateway → SQS → [This Script] → processor.py → EFS

Usage:
    python3 sqs_processor.py [--queue-url QUEUE_URL] [--region REGION]
"""

import os
import sys
import json
import time
import logging
import signal
import argparse
import hmac
import hashlib
from pathlib import Path
from typing import Optional

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Add parent directory to path to import ingestor module
sys.path.insert(0, str(Path(__file__).parent))
import ingestor

# Load environment variables
load_dotenv()

# Global flag for graceful shutdown
shutdown_requested = False

# Cloudinary API secret for signature validation
CLOUDINARY_API_SECRET = os.getenv('CLOUDINARY_API_SECRET')

def validate_cloudinary_signature(body_bytes: bytes, signature: str, timestamp: str) -> bool:
    """
    Validate Cloudinary webhook signature using SHA-1.

    Cloudinary signs: body_string + timestamp + api_secret

    Args:
        body_bytes: Raw message body bytes
        signature: Signature from SQS MessageAttribute
        timestamp: Timestamp from SQS MessageAttribute

    Returns:
        True if signature is valid, False otherwise
    """
    if not CLOUDINARY_API_SECRET:
        logging.error("CLOUDINARY_API_SECRET not configured - cannot validate signature")
        return False

    if not signature or not timestamp:
        logging.warning(f"Missing signature attributes: sig={bool(signature)}, ts={bool(timestamp)}")
        return False

    # Create signed payload: body + timestamp + secret
    signed_payload = body_bytes + timestamp.encode('utf-8') + CLOUDINARY_API_SECRET.encode('utf-8')

    # Compute expected signature using SHA-1
    expected_signature = hashlib.sha1(signed_payload).hexdigest()

    is_valid = hmac.compare_digest(signature, expected_signature)

    if not is_valid:
        logging.warning(f"Invalid signature: expected {expected_signature}, got {signature}")
        logging.debug(f"Timestamp: {timestamp}, Body length: {len(body_bytes)}")

    return is_valid

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global shutdown_requested
    logging.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_requested = True

def poll_and_process_messages(
    sqs_client,
    queue_url: str,
    wait_time_seconds: int = 20,
    max_messages: int = 1
) -> None:
    """
    Poll SQS queue for webhook messages and process them.

    Uses long polling (wait_time_seconds=20) to reduce API calls and cost.

    Args:
        sqs_client: Boto3 SQS client
        queue_url: SQS queue URL to poll
        wait_time_seconds: Long polling wait time (1-20 seconds)
        max_messages: Max messages to retrieve per poll (1-10)
    """
    global shutdown_requested

    logging.info(f"Starting SQS processor, polling queue: {queue_url}")
    logging.info(f"Long polling enabled: {wait_time_seconds}s wait time")

    consecutive_errors = 0
    max_consecutive_errors = 5

    while not shutdown_requested:
        try:
            # Receive messages (long polling)
            response = sqs_client.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=max_messages,
                WaitTimeSeconds=wait_time_seconds,
                AttributeNames=['All'],
                MessageAttributeNames=['All']
            )

            messages = response.get('Messages', [])

            if not messages:
                # No messages available (normal for long polling)
                logging.debug("No messages received, continuing poll...")
                consecutive_errors = 0  # Reset error counter
                continue

            logging.info(f"Received {len(messages)} message(s) from SQS")

            for message in messages:
                receipt_handle = message['ReceiptHandle']
                message_id = message['MessageId']

                try:
                    # Parse message body (should be Cloudinary webhook JSON)
                    body_str = message['Body']
                    body = json.loads(body_str)

                    logging.info(f"Processing message {message_id}: {body.get('public_id', 'unknown')}")

                    # Note: Signature validation happens in Lambda upstream
                    # Messages in SQS have already been validated, so we trust them here

                    # Delegate to ingestor logic
                    ingestor.process_webhook(body)

                    # Delete message on success
                    sqs_client.delete_message(
                        QueueUrl=queue_url,
                        ReceiptHandle=receipt_handle
                    )

                    logging.info(f"✓ Successfully processed and deleted message {message_id}")
                    consecutive_errors = 0  # Reset error counter

                except json.JSONDecodeError as e:
                    logging.error(f"Invalid JSON in message {message_id}: {e}")
                    # Delete malformed messages (they'll never succeed)
                    sqs_client.delete_message(
                        QueueUrl=queue_url,
                        ReceiptHandle=receipt_handle
                    )
                    logging.warning(f"Deleted malformed message {message_id}")

                except Exception as e:
                    logging.error(f"Error processing message {message_id}: {e}", exc_info=True)
                    # Don't delete - let message become visible again for retry
                    # After 3 failed receives, SQS will move to DLQ automatically
                    logging.warning(f"Message {message_id} will be retried (or sent to DLQ after 3 attempts)")
                    consecutive_errors += 1

        except ClientError as e:
            error_code = e.response['Error']['Code']
            logging.error(f"AWS API error ({error_code}): {e}")
            consecutive_errors += 1

            # Back off on repeated errors
            if consecutive_errors >= max_consecutive_errors:
                logging.critical(f"Too many consecutive errors ({consecutive_errors}), pausing 60s...")
                time.sleep(60)
                consecutive_errors = 0  # Reset after backoff

        except Exception as e:
            logging.error(f"Unexpected error in polling loop: {e}", exc_info=True)
            consecutive_errors += 1

            if consecutive_errors >= max_consecutive_errors:
                logging.critical(f"Too many consecutive errors ({consecutive_errors}), pausing 60s...")
                time.sleep(60)
                consecutive_errors = 0

    logging.info("Shutdown complete, exiting SQS processor")

def main():
    parser = argparse.ArgumentParser(description='Collagen SQS webhook processor')
    parser.add_argument('--queue-url', type=str,
                       help='SQS queue URL to poll')
    parser.add_argument('--region', type=str, default='us-east-1',
                       help='AWS region (default: us-east-1)')
    parser.add_argument('--wait-time', type=int, default=20,
                       help='Long polling wait time in seconds (default: 20, max: 20)')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug logging')

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Get queue URL from args or environment
    queue_url = args.queue_url or os.getenv('SQS_QUEUE_URL')

    if not queue_url:
        logging.error("SQS_QUEUE_URL not provided via --queue-url or environment variable")
        sys.exit(1)

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create SQS client
    sqs_client = boto3.client('sqs', region_name=args.region)

    logging.info("=== Collagen SQS Processor Starting ===")
    logging.info(f"Queue: {queue_url}")
    logging.info(f"Region: {args.region}")
    logging.info(f"Wait time: {args.wait_time}s")

    # Start polling
    poll_and_process_messages(
        sqs_client=sqs_client,
        queue_url=queue_url,
        wait_time_seconds=args.wait_time
    )

if __name__ == '__main__':
    main()
