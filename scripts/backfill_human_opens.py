#!/usr/bin/env python3
"""
Backfill human opens from Lambda logs.

Replaces bot opens (within BOT_SECS of email send) with human opens (>BOT_SECS).
Uses Lambda logs which capture all tracking pixel loads before deduplication.
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

# Add lib/ to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
from tracking import TrackingDB, BOT_SECS

import argparse


def parse_lambda_logs(log_file: Path):
    """
    Parse Lambda logs to extract all open events.

    Returns:
        dict: {uid: [timestamp1, timestamp2, ...]} - all open event times per UID
    """
    with open(log_file) as f:
        data = json.load(f)

    uid_requests = defaultdict(list)

    for event in data.get('events', []):
        message = event.get('message', '')
        timestamp_ms = event.get('timestamp', 0)

        # Look for open events: /t/sayno/UID/BUILD_ID.jpg
        match = re.search(r'/t/sayno/(\w+)/[^/]+\.jpg', message)
        if match:
            uid = match.group(1)
            request_time = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
            uid_requests[uid].append(request_time)

    # Sort each UID's requests by time
    for uid in uid_requests:
        uid_requests[uid].sort()

    return dict(uid_requests)


def backfill_opens(campaign: str, lambda_logs: Path, data_dir: str = "/mnt/efs", dry_run: bool = False):
    """
    Backfill human opens from Lambda logs.

    For each user:
    - If they have opens >BOT_SECS in Lambda logs
    - And their current opened_at is ≤BOT_SECS (bot open)
    - Update to the first human open time
    """
    print(f"Parsing Lambda logs from {lambda_logs}...")
    uid_requests = parse_lambda_logs(lambda_logs)
    print(f"Found {len(uid_requests)} UIDs with open events in Lambda logs")
    print()

    db = TrackingDB(campaign, data_dir)

    # Get all users with emailed_at
    import sqlite3
    conn = sqlite3.connect(db.db_path)
    conn.row_factory = sqlite3.Row

    users = conn.execute('SELECT uid, emailed_at FROM users WHERE emailed_at IS NOT NULL').fetchall()
    user_times = {u['uid']: datetime.fromisoformat(u['emailed_at']) for u in users}

    print(f"Campaign {campaign}: {len(user_times)} users emailed")
    print()

    # Find users to update
    updates = []

    for uid, emailed_at in user_times.items():
        if uid not in uid_requests:
            continue

        # Get all open times for this user
        open_times = uid_requests[uid]

        # Separate bot vs human opens
        bot_opens = [t for t in open_times if (t - emailed_at).total_seconds() <= BOT_SECS]
        human_opens = [t for t in open_times if (t - emailed_at).total_seconds() > BOT_SECS]

        if not human_opens:
            continue  # No human opens to backfill

        # Get current opened_at from DB
        user = db.get_user_by_uid(uid)
        if not user or not user.get('opened_at'):
            # No current open - mark_opened will handle this normally
            continue

        current_opened = datetime.fromisoformat(user['opened_at'])
        current_seconds = (current_opened - emailed_at).total_seconds()

        if current_seconds <= BOT_SECS:
            # Current open is a bot open, and we have a human open to replace it with
            first_human_open = human_opens[0]
            updates.append((uid, user['email'], current_opened, first_human_open))

    print(f"Found {len(updates)} users with bot opens to replace with human opens")

    if not updates:
        print("No updates needed!")
        return

    if dry_run:
        print("\n[DRY RUN] Would update:")
        for uid, email, current, new in updates[:10]:
            print(f"  {uid} ({email}): {current} → {new}")
        if len(updates) > 10:
            print(f"  ... and {len(updates) - 10} more")
        return

    # Perform updates
    print("\nUpdating...")
    updated_count = 0

    for uid, email, current_opened, new_opened in updates:
        # Use mark_opened with the new time - it will update if current is within BOT_SECS
        if db.mark_opened(uid, new_opened):
            updated_count += 1
            print(f"✓ Updated {uid} ({email})")

    print()
    print(f"Updated {updated_count}/{len(updates)} users")


def main():
    parser = argparse.ArgumentParser(description="Backfill human opens from Lambda logs")
    parser.add_argument("campaign", help="Campaign name (e.g., sayno)")
    parser.add_argument("lambda_logs", help="Path to Lambda logs JSON file", type=Path)
    parser.add_argument("--data-dir", default="/mnt/efs", help="Data directory (default: /mnt/efs)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be updated without updating")

    args = parser.parse_args()

    if not args.lambda_logs.exists():
        print(f"Error: Lambda logs file not found: {args.lambda_logs}")
        sys.exit(1)

    backfill_opens(args.campaign, args.lambda_logs, args.data_dir, args.dry_run)


if __name__ == "__main__":
    main()
