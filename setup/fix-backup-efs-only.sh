#!/bin/bash
# Fix AWS Backup to only backup EFS (EC2 backup broken due to AWS policy bug)
# Run this to update existing backup configuration

set -e

REGION="us-east-1"
BACKUP_PLAN_ID="4b57a30f-68de-49b1-94fc-712ec325af41"

# Load existing config
if [ -f .aws-config ]; then
    source .aws-config
    echo "Loaded configuration from .aws-config"
else
    echo "ERROR: .aws-config not found"
    exit 1
fi

if [ -z "$EFS_ID" ]; then
    echo "ERROR: EFS_ID not found in .aws-config"
    exit 1
fi

echo "=== Fixing AWS Backup Configuration (EFS only) ==="
echo "Reason: AWS managed policy bug - missing ec2:DescribeTags permission"
echo ""

# Step 1: Remove any existing backup selections
echo "Cleaning up existing backup selections..."
for SELECTION_ID in $(aws backup list-backup-selections \
    --backup-plan-id "$BACKUP_PLAN_ID" \
    --region "$REGION" \
    --query 'BackupSelectionsList[].SelectionId' \
    --output text 2>/dev/null); do

    aws backup delete-backup-selection \
        --backup-plan-id "$BACKUP_PLAN_ID" \
        --selection-id "$SELECTION_ID" \
        --region "$REGION" 2>/dev/null && \
    echo "  Deleted selection: $SELECTION_ID"
done

# Step 2: Enable EFS automatic backups (this adds AWS-managed tag)
echo ""
echo "Enabling EFS automatic backups..."
aws efs put-backup-policy \
    --file-system-id "$EFS_ID" \
    --backup-policy Status=ENABLED \
    --region "$REGION" || echo "  Already enabled"

echo "✅ EFS automatic backups enabled (AWS adds required tag automatically)"
sleep 5

# Step 3: Create new backup selection for EFS only
echo ""
echo "Creating backup selection for EFS..."
BACKUP_ROLE_ARN="arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/aws-service-role/backup.amazonaws.com/AWSServiceRoleForBackup"

aws backup create-backup-selection \
    --region "$REGION" \
    --backup-plan-id "$BACKUP_PLAN_ID" \
    --backup-selection "{
        \"SelectionName\": \"collagen-efs-only\",
        \"IamRoleArn\": \"$BACKUP_ROLE_ARN\",
        \"Resources\": [
            \"arn:aws:elasticfilesystem:$REGION:$(aws sts get-caller-identity --query Account --output text):file-system/$EFS_ID\"
        ]
    }" --output json | jq -r '.SelectionId'

echo ""
echo "✅ AWS Backup configured for EFS only: $EFS_ID"
echo ""
echo "Backup schedule:"
echo "  - Daily: 5 AM UTC (14-day retention)"
echo "  - Weekly: Sundays 5 AM UTC (60-day retention)"
echo "  - Monthly: 1st at 5 AM UTC (365-day retention)"
echo ""
echo "EC2 backup NOT configured (AWS policy bug prevents it from working)"