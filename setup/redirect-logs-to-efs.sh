#!/bin/bash
# Redirect systemd service logs to EFS for backup coverage
# This preserves important operational logs (user actions, processing events)
#
# IMPORTANT: This script copies service files from setup/ directory.
# If you need to modify service configuration, edit the files in setup/ first,
# then re-run this script to deploy them.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KEY="$HOME/.ssh/collagen-server-key.pem"
EC2_HOST="ubuntu@3.85.173.169"

# Verify service files exist locally
if [[ ! -f "$SCRIPT_DIR/collagen-ingestor.service" ]] || [[ ! -f "$SCRIPT_DIR/collagen-tracking-worker.service" ]]; then
    echo "ERROR: Service files not found in $SCRIPT_DIR"
    echo "Expected: collagen-ingestor.service, collagen-tracking-worker.service"
    exit 1
fi

echo "=== Redirecting Collagen Service Logs to EFS ==="
echo ""
echo "Using service files from: $SCRIPT_DIR"
echo ""

# Copy service files to EC2
echo "Copying service files to EC2..."
scp -i "$KEY" \
    "$SCRIPT_DIR/collagen-ingestor.service" \
    "$SCRIPT_DIR/collagen-tracking-worker.service" \
    "$EC2_HOST":~/collagen/setup/

# Run setup on EC2
ssh -i "$KEY" "$EC2_HOST" << 'EOF'
    # Create centralized log directory for systemd services
    sudo mkdir -p /mnt/efs/system-logs
    sudo chown ubuntu:ubuntu /mnt/efs/system-logs

    # Export existing journald logs first (preserve history)
    echo "Exporting existing journald logs to EFS..."
    sudo journalctl -u collagen-ingestor > /mnt/efs/system-logs/collagen-ingestor-journal-export.log 2>/dev/null || true
    sudo journalctl -u collagen-tracking-worker > /mnt/efs/system-logs/collagen-tracking-worker-journal-export.log 2>/dev/null || true

    echo "Exported $(wc -l < /mnt/efs/system-logs/collagen-ingestor-journal-export.log 2>/dev/null || echo 0) lines from ingestor"
    echo "Exported $(wc -l < /mnt/efs/system-logs/collagen-tracking-worker-journal-export.log 2>/dev/null || echo 0) lines from tracking worker"

    # Install service files from setup/ (single source of truth)
    echo ""
    echo "Installing service files..."
    sudo cp ~/collagen/setup/collagen-ingestor.service /etc/systemd/system/
    sudo cp ~/collagen/setup/collagen-tracking-worker.service /etc/systemd/system/

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