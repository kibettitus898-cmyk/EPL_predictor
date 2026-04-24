"""
Scrapes current EPL injury & suspension data from Transfermarkt
using transfermarkt-wrapper (unofficial API — no key required).
Refreshed before each matchday.
"""
import logging, time, requests
from datetime import date
from app.core.supabase_client import get_supabase

logger = logging.getLogger(__name__)

TM_BASE = "https://transfermarkt-api.fly.dev"

# Transfermarkt competition ID for EPL
EPL_COMP_ID = "GB1"

def fetch_current_injuries() -> list[dict]:
    """
    Calls the Transfermarkt public API wrapper for live EPL injuries.
    Returns list of {player_name, team, injury_reason, games_missed, return_date}
    """
    try:
        url = f"{TM_BASE}/competitions/{EPL_COMP_ID}/injuries"
        r   = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()

        records = []
        today   = date.today().isoformat()

        for player in data.get("injuries", []):
            records.append({
                "fetched_date":  today,
                "player_name":   player.get("playerName", "Unknown"),
                "team":          player.get("clubName", "Unknown"),
                "injury_reason": player.get("type", "Unknown"),
                "games_missed":  player.get("gamesMissed") or 0,
                "return_date":   player.get("expectedReturn", "Unknown"),
            })
        return records

    except Exception as e:
        logger.error(f"Transfermarkt injury fetch failed: {e}")
        return []

def upsert_injuries(records: list[dict]):
    if not records:
        logger.warning("No injury records — skipping upsert")
        return
    supabase = get_supabase()
    supabase.table("player_injuries").upsert(
        records, on_conflict="fetched_date,player_name,team"
    ).execute()
    logger.info(f"Upserted {len(records)} injury records")

def get_team_injury_count(team: str) -> dict:
    """
    Returns injury/suspension summary for a team as of today.
    Used by prediction endpoint to build pre-match features.
    """
    supabase = get_supabase()
    today    = date.today().isoformat()
    result   = (
        supabase.table("player_injuries")
        .select("injury_reason, games_missed")
        .eq("team", team)
        .eq("fetched_date", today)
        .execute()
    )
    players = result.data
    injured    = sum(1 for p in players if "suspend" not in p.get("injury_reason","").lower())
    suspended  = sum(1 for p in players if "suspend"     in p.get("injury_reason","").lower())
    return {
        "injured_count":   injured,
        "suspended_count": suspended,
        "total_missing":   injured + suspended,
    }

def ingest_live_injuries():
    logger.info("Fetching live EPL injuries from Transfermarkt...")
    records = fetch_current_injuries()
    upsert_injuries(records)
    logger.info(f"✅ {len(records)} injury records saved for today")
    return len(records)