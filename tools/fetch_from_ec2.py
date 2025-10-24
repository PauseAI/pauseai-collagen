#!/usr/bin/env python3
"""
Fetch file from EC2 EFS to local equivalent path.

Usage:
    ./tools/fetch_from_ec2.py /mnt/efs/test_prototype/collages/20251023T152825Z,20=5x4/4096.jpg

Result: Downloaded to /tmp/collagen-local/test_prototype/collages/20251023T152825Z,20=5x4/4096.jpg
"""

import sys
import subprocess
from pathlib import Path

EC2_HOST = "3.85.173.169"
EC2_USER = "ubuntu"
SSH_KEY = Path.home() / ".ssh" / "collagen-server-key.pem"

def fetch_file(remote_path: str):
    """Fetch file from EC2 and place in local equivalent path."""

    if not remote_path.startswith("/mnt/efs/"):
        print(f"❌ Path must start with /mnt/efs/")
        print(f"   Got: {remote_path}")
        sys.exit(1)

    # Convert /mnt/efs/campaign/... to /tmp/collagen-local/campaign/...
    local_path = Path("/tmp/collagen-local") / remote_path.removeprefix("/mnt/efs/")

    # Create parent directory
    local_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"📥 Fetching from EC2...")
    print(f"   Remote: {remote_path}")
    print(f"   Local:  {local_path}")
    print()

    # Use scp
    cmd = [
        "scp",
        "-i", str(SSH_KEY),
        "-o", "StrictHostKeyChecking=no",
        f"{EC2_USER}@{EC2_HOST}:{remote_path}",
        str(local_path)
    ]

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"❌ Failed to fetch file")
        sys.exit(1)

    print()
    print(f"✅ File saved to: {local_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: ./tools/fetch_from_ec2.py <remote_path>")
        print("Example: ./tools/fetch_from_ec2.py /mnt/efs/test_prototype/collages/20251023T152825Z,20=5x4/4096.jpg")
        sys.exit(1)

    fetch_file(sys.argv[1])
