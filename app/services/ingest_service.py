"""
Loads raw CSV seasons from football-data.co.uk, cleans them,
applies time-decay weights, and upserts into Supabase match_results table.
"""
import logging
import math
import pandas as pd
import requests
from io import StringIO
from datetime import datetime
from app.core.supabase_client import get_supabase

logger = logging.getLogger(__name__)

SEASONS = [
    "1011","1112","1213","1314","1415","1516",
    "1617","1718","1819","1920","2021","2122","2223","2324","2425",
]
BASE_URL = "https://www.football-data.co.uk/mmz4281/{season}/E0.csv"

COLUMN_MAP = {
    "Date": "date", "HomeTeam": "home_team", "AwayTeam": "away_team",
    "FTR": "ftr", "FTHG": "fthg", "FTAG": "ftag",
    "HTHG": "hthg", "HTAG": "htag",
    "HS": "hs", "AS": "as_", "HST": "hst", "AST": "ast",
    "HC": "hc", "AC": "ac", "HY": "hy", "AY": "ay",
    "HR": "hr", "AR": "ar", "Referee": "referee","HF": "hf","AF": "af",
}

def _get_season_label(season_code: str) -> str:
    """'2425' → '24/25'"""
    return f"{season_code[:2]}/{season_code[2:]}"

def _time_weight(season_code: str, total: int) -> float:
    idx = SEASONS.index(season_code)
    return round(math.exp(-0.15 * (total - 1 - idx)), 4)

def fetch_season(season_code: str) -> pd.DataFrame:
    url = BASE_URL.format(season=season_code)
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    df = pd.read_csv(StringIO(response.text), on_bad_lines="skip")
    return df

def clean_season(df: pd.DataFrame, season_code: str) -> pd.DataFrame:
    df = df.rename(columns=COLUMN_MAP)
    df = df[[c for c in COLUMN_MAP.values() if c in df.columns]]
    df["season"] = _get_season_label(season_code)
    df["time_weight"] = _time_weight(season_code, len(SEASONS))
    df["date"] = pd.to_datetime(df["date"], format="mixed", dayfirst=True, errors="coerce")
    df = df.dropna(subset=["date", "home_team", "away_team"])
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")

    # ── FIX: Cast integer columns using pandas nullable Int64 dtype ──
    int_cols = [
        "fthg", "ftag", "hthg", "htag",
        "hs", "as_", "hst", "ast",
        "hc", "ac", "hy", "ay", "hr", "ar", "hf", "af"
    ]
    for col in int_cols:
        if col in df.columns:
            # pd.Int64Dtype() preserves NaN as pd.NA (not float NaN)
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    # Convert pd.NA → None so JSON serializer sends null (not NaN)
    df = df.where(pd.notna(df), other=None)

    # ── FIX: Convert Int64 columns to Python native int/None for JSON ──
    for col in int_cols:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: int(x) if pd.notna(x) and x is not None else None
            )

    return df

def upsert_season(df: pd.DataFrame):
    supabase = get_supabase()
    records = df.to_dict(orient="records")
    supabase.table("match_results").upsert(records, on_conflict="season,date,home_team,away_team").execute()
    logger.info(f"Upserted {len(records)} rows")

def ingest_all():
    for code in SEASONS:
        logger.info(f"Ingesting season {code}...")
        try:
            raw = fetch_season(code)
            clean = clean_season(raw, code)
            upsert_season(clean)
            logger.info(f"  ✅ {code}: {len(clean)} matches")
        except Exception as e:
            logger.error(f"  ❌ {code} failed: {e}")
