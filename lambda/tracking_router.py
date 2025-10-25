"""
Lambda function for tracking URL routing.

Routes:
  /t/{campaign}/{uid}/{build_id}.jpg  → Enqueue SQS + redirect to S3 image
  /t/{campaign}/{uid}/validate        → Enqueue SQS + redirect to pauseai.info/{campaign}?collagen_uid_{campaign}={uid}
  /t/{campaign}/{uid}/subscribe       → Enqueue SQS + redirect to pauseai.info/join?collagen_uid_{campaign}={uid}
"""

import json
import os
import re
from urllib.parse import quote

import boto3

# Configuration
QUEUE_NAME = os.environ.get('QUEUE_NAME', 'collagen-tracking-queue')
REGION = os.environ.get('AWS_REGION', 'us-east-1')
S3_BUCKET = os.environ.get('S3_BUCKET', 'pauseai-collagen')

# Initialize SQS client
sqs = boto3.client('sqs', region_name=REGION)

# Get queue URL (cached for Lambda container reuse)
queue_url = None


def get_queue_url():
    """Get SQS queue URL (cached)."""
    global queue_url
    if queue_url is None:
        response = sqs.get_queue_url(QueueName=QUEUE_NAME)
        queue_url = response['QueueUrl']
    return queue_url


def enqueue_tracking_event(path: str):
    """Enqueue tracking event to SQS."""
    message_body = json.dumps({
        'path': path,
        'timestamp': None  # SQS adds timestamp
    })

    sqs.send_message(
        QueueUrl=get_queue_url(),
        MessageBody=message_body
    )


def parse_path(path: str) -> dict:
    """
    Parse tracking URL path.

    Returns dict with: event_type, campaign, uid, build_id (if open)
    Returns None if invalid path
    """
    # Open event: /t/{campaign}/{uid}/{build_id}.jpg
    match = re.match(r'/t/([^/]+)/([^/]+)/(.+)\.jpg$', path)
    if match:
        campaign, uid, build_id = match.groups()
        return {
            'event_type': 'open',
            'campaign': campaign,
            'uid': uid,
            'build_id': build_id
        }

    # Validate event: /t/{campaign}/{uid}/validate
    match = re.match(r'/t/([^/]+)/([^/]+)/validate$', path)
    if match:
        campaign, uid = match.groups()
        return {
            'event_type': 'validate',
            'campaign': campaign,
            'uid': uid
        }

    # Subscribe event: /t/{campaign}/{uid}/subscribe
    match = re.match(r'/t/([^/]+)/([^/]+)/subscribe$', path)
    if match:
        campaign, uid = match.groups()
        return {
            'event_type': 'subscribe',
            'campaign': campaign,
            'uid': uid
        }

    return None


def lambda_handler(event, context):
    """
    Lambda handler for API Gateway proxy integration.

    Returns 302 redirect and enqueues tracking event to SQS.
    """
    # Extract path from API Gateway event (HTTP API v2 uses 'rawPath')
    path = event.get('rawPath') or event.get('path', '')

    print(f"Tracking request: {path}")

    # Parse path
    parsed = parse_path(path)
    if not parsed:
        return {
            'statusCode': 404,
            'body': json.dumps({'error': 'Not found'})
        }

    event_type = parsed['event_type']
    campaign = parsed['campaign']
    uid = parsed['uid']

    # Enqueue to SQS (async tracking)
    try:
        enqueue_tracking_event(path)
        print(f"Enqueued: {event_type} for {campaign}/{uid}")
    except Exception as e:
        print(f"ERROR: Failed to enqueue: {e}")
        # Continue with redirect even if enqueue fails

    # Generate redirect URL
    if event_type == 'open':
        # Redirect to S3 image
        build_id = parsed['build_id']
        redirect_url = f"https://s3.amazonaws.com/{S3_BUCKET}/{campaign}/{build_id}/1024.jpg"

    elif event_type == 'validate':
        # Map test_prototype to sayno for website display (dev convention)
        display_campaign = 'sayno' if campaign == 'test_prototype' else campaign
        redirect_url = f"https://pauseai.info/{display_campaign}?collagen_uid_{campaign}={uid}"

    elif event_type == 'subscribe':
        # Redirect to join page with campaign-aware collagen_uid
        redirect_url = f"https://pauseai.info/join?collagen_uid_{campaign}={uid}"

    else:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Invalid event type'})
        }

    # Return 302 redirect
    return {
        'statusCode': 302,
        'headers': {
            'Location': redirect_url,
            'Cache-Control': 'no-cache, no-store, must-revalidate'
        },
        'body': ''
    }
