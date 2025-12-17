-- schema.sql
CREATE TABLE scenario_lists (
    id INTEGER PRIMARY KEY,
    meta TEXT NOT NULL
);

CREATE TABLE scenarios (
    list_id INTEGER,
    position INTEGER,
    payload TEXT NOT NULL,
    PRIMARY KEY (list_id, position)
);

CREATE TABLE scenario_list_overrides (
    list_id INTEGER,
    position INTEGER,
    payload TEXT NOT NULL,
    PRIMARY KEY (list_id, position)
);
