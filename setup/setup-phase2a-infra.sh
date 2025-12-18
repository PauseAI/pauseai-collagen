#!/bin/bash
set -e

# Collagen Phase 2A Infrastructure Setup Script
# Sets up SQS, Lambda validator, API Gateway (REST v1), IAM roles, and AWS Backup for production webhook handling

REGION="us-east-1"
SQS_DLQ_NAME="collagen-webhooks-dlq"
SQS_QUEUE_NAME="collagen-webhooks"
API_NAME="collagen-webhook-api"

# Load existing config if available
if [ -f .aws-config ]; then
    source .aws-config
    echo "Loaded configuration from .aws-config"
fi

echo "=== Collagen Phase 2A Infrastructure Setup ==="
echo "Region: $REGION"
echo ""

# Create SQS Dead Letter Queue
echo "Creating SQS dead letter queue..."
DLQ_URL=$(aws sqs get-queue-url --queue-name "$SQS_DLQ_NAME" --region "$REGION" --query 'QueueUrl' --output text 2>/dev/null || echo "")

if [ -z "$DLQ_URL" ]; then
    DLQ_URL=$(aws sqs create-queue \
        --queue-name "$SQS_DLQ_NAME" \
        --region "$REGION" \
        --attributes '{
            "MessageRetentionPeriod": "1209600"
        }' \
        --query 'QueueUrl' \
        --output text)

    echo "Created SQS DLQ: $DLQ_URL (14-day retention)"
else
    echo "SQS DLQ already exists: $DLQ_URL"
fi

# Get DLQ ARN
DLQ_ARN=$(aws sqs get-queue-attributes \
    --queue-url "$DLQ_URL" \
    --attribute-names QueueArn \
    --region "$REGION" \
    --query 'Attributes.QueueArn' \
    --output text)

echo "DLQ ARN: $DLQ_ARN"

# Create SQS Main Queue with DLQ
echo "Creating SQS main queue..."
QUEUE_URL=$(aws sqs get-queue-url --queue-name "$SQS_QUEUE_NAME" --region "$REGION" --query 'QueueUrl' --output text 2>/dev/null || echo "")

if [ -z "$QUEUE_URL" ]; then
    QUEUE_URL=$(aws sqs create-queue \
        --queue-name "$SQS_QUEUE_NAME" \
        --region "$REGION" \
        --attributes "{
            \"MessageRetentionPeriod\": \"1209600\",
            \"VisibilityTimeout\": \"300\",
            \"RedrivePolicy\": \"{\\\"deadLetterTargetArn\\\":\\\"$DLQ_ARN\\\",\\\"maxReceiveCount\\\":3}\"
        }" \
        --query 'QueueUrl' \
        --output text)

    echo "Created SQS queue: $QUEUE_URL (14-day retention, 5min visibility, 3 retries→DLQ)"
else
    echo "SQS queue already exists: $QUEUE_URL"
fi

# Get Queue ARN
QUEUE_ARN=$(aws sqs get-queue-attributes \
    --queue-url "$QUEUE_URL" \
    --attribute-names QueueArn \
    --region "$REGION" \
    --query 'Attributes.QueueArn' \
    --output text)

echo "Queue ARN: $QUEUE_ARN"

# Create IAM Role for API Gateway to send to SQS
echo "Creating IAM role for API Gateway..."
ROLE_NAME="collagen-apigw-sqs-role"

if aws iam get-role --role-name "$ROLE_NAME" 2>/dev/null; then
    echo "IAM role already exists: $ROLE_NAME"
    ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text)
else
    # Create trust policy
    cat > /tmp/apigw-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Service": "apigateway.amazonaws.com"
    },
    "Action": "sts:AssumeRole"
  }]
}
EOF

    ROLE_ARN=$(aws iam create-role \
        --role-name "$ROLE_NAME" \
        --assume-role-policy-document file:///tmp/apigw-trust-policy.json \
        --query 'Role.Arn' \
        --output text)

    # Create inline policy for SQS SendMessage
    cat > /tmp/apigw-sqs-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "sqs:SendMessage",
      "sqs:GetQueueUrl"
    ],
    "Resource": "$QUEUE_ARN"
  }]
}
EOF

    aws iam put-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-name "sqs-send-message" \
        --policy-document file:///tmp/apigw-sqs-policy.json

    echo "Created IAM role: $ROLE_ARN"
    echo "Waiting 10s for IAM propagation..."
    sleep 10
fi

# Create Lambda function for webhook signature validation
echo "Creating Lambda function for webhook validation..."

FUNCTION_NAME="collagen-webhook-validator"
LAMBDA_ROLE_NAME="collagen-lambda-role"

# Check if Lambda role exists
if aws iam get-role --role-name "$LAMBDA_ROLE_NAME" 2>/dev/null >/dev/null; then
    echo "Lambda role already exists"
    LAMBDA_ROLE_ARN=$(aws iam get-role --role-name "$LAMBDA_ROLE_NAME" --query 'Role.Arn' --output text)
else
    cat > /tmp/lambda-trust-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Service": "lambda.amazonaws.com"
    },
    "Action": "sts:AssumeRole"
  }]
}
EOF

    LAMBDA_ROLE_ARN=$(aws iam create-role \
        --role-name "$LAMBDA_ROLE_NAME" \
        --assume-role-policy-document file:///tmp/lambda-trust-policy.json \
        --query 'Role.Arn' \
        --output text)

    # Attach basic Lambda execution policy (CloudWatch Logs)
    aws iam attach-role-policy \
        --role-name "$LAMBDA_ROLE_NAME" \
        --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"

    # Add SQS permissions
    cat > /tmp/lambda-sqs-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "sqs:SendMessage",
      "sqs:GetQueueUrl"
    ],
    "Resource": "$QUEUE_ARN"
  }]
}
EOF

    aws iam put-role-policy \
        --role-name "$LAMBDA_ROLE_NAME" \
        --policy-name "sqs-send" \
        --policy-document file:///tmp/lambda-sqs-policy.json

    echo "Created Lambda role: $LAMBDA_ROLE_ARN"
    echo "Waiting 10s for IAM propagation..."
    sleep 10
fi

# Package and deploy Lambda
if [ -f lambda/webhook_validator.py ]; then
    echo "Packaging Lambda function..."
    cd lambda
    zip -q webhook_validator.zip webhook_validator.py
    cd ..

    # Get Cloudinary API secret from .env
    CLOUDINARY_SECRET=$(grep "^CLOUDINARY_API_SECRET=" .env | cut -d'=' -f2- | tr -d '"' | sed 's/ *#.*//')

    if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" 2>/dev/null >/dev/null; then
        echo "Updating Lambda function code..."
        aws lambda update-function-code \
            --function-name "$FUNCTION_NAME" \
            --zip-file fileb://lambda/webhook_validator.zip \
            --region "$REGION" >/dev/null

        echo "Waiting for Lambda code update to complete..."
        aws lambda wait function-updated --function-name "$FUNCTION_NAME" --region "$REGION"

        # Update environment variables
        aws lambda update-function-configuration \
            --function-name "$FUNCTION_NAME" \
            --environment "Variables={SQS_WEBHOOK_QUEUE_URL=$QUEUE_URL,CLOUDINARY_API_SECRET=$CLOUDINARY_SECRET}" \
            --region "$REGION" >/dev/null

        echo "Waiting for Lambda configuration update to complete..."
        aws lambda wait function-updated --function-name "$FUNCTION_NAME" --region "$REGION"

        echo "Updated Lambda function"
    else
        echo "Creating Lambda function..."
        aws lambda create-function \
            --function-name "$FUNCTION_NAME" \
            --runtime python3.10 \
            --role "$LAMBDA_ROLE_ARN" \
            --handler webhook_validator.lambda_handler \
            --zip-file fileb://lambda/webhook_validator.zip \
            --timeout 10 \
            --memory-size 128 \
            --environment "Variables={SQS_WEBHOOK_QUEUE_URL=$QUEUE_URL,CLOUDINARY_API_SECRET=$CLOUDINARY_SECRET}" \
            --region "$REGION" >/dev/null

        echo "Waiting for function to be active..."
        aws lambda wait function-active --function-name "$FUNCTION_NAME" --region "$REGION"
        echo "Lambda function created"
    fi

    LAMBDA_ARN=$(aws lambda get-function \
        --function-name "$FUNCTION_NAME" \
        --region "$REGION" \
        --query 'Configuration.FunctionArn' \
        --output text)

    echo "Lambda ARN: $LAMBDA_ARN"
else
    echo "WARNING: lambda/webhook_validator.py not found - skipping Lambda deployment"
    echo "Lambda is required for signature validation!"
    LAMBDA_ARN=""
fi

# Create REST API Gateway v1 with Lambda integration
echo "Creating REST API Gateway v1 with Lambda integration..."

# Check if API exists and is valid
if [ -n "$API_GATEWAY_ID" ]; then
    if aws apigateway get-rest-api --region "$REGION" --rest-api-id "$API_GATEWAY_ID" 2>/dev/null >/dev/null; then
        echo "REST API already exists: $API_GATEWAY_ID"
        API_ID="$API_GATEWAY_ID"

        # Get existing endpoint
        API_ENDPOINT="https://$API_ID.execute-api.$REGION.amazonaws.com/prod"
        echo "Using existing API endpoint: $API_ENDPOINT"

        # Skip to next section
        SKIP_API_CREATION=true
    else
        echo "Configured API Gateway ID not found, creating new one..."
        SKIP_API_CREATION=false
    fi
else
    SKIP_API_CREATION=false
fi

if [ "$SKIP_API_CREATION" != "true" ]; then
    # Create REST API
    API_ID=$(aws apigateway create-rest-api \
        --region "$REGION" \
        --name "$API_NAME" \
        --description "Cloudinary webhook receiver for Collagen (REST API v1 with VTL support)" \
        --endpoint-configuration '{"types":["REGIONAL"]}' \
        --query 'id' \
        --output text)

    echo "Created REST API: $API_ID"

    # Get root resource ID
    ROOT_ID=$(aws apigateway get-resources \
        --region "$REGION" \
        --rest-api-id "$API_ID" \
        --query 'items[0].id' \
        --output text)

    # Create /webhook resource
    WEBHOOK_RESOURCE_ID=$(aws apigateway create-resource \
        --region "$REGION" \
        --rest-api-id "$API_ID" \
        --parent-id "$ROOT_ID" \
        --path-part "webhook" \
        --query 'id' \
        --output text)

    echo "Created /webhook resource"

    # Create /webhook/moderation resource
    MODERATION_RESOURCE_ID=$(aws apigateway create-resource \
        --region "$REGION" \
        --rest-api-id "$API_ID" \
        --parent-id "$WEBHOOK_RESOURCE_ID" \
        --path-part "moderation" \
        --query 'id' \
        --output text)

    echo "Created /webhook/moderation resource"

    # Create POST method
    aws apigateway put-method \
        --region "$REGION" \
        --rest-api-id "$API_ID" \
        --resource-id "$MODERATION_RESOURCE_ID" \
        --http-method POST \
        --authorization-type NONE \
        --no-api-key-required \
        >/dev/null

    echo "Created POST method"

    # Create Lambda integration (AWS_PROXY for signature validation)
    if [ -n "$LAMBDA_ARN" ]; then
        aws apigateway put-integration \
            --region "$REGION" \
            --rest-api-id "$API_ID" \
            --resource-id "$MODERATION_RESOURCE_ID" \
            --http-method POST \
            --type AWS_PROXY \
            --integration-http-method POST \
            --uri "arn:aws:apigateway:$REGION:lambda:path/2015-03-31/functions/$LAMBDA_ARN/invocations" \
            >/dev/null

        echo "Created Lambda integration"

        # Grant API Gateway permission to invoke Lambda
        AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
        aws lambda add-permission \
            --function-name "$FUNCTION_NAME" \
            --statement-id "apigateway-invoke-$(date +%s)" \
            --action lambda:InvokeFunction \
            --principal apigateway.amazonaws.com \
            --source-arn "arn:aws:execute-api:$REGION:$AWS_ACCOUNT_ID:$API_ID/*/*" \
            --region "$REGION" 2>/dev/null || echo "Lambda permission already exists"
    else
        echo "ERROR: Lambda ARN not available, cannot create integration"
        exit 1
    fi

    # AWS_PROXY integration handles responses automatically (no explicit response configuration needed)

    # Deploy to prod stage
    aws apigateway create-deployment \
        --region "$REGION" \
        --rest-api-id "$API_ID" \
        --stage-name prod \
        --stage-description "Production stage" \
        >/dev/null

    echo "Deployed to prod stage"

    # Set API endpoint
    API_ENDPOINT="https://$API_ID.execute-api.$REGION.amazonaws.com/prod"
    echo "API Endpoint: $API_ENDPOINT"
fi

# Set up AWS Backup for EC2
echo "Setting up AWS Backup for EC2..."

if [ -z "$INSTANCE_ID" ]; then
    echo "WARNING: INSTANCE_ID not found in .aws-config - skipping AWS Backup setup"
    echo "Run this section manually after loading INSTANCE_ID"
else
    BACKUP_PLAN_NAME="collagen-ec2-daily-backup"

    # Check if backup vault exists
    VAULT_NAME="collagen-backup-vault"
    aws backup create-backup-vault \
        --backup-vault-name "$VAULT_NAME" \
        --region "$REGION" 2>/dev/null || echo "Backup vault already exists: $VAULT_NAME"

    # Check if backup plan exists
    PLAN_ID=$(aws backup list-backup-plans \
        --region "$REGION" \
        --query "BackupPlansList[?BackupPlanName=='$BACKUP_PLAN_NAME'].BackupPlanId" \
        --output text 2>/dev/null || echo "")

    if [ -z "$PLAN_ID" ]; then
        # Create backup plan with GFS (Grandfather-Father-Son) retention strategy
        # - Daily: 14 days (Son)
        # - Weekly: 60 days (Father)
        # - Monthly: 365 days (Grandfather)
        PLAN_ID=$(aws backup create-backup-plan \
            --region "$REGION" \
            --backup-plan "{
                \"BackupPlanName\": \"$BACKUP_PLAN_NAME\",
                \"Rules\": [
                    {
                        \"RuleName\": \"daily-backup\",
                        \"TargetBackupVaultName\": \"$VAULT_NAME\",
                        \"ScheduleExpression\": \"cron(0 5 * * ? *)\",
                        \"StartWindowMinutes\": 60,
                        \"CompletionWindowMinutes\": 120,
                        \"Lifecycle\": {
                            \"DeleteAfterDays\": 14
                        }
                    },
                    {
                        \"RuleName\": \"weekly-backup\",
                        \"TargetBackupVaultName\": \"$VAULT_NAME\",
                        \"ScheduleExpression\": \"cron(0 5 ? * SUN *)\",
                        \"StartWindowMinutes\": 60,
                        \"CompletionWindowMinutes\": 120,
                        \"Lifecycle\": {
                            \"DeleteAfterDays\": 60
                        }
                    },
                    {
                        \"RuleName\": \"monthly-backup\",
                        \"TargetBackupVaultName\": \"$VAULT_NAME\",
                        \"ScheduleExpression\": \"cron(0 5 1 * ? *)\",
                        \"StartWindowMinutes\": 60,
                        \"CompletionWindowMinutes\": 120,
                        \"Lifecycle\": {
                            \"DeleteAfterDays\": 365
                        }
                    }
                ]
            }" \
            --query 'BackupPlanId' \
            --output text)

        echo "Created backup plan with GFS retention: $PLAN_ID"
        echo "  - Daily: 14 days"
        echo "  - Weekly (Sunday): 60 days"
        echo "  - Monthly (1st): 365 days"
    else
        echo "Backup plan already exists: $PLAN_ID"
    fi

    # Create AWS Backup service-linked role if it doesn't exist
    # Note: Service-linked role name is AWSServiceRoleForBackup (managed by AWS)
    aws iam create-service-linked-role --aws-service-name backup.amazonaws.com 2>/dev/null || echo "AWS Backup service-linked role already exists"

    BACKUP_ROLE_ARN="arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/aws-service-role/backup.amazonaws.com/AWSServiceRoleForBackup"

    echo "Using AWS Backup service-linked role: AWSServiceRoleForBackup"

    # Enable EFS automatic backups (required for AWS Backup to work)
    # Note: EC2 backup is not configured due to AWS managed policy bug (missing ec2:DescribeTags)
    if [ -n "$EFS_ID" ]; then
        # Enable automatic backups - AWS will add the required tag automatically
        aws efs put-backup-policy \
            --file-system-id "$EFS_ID" \
            --backup-policy Status=ENABLED \
            --region "$REGION" 2>/dev/null || echo "EFS automatic backups already enabled"

        echo "Enabled EFS automatic backups (adds aws:elasticfilesystem:default-backup tag)"
        sleep 5
    else
        echo "WARNING: EFS_ID not found in .aws-config - skipping EFS backup setup"
        echo "Daily backups at 5 AM UTC will fail without EFS_ID"
        return
    fi

    # Create backup selection for EFS only (using direct resource ARN)
    aws backup create-backup-selection \
        --region "$REGION" \
        --backup-plan-id "$PLAN_ID" \
        --backup-selection "{
            \"SelectionName\": \"collagen-efs-backup\",
            \"IamRoleArn\": \"$BACKUP_ROLE_ARN\",
            \"Resources\": [
                \"arn:aws:elasticfilesystem:$REGION:$(aws sts get-caller-identity --query Account --output text):file-system/$EFS_ID\"
            ]
        }" 2>/dev/null || echo "Backup selection already exists"

    echo "AWS Backup configured for EFS filesystem: $EFS_ID"
    echo "GFS retention: Daily (14d), Weekly (60d), Monthly (365d)"
    echo "Next scheduled backup: 5 AM UTC"
    echo ""
    echo "NOTE: EC2 backup not configured due to AWS managed policy bug"
    echo "      (AWSBackupServiceLinkedRolePolicyForBackup v20 missing ec2:DescribeTags)"
fi

# Create IAM role for EC2 to access SQS
echo "Creating IAM role for EC2 SQS access..."

EC2_ROLE_NAME="collagen-ec2-role"
EC2_PROFILE_NAME="collagen-ec2-profile"

# Create IAM role
if aws iam get-role --role-name "$EC2_ROLE_NAME" 2>/dev/null; then
    echo "EC2 IAM role already exists: $EC2_ROLE_NAME"
else
    cat > /tmp/ec2-trust-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Service": "ec2.amazonaws.com"
    },
    "Action": "sts:AssumeRole"
  }]
}
EOF

    aws iam create-role \
        --role-name "$EC2_ROLE_NAME" \
        --assume-role-policy-document file:///tmp/ec2-trust-policy.json \
        --description "Allows EC2 instance to access SQS for webhook processing" \
        >/dev/null

    echo "Created EC2 IAM role: $EC2_ROLE_NAME"
fi

# Add SQS permissions policy
cat > /tmp/ec2-sqs-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
      "sqs:GetQueueUrl"
    ],
    "Resource": "arn:aws:sqs:$REGION:$(aws sts get-caller-identity --query Account --output text):collagen-*"
  }]
}
EOF

aws iam put-role-policy \
    --role-name "$EC2_ROLE_NAME" \
    --policy-name "sqs-access" \
    --policy-document file:///tmp/ec2-sqs-policy.json

echo "Added SQS permissions to role"

# Create instance profile
if aws iam get-instance-profile --instance-profile-name "$EC2_PROFILE_NAME" 2>/dev/null; then
    echo "Instance profile already exists: $EC2_PROFILE_NAME"
else
    aws iam create-instance-profile \
        --instance-profile-name "$EC2_PROFILE_NAME" \
        >/dev/null

    aws iam add-role-to-instance-profile \
        --instance-profile-name "$EC2_PROFILE_NAME" \
        --role-name "$EC2_ROLE_NAME"

    echo "Created instance profile: $EC2_PROFILE_NAME"
    echo "Waiting 10s for IAM propagation..."
    sleep 10
fi

# Attach instance profile to EC2 (if INSTANCE_ID exists)
if [ -n "$INSTANCE_ID" ]; then
    # Check if already attached
    CURRENT_PROFILE=$(aws ec2 describe-instances \
        --region "$REGION" \
        --instance-ids "$INSTANCE_ID" \
        --query 'Reservations[0].Instances[0].IamInstanceProfile.Arn' \
        --output text 2>/dev/null || echo "None")

    if [ "$CURRENT_PROFILE" = "None" ]; then
        aws ec2 associate-iam-instance-profile \
            --region "$REGION" \
            --instance-id "$INSTANCE_ID" \
            --iam-instance-profile "Name=$EC2_PROFILE_NAME" \
            >/dev/null

        echo "Attached instance profile to EC2: $INSTANCE_ID"
        echo "Note: Restart collagen-processor service after deployment for credentials to take effect"
    else
        echo "EC2 instance already has IAM instance profile attached"
    fi
else
    echo "WARNING: INSTANCE_ID not found - skipping instance profile attachment"
    echo "Manually attach profile later: aws ec2 associate-iam-instance-profile --instance-id <ID> --iam-instance-profile Name=$EC2_PROFILE_NAME"
fi

echo ""
echo "=== Phase 2A Setup Complete ==="
echo "SQS Queue: $QUEUE_URL"
echo "SQS DLQ: $DLQ_URL"
echo "API Gateway ID: $API_ID"
echo "Webhook URL: ${API_ENDPOINT}/webhook/moderation"
echo ""
echo "Next steps:"
echo "1. Update Cloudinary webhook URL to: ${API_ENDPOINT}/webhook/moderation"
echo "2. Update EC2 processor to poll SQS instead of Flask HTTP"
echo "3. Deploy updated processor to EC2"
echo "4. Test with test_prototype campaign"
echo ""

# Update .aws-config (remove old entries, append new)
sed -i '/^# Phase 2A Resources/,/^WEBHOOK_URL=/d' .aws-config 2>/dev/null || true
sed -i '/^# REST API Gateway v1/,/^WEBHOOK_URL=/d' .aws-config 2>/dev/null || true

cat >> .aws-config << EOF

# Phase 2A Resources (REST API v1 with VTL support)
SQS_WEBHOOK_QUEUE_URL=$QUEUE_URL
SQS_DLQ_URL=$DLQ_URL
API_GATEWAY_ID=$API_ID
API_ENDPOINT=$API_ENDPOINT
WEBHOOK_URL=${API_ENDPOINT}/webhook/moderation
EOF

echo "Configuration updated in .aws-config"
