-- Run this in your Supabase SQL editor to create the required table

CREATE TABLE IF NOT EXISTS match_results (
    id            BIGSERIAL PRIMARY KEY,
    season        TEXT NOT NULL,            -- e.g. "24/25"
    date          DATE NOT NULL,
    home_team     TEXT NOT NULL,
    away_team     TEXT NOT NULL,
    ftr           TEXT,                     -- "H" | "D" | "A"
    fthg          INTEGER,
    ftag          INTEGER,
    hthg          INTEGER,
    htag          INTEGER,
    hs            INTEGER,                  -- home shots
    as_           INTEGER,                  -- away shots
    hst           INTEGER,                  -- home shots on target
    ast           INTEGER,
    hc            INTEGER,                  -- home corners
    ac            INTEGER,
    hy            INTEGER,                  -- home yellows
    ay            INTEGER,
    hr            INTEGER,                  -- home reds
    ar            INTEGER,
    referee       TEXT,
    time_weight   FLOAT DEFAULT 1.0,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (season, date, home_team, away_team)
);

-- Index for fast team lookups
CREATE INDEX IF NOT EXISTS idx_match_home ON match_results(home_team);
CREATE INDEX IF NOT EXISTS idx_match_away ON match_results(away_team);
CREATE INDEX IF NOT EXISTS idx_match_season ON match_results(season);
CREATE INDEX IF NOT EXISTS idx_match_date ON match_results(date);
