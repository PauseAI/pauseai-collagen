#!/usr/bin/env python3
"""
Sync campaign tiles from EC2 to local filesystem for development.

Usage:
    ./tools/sync_tiles_from_ec2.py test_prototype    # Sync test_prototype campaign
    ./tools/sync_tiles_from_ec2.py sayno             # Sync sayno campaign
"""

import sys
import subprocess
from pathlib import Path

# EC2 connection details (from CLAUDE.md)
EC2_HOST = "3.85.173.169"
EC2_USER = "ubuntu"
SSH_KEY = Path.home() / ".ssh" / "collagen-server-key.pem"
REMOTE_BASE = "/mnt/efs"
LOCAL_BASE = Path("/tmp/collagen-local")


def sync_campaign(campaign: str):
    """Sync campaign tiles from EC2 to local filesystem."""

    if not SSH_KEY.exists():
        print(f"❌ SSH key not found: {SSH_KEY}")
        print(f"   Expected location: {SSH_KEY}")
        sys.exit(1)

    # Create local directory structure
    local_campaign = LOCAL_BASE / campaign
    (local_campaign / "tiles").mkdir(parents=True, exist_ok=True)
    (local_campaign / "collages").mkdir(parents=True, exist_ok=True)
    (local_campaign / "logs").mkdir(parents=True, exist_ok=True)

    print(f"📥 Syncing {campaign} tiles from EC2...")
    print(f"   Remote: {EC2_USER}@{EC2_HOST}:{REMOTE_BASE}/{campaign}/tiles/")
    print(f"   Local:  {local_campaign}/tiles/")
    print()

    # Sync tiles using rsync (preserves timestamps, only transfers changes)
    cmd = [
        "rsync",
        "-avz",  # archive, verbose, compress
        "--progress",
        "-e", f"ssh -i {SSH_KEY} -o StrictHostKeyChecking=no",
        f"{EC2_USER}@{EC2_HOST}:{REMOTE_BASE}/{campaign}/tiles/",
        f"{local_campaign}/tiles/"
    ]

    result = subprocess.run(cmd, capture_output=False)

    if result.returncode != 0:
        print(f"❌ Failed to sync tiles/")
        sys.exit(1)

    # Count what we synced
    tile_count = len(list((local_campaign / "tiles").glob("*.png")))

    print()
    print(f"✅ Sync complete!")
    print(f"   Tiles:   {tile_count} PNGs")
    print(f"   Location: {local_campaign}/")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: ./tools/sync_tiles_from_ec2.py <campaign>")
        print("Example: ./tools/sync_tiles_from_ec2.py test_prototype")
        sys.exit(1)

    campaign = sys.argv[1]
    sync_campaign(campaign)
