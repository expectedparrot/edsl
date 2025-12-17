-- schema.sql

-- Main list registry
CREATE TABLE scenario_lists (
    id INTEGER PRIMARY KEY,
    current_version INTEGER NOT NULL DEFAULT 0
);

-- Scenarios with version tracking and digest for stable identification
CREATE TABLE scenarios (
    list_id INTEGER,
    position INTEGER,
    digest TEXT NOT NULL,  -- Content hash of original payload (stable ID)
    version_added INTEGER NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY (list_id, position)
);

-- Index for digest-based lookups
CREATE INDEX idx_scenarios_digest ON scenarios(list_id, digest);

-- Versioned meta (renames, drops) - each mutation creates a new row
CREATE TABLE scenario_list_meta (
    list_id INTEGER,
    version INTEGER,
    meta TEXT NOT NULL,
    PRIMARY KEY (list_id, version)
);

-- Versioned overrides - keyed by digest (stable ID), not position
CREATE TABLE scenario_list_overrides (
    list_id INTEGER,
    digest TEXT NOT NULL,  -- References scenarios.digest
    version INTEGER,
    payload TEXT NOT NULL,
    PRIMARY KEY (list_id, digest, version)
);

-- Lightweight history log (operation metadata only, not full payloads)
CREATE TABLE scenario_list_history (
    list_id INTEGER,
    version INTEGER,
    method_name TEXT NOT NULL,
    args TEXT NOT NULL,      -- JSON: lightweight args (no large data)
    kwargs TEXT NOT NULL,    -- JSON: lightweight kwargs
    PRIMARY KEY (list_id, version)
);

-- Optional snapshots for faster reconstruction
CREATE TABLE scenario_list_snapshots (
    list_id INTEGER,
    version INTEGER,
    scenarios TEXT NOT NULL,  -- JSON array of materialized scenarios
    meta TEXT NOT NULL,       -- JSON meta at this version
    PRIMARY KEY (list_id, version)
);
