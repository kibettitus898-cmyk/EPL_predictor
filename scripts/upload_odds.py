"""
Reads B365 odds from football-data CSVs and updates match_results in Supabase.
Matches rows by date + home_team + away_team.
"""
import sys, os, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from pathlib import Path
from app.core.supabase_client import get_supabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Point this at your raw CSV folder ────────────────────────────────────────
CSV_DIR = Path("data/raw/seasons")   # adjust if your CSVs are elsewhere

TEAM_NAME_MAP = {
    "Manchester City":         "Man City",
    "Manchester United":       "Man United",
    "Newcastle United":        "Newcastle",
    "West Ham United":         "West Ham",
    "Wolverhampton Wanderers": "Wolves",
    "Nottingham Forest":       "Nott'm Forest",
    "Tottenham Hotspur":       "Tottenham",
    "Brighton & Hove Albion":  "Brighton",
    "Sheffield Utd":           "Sheffield United",
    "Nott'ham Forest":         "Nott'm Forest",
    "Leicester City":          "Leicester",
    "Leeds United":            "Leeds",
}

def load_csvs() -> pd.DataFrame:
    frames = []
    for csv_file in sorted(CSV_DIR.glob("*.csv")):
        try:
            df = pd.read_csv(csv_file, encoding="latin-1", low_memory=False)
            # Normalise column names to lowercase
            df.columns = df.columns.str.strip().str.lower()
            if "b365h" not in df.columns:
                logger.warning(f"  {csv_file.name} — no B365 cols, skipping")
                continue
            needed = ["date", "hometeam", "awayteam", "b365h", "b365d", "b365a"]
            missing = [c for c in needed if c not in df.columns]
            if missing:
                logger.warning(f"  {csv_file.name} — missing {missing}, skipping")
                continue
            df = df[needed].copy()
            df = df.rename(columns={"hometeam": "home_team", "awayteam": "away_team"})
            df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
            df = df.dropna(subset=["date", "b365h"])
            df["home_team"] = df["home_team"].replace(TEAM_NAME_MAP)
            df["away_team"] = df["away_team"].replace(TEAM_NAME_MAP)
            frames.append(df)
            logger.info(f"  ✅ {csv_file.name} — {len(df)} rows with odds")
        except Exception as e:
            logger.error(f"  ❌ {csv_file.name} — {e}")
    if not frames:
        raise ValueError("No CSVs with B365 odds found in data/raw/")
    return pd.concat(frames, ignore_index=True)


def upload_odds(df: pd.DataFrame) -> None:
    supabase = get_supabase()
    updated  = 0
    skipped  = 0

    for _, row in df.iterrows():
        date_str = row["date"].strftime("%Y-%m-%d")
        try:
            result = (
                supabase.table("match_results")
                .update({
                    "b365h": float(row["b365h"]),
                    "b365d": float(row["b365d"]),
                    "b365a": float(row["b365a"]),
                })
                .eq("date",      date_str)
                .eq("home_team", row["home_team"])
                .eq("away_team", row["away_team"])
                .execute()
            )
            if result.data:
                updated += 1
            else:
                skipped += 1
        except Exception as e:
            logger.warning(f"  Row {date_str} {row['home_team']} v {row['away_team']}: {e}")

    logger.info(f"\n  ✅ Updated : {updated} rows")
    logger.info(f"  ⚠️  Skipped : {skipped} rows (no match found)")


if __name__ == "__main__":
    logger.info("Loading odds from CSVs...")
    odds_df = load_csvs()
    logger.info(f"Total rows with odds: {len(odds_df)}")
    logger.info("Uploading to Supabase...")
    upload_odds(odds_df)
    logger.info("Done — re-run build_features.py to regenerate parquet")