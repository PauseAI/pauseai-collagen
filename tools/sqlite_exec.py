#!/usr/bin/env python3
"""
Execute SQLite commands on campaign tracking database.

Usage:
    ./tools/sqlite_exec.py test_prototype "UPDATE users SET emailed_at = NULL WHERE uid = 's6LLLEW4'"
    ./tools/sqlite_exec.py test_prototype "SELECT uid, email FROM users LIMIT 3"
"""

import sys
import sqlite3
import os
from pathlib import Path

DATA_DIR = os.environ.get("COLLAGEN_DATA_DIR", "/mnt/efs")

if len(sys.argv) != 3:
    print("Usage: ./tools/sqlite_exec.py <campaign> <sql>")
    sys.exit(1)

campaign, sql = sys.argv[1], sys.argv[2]
db_path = Path(DATA_DIR) / campaign / "tracking.db"

with sqlite3.connect(db_path) as conn:
    cursor = conn.execute(sql)

    if cursor.description:  # SELECT
        for row in cursor.fetchall():
            print(row)
    else:  # UPDATE/INSERT/DELETE
        print(f"{cursor.rowcount} row(s) affected")
