#!/bin/bash
set -e

# Collagen AWS Infrastructure Setup Script
# Sets up EC2, EFS, and security groups for webhook testing

REGION="us-east-1"
KEY_NAME="collagen-server-key"
SG_NAME="collagen-server-sg"
INSTANCE_NAME="collagen-server-dev"
EFS_NAME="collagen-storage"

echo "=== Collagen AWS Infrastructure Setup ==="
echo "Region: $REGION"
echo ""

# 1. Create EC2 Key Pair
echo "[1/6] Creating EC2 key pair..."
if aws ec2 describe-key-pairs --region "$REGION" --key-names "$KEY_NAME" &>/dev/null; then
    echo "Key pair $KEY_NAME already exists, skipping..."
else
    aws ec2 create-key-pair \
        --region "$REGION" \
        --key-name "$KEY_NAME" \
        --query 'KeyMaterial' \
        --output text > ~/.ssh/${KEY_NAME}.pem

    chmod 400 ~/.ssh/${KEY_NAME}.pem
    echo "Created key pair: ~/.ssh/${KEY_NAME}.pem"
fi

# 2. Create Security Group
echo "[2/6] Creating security group..."
SG_ID=$(aws ec2 describe-security-groups \
    --region "$REGION" \
    --filters "Name=group-name,Values=$SG_NAME" \
    --query 'SecurityGroups[0].GroupId' \
    --output text 2>/dev/null || echo "None")

if [ "$SG_ID" = "None" ]; then
    SG_ID=$(aws ec2 create-security-group \
        --region "$REGION" \
        --group-name "$SG_NAME" \
        --description "Security group for Collagen server" \
        --query 'GroupId' \
        --output text)

    echo "Created security group: $SG_ID"

    # Get your current IP
    MY_IP=$(curl -s https://checkip.amazonaws.com)

    # Allow SSH from your IP
    aws ec2 authorize-security-group-ingress \
        --region "$REGION" \
        --group-id "$SG_ID" \
        --protocol tcp \
        --port 22 \
        --cidr "${MY_IP}/32"

    echo "Allowed SSH from: $MY_IP"

    # Allow HTTP from anywhere (for Cloudinary webhooks)
    aws ec2 authorize-security-group-ingress \
        --region "$REGION" \
        --group-id "$SG_ID" \
        --protocol tcp \
        --port 80 \
        --cidr 0.0.0.0/0

    echo "Allowed HTTP from: 0.0.0.0/0"
else
    echo "Security group already exists: $SG_ID"
fi

# 3. Create EFS Filesystem
echo "[3/6] Creating EFS filesystem..."
EFS_ID=$(aws efs describe-file-systems \
    --region "$REGION" \
    --query "FileSystems[?Name=='$EFS_NAME'].FileSystemId" \
    --output text 2>/dev/null || echo "")

if [ -z "$EFS_ID" ]; then
    EFS_ID=$(aws efs create-file-system \
        --region "$REGION" \
        --performance-mode generalPurpose \
        --throughput-mode bursting \
        --encrypted \
        --tags Key=Name,Value="$EFS_NAME" \
        --query 'FileSystemId' \
        --output text)

    echo "Created EFS filesystem: $EFS_ID"
    echo "Waiting for EFS to become available..."

    while true; do
        STATE=$(aws efs describe-file-systems \
            --region "$REGION" \
            --file-system-id "$EFS_ID" \
            --query 'FileSystems[0].LifeCycleState' \
            --output text)

        if [ "$STATE" = "available" ]; then
            break
        fi
        echo "  EFS state: $STATE (waiting...)"
        sleep 5
    done

    echo "EFS is available"
else
    echo "EFS filesystem already exists: $EFS_ID"
fi

# 4. Create EFS Mount Target
echo "[4/6] Creating EFS mount target..."
SUBNET_ID=$(aws ec2 describe-subnets \
    --region "$REGION" \
    --query 'Subnets[0].SubnetId' \
    --output text)

MOUNT_TARGET=$(aws efs describe-mount-targets \
    --region "$REGION" \
    --file-system-id "$EFS_ID" \
    --query 'MountTargets[0].MountTargetId' \
    --output text 2>/dev/null || echo "None")

if [ "$MOUNT_TARGET" = "None" ]; then
    aws efs create-mount-target \
        --region "$REGION" \
        --file-system-id "$EFS_ID" \
        --subnet-id "$SUBNET_ID" \
        --security-groups "$SG_ID"

    echo "Created mount target in subnet: $SUBNET_ID"
    echo "Waiting for mount target to become available..."

    while true; do
        STATE=$(aws efs describe-mount-targets \
            --region "$REGION" \
            --file-system-id "$EFS_ID" \
            --query 'MountTargets[0].LifeCycleState' \
            --output text)

        if [ "$STATE" = "available" ]; then
            break
        fi
        echo "  Mount target state: $STATE (waiting...)"
        sleep 5
    done

    echo "Mount target is available"
else
    echo "Mount target already exists: $MOUNT_TARGET"
fi

# 5. Launch EC2 Instance
echo "[5/6] Launching EC2 instance..."

# Get Ubuntu 24.04 LTS AMI for us-east-1
AMI_ID="ami-0c7217cdde317cfec"

# Check if instance already exists
INSTANCE_ID=$(aws ec2 describe-instances \
    --region "$REGION" \
    --filters "Name=tag:Name,Values=$INSTANCE_NAME" "Name=instance-state-name,Values=running,pending,stopping,stopped" \
    --query 'Reservations[0].Instances[0].InstanceId' \
    --output text 2>/dev/null || echo "None")

if [ "$INSTANCE_ID" = "None" ]; then
    # Create user-data script
    USER_DATA=$(cat <<'USERDATA'
#!/bin/bash
set -e
apt-get update
apt-get upgrade -y
apt-get install -y python3 python3-pip python3-venv imagemagick exiftool git nfs-common nginx
mkdir -p /mnt/efs
echo "Setup complete" > /tmp/setup-complete
USERDATA
)

    INSTANCE_ID=$(aws ec2 run-instances \
        --region "$REGION" \
        --image-id "$AMI_ID" \
        --instance-type t3.micro \
        --key-name "$KEY_NAME" \
        --security-group-ids "$SG_ID" \
        --user-data "$USER_DATA" \
        --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME}]" \
        --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=20}' \
        --query 'Instances[0].InstanceId' \
        --output text)

    echo "Launched instance: $INSTANCE_ID"
    echo "Waiting for instance to be running..."

    aws ec2 wait instance-running \
        --region "$REGION" \
        --instance-ids "$INSTANCE_ID"

    echo "Instance is running"
else
    echo "Instance already exists: $INSTANCE_ID"
fi

# 6. Get Instance Info
echo "[6/6] Getting instance information..."
PUBLIC_IP=$(aws ec2 describe-instances \
    --region "$REGION" \
    --instance-ids "$INSTANCE_ID" \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text)

echo ""
echo "=== Setup Complete ==="
echo "Instance ID: $INSTANCE_ID"
echo "Public IP: $PUBLIC_IP"
echo "EFS ID: $EFS_ID"
echo "Security Group: $SG_ID"
echo ""
echo "SSH command:"
echo "  ssh -i ~/.ssh/${KEY_NAME}.pem ubuntu@${PUBLIC_IP}"
echo ""
echo "EFS mount command (run on EC2):"
echo "  sudo mount -t nfs4 -o nfsvers=4.1 ${EFS_ID}.efs.${REGION}.amazonaws.com:/ /mnt/efs"
echo ""
echo "Next steps:"
echo "1. SSH to the instance"
echo "2. Mount EFS"
echo "3. Create directory structure: sudo mkdir -p /mnt/efs/{dev,prod}/{sources,tiles,collages,logs}"
echo "4. Set permissions: sudo chown -R ubuntu:ubuntu /mnt/efs"
echo ""

# Save config to file
cat > .aws-config << EOF
REGION=$REGION
INSTANCE_ID=$INSTANCE_ID
PUBLIC_IP=$PUBLIC_IP
EFS_ID=$EFS_ID
SG_ID=$SG_ID
KEY_NAME=$KEY_NAME
EOF

echo "Configuration saved to .aws-config"
