#!/usr/bin/env python3
"""
Upload collage images to S3.

Uploads both the specific build_id version and updates the /latest/ symlink.
"""

import argparse
import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

# Add lib/ to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
from collage_generator import DERIVATIVE_SIZES


def upload_collage(campaign: str, build_id: str, data_dir: str = "/mnt/efs"):
    """
    Upload collage images to S3.

    Uploads all derivative sizes (from DERIVATIVE_SIZES):
      - {campaign}/{build_id}/{size}.jpg (specific version)
      - {campaign}/latest/{size}.jpg (latest version)

    Args:
        campaign: Campaign name (e.g. "sayno")
        build_id: Build ID (e.g. "20251024T230728Z,266=19x14")
        data_dir: Root data directory (default: /mnt/efs)
    """
    bucket_name = "pauseai-collagen"
    sizes = DERIVATIVE_SIZES

    # Source path
    collage_dir = Path(data_dir) / campaign / "collages" / build_id

    # Verify build directory exists
    if not collage_dir.exists():
        print(f"ERROR: Build directory not found: {collage_dir}", file=sys.stderr)
        sys.exit(1)

    # S3 client
    s3 = boto3.client('s3', region_name='us-east-1')

    # Upload all sizes
    for size in sizes:
        source_file = collage_dir / f"{size}.jpg"

        if not source_file.exists():
            print(f"WARNING: Skipping {size}.jpg (not found)", file=sys.stderr)
            continue

        # Upload specific build version
        build_key = f"{campaign}/{build_id}/{size}.jpg"
        print(f"Uploading to s3://{bucket_name}/{build_key}")

        try:
            s3.upload_file(
                str(source_file),
                bucket_name,
                build_key,
                ExtraArgs={
                    'ContentType': 'image/jpeg',
                    'CacheControl': 'public, max-age=31536000'  # 1 year (immutable)
                }
            )
            print(f"  ✓ Uploaded {build_key}")
        except ClientError as e:
            print(f"  ERROR: {e}", file=sys.stderr)
            sys.exit(1)

        # Upload latest version
        latest_key = f"{campaign}/latest/{size}.jpg"
        print(f"Uploading to s3://{bucket_name}/{latest_key}")

        try:
            s3.upload_file(
                str(source_file),
                bucket_name,
                latest_key,
                ExtraArgs={
                    'ContentType': 'image/jpeg',
                    'CacheControl': 'public, max-age=300'  # 5 minutes (can change)
                }
            )
            print(f"  ✓ Uploaded {latest_key}")
        except ClientError as e:
            print(f"  ERROR: {e}", file=sys.stderr)
            sys.exit(1)

    # Print public URLs
    print("\nPublic URLs:")
    for size in sizes:
        print(f"  {size}px:")
        print(f"    Specific: https://s3.amazonaws.com/{bucket_name}/{campaign}/{build_id}/{size}.jpg")
        print(f"    Latest:   https://s3.amazonaws.com/{bucket_name}/{campaign}/latest/{size}.jpg")


def main():
    parser = argparse.ArgumentParser(description="Upload collage to S3")
    parser.add_argument("campaign", help="Campaign name (e.g. sayno)")
    parser.add_argument("build_id", help="Build ID (e.g. 20251024T230728Z,266=19x14)")
    parser.add_argument(
        "--data-dir",
        default=os.environ.get("COLLAGEN_DATA_DIR", "/mnt/efs"),
        help="Data directory (default: $COLLAGEN_DATA_DIR or /mnt/efs)"
    )

    args = parser.parse_args()
    upload_collage(args.campaign, args.build_id, args.data_dir)


if __name__ == "__main__":
    main()
