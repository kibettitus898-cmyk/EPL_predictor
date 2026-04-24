"""
Derives squad availability (injured + suspended count) per team
before each matchday and stores it for use as a training feature.
"""
import logging
from datetime import date
from app.core.supabase_client import get_supabase
from app.services.transfermarkt_service import get_team_injury_count

logger = logging.getLogger(__name__)

EPL_TEAMS = [
    "Arsenal", "Aston Villa", "Bournemouth", "Brentford", "Brighton",
    "Chelsea", "Crystal Palace", "Everton", "Fulham", "Ipswich Town",
    "Leicester City", "Liverpool", "Manchester City", "Manchester United",
    "Newcastle United", "Nottingham Forest", "Southampton", "Tottenham",
    "West Ham United", "Wolverhampton",
]

def build_squad_availability_snapshot():
    """
    Call this before each matchday (e.g. via /pipeline/refresh endpoint).
    Saves injury counts for all 20 EPL teams into squad_availability table.
    """
    supabase = get_supabase()
    today    = date.today().isoformat()
    records  = []

    for team in EPL_TEAMS:
        counts = get_team_injury_count(team)
        records.append({
            "date":             today,
            "team":             team,
            "injured_count":    counts["injured_count"],
            "suspended_count":  counts["suspended_count"],
            "total_missing":    counts["total_missing"],
        })

    if records:
        supabase.table("squad_availability").upsert(
            records, on_conflict="date,team"
        ).execute()
        logger.info(f"✅ Squad availability snapshot saved for {today}")
    return records

def get_availability_feature(team: str, match_date: str) -> int:
    """
    Looks up total_missing for a team on or before a given date.
    Returns 0 if no data available (safe default).
    """
    supabase = get_supabase()
    result   = (
        supabase.table("squad_availability")
        .select("total_missing")
        .eq("team", team)
        .lte("date", match_date)
        .order("date", desc=True)
        .limit(1)
        .execute()
    )
    if result.data:
        return result.data[0]["total_missing"]
    return 0