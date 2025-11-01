#!/usr/bin/env python3
"""
One-time script to deduplicate shares for a specific user.

Applies 60-second window deduplication retroactively to existing share records.
Keeps the earliest share in each 60s window per uid+platform.

Usage: ./dedupe_user_shares.py <campaign> <uid>
"""

import sys
import sqlite3
from pathlib import Path
from datetime import datetime

def dedupe_user_shares(campaign: str, uid: str, data_dir: Path):
    """Deduplicate shares for a specific user, keeping first in each 60s window per platform."""

    db_path = data_dir / campaign / "tracking.db"

    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Get user email for display
    cursor = conn.execute('SELECT email FROM users WHERE uid = ?', (uid,))
    user = cursor.fetchone()
    if not user:
        print(f"Error: User {uid} not found")
        sys.exit(1)

    email = user['email']
    print(f"Deduplicating shares for {email} (UID: {uid})")
    print()

    # Get all shares for this user, ordered by platform and timestamp
    cursor = conn.execute('''
        SELECT id, platform, shared_at
        FROM shares
        WHERE uid = ?
        ORDER BY platform, shared_at
    ''', (uid,))

    shares = cursor.fetchall()
    total_shares = len(shares)
    print(f"Total shares before dedup: {total_shares}")

    # Track which rowids to delete
    to_delete = []

    # Process shares grouped by platform
    last_kept = {}  # platform -> datetime

    for share in shares:
        share_id = share['id']
        platform = share['platform']
        shared_at = datetime.fromisoformat(share['shared_at'])

        if platform not in last_kept:
            # First share for this platform
            last_kept[platform] = shared_at
        else:
            # Check if within 60s of last kept share
            time_diff = (shared_at - last_kept[platform]).total_seconds()

            if time_diff < 60:
                # Duplicate - mark for deletion
                to_delete.append(share_id)
            else:
                # Outside window - keep this one, update last kept
                last_kept[platform] = shared_at

    print(f"Shares to delete (duplicates within 60s): {len(to_delete)}")
    print(f"Shares to keep: {total_shares - len(to_delete)}")

    if to_delete:
        # Show breakdown by platform
        cursor = conn.execute(f'''
            SELECT platform, COUNT(*) as count
            FROM shares
            WHERE id IN ({','.join('?' * len(to_delete))})
            GROUP BY platform
            ORDER BY count DESC
        ''', to_delete)

        print("\nDuplicates by platform:")
        for row in cursor:
            print(f"  {row['platform']}: {row['count']} duplicates")

        # Ask for confirmation
        response = input("\nProceed with deletion? (yes/no): ")

        if response.lower() == 'yes':
            # Delete duplicates
            cursor = conn.execute(f'''
                DELETE FROM shares
                WHERE id IN ({','.join('?' * len(to_delete))})
            ''', to_delete)

            conn.commit()
            print(f"\n✓ Deleted {cursor.rowcount} duplicate shares for {email}")

            # Show final stats for this user
            cursor = conn.execute('''
                SELECT platform, COUNT(*) as count
                FROM shares
                WHERE uid = ?
                GROUP BY platform
                ORDER BY count DESC
            ''', (uid,))

            print(f"\nFinal shares for {email}:")
            for row in cursor:
                print(f"  {row['platform']}: {row['count']}")
        else:
            print("Deletion cancelled")
    else:
        print("No duplicates found!")

    conn.close()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: ./dedupe_user_shares.py <campaign> <uid>")
        sys.exit(1)

    campaign = sys.argv[1]
    uid = sys.argv[2]

    # Use DATA_DIR from environment or default
    import os
    data_dir = Path(os.environ.get('COLLAGEN_DATA_DIR', '/mnt/efs'))

    dedupe_user_shares(campaign, uid, data_dir)
