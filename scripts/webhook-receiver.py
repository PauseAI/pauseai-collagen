#!/usr/bin/env python3
"""
Webhook receiver for Collagen - receives Cloudinary webhooks and processes images.

Validates webhook signatures, logs requests, and delegates image processing.

Usage:
    python3 webhook-receiver.py [--port PORT] [--log-dir LOG_DIR]
"""

from flask import Flask, request, jsonify
import json
import logging
import hmac
import hashlib
import os
import sys
from datetime import datetime
from pathlib import Path
import argparse
from dotenv import load_dotenv

# Add parent directory to path to import ingestor
sys.path.insert(0, str(Path(__file__).parent.parent))
import ingestor

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configuration (can be overridden via command-line args)
LOG_DIR = Path('/mnt/efs/dev/logs')
PORT = 80

# Cloudinary API secret for signature validation
CLOUDINARY_API_SECRET = os.getenv('CLOUDINARY_API_SECRET')


def validate_cloudinary_signature(body_bytes: bytes, signature: str, timestamp: str) -> bool:
    """
    Validate Cloudinary webhook signature using SHA-1.

    Cloudinary signs: body_string + timestamp + api_secret

    Args:
        body_bytes: Raw request body bytes
        signature: X-Cld-Signature header value
        timestamp: X-Cld-Timestamp header value

    Returns:
        True if signature is valid, False otherwise
    """
    if not CLOUDINARY_API_SECRET:
        app.logger.error("CLOUDINARY_API_SECRET not configured - cannot validate signature")
        return False

    if not signature or not timestamp:
        app.logger.warning(f"Missing signature headers: sig={bool(signature)}, ts={bool(timestamp)}")
        return False

    # Create signed payload: body + timestamp + secret
    signed_payload = body_bytes + timestamp.encode('utf-8') + CLOUDINARY_API_SECRET.encode('utf-8')

    # Compute expected signature using SHA-1
    expected_signature = hashlib.sha1(signed_payload).hexdigest()

    is_valid = hmac.compare_digest(signature, expected_signature)

    if not is_valid:
        app.logger.warning(f"Invalid signature: expected {expected_signature}, got {signature}")
        app.logger.debug(f"Timestamp: {timestamp}, Body length: {len(body_bytes)}")

    return is_valid


@app.route('/webhook/<path:webhook_type>', methods=['POST'])
def webhook_handler(webhook_type):
    """
    Receives webhook notifications from Cloudinary.

    Validates signature, logs request, and processes moderation webhooks.
    webhook_type allows us to distinguish different webhook sources.
    """
    # Validate Cloudinary signature
    signature = request.headers.get('X-Cld-Signature', '')
    cld_timestamp = request.headers.get('X-Cld-Timestamp', '')
    body_bytes = request.get_data()

    if not validate_cloudinary_signature(body_bytes, signature, cld_timestamp):
        app.logger.error("Webhook signature validation failed - rejecting")
        return jsonify({'error': 'Invalid signature'}), 401

    # Record receipt timestamp
    timestamp = datetime.utcnow().isoformat()

    # Extract request data
    headers = dict(request.headers)

    # Try to parse JSON body, fallback to raw data
    try:
        body = request.get_json(force=True) if request.data else {}
    except Exception as e:
        body = {
            'raw_data': request.data.decode('utf-8', errors='replace'),
            'parse_error': str(e)
        }

    # Log to console
    app.logger.info("=== WEBHOOK RECEIVED ===")
    app.logger.info(f"Endpoint: /webhook/{webhook_type}")
    app.logger.info(f"Timestamp: {timestamp}")
    app.logger.info(f"Notification Type: {body.get('notification_type', 'unknown')}")
    app.logger.info(f"Public ID: {body.get('public_id', 'N/A')}")

    # Save full details to file (legacy logging)
    log_data = {
        'timestamp': timestamp,
        'webhook_endpoint': webhook_type,
        'headers': headers,
        'body': body,
        'url': request.url,
        'method': request.method,
        'remote_addr': request.remote_addr
    }

    # Create log filename from timestamp (safe for filesystem)
    safe_timestamp = timestamp.replace(':', '-').replace('.', '-')
    log_file = LOG_DIR / f'webhook-{webhook_type}-{safe_timestamp}.json'

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(log_file, 'w') as f:
            json.dump(log_data, f, indent=2)
        app.logger.info(f"Saved to: {log_file}")
    except Exception as e:
        app.logger.error(f"Failed to save webhook: {e}")

    # Process moderation webhooks
    if body.get('notification_type') == 'moderation':
        asset_folder = body.get('asset_folder', 'unknown')

        # Log webhook to campaign-specific directory
        ingestor.log_webhook_to_file(body, asset_folder)

        # Ingest image
        try:
            ingestor.process_webhook(body)
        except Exception as e:
            app.logger.error(f"Ingestor failed: {e}", exc_info=True)
            # Return 200 anyway - we don't want Cloudinary to retry on our bugs

    # Return success response
    return jsonify({'status': 'received', 'timestamp': timestamp}), 200

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'service': 'collagen-webhook-receiver',
        'timestamp': datetime.utcnow().isoformat()
    }), 200

@app.route('/', methods=['GET'])
def index():
    """Root endpoint with service info."""
    log_count = len(list(LOG_DIR.glob('webhook-*.json'))) if LOG_DIR.exists() else 0

    return jsonify({
        'service': 'Collagen Webhook Receiver',
        'endpoints': {
            '/webhook/<type>': 'POST - Receives Cloudinary webhooks (type: global, moderation, etc.)',
            '/health': 'GET - Health check',
            '/': 'GET - This info page'
        },
        'log_directory': str(LOG_DIR),
        'webhooks_received': log_count,
        'timestamp': datetime.utcnow().isoformat()
    }), 200

def main():
    global LOG_DIR, PORT

    parser = argparse.ArgumentParser(description='Cloudinary webhook receiver')
    parser.add_argument('--port', type=int, default=PORT,
                       help=f'Port to listen on (default: {PORT})')
    parser.add_argument('--log-dir', type=Path, default=LOG_DIR,
                       help=f'Directory to save webhook logs (default: {LOG_DIR})')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug mode')

    args = parser.parse_args()

    LOG_DIR = args.log_dir
    PORT = args.port

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    app.logger.info(f"Starting Collagen webhook receiver")
    app.logger.info(f"Listening on port: {PORT}")
    app.logger.info(f"Logging to: {LOG_DIR}")

    # Run Flask app
    # Note: Using 0.0.0.0 makes it accessible from external IPs (needed for Cloudinary)
    app.run(host='0.0.0.0', port=PORT, debug=args.debug)

if __name__ == '__main__':
    main()
