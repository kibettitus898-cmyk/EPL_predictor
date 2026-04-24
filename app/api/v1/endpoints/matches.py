from fastapi import APIRouter, HTTPException
from app.core.supabase_client import get_supabase

router = APIRouter()

@router.get("/matches")
def get_matches(season: str | None = None, limit: int = 50):
    supabase = get_supabase()
    query = supabase.table("match_results").select("*").limit(limit)
    if season:
        query = query.eq("season", season)
    result = query.execute()
    return {"count": len(result.data), "data": result.data}

@router.get("/matches/seasons")
def get_seasons():
    supabase = get_supabase()
    result = supabase.table("match_results").select("season").execute()
    seasons = sorted(set(r["season"] for r in result.data))
    return {"seasons": seasons}
