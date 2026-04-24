"""
Loads the Kaggle football players stats CSV and ingests EPL squad data into Supabase.
Dataset: hubertsidorowicz/football-players-stats-2025-2026
"""
import logging
import pandas as pd
import numpy as np
from app.core.supabase_client import get_supabase

logger = logging.getLogger(__name__)

# Map CSV column names → our clean DB column names
# (adjust if your CSV uses different headers)
COLUMN_MAP = {
    "Player":                "player",
    "Squad":                 "squad",
    "Comp":                  "comp",
    "Nation":                "nation",
    "Pos":                   "pos",
    "Age":                   "age",
    "MP":                    "mp",
    "Starts":                "starts",
    "Min":                   "min",
    "Gls":                   "goals",
    "Ast":                   "assists",
    "Gls.1":                 "goals_per90",    # per90 version
    "Ast.1":                 "assists_per90",
    "xG":                    "xg",
    "xAG":                   "xag",
    "PrgC":                  "progressive_carries",
    "PrgP":                  "progressive_passes",
    "Tkl":                   "tackles",
    "Int":                   "interceptions",
    "B365H": "b365h",
    "B365D": "b365d",
    "B365A": "b365a",
}

EPL_COMP_NAMES = [
    "eng Premier League",
    "Premier League",
    "ENG-Premier League",
]

def load_and_clean(csv_path: str, season: str = "25/26") -> pd.DataFrame:
    df = pd.read_csv(csv_path, encoding="utf-8", on_bad_lines="skip")
    logger.info(f"Loaded {len(df)} rows, {len(df.columns)} columns from CSV")

    # Rename known columns
    rename = {k: v for k, v in COLUMN_MAP.items() if k in df.columns}
    df = df.rename(columns=rename)

    # Keep only columns we need
    keep = list(rename.values())
    df = df[[c for c in keep if c in df.columns]]

    # Add season
    df["season"] = season

    # Filter EPL only
    if "comp" in df.columns:
        epl_mask = df["comp"].str.contains("Premier League", case=False, na=False)
        df_epl = df[epl_mask].copy()
        logger.info(f"EPL players after filtering: {len(df_epl)}")
    else:
        df_epl = df.copy()
        logger.warning("No 'comp' column found — using all rows")

    # Clean numeric columns
    num_cols = ["age","mp","starts","min","goals","assists",
                "goals_per90","assists_per90","xg","xag",
                "progressive_carries","progressive_passes",
                "tackles","interceptions"]
    for col in num_cols:
        if col in df_epl.columns:
            df_epl[col] = pd.to_numeric(df_epl[col], errors="coerce")

    # Convert int columns
    int_cols = ["mp", "starts", "min", "progressive_carries", "progressive_passes"]
    for col in int_cols:
        if col in df_epl.columns:
            df_epl[col] = df_epl[col].apply(
                lambda x: int(x) if pd.notna(x) else None
            )

    # Drop rows with no player or squad
    df_epl = df_epl.dropna(subset=["player", "squad"])

    # Replace NaN with None for JSON serialization
    df_epl = df_epl.where(pd.notna(df_epl), None)

    return df_epl

def upsert_player_stats(df: pd.DataFrame):
    supabase = get_supabase()
    records  = df.to_dict(orient="records")

    # Batch upsert in chunks of 500
    batch_size = 500
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        supabase.table("player_stats").upsert(
            batch, on_conflict="season,player,squad"
        ).execute()
        logger.info(f"  Upserted batch {i // batch_size + 1}: {len(batch)} rows")

def ingest_player_stats(csv_path: str, season: str = "25/26"):
    logger.info(f"Loading player stats from: {csv_path}")
    df = load_and_clean(csv_path, season)
    logger.info(f"Ingesting {len(df)} EPL player records...")
    upsert_player_stats(df)
    logger.info(f"✅ Player stats ingested: {len(df)} players")
    return len(df)