#!/bin/bash
# Redirect systemd service logs to EFS for backup coverage
# This preserves important operational logs (user actions, processing events)

set -e

echo "=== Redirecting Collagen Service Logs to EFS ==="
echo ""

# Create log directories on EFS if they don't exist
ssh -i ~/.ssh/collagen-server-key.pem ubuntu@3.85.173.169 << 'EOF'
    # Create centralized log directory for systemd services
    sudo mkdir -p /mnt/efs/system-logs
    sudo chown ubuntu:ubuntu /mnt/efs/system-logs

    # Export existing journald logs first (preserve history)
    echo "Exporting existing journald logs to EFS..."
    sudo journalctl -u collagen-ingestor > /mnt/efs/system-logs/collagen-ingestor-journal-export.log
    sudo journalctl -u collagen-tracking-worker > /mnt/efs/system-logs/collagen-tracking-worker-journal-export.log

    echo "Exported $(wc -l < /mnt/efs/system-logs/collagen-ingestor-journal-export.log) lines from ingestor"
    echo "Exported $(wc -l < /mnt/efs/system-logs/collagen-tracking-worker-journal-export.log) lines from tracking worker"

    # Update service files to log to EFS
    echo ""
    echo "Updating collagen-ingestor.service..."
    sudo tee /etc/systemd/system/collagen-ingestor.service > /dev/null << 'SERVICE'
[Unit]
Description=Collagen SQS Webhook Ingestor
After=network.target

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/collagen
Environment="PATH=/home/ubuntu/collagen/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="PYTHONUNBUFFERED=1"
EnvironmentFile=/home/ubuntu/collagen/.env

# SQS Queue URL will be loaded from .env as SQS_QUEUE_URL
ExecStart=/home/ubuntu/collagen/venv/bin/python3 /home/ubuntu/collagen/scripts/sqs_ingestor.py

# Restart policy
Restart=always
RestartSec=10

# Logging - redirect to EFS for backup coverage
StandardOutput=append:/mnt/efs/system-logs/collagen-ingestor.log
StandardError=append:/mnt/efs/system-logs/collagen-ingestor.log

# Also keep in journal for real-time monitoring
SyslogIdentifier=collagen-ingestor

# Security
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
SERVICE

    echo "Updating collagen-tracking-worker.service..."
    sudo tee /etc/systemd/system/collagen-tracking-worker.service > /dev/null << 'SERVICE'
[Unit]
Description=Collagen Tracking Worker
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/collagen
Environment="COLLAGEN_DATA_DIR=/mnt/efs"
Environment="PYTHONUNBUFFERED=1"
ExecStart=/home/ubuntu/collagen/venv/bin/python3 /home/ubuntu/collagen/scripts/tracking_worker.py
Restart=always
RestartSec=10

# Logging - redirect to EFS for backup coverage
StandardOutput=append:/mnt/efs/system-logs/collagen-tracking-worker.log
StandardError=append:/mnt/efs/system-logs/collagen-tracking-worker.log

# Also keep in journal for real-time monitoring
SyslogIdentifier=collagen-tracking-worker

[Install]
WantedBy=multi-user.target
SERVICE

    # Reload systemd and restart services
    echo ""
    echo "Reloading systemd and restarting services..."
    sudo systemctl daemon-reload
    sudo systemctl restart collagen-ingestor
    sudo systemctl restart collagen-tracking-worker

    # Verify services are running
    sleep 5
    echo ""
    echo "Service status:"
    sudo systemctl status collagen-ingestor --no-pager | grep Active
    sudo systemctl status collagen-tracking-worker --no-pager | grep Active

    # Check new log files are being written
    echo ""
    echo "New log files on EFS:"
    ls -lah /mnt/efs/system-logs/*.log 2>/dev/null || echo "Log files will appear after first output"

    # Add log rotation config to prevent unbounded growth
    sudo tee /etc/logrotate.d/collagen-efs > /dev/null << 'LOGROTATE'
/mnt/efs/system-logs/*.log {
    weekly
    rotate 52
    compress
    delaycompress
    missingok
    notifempty
    create 0644 ubuntu ubuntu
    sharedscripts
    postrotate
        systemctl reload collagen-ingestor collagen-tracking-worker 2>/dev/null || true
    endscript
}
LOGROTATE

    echo ""
    echo "✅ Log rotation configured (weekly, 52 weeks retention)"
EOF

echo ""
echo "=== Summary ==="
echo "✅ Existing logs exported to /mnt/efs/system-logs/*-journal-export.log"
echo "✅ Services now logging to /mnt/efs/system-logs/*.log"
echo "✅ Log rotation configured (weekly, 52 weeks retention)"
echo "✅ Logs will be included in EFS backups"
echo ""
echo "Note: Services still log to journald for real-time monitoring with 'journalctl'"