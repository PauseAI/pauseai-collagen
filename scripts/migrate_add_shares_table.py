#!/usr/bin/env python3
"""
Migration: Add shares table to existing tracking databases.

This migration adds the shares table to test_prototype and sayno campaign databases.
"""

import sqlite3
import sys
from pathlib import Path

# Add lib/ to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

DATA_DIR = "/mnt/efs"
CAMPAIGNS = ["test_prototype", "sayno"]

MIGRATION_SQL = """
-- Social shares: track when users share on social platforms
CREATE TABLE IF NOT EXISTS shares (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uid TEXT NOT NULL,
    platform TEXT NOT NULL,
    shared_at TEXT NOT NULL,
    FOREIGN KEY (uid) REFERENCES users(uid) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_shares_uid ON shares(uid);
CREATE INDEX IF NOT EXISTS idx_shares_platform ON shares(platform);
"""

def migrate_campaign(campaign: str, data_dir: str = DATA_DIR):
    """Add shares table to a campaign database."""
    db_path = Path(data_dir) / campaign / "tracking.db"

    if not db_path.exists():
        print(f"⚠️  Database not found: {db_path}")
        return False

    print(f"Migrating {campaign} database...")

    with sqlite3.connect(db_path) as conn:
        # Check if table already exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='shares'"
        )
        if cursor.fetchone():
            print(f"  ✓ shares table already exists")
            return True

        # Run migration
        conn.executescript(MIGRATION_SQL)
        print(f"  ✓ shares table created")

        # Verify
        cursor = conn.execute("SELECT COUNT(*) FROM shares")
        count = cursor.fetchone()[0]
        print(f"  ✓ Verified: {count} share records")

    return True

def main():
    print("=== Add shares table migration ===\n")

    success_count = 0
    for campaign in CAMPAIGNS:
        if migrate_campaign(campaign):
            success_count += 1
        print()

    print(f"Migration complete: {success_count}/{len(CAMPAIGNS)} campaigns migrated")

if __name__ == "__main__":
    main()
