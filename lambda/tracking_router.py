"""
Lambda function for tracking URL routing.

Routes:
  /t/{campaign}/{uid}/{build_id}.jpg     → Enqueue SQS + redirect to S3 image
  /t/{campaign}/{uid}/validate           → Enqueue SQS + redirect to pauseai.info/{campaign}?collagen_uid_{campaign}={uid}
  /t/{campaign}/{uid}/subscribe          → Enqueue SQS + redirect to pauseai.info/join?collagen_uid_{campaign}={uid}
  /t/{campaign}/{uid}/share/{platform}   → Enqueue SQS + redirect to social network share URL
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

# Social share configuration
SHARE_CONFIG = {
    'test_prototype': {
        'share_url_base': 'https://pauseai.info/sayno',
        'share_title': 'Test me in calling for a pause on superintelligence development',
        'hashtags': 'AISafety,PauseAI',
        'twitter_via': 'PauseAI'
    },
    'sayno': {
        'share_url_base': 'https://pauseai.info/sayno',
        'share_title': 'Join me in calling for a pause on superintelligence development',
        'hashtags': 'AISafety,PauseAI',
        'twitter_via': 'PauseAI'
    }
}

# Allowed share platforms (security: prevent open redirect)
ALLOWED_PLATFORMS = ['facebook', 'twitter', 'whatsapp', 'linkedin', 'reddit']

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


def generate_share_url(platform: str, share_url: str, config: dict) -> str:
    """
    Generate platform-specific social share URL.

    Args:
        platform: Social platform (facebook, twitter, whatsapp, linkedin, reddit)
        share_url: URL to share (pauseai.info with ?ref=uid)
        config: Campaign share configuration (title, hashtags, etc.)

    Returns:
        Social network share URL with pre-populated content
    """
    title = config['share_title']

    if platform == 'facebook':
        return f"https://www.facebook.com/sharer.php?u={quote(share_url)}"

    elif platform == 'twitter':
        hashtags = config['hashtags']
        via = config['twitter_via']
        return f"https://twitter.com/intent/tweet?url={quote(share_url)}&text={quote(title)}&hashtags={hashtags}&via={via}"

    elif platform == 'whatsapp':
        text = f"{title} {share_url}"
        return f"https://api.whatsapp.com/send?text={quote(text)}"

    elif platform == 'linkedin':
        return f"https://www.linkedin.com/sharing/share-offsite/?url={quote(share_url)}"

    elif platform == 'reddit':
        return f"https://reddit.com/submit?url={quote(share_url)}&title={quote(title)}"

    else:
        raise ValueError(f"Unsupported platform: {platform}")


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

    # Share event: /t/{campaign}/{uid}/share/{platform}
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
        redirect_url = f"https://pauseai.info/{display_campaign}?collagen_uid_{display_campaign}={uid}"

    elif event_type == 'subscribe':
        # Map test_prototype to sayno for website display (dev convention)
        display_campaign = 'sayno' if campaign == 'test_prototype' else campaign
        email = (event.get('queryStringParameters') or {}).get('email', '')

        # Redirect to join page with UID and email
        redirect_url = f"https://pauseai.info/join?collagen_uid_{display_campaign}={uid}&subscribe-email={quote(email)}"

    elif event_type == 'share':
        # Validate platform
        platform = parsed['platform']
        if platform not in ALLOWED_PLATFORMS:
            print(f"ERROR: Invalid platform: {platform}")
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Invalid platform'})
            }

        # Get campaign config
        config = SHARE_CONFIG.get(campaign)
        if not config:
            print(f"ERROR: Invalid campaign: {campaign}")
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Invalid campaign'})
            }

        # Generate share URL with ref parameter
        share_url = f"{config['share_url_base']}?ref={uid}"

        # Generate platform-specific social share URL
        redirect_url = generate_share_url(platform, share_url, config)

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
