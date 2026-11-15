PRAGMA foreign_keys = ON;

-- Replaces Firebase Auth users + /groups/admins + /access/{read,write}
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,               -- Firebase UID is kept on import
    email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT,                           -- NULL = imported user without a password yet
    display_name  TEXT,
    photo_url     TEXT,
    is_admin      INTEGER NOT NULL DEFAULT 0,
    can_read      INTEGER NOT NULL DEFAULT 0,
    can_write     INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL
);

-- Replaces /projects
CREATE TABLE IF NOT EXISTS projects (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    year       TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Replaces /project-data/{pid}/data/{fid} and the /projects/{pid}/data/{fid} title references
CREATE TABLE IF NOT EXISTS layers (
    id         TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title      TEXT NOT NULL,
    content    TEXT NOT NULL,                     -- GeoJSON as text
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_layers_project ON layers(project_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
