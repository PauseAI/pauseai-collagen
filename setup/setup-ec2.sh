#!/bin/bash
# Setup script to run on EC2 instance
# Installs dependencies, mounts EFS, creates directory structure
# Can be run multiple times (idempotent)

set -e

EFS_ID="${1:-fs-001b5fdce1b4db8c8}"
REGION="${2:-us-east-1}"

echo "=== Collagen EC2 Setup ==="
echo "EFS ID: $EFS_ID"
echo "Region: $REGION"
echo ""

# 1. Install system dependencies
echo "[1/4] Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y \
  python3 \
  python3-pip \
  python3-venv \
  imagemagick \
  exiftool \
  git \
  nfs-common \
  nginx

echo "Installed Python version: $(python3 --version)"

# 2. Create EFS mount point and mount
echo "[2/4] Setting up EFS mount..."
sudo mkdir -p /mnt/efs

# Check if already mounted
if mountpoint -q /mnt/efs; then
    echo "EFS already mounted"
else
    sudo mount -t nfs4 -o nfsvers=4.1 ${EFS_ID}.efs.${REGION}.amazonaws.com:/ /mnt/efs
    echo "EFS mounted successfully"
fi

# 3. Add to /etc/fstab for persistence (if not already there)
echo "[3/4] Configuring automatic mount on boot..."
FSTAB_ENTRY="${EFS_ID}.efs.${REGION}.amazonaws.com:/ /mnt/efs nfs4 nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,_netdev 0 0"

if ! grep -q "$EFS_ID" /etc/fstab 2>/dev/null; then
    echo "$FSTAB_ENTRY" | sudo tee -a /etc/fstab
    echo "Added to /etc/fstab"
else
    echo "Already in /etc/fstab"
fi

# 4. Create directory structure
echo "[4/4] Creating directory structure..."
sudo mkdir -p /mnt/efs/{dev,prod}/{sources,tiles,collages,logs}
sudo chown -R ubuntu:ubuntu /mnt/efs

echo ""
echo "=== Setup Complete ==="
echo ""
echo "EFS mount:"
df -h /mnt/efs
echo ""
echo "Directory structure:"
tree -L 2 /mnt/efs 2>/dev/null || ls -laR /mnt/efs
echo ""
echo "Ready for webhook receiver deployment!"
