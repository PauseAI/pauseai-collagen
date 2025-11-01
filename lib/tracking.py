"""
User tracking database utilities for Collagen.

Each campaign has its own tracking.db SQLite database at:
  /mnt/efs/{campaign}/tracking.db
"""

import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# Base58 alphabet (excludes ambiguous characters: 0O1Il)
BASE58 = '23456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz'


def generate_uid() -> str:
    """Generate a random 8-character base58 UID."""
    return ''.join(secrets.choice(BASE58) for _ in range(8))


def now_iso() -> str:
    """Return current UTC timestamp in ISO8601 format."""
    return datetime.now(timezone.utc).isoformat()


class TrackingDB:
    """Interface to campaign tracking database."""

    def __init__(self, campaign: str, data_dir: str = "/mnt/efs"):
        """
        Initialize tracking database for a campaign.

        Args:
            campaign: Campaign name (e.g. "sayno", "test_prototype")
            data_dir: Root data directory (default: /mnt/efs)
        """
        self.campaign = campaign
        self.db_path = Path(data_dir) / campaign / "tracking.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize database schema if it doesn't exist."""
        schema_path = Path(__file__).parent.parent / "schema" / "tracking.sql"

        with sqlite3.connect(self.db_path) as conn:
            # Check if tables exist
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
            )
            if cursor.fetchone() is None:
                # Create schema
                schema = schema_path.read_text()
                conn.executescript(schema)

    def record_participation(self, email: str, build_id: str, row: int, col: int) -> str:
        """
        Record a user's participation in a published collage.
        Creates user record if it doesn't exist, otherwise appends to existing user.

        Args:
            email: User's email address
            build_id: Collage build ID
            row: Row position in grid (0-based)
            col: Column position in grid (0-based)

        Returns:
            UID for this user (existing or newly created)
        """
        with sqlite3.connect(self.db_path) as conn:
            # Look up existing user
            cursor = conn.execute("SELECT uid FROM users WHERE email = ?", (email,))
            row_result = cursor.fetchone()

            if row_result:
                # User exists - use existing UID
                uid = row_result[0]
            else:
                # Create new user
                uid = generate_uid()
                timestamp = now_iso()
                conn.execute(
                    """
                    INSERT INTO users (uid, email, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (uid, email, timestamp, timestamp)
                )

            # Record collage participation
            conn.execute(
                """
                INSERT INTO collages (uid, build_id, row, col)
                VALUES (?, ?, ?, ?)
                """,
                (uid, build_id, row, col)
            )

        return uid

    def get_user_by_uid(self, uid: str) -> Optional[dict]:
        """Get user record by UID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM users WHERE uid = ?", (uid,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_user_by_email(self, email: str) -> Optional[dict]:
        """Get user record by email."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM users WHERE email = ?", (email,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def mark_emailed(self, uid: str) -> bool:
        """
        Mark user as emailed.

        Returns:
            True if updated, False if already set (idempotent)
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                UPDATE users
                SET emailed_at = ?, updated_at = ?
                WHERE uid = ? AND emailed_at IS NULL
                """,
                (now_iso(), now_iso(), uid)
            )
            return cursor.rowcount > 0

    def mark_opened(self, uid: str, event_time: Optional[datetime] = None) -> bool:
        """
        Mark user as opened (tracking pixel loaded).

        Args:
            uid: User UID
            event_time: When event occurred (defaults to now). Use SQS message timestamp for accuracy.

        Returns:
            True if updated, False if already set (idempotent)
        """
        event_ts = event_time.isoformat() if event_time else now_iso()
        updated_ts = now_iso()  # Metadata: when record was actually updated

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                UPDATE users
                SET opened_at = ?, updated_at = ?
                WHERE uid = ? AND opened_at IS NULL
                """,
                (event_ts, updated_ts, uid)
            )
            return cursor.rowcount > 0

    def mark_validated(self, uid: str, event_time: Optional[datetime] = None) -> bool:
        """
        Mark user as validated (clicked validate link).

        Args:
            uid: User UID
            event_time: When event occurred (defaults to now). Use SQS message timestamp for accuracy.

        Returns:
            True if updated, False if already set (idempotent)
        """
        event_ts = event_time.isoformat() if event_time else now_iso()
        updated_ts = now_iso()  # Metadata: when record was actually updated

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                UPDATE users
                SET validated_at = ?, updated_at = ?
                WHERE uid = ? AND validated_at IS NULL
                """,
                (event_ts, updated_ts, uid)
            )
            return cursor.rowcount > 0

    def mark_subscribed(self, uid: str, event_time: Optional[datetime] = None) -> bool:
        """
        Mark user as subscribed (clicked subscribe link).
        Also marks as validated.

        Args:
            uid: User UID
            event_time: When event occurred (defaults to now). Use SQS message timestamp for accuracy.

        Returns:
            True if updated, False if already set (idempotent)
        """
        event_ts = event_time.isoformat() if event_time else now_iso()
        updated_ts = now_iso()  # Metadata: when record was actually updated

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                UPDATE users
                SET validated_at = COALESCE(validated_at, ?),
                    subscribed_at = ?,
                    updated_at = ?
                WHERE uid = ? AND subscribed_at IS NULL
                """,
                (event_ts, event_ts, updated_ts, uid)
            )
            return cursor.rowcount > 0

    def record_share(self, uid: str, platform: str, event_time: Optional[datetime] = None):
        """
        Record a social share intent event.
        Tracks when user clicked share link and was redirected to social platform.
        Note: Does not confirm share was completed/posted.
        Allows multiple shares per user per platform over time.

        Args:
            uid: User UID
            platform: Platform name ('facebook', 'twitter', 'whatsapp', 'linkedin', 'reddit')
            event_time: When event occurred (defaults to now). Use SQS message timestamp for accuracy.
        """
        event_ts = event_time.isoformat() if event_time else now_iso()

        with sqlite3.connect(self.db_path) as conn:
            # Insert share record (no metadata fields, just event timestamp)
            conn.execute(
                """
                INSERT INTO shares (uid, platform, shared_at)
                VALUES (?, ?, ?)
                """,
                (uid, platform, event_ts)
            )

            # Update user's updated_at metadata (real clock, not event time)
            conn.execute(
                """
                UPDATE users
                SET updated_at = ?
                WHERE uid = ?
                """,
                (now_iso(), uid)
            )

    def get_user_collages(self, uid: str) -> list[dict]:
        """Get all collages this user appears in."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM collages WHERE uid = ? ORDER BY build_id",
                (uid,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_stats(self) -> dict:
        """Get campaign tracking statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT
                    COUNT(*) as total_users,
                    COUNT(emailed_at) as emailed,
                    COUNT(opened_at) as opened,
                    COUNT(validated_at) as validated,
                    COUNT(subscribed_at) as subscribed
                FROM users
                """
            )
            row = cursor.fetchone()
            return {
                'total_users': row[0],
                'emailed': row[1],
                'opened': row[2],
                'validated': row[3],
                'subscribed': row[4]
            }
