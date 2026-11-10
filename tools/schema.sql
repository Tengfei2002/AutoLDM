PRAGMA user_version=1;
CREATE TABLE IF NOT EXISTS runs (
 run_id TEXT PRIMARY KEY, profile_id TEXT NOT NULL, profile_version TEXT NOT NULL,
 started_at TEXT NOT NULL, finished_at TEXT, status TEXT NOT NULL,
 directory TEXT NOT NULL, manifest_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS stages (
 run_id TEXT REFERENCES runs(run_id), name TEXT, returncode INTEGER,
 status TEXT, log TEXT, PRIMARY KEY(run_id,name)
);
CREATE TABLE IF NOT EXISTS artifacts (
 artifact_id INTEGER PRIMARY KEY, run_id TEXT REFERENCES runs(run_id),
 path TEXT NOT NULL, bytes INTEGER NOT NULL, sha256 TEXT NOT NULL,
 UNIQUE(run_id,path)
);
CREATE TABLE IF NOT EXISTS measurements (
 measurement_id INTEGER PRIMARY KEY, run_id TEXT REFERENCES runs(run_id),
 source TEXT, row_number INTEGER, payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS configuration_packages (
 id TEXT, version TEXT, manifest_path TEXT, payload TEXT NOT NULL,
 PRIMARY KEY(id,version)
);
CREATE TABLE IF NOT EXISTS legacy_collections (
 collection_id TEXT PRIMARY KEY, category TEXT NOT NULL, relative_path TEXT NOT NULL,
 file_count INTEGER, logical_bytes INTEGER, review_status TEXT NOT NULL,
 provenance TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS legacy_records (
 collection_id TEXT REFERENCES legacy_collections(collection_id), source TEXT,
 row_number INTEGER, payload TEXT NOT NULL,
 PRIMARY KEY(collection_id,source,row_number)
);
CREATE INDEX IF NOT EXISTS runs_profile ON runs(profile_id,started_at);
