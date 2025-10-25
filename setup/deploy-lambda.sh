#!/bin/bash
# Deploy tracking router Lambda function

set -e

FUNCTION_NAME="collagen-tracking-router"
REGION="us-east-1"
ROLE_NAME="collagen-lambda-role"

echo "=== Deploying Lambda Function: ${FUNCTION_NAME} ==="
echo ""

# 1. Create IAM role for Lambda (if not exists)
echo "1. Creating IAM role for Lambda"
ROLE_ARN=$(aws iam get-role --role-name "${ROLE_NAME}" --query 'Role.Arn' --output text 2>/dev/null || true)

if [ -z "$ROLE_ARN" ]; then
    echo "   Creating role..."

    # Trust policy
    cat > /tmp/lambda-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

    aws iam create-role \
        --role-name "${ROLE_NAME}" \
        --assume-role-policy-document file:///tmp/lambda-trust-policy.json \
        --description "Role for Collagen tracking router Lambda"

    # Attach policies
    aws iam attach-role-policy \
        --role-name "${ROLE_NAME}" \
        --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"

    # Create inline policy for SQS access
    cat > /tmp/lambda-sqs-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "sqs:GetQueueUrl",
        "sqs:SendMessage"
      ],
      "Resource": "arn:aws:sqs:${REGION}:*:collagen-tracking-queue"
    }
  ]
}
EOF

    aws iam put-role-policy \
        --role-name "${ROLE_NAME}" \
        --policy-name "SQSAccess" \
        --policy-document file:///tmp/lambda-sqs-policy.json

    ROLE_ARN=$(aws iam get-role --role-name "${ROLE_NAME}" --query 'Role.Arn' --output text)

    echo "   ✓ Role created: ${ROLE_ARN}"
    echo "   Waiting 10s for IAM propagation..."
    sleep 10
else
    echo "   Role already exists: ${ROLE_ARN}"

    # Ensure SQS policy exists (in case role was created before SQS)
    ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text)
    cat > /tmp/lambda-sqs-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "sqs:GetQueueUrl",
        "sqs:SendMessage"
      ],
      "Resource": "arn:aws:sqs:${REGION}:${ACCOUNT_ID}:collagen-tracking-queue"
    }
  ]
}
EOF

    aws iam put-role-policy \
        --role-name "${ROLE_NAME}" \
        --policy-name "SQSAccess" \
        --policy-document file:///tmp/lambda-sqs-policy.json

    echo "   ✓ SQS policy updated"
fi

# 2. Package Lambda function
echo "2. Packaging Lambda function"
cd lambda
zip -q tracking_router.zip tracking_router.py
echo "   ✓ Created tracking_router.zip"

# 3. Create or update Lambda function
echo "3. Deploying Lambda function"
FUNCTION_EXISTS=$(aws lambda get-function --function-name "${FUNCTION_NAME}" --region "${REGION}" 2>/dev/null || true)

if [ -z "$FUNCTION_EXISTS" ]; then
    echo "   Creating new function..."
    aws lambda create-function \
        --function-name "${FUNCTION_NAME}" \
        --runtime python3.10 \
        --role "${ROLE_ARN}" \
        --handler tracking_router.lambda_handler \
        --zip-file fileb://tracking_router.zip \
        --timeout 10 \
        --memory-size 128 \
        --environment "Variables={QUEUE_NAME=collagen-tracking-queue,S3_BUCKET=pauseai-collagen}" \
        --region "${REGION}"
    echo "   ✓ Function created"
else
    echo "   Updating existing function..."
    aws lambda update-function-code \
        --function-name "${FUNCTION_NAME}" \
        --zip-file fileb://tracking_router.zip \
        --region "${REGION}"

    aws lambda update-function-configuration \
        --function-name "${FUNCTION_NAME}" \
        --environment "Variables={QUEUE_NAME=collagen-tracking-queue,S3_BUCKET=pauseai-collagen}" \
        --region "${REGION}"
    echo "   ✓ Function updated"
fi

# Clean up
rm tracking_router.zip
cd ..

# Get function ARN
FUNCTION_ARN=$(aws lambda get-function --function-name "${FUNCTION_NAME}" --region "${REGION}" --query 'Configuration.FunctionArn' --output text)

echo ""
echo "=== Lambda Deployment Complete ==="
echo ""
echo "Function ARN: ${FUNCTION_ARN}"
echo ""
echo "Next: Create API Gateway and connect to this Lambda"
