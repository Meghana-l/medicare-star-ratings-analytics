-- Normalized tables. Both the demo generator and the CMS ingest load into these.

DROP VIEW IF EXISTS overall_calc;
DROP VIEW IF EXISTS gap_to_next;
DROP VIEW IF EXISTS calc;
DROP TABLE IF EXISTS meta;
DROP TABLE IF EXISTS summary;
DROP TABLE IF EXISTS cutpoints;
DROP TABLE IF EXISTS scores;
DROP TABLE IF EXISTS measures;
DROP TABLE IF EXISTS contracts;

CREATE TABLE contracts (
  contract_id TEXT PRIMARY KEY,
  name        TEXT,
  org_type    TEXT
);

CREATE TABLE measures (
  measure_id       TEXT PRIMARY KEY,
  name             TEXT NOT NULL,
  source           TEXT,               -- HEDIS | CAHPS | HOS | Admin | Part D
  part             TEXT,               -- C or D
  weight           REAL,               -- Star Ratings measure weight
  higher_is_better INTEGER DEFAULT 1,
  definition       TEXT,
  numerator        TEXT,
  denominator      TEXT,
  exclusions       TEXT
);

CREATE TABLE scores (
  contract_id TEXT NOT NULL,
  measure_id  TEXT NOT NULL,
  score       REAL,                    -- raw measure score (NULL = not reported / not enough data)
  cms_star    REAL,                    -- star CMS published for this measure
  PRIMARY KEY (contract_id, measure_id)
);

-- t2..t5 = cut points. Higher-is-better: score >= t_k earns k stars.
-- Lower-is-better: score < t_k earns k stars (t5 < t4 < t3 < t2).
CREATE TABLE cutpoints (
  year       INTEGER NOT NULL,
  measure_id TEXT NOT NULL,
  t2 REAL, t3 REAL, t4 REAL, t5 REAL,
  PRIMARY KEY (year, measure_id)
);

CREATE TABLE summary (
  contract_id TEXT PRIMARY KEY,
  cms_overall REAL
);

CREATE TABLE meta (
  key   TEXT PRIMARY KEY,
  value TEXT
);
