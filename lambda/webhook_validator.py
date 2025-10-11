"""
Lambda function to validate Cloudinary webhook signatures and forward to SQS.

Architecture:
    Cloudinary → API Gateway → [This Lambda] → SQS
                                    ↓
                            Validates signature
                            Rejects if invalid
"""

import json
import os
import hmac
import hashlib
import boto3
from base64 import b64decode

sqs = boto3.client('sqs')
QUEUE_URL = os.environ['SQS_QUEUE_URL']
CLOUDINARY_API_SECRET = os.environ['CLOUDINARY_API_SECRET']

def validate_signature(body_bytes: bytes, signature: str, timestamp: str) -> bool:
    """Validate Cloudinary webhook signature using SHA-1."""

    if not signature or not timestamp:
        return False

    # Cloudinary signs: body + timestamp + api_secret
    signed_payload = body_bytes + timestamp.encode('utf-8') + CLOUDINARY_API_SECRET.encode('utf-8')
    expected_signature = hashlib.sha1(signed_payload).hexdigest()

    return hmac.compare_digest(signature, expected_signature)

def lambda_handler(event, context):
    """
    Validate Cloudinary webhook and forward to SQS.

    Returns 401 if signature invalid, 200 if queued successfully.
    """

    # Extract body and headers
    body = event.get('body', '')
    headers = event.get('headers', {})

    # Get signature headers (case-insensitive)
    signature = headers.get('x-cld-signature') or headers.get('X-Cld-Signature', '')
    timestamp = headers.get('x-cld-timestamp') or headers.get('X-Cld-Timestamp', '')

    # Decode body if base64 encoded
    is_base64 = event.get('isBase64Encoded', False)
    if is_base64:
        body_bytes = b64decode(body)
        body_str = body_bytes.decode('utf-8')
    else:
        body_str = body
        body_bytes = body.encode('utf-8')

    # Validate signature
    if not validate_signature(body_bytes, signature, timestamp):
        print(f"Invalid signature - rejecting webhook")
        return {
            'statusCode': 401,
            'body': json.dumps({'error': 'Invalid signature'})
        }

    # Parse body to extract campaign from public_id
    try:
        webhook_data = json.loads(body_str)
        public_id = webhook_data.get('public_id', '')
        campaign = public_id.split('/')[0] if '/' in public_id else 'unknown'
    except Exception as e:
        print(f"Failed to parse webhook body: {e}")
        campaign = 'unknown'

    # Send to SQS with MessageAttributes
    try:
        sqs.send_message(
            QueueUrl=QUEUE_URL,
            MessageBody=body_str,
            MessageAttributes={
                'signature': {'StringValue': signature, 'DataType': 'String'},
                'timestamp': {'StringValue': timestamp, 'DataType': 'String'},
                'campaign': {'StringValue': campaign, 'DataType': 'String'}
            }
        )

        print(f"✓ Validated and queued webhook for {public_id} (campaign: {campaign})")

        return {
            'statusCode': 200,
            'body': json.dumps({'status': 'queued'})
        }

    except Exception as e:
        print(f"Failed to queue message: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal error'})
        }
