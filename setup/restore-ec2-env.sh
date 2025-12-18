#!/bin/bash
# Restore/recreate .env file on EC2 instance
# Run this on a fresh EC2 or when .env is missing/corrupted
#
# Usage: ./setup/restore-ec2-env.sh
#
# This script:
# 1. Pulls SQS queue URLs from AWS (auto-discovered)
# 2. Prompts for secrets (Cloudinary, SMTP)
# 3. Generates ~/collagen/.env on the EC2

set -e

# Load local config for SSH details
if [ ! -f .aws-config ]; then
    echo "ERROR: .aws-config not found. Run from pauseai-collagen directory."
    exit 1
fi

source .aws-config

echo "=== Restore EC2 .env File ==="
echo "Instance: $INSTANCE_ID ($PUBLIC_IP)"
echo ""

# Test SSH connectivity
echo "[1/4] Testing SSH connectivity..."
if ! ssh -i ~/.ssh/${KEY_NAME}.pem -o ConnectTimeout=5 ubuntu@${PUBLIC_IP} "echo 'SSH OK'" 2>/dev/null; then
    echo "ERROR: Cannot connect to EC2 instance"
    echo "Check: Security group allows your IP, instance is running"
    exit 1
fi

# Discover SQS queues from AWS
echo "[2/4] Discovering SQS queues from AWS..."
WEBHOOK_QUEUE=$(aws sqs get-queue-url --queue-name collagen-webhooks --region $REGION --query 'QueueUrl' --output text 2>/dev/null || echo "")
TRACKING_QUEUE=$(aws sqs get-queue-url --queue-name collagen-tracking-queue --region $REGION --query 'QueueUrl' --output text 2>/dev/null || echo "")

if [ -z "$WEBHOOK_QUEUE" ]; then
    echo "WARNING: collagen-webhooks queue not found in AWS"
    echo "Using value from .aws-config: $SQS_WEBHOOK_QUEUE_URL"
    WEBHOOK_QUEUE="$SQS_WEBHOOK_QUEUE_URL"
fi

if [ -z "$TRACKING_QUEUE" ]; then
    echo "WARNING: collagen-tracking-queue not found"
    TRACKING_QUEUE=""
fi

echo "  Webhook queue: $WEBHOOK_QUEUE"
echo "  Tracking queue: $TRACKING_QUEUE"

# Prompt for secrets
echo ""
echo "[3/4] Gathering secrets..."
echo "(Get these from Psono or your password manager)"
echo ""

# Check if we can read existing values from EC2
EXISTING_ENV=$(ssh -i ~/.ssh/${KEY_NAME}.pem ubuntu@${PUBLIC_IP} "cat ~/collagen/.env 2>/dev/null" || echo "")

# Extract existing values if present
EXISTING_CLOUD_NAME=$(echo "$EXISTING_ENV" | grep "^CLOUDINARY_CLOUD_NAME=" | cut -d= -f2 | tr -d '"' || echo "")
EXISTING_API_KEY=$(echo "$EXISTING_ENV" | grep "^CLOUDINARY_API_KEY=" | cut -d= -f2 | tr -d '"' || echo "")
EXISTING_API_SECRET=$(echo "$EXISTING_ENV" | grep "^CLOUDINARY_API_SECRET=" | cut -d= -f2 | tr -d '"' || echo "")
EXISTING_SMTP_USER=$(echo "$EXISTING_ENV" | grep "^SAYNO_SMTP_USER=" | cut -d= -f2 | tr -d '"' || echo "")
EXISTING_SMTP_PASS=$(echo "$EXISTING_ENV" | grep "^SAYNO_SMTP_PASSWORD=" | cut -d= -f2 | tr -d '"' || echo "")

# Use defaults from config.py or existing
DEFAULT_CLOUD_NAME="${EXISTING_CLOUD_NAME:-dyjlw1syg}"
DEFAULT_API_KEY="${EXISTING_API_KEY:-779717836612829}"

read -p "Cloudinary cloud name [$DEFAULT_CLOUD_NAME]: " CLOUD_NAME
CLOUD_NAME="${CLOUD_NAME:-$DEFAULT_CLOUD_NAME}"

read -p "Cloudinary API key [$DEFAULT_API_KEY]: " API_KEY
API_KEY="${API_KEY:-$DEFAULT_API_KEY}"

if [ -n "$EXISTING_API_SECRET" ]; then
    read -p "Cloudinary API secret [keep existing]: " API_SECRET
    API_SECRET="${API_SECRET:-$EXISTING_API_SECRET}"
else
    read -p "Cloudinary API secret (from Psono): " API_SECRET
    if [ -z "$API_SECRET" ]; then
        echo "ERROR: Cloudinary API secret is required"
        exit 1
    fi
fi

DEFAULT_SMTP_USER="${EXISTING_SMTP_USER:-sayno@pauseai.info}"
read -p "SMTP user [$DEFAULT_SMTP_USER]: " SMTP_USER
SMTP_USER="${SMTP_USER:-$DEFAULT_SMTP_USER}"

if [ -n "$EXISTING_SMTP_PASS" ]; then
    read -p "SMTP password [keep existing]: " SMTP_PASS
    SMTP_PASS="${SMTP_PASS:-$EXISTING_SMTP_PASS}"
else
    read -p "SMTP password (Google app password from Psono): " SMTP_PASS
    if [ -z "$SMTP_PASS" ]; then
        echo "ERROR: SMTP password is required"
        exit 1
    fi
fi

# Generate and upload .env
echo ""
echo "[4/4] Generating .env on EC2..."

ssh -i ~/.ssh/${KEY_NAME}.pem ubuntu@${PUBLIC_IP} << ENDSSH
cat > ~/collagen/.env << 'ENVFILE'
# Cloudinary credentials
CLOUDINARY_CLOUD_NAME=$CLOUD_NAME
CLOUDINARY_API_KEY=$API_KEY
CLOUDINARY_API_SECRET=$API_SECRET

# AWS SQS Queues
SQS_WEBHOOK_QUEUE_URL=$WEBHOOK_QUEUE
SQS_TRACKING_QUEUE_URL=$TRACKING_QUEUE

# SMTP for Email Sending
SAYNO_SMTP_USER=$SMTP_USER
SAYNO_SMTP_PASSWORD="$SMTP_PASS"
ENVFILE

echo "Created ~/collagen/.env"
ENDSSH

echo ""
echo "=== Restore Complete ==="
echo ""
echo "Next steps:"
echo "1. Restart services: sudo systemctl restart collagen-ingestor collagen-tracking-worker"
echo "2. Check status: sudo systemctl status collagen-ingestor"
echo "3. Watch logs: sudo journalctl -u collagen-ingestor -f"
