#!/bin/bash
# Phase 3 Infrastructure Setup: Email Tracking & Notification System
# Creates: S3 bucket, SQS queue, API Gateway, Lambda functions

set -e

REGION="us-east-1"
BUCKET_NAME="pauseai-collagen"
QUEUE_NAME="collagen-tracking-queue"

echo "=== Phase 3 Infrastructure Setup ==="
echo ""

# 1. Create S3 bucket for collage images
echo "1. Creating S3 bucket: ${BUCKET_NAME}"
if aws s3 ls "s3://${BUCKET_NAME}" 2>/dev/null; then
    echo "   Bucket already exists"
else
    aws s3 mb "s3://${BUCKET_NAME}" --region "${REGION}"
    echo "   ✓ Bucket created"
fi

# 2. Apply public-read policy
echo "2. Applying public-read policy to bucket"
aws s3api put-bucket-policy \
    --bucket "${BUCKET_NAME}" \
    --policy file://setup/s3-bucket-policy.json
echo "   ✓ Policy applied"

# 3. Enable S3 versioning (optional, for safety)
echo "3. Enabling versioning on bucket"
aws s3api put-bucket-versioning \
    --bucket "${BUCKET_NAME}" \
    --versioning-configuration Status=Enabled
echo "   ✓ Versioning enabled"

# 4. Create SQS queue for tracking events
echo "4. Creating SQS queue: ${QUEUE_NAME}"
QUEUE_URL=$(aws sqs create-queue \
    --queue-name "${QUEUE_NAME}" \
    --attributes VisibilityTimeout=60,MessageRetentionPeriod=1209600 \
    --region "${REGION}" \
    --output text \
    --query 'QueueUrl' 2>/dev/null || true)

if [ -z "$QUEUE_URL" ]; then
    # Queue might already exist
    QUEUE_URL=$(aws sqs get-queue-url \
        --queue-name "${QUEUE_NAME}" \
        --region "${REGION}" \
        --output text \
        --query 'QueueUrl')
    echo "   Queue already exists"
else
    echo "   ✓ Queue created"
fi

echo "   Queue URL: ${QUEUE_URL}"

# Get queue ARN for later use
QUEUE_ARN=$(aws sqs get-queue-attributes \
    --queue-url "${QUEUE_URL}" \
    --attribute-names QueueArn \
    --region "${REGION}" \
    --output text \
    --query 'Attributes.QueueArn')

echo "   Queue ARN: ${QUEUE_ARN}"

echo ""
echo "=== Phase 3 Infrastructure Complete ==="
echo ""
echo "Next steps:"
echo "  - Create Lambda function for API Gateway routing"
echo "  - Set up API Gateway with custom domain (collagen.pauseai.info)"
echo "  - Deploy EC2 worker script to process SQS messages"
echo "  - Configure DNS for collagen.pauseai.info"
