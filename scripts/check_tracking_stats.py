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


def report_experiment_breakdown(conn, experiment, sample_file):
    """
    Report A/B test breakdown for an experiment.

    Args:
        conn: SQLite connection
        experiment: Experiment object
        sample_file: Path to ab_test_sample.txt file
    """
    from experiments import get_experiment

    with open(sample_file) as f:
        ab_sample_emails = {line.strip().lower() for line in f if line.strip()}

    print()
    print(f"=== A/B Test Breakdown: {experiment.name} ({len(ab_sample_emails)} sample users) ===")

    variant_stats = {
        'control': {'emailed': 0, 'opened': 0, 'validated': 0, 'subscribed': 0, 'shared': 0, 'share_uids': set()},
        'treatment': {'emailed': 0, 'opened': 0, 'validated': 0, 'subscribed': 0, 'shared': 0, 'share_uids': set()}
    }

    for sample_email in ab_sample_emails:
        cursor = conn.execute(
            'SELECT uid, emailed_at, opened_at, validated_at, subscribed_at FROM users WHERE email = ?',
            (sample_email,)
        )
        user = cursor.fetchone()
        if not user:
            continue

        uid, emailed_at, opened_at, validated_at, subscribed_at = user
        variant = experiment.get_variant(sample_email)

        if emailed_at:
            variant_stats[variant]['emailed'] += 1
        if opened_at:
            variant_stats[variant]['opened'] += 1
        if validated_at:
            variant_stats[variant]['validated'] += 1
        if subscribed_at:
            variant_stats[variant]['subscribed'] += 1

        # Check if user shared on any platform
        share_cursor = conn.execute(
            'SELECT COUNT(DISTINCT platform) FROM shares WHERE uid = ?',
            (uid,)
        )
        share_count = share_cursor.fetchone()[0]
        if share_count > 0:
            variant_stats[variant]['shared'] += 1
            variant_stats[variant]['share_uids'].add(uid)

    for variant in ['control', 'treatment']:
        v = variant_stats[variant]
        print(f"\n{variant.upper()} (email starts with {'consonant' if variant == 'control' else 'vowel'}):")
        print(f"  Emailed:    {v['emailed']}")
        print(f"  Opened:     {v['opened']}")

        # Calculate rates (relative to opened, since that's when they can act)
        if v['opened'] > 0:
            validated_rate = 100.0 * v['validated'] / v['opened']
            subscribed_rate = 100.0 * v['subscribed'] / v['opened']
            shared_rate = 100.0 * v['shared'] / v['opened']

            print(f"  Validated:  {v['validated']} ({validated_rate:.1f}% of opened)")
            print(f"  Subscribed: {v['subscribed']} ({subscribed_rate:.1f}% of opened)")
            print(f"  Shared:     {v['shared']} ({shared_rate:.1f}% of opened)")
        else:
            print(f"  Validated:  {v['validated']}")
            print(f"  Subscribed: {v['subscribed']}")
            print(f"  Shared:     {v['shared']}")

    # Summary comparison
    c = variant_stats['control']
    t = variant_stats['treatment']

    print(f"\n=== A/B Test Summary ===")
    if c['opened'] > 0 and t['opened'] > 0:
        c_share_rate = 100.0 * c['shared'] / c['opened']
        t_share_rate = 100.0 * t['shared'] / t['opened']

        print(f"Share rate comparison:")
        print(f"  Control:   {c_share_rate:.1f}% ({c['shared']}/{c['opened']})")
        print(f"  Treatment: {t_share_rate:.1f}% ({t['shared']}/{t['opened']})")

        if t_share_rate > c_share_rate:
            lift = t_share_rate - c_share_rate
            print(f"  → Treatment +{lift:.1f}pp higher share rate")
        elif c_share_rate > t_share_rate:
            drop = c_share_rate - t_share_rate
            print(f"  → Treatment -{drop:.1f}pp lower share rate")
        else:
            print(f"  → No difference")

    # Platform diversity (average platforms per sharer)
    if c['shared'] > 0 or t['shared'] > 0:
        print(f"\nPlatform diversity (avg platforms per sharer):")

        for variant in ['control', 'treatment']:
            v = variant_stats[variant]
            if v['shared'] > 0:
                # Get total platform count for these users
                uid_list = ','.join(f"'{uid}'" for uid in v['share_uids'])
                platform_cursor = conn.execute(
                    f'SELECT COUNT(DISTINCT platform) FROM shares WHERE uid IN ({uid_list})'
                )
                total_platforms = platform_cursor.fetchone()[0]
                avg_platforms = total_platforms / v['shared']
                print(f"  {variant.capitalize()}: {avg_platforms:.1f} platforms/user ({total_platforms} total platforms, {v['shared']} users)")
            else:
                print(f"  {variant.capitalize()}: N/A (no shares)")


def main():
    parser = argparse.ArgumentParser(description="Check tracking database stats")
    parser.add_argument("campaign", help="Campaign name (e.g. test_prototype, sayno)")
    parser.add_argument("--email", help="Show detailed info for a specific email address")
    parser.add_argument(
        "--experiment",
        help="Show A/B test breakdown for experiment (number like '1' or ID like 'X001_CTAS_ABOVE_COLLAGE')"
    )
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

    # A/B test breakdown (only if --experiment specified)
    if args.experiment:
        from experiments import get_experiment

        try:
            experiment = get_experiment(args.experiment)
            sample_file = experiment.get_sample_path(Path(__file__).parent)

            if not sample_file.exists():
                print()
                print(f"⚠️  Warning: Experiment sample file not found: {sample_file}")
                print(f"   Run ./scripts/select_ab_test_sample.py {args.campaign} --experiment {args.experiment}")
            else:
                report_experiment_breakdown(conn, experiment, sample_file)
        except ValueError as e:
            print()
            print(f"Error: {e}")

    print()

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
