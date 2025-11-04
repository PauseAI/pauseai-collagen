#!/usr/bin/env python3
"""
Select A/B test sample: 40 not-yet-emailed users (20 per variant).

Creates scripts/ab_test_sample.txt with email addresses.
"""

import argparse
import os
import random
import sqlite3
import sys
from pathlib import Path

# Add lib/ to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
from tracking import TrackingDB


def select_sample(campaign: str, data_dir: str, sample_size_per_variant: int, seed: int, experiment):
    """
    Select random sample of not-yet-emailed users, stratified by A/B variant.

    Args:
        campaign: Campaign name
        data_dir: Data directory
        sample_size_per_variant: Number of users per variant
        seed: Random seed for reproducibility
        experiment: Experiment object for variant assignment

    Returns:
        List of email addresses (sorted by variant then created_at)
    """
    db = TrackingDB(campaign, data_dir)
    conn = sqlite3.connect(db.db_path)
    conn.row_factory = sqlite3.Row

    # Get all not-yet-emailed users
    cursor = conn.execute('''
        SELECT email, created_at
        FROM users
        WHERE emailed_at IS NULL
        ORDER BY created_at
    ''')

    all_users = [dict(row) for row in cursor.fetchall()]
    print(f"Found {len(all_users)} not-yet-emailed users")

    # Split by variant
    variant_users = {'control': [], 'treatment': []}
    for user in all_users:
        variant = experiment.get_variant(user['email'])
        variant_users[variant].append(user)

    print(f"  Control (consonant):  {len(variant_users['control'])} users")
    print(f"  Treatment (vowel):    {len(variant_users['treatment'])} users")

    # Check if we have enough users
    for variant in ['control', 'treatment']:
        if len(variant_users[variant]) < sample_size_per_variant:
            print(f"\n⚠️  WARNING: Only {len(variant_users[variant])} {variant} users available")
            print(f"   Requested {sample_size_per_variant} per variant")
            print(f"   Consider reducing sample size or sending more collage invites first")
            sys.exit(1)

    # Random sample from each variant
    random.seed(seed)
    sample = []

    for variant in ['control', 'treatment']:
        variant_sample = random.sample(variant_users[variant], sample_size_per_variant)
        # Sort by created_at to show time distribution
        variant_sample.sort(key=lambda u: u['created_at'])
        sample.extend(variant_sample)

        print(f"\n{variant.upper()} sample time range:")
        print(f"  Earliest: {variant_sample[0]['created_at']}")
        print(f"  Latest:   {variant_sample[-1]['created_at']}")

    return [u['email'] for u in sample]


def main():
    parser = argparse.ArgumentParser(
        description="Select A/B test sample of not-yet-emailed users",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("campaign", help="Campaign name (e.g. sayno)")
    parser.add_argument(
        "--experiment",
        required=True,
        help="Experiment number (e.g. '1') or ID (e.g. 'X001_CTAS_ABOVE_COLLAGE')"
    )
    parser.add_argument(
        "-n", "--per-variant",
        type=int,
        default=20,
        help="Number of users per variant (default: 20)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)"
    )
    parser.add_argument(
        "--data-dir",
        default=os.environ.get("COLLAGEN_DATA_DIR", "/mnt/efs"),
        help="Data directory (default: $COLLAGEN_DATA_DIR or /mnt/efs)"
    )

    args = parser.parse_args()

    # Get experiment and output path
    from experiments import get_experiment
    try:
        experiment = get_experiment(args.experiment)
        output_path = experiment.get_sample_path(Path(__file__).parent)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    print(f"Selecting A/B test sample for experiment: {experiment.name}")
    print(f"Campaign: {args.campaign}")
    print(f"Target: {args.per_variant} users per variant ({args.per_variant * 2} total)")
    print(f"Output: {output_path}")
    print()

    # Select sample using experiment's assignment function
    sample_emails = select_sample(
        args.campaign,
        args.data_dir,
        args.per_variant,
        args.seed,
        experiment
    )

    # Write to output file
    with open(output_path, 'w') as f:
        for email in sample_emails:
            f.write(f"{email}\n")

    print(f"\n✓ Wrote {len(sample_emails)} email addresses to: {output_path}")
    print()
    print("Next steps:")
    print(f"  1. Review: cat {output_path}")
    print(f"  2. Copy to allowlist: cp {output_path} {output_path.parent / 'allowlist_emails.txt'}")
    print(f"  3. Send emails: ./scripts/send_notifications.py {args.campaign} BUILD_ID")


if __name__ == "__main__":
    main()
