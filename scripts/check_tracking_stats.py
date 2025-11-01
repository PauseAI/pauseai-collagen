#!/usr/bin/env python3
"""
Check tracking database statistics for a campaign.
"""

import argparse
import os
import sys
from pathlib import Path

# Add lib/ to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
from tracking import TrackingDB


def main():
    parser = argparse.ArgumentParser(description="Check tracking database stats")
    parser.add_argument("campaign", help="Campaign name (e.g. test_prototype, sayno)")
    parser.add_argument("--email", help="Show detailed info for a specific email address")
    parser.add_argument(
        "--data-dir",
        default=os.environ.get("COLLAGEN_DATA_DIR", "/mnt/efs"),
        help="Data directory (default: $COLLAGEN_DATA_DIR or /mnt/efs)"
    )

    args = parser.parse_args()

    db = TrackingDB(args.campaign, args.data_dir)

    # If --email specified, show detailed info for that email
    if args.email:
        import sqlite3
        conn = sqlite3.connect(db.db_path)
        conn.row_factory = sqlite3.Row

        # Get user info
        cursor = conn.execute('SELECT * FROM users WHERE email = ?', (args.email,))
        user = cursor.fetchone()

        if not user:
            print(f"No user found with email: {args.email}")
            return

        # Get collage participation
        cursor = conn.execute('''
            SELECT build_id, row, col
            FROM collages
            WHERE uid = ?
            ORDER BY build_id
        ''', (user['uid'],))

        collages = [dict(c) for c in cursor.fetchall()]

        # Get share activity
        cursor = conn.execute('''
            SELECT platform, shared_at
            FROM shares
            WHERE uid = ?
            ORDER BY shared_at
        ''', (user['uid'],))

        shares = [dict(s) for s in cursor.fetchall()]

        # Build complete user record
        user_data = {
            'user': dict(user),
            'collages': collages,
            'shares': shares
        }

        import json
        print(json.dumps(user_data, indent=2))
        return

    # Overall stats
    stats = db.get_stats()
    print(f"=== {args.campaign} Tracking Stats ===")
    print(f"Total users:  {stats['total_users']}")
    print(f"Emailed:      {stats['emailed']}")
    print(f"Opened:       {stats['opened']}")
    print(f"Validated:    {stats['validated']}")
    print(f"Subscribed:   {stats['subscribed']}")

    # Connect to database for additional queries
    import sqlite3
    conn = sqlite3.connect(db.db_path)

    # Get share stats - show unique user+platform combinations
    cursor = conn.execute('SELECT COUNT(DISTINCT uid || "-" || platform) as unique_shares, COUNT(*) as total FROM shares')
    shares = cursor.fetchone()
    if shares[1] > 0:
        # Show unique users who shared
        cursor = conn.execute('SELECT COUNT(DISTINCT uid) FROM shares')
        unique_users = cursor.fetchone()[0]
        print(f"Shared:       {unique_users} users, {shares[0]} unique user+platform combinations ({shares[1]} total clicks)")

        # Breakdown by platform (show unique users per platform + total clicks)
        cursor = conn.execute('''
            SELECT platform, COUNT(DISTINCT uid) as users, COUNT(*) as clicks
            FROM shares
            GROUP BY platform
            ORDER BY users DESC, clicks DESC
        ''')
        platform_counts = cursor.fetchall()
        for platform, users, clicks in platform_counts:
            print(f"  - {platform}: {users} users ({clicks} clicks)")
    else:
        print(f"Shared:       0")

    print()

    # Check for duplicate emails (should always be unique)

    cursor = conn.execute('''
        SELECT email, COUNT(*) as count
        FROM users
        GROUP BY email
        HAVING count > 1
        ORDER BY count DESC
    ''')

    duplicates = cursor.fetchall()
    if duplicates:
        print("⚠️  WARNING: Duplicate emails found (this should not happen!):")
        for email, count in duplicates:
            print(f"  {count}x: {email}")
    else:
        print("✓ All emails are unique")

    print()

    # Show collage participation
    cursor = conn.execute('''
        SELECT build_id, COUNT(*) as users
        FROM collages
        GROUP BY build_id
        ORDER BY build_id DESC
    ''')

    collage_counts = cursor.fetchall()
    if collage_counts:
        print("Collage participation:")
        for build_id, users in collage_counts:
            print(f"  {build_id}: {users} users")


if __name__ == "__main__":
    main()
