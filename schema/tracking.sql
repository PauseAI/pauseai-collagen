-- Collagen User Tracking Schema
-- Location: /mnt/efs/{campaign}/tracking.db
-- One database per campaign (test_prototype, sayno, etc.)

-- User records: created at collage publish time
CREATE TABLE users (
    uid TEXT PRIMARY KEY,              -- 8-char base58 UID (non-guessable)
    email TEXT UNIQUE NOT NULL,        -- Unique email per campaign
    emailed_at TEXT,                   -- ISO8601: when collagen email sent
    opened_at TEXT,                    -- ISO8601: when tracking pixel loaded (idempotent)
    validated_at TEXT,                 -- ISO8601: when they clicked any link (idempotent)
    subscribed_at TEXT,                -- ISO8601: when they clicked subscribe (idempotent, NULL = validated only)
    created_at TEXT NOT NULL,          -- ISO8601: when user record created
    updated_at TEXT NOT NULL           -- ISO8601: last update
);

-- Collage participation: which collages does this user appear in?
CREATE TABLE collages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uid TEXT NOT NULL,
    build_id TEXT NOT NULL,            -- e.g. "20251024T230728Z,266=19x14"
    row INTEGER NOT NULL,              -- 0-based row position in grid
    col INTEGER NOT NULL,              -- 0-based col position in grid
    FOREIGN KEY (uid) REFERENCES users(uid) ON DELETE CASCADE
);

-- Indexes for fast lookups
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_collages_uid ON collages(uid);
CREATE INDEX idx_collages_build ON collages(build_id);

-- Derived states (computed from timestamps):
-- Uncontacted: No record exists OR emailed_at IS NULL
-- Emailed: emailed_at IS NOT NULL
-- Opened: opened_at IS NOT NULL
-- Validated: validated_at IS NOT NULL (user confirmed email via either link)
-- Subscribed: subscribed_at IS NOT NULL (user wants newsletter)
