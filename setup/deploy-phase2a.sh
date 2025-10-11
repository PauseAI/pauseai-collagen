#!/bin/bash
set -e

# Deploy Phase 2A SQS Processor to EC2
# Replaces Flask webhook receiver with SQS-based polling

# Load config
if [ ! -f .aws-config ]; then
    echo "ERROR: .aws-config not found. Run setup-aws-infra.sh first."
    exit 1
fi

source .aws-config

echo "=== Deploying Phase 2A SQS Processor to EC2 ==="
echo "Instance: $INSTANCE_ID ($PUBLIC_IP)"
echo "Queue: $SQS_QUEUE_URL"
echo ""

# Check SSH connectivity
echo "[1/6] Testing SSH connectivity..."
if ! ssh -i ~/.ssh/${KEY_NAME}.pem -o ConnectTimeout=5 ubuntu@${PUBLIC_IP} "echo 'SSH OK'"; then
    echo "ERROR: Cannot connect to EC2 instance"
    exit 1
fi

# Create collagen directory if it doesn't exist
echo "[2/6] Setting up directory structure on EC2..."
ssh -i ~/.ssh/${KEY_NAME}.pem ubuntu@${PUBLIC_IP} "mkdir -p ~/collagen/scripts ~/collagen/setup"

# Copy updated files to EC2
echo "[3/6] Copying files to EC2..."
scp -i ~/.ssh/${KEY_NAME}.pem \
    scripts/sqs_ingestor.py \
    scripts/ingestor.py \
    scripts/campaign_logger.py \
    ubuntu@${PUBLIC_IP}:~/collagen/scripts/

scp -i ~/.ssh/${KEY_NAME}.pem \
    requirements.txt \
    .env.example \
    ubuntu@${PUBLIC_IP}:~/collagen/

scp -i ~/.ssh/${KEY_NAME}.pem \
    setup/collagen-ingestor.service \
    ubuntu@${PUBLIC_IP}:~/collagen/setup/

# Create virtualenv and install dependencies
echo "[4/6] Setting up Python virtualenv and dependencies..."
ssh -i ~/.ssh/${KEY_NAME}.pem ubuntu@${PUBLIC_IP} << 'ENDSSH'
    cd ~/collagen

    # Create venv if it doesn't exist
    if [ ! -d "venv" ]; then
        echo "Creating virtualenv..."
        python3 -m venv venv
    fi

    # Install all dependencies
    source venv/bin/activate
    pip install --quiet --upgrade pip
    pip install --quiet -r requirements.txt
    deactivate

    echo "Python dependencies installed"
ENDSSH

# Update .env with SQS_QUEUE_URL
echo "[5/6] Updating .env with SQS_QUEUE_URL..."
ssh -i ~/.ssh/${KEY_NAME}.pem ubuntu@${PUBLIC_IP} << ENDSSH
    if ! grep -q "SQS_QUEUE_URL" ~/collagen/.env 2>/dev/null; then
        echo "" >> ~/collagen/.env
        echo "# AWS SQS Queue (Phase 2A)" >> ~/collagen/.env
        echo "SQS_QUEUE_URL=$SQS_QUEUE_URL" >> ~/collagen/.env
        echo "Added SQS_QUEUE_URL to .env"
    else
        echo "SQS_QUEUE_URL already in .env"
    fi
ENDSSH

# Stop old services, install and start new ingestor service
echo "[6/6] Installing systemd service..."
ssh -i ~/.ssh/${KEY_NAME}.pem ubuntu@${PUBLIC_IP} << 'ENDSSH'
    # Stop old services if running
    if sudo systemctl is-active --quiet webhook-receiver; then
        echo "Stopping old webhook-receiver service..."
        sudo systemctl stop webhook-receiver
        sudo systemctl disable webhook-receiver
    fi

    if sudo systemctl is-active --quiet collagen-processor; then
        echo "Stopping old collagen-processor service..."
        sudo systemctl stop collagen-processor
        sudo systemctl disable collagen-processor
    fi

    # Install new collagen-ingestor service
    sudo cp ~/collagen/setup/collagen-ingestor.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable collagen-ingestor
    sudo systemctl start collagen-ingestor

    echo "Waiting 3s for service to start..."
    sleep 3

    # Check service status
    if sudo systemctl is-active --quiet collagen-ingestor; then
        echo "✓ collagen-ingestor service is running"
    else
        echo "ERROR: collagen-ingestor service failed to start"
        sudo journalctl -u collagen-ingestor -n 20 --no-pager
        exit 1
    fi
ENDSSH

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Service status:"
ssh -i ~/.ssh/${KEY_NAME}.pem ubuntu@${PUBLIC_IP} "sudo systemctl status collagen-ingestor --no-pager -l | head -20"

echo ""
echo "Recent logs:"
ssh -i ~/.ssh/${KEY_NAME}.pem ubuntu@${PUBLIC_IP} "sudo journalctl -u collagen-ingestor -n 10 --no-pager"

echo ""
echo "Next steps:"
echo "1. Update Cloudinary webhook URL to: $WEBHOOK_URL"
echo "2. Test by approving a test_prototype image in Cloudinary"
echo "3. Monitor logs: ssh ubuntu@$PUBLIC_IP 'sudo journalctl -u collagen-ingestor -f'"
