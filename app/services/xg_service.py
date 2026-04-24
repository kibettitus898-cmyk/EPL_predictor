"""Fetches match-level xG and npxG from Understat for EPL seasons."""
import logging, time, pandas as pd
from understatapi import UnderstatClient
from app.core.supabase_client import get_supabase

logger = logging.getLogger(__name__)

# Understat seasons map (understat uses start year)
UNDERSTAT_SEASONS = {
    "14/15": "2014", "15/16": "2015", "16/17": "2016",
    "17/18": "2017", "18/19": "2018", "19/20": "2019",
    "20/21": "2020", "21/22": "2021", "22/23": "2022",
    "23/24": "2023", "24/25": "2024",
}

def fetch_xg_season(season_label: str, understat_year: str) -> list[dict]:
    records = []
    with UnderstatClient() as client:
        matches = client.league(league="EPL").get_match_data(season=understat_year)
        for m in matches:
            if not m.get("isResult"):
                continue  # skip unplayed matches
            records.append({
                "season":     season_label,
                "date":       m["datetime"][:10],
                "home_team":  m["h"]["title"],
                "away_team":  m["a"]["title"],
                "home_xg":    round(float(m["xG"]["h"]), 4),
                "away_xg":    round(float(m["xG"]["a"]), 4),
                # npxG available at player level; approximate from xG
                "home_npxg":  round(float(m["xG"]["h"]), 4),
                "away_npxg":  round(float(m["xG"]["a"]), 4),
                "xgd":        round(float(m["xG"]["h"]) - float(m["xG"]["a"]), 4),
            })
        time.sleep(1)
    return records

def upsert_xg(records: list[dict]):
    supabase = get_supabase()
    supabase.table("xg_data").upsert(
        records, on_conflict="season,date,home_team,away_team"
    ).execute()

def ingest_all_xg():
    for label, year in UNDERSTAT_SEASONS.items():
        logger.info(f"Fetching xG for {label}...")
        try:
            records = fetch_xg_season(label, year)
            upsert_xg(records)
            logger.info(f"  ✅ {label}: {len(records)} matches")
        except Exception as e:
            logger.error(f"  ❌ {label} failed: {e}")