#!/usr/bin/env python3
"""
Simple webhook receiver for testing Cloudinary notifications.

Logs all incoming POST requests to /webhook/moderation to files in /mnt/efs/dev/logs/
for inspection and analysis.

Usage:
    python3 webhook-receiver.py [--port PORT] [--log-dir LOG_DIR]
"""

from flask import Flask, request, jsonify
import json
import logging
from datetime import datetime
from pathlib import Path
import argparse

app = Flask(__name__)

# Configuration (can be overridden via command-line args)
LOG_DIR = Path('/mnt/efs/dev/logs')
PORT = 80

@app.route('/webhook/<path:webhook_type>', methods=['POST'])
def webhook_handler(webhook_type):
    """
    Receives webhook notifications from Cloudinary.

    Logs the full request (headers + body) to a timestamped JSON file.
    webhook_type allows us to distinguish different webhook sources.
    """
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

    # Save full details to file
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
