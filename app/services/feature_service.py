"""
Loads all data sources from Supabase, engineers pre-match features,
and returns a model-ready DataFrame saved to data/processed/features.parquet.
"""
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from app.core.supabase_client import get_supabase

import json
import os

ELO_RATINGS_PATH = "models/saved/elo_ratings.json"

# Load at module level (once at startup)
if os.path.exists(ELO_RATINGS_PATH):
    with open(ELO_RATINGS_PATH) as f:
        _ELO_STATE = json.load(f)
else:
    _ELO_STATE = {}

def get_current_elo(team: str, default: float = 1500.0) -> float:
    return _ELO_STATE.get(team, default)

logger          = logging.getLogger(__name__)
ROLLING_WINDOWS = [3, 5, 10]
ELO_K           = 32
ELO_DEFAULT     = 1500
PROCESSED_DIR   = Path("data/processed")

# ─────────────────────────────────────────────────────────────────────────────
# TEAM NAME NORMALISER
# ─────────────────────────────────────────────────────────────────────────────

TEAM_NAME_MAP = {
    "Manchester City":           "Man City",
    "Manchester United":         "Man United",
    "Newcastle United":          "Newcastle",
    "West Ham United":           "West Ham",
    "Wolverhampton Wanderers":   "Wolves",
    "Nottingham Forest":         "Nott'm Forest",
    "Leicester City":            "Leicester",
    "Leeds United":              "Leeds",
    "West Bromwich Albion":      "West Brom",
    "Tottenham Hotspur":         "Tottenham",
    "Cardiff City":              "Cardiff",
    "Huddersfield Town":         "Huddersfield",
    "Hull City":                 "Hull",
    "Ipswich Town":              "Ipswich",
    "Luton Town":                "Luton",
    "Norwich City":              "Norwich",
    "Queens Park Rangers":       "QPR",
    "Stoke City":                "Stoke",
    "Swansea City":              "Swansea",
    "Wigan Athletic":            "Wigan",
    "Bolton Wanderers":          "Bolton",
    "Blackburn Rovers":          "Blackburn",
    "Sunderland AFC":            "Sunderland",
    "Brighton & Hove Albion":    "Brighton",
    "Sheffield Utd":             "Sheffield United",
    "Nott'ham Forest":           "Nott'm Forest",
}

def _normalise_teams(df: pd.DataFrame,
                     cols: list | None = None) -> pd.DataFrame:
    if cols is None:
        cols = [c for c in ["home_team", "away_team", "team"] if c in df.columns]
    for col in cols:
        df[col] = df[col].replace(TEAM_NAME_MAP)
    return df


# ─────────────────────────────────────────────────────────────────────────────
# PAGINATED LOADER
# ─────────────────────────────────────────────────────────────────────────────

def _paginated_query(table: str, select: str = "*",
                     order_col: str | None = None) -> list:
    supabase  = get_supabase()
    all_rows  = []
    page_size = 1000
    offset    = 0
    while True:
        q = supabase.table(table).select(select)
        if order_col:
            q = q.order(order_col)
        result = q.range(offset, offset + page_size - 1).execute()
        batch  = result.data
        if not batch:
            break
        all_rows.extend(batch)
        logger.info(f"  [{table}] fetched {len(all_rows)} rows...")
        offset += page_size
        if len(batch) < page_size:
            break
    logger.info(f"  [{table}] ✅ {len(all_rows)} total rows")
    return all_rows


# ─────────────────────────────────────────────────────────────────────────────
# DATA LOADERS (each defined exactly once)
# ─────────────────────────────────────────────────────────────────────────────

def load_matches() -> pd.DataFrame:
    rows = _paginated_query("match_results", "*", order_col="date")
    df   = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def load_xg() -> pd.DataFrame:
    rows = _paginated_query(
        "xg_data",
        "season,date,home_team,away_team,home_xg,away_xg,home_npxg,away_npxg,xgd"
    )
    df = pd.DataFrame(rows)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df = _normalise_teams(df)
    return df


def load_possession() -> pd.DataFrame:
    rows = _paginated_query(
        "match_stats",
        "date,home_team,away_team,home_possession,away_possession"
    )
    df = pd.DataFrame(rows)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df = _normalise_teams(df)
    return df


def load_squad_strength() -> pd.DataFrame:
    rows = _paginated_query(
        "player_minutes",
        "season,team,minutes,xg,xa,npxg,goals,assists"
    )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["season"] = df["season"].str.replace(
        r"20(\d{2})/20(\d{2})", r"\1/\2", regex=True
    )
    df = _normalise_teams(df, cols=["team"])
    df = df.sort_values("minutes", ascending=False)
    df = df.groupby(["season", "team"]).head(14)
    squad = df.groupby(["season", "team"]).agg(
        squad_avg_xg     =("xg",      "mean"),
        squad_avg_xa     =("xa",      "mean"),
        squad_avg_npxg   =("npxg",    "mean"),
        squad_total_goals=("goals",   "sum"),
        squad_total_ast  =("assists", "sum"),
        squad_avg_min    =("minutes", "mean"),
    ).reset_index()
    return squad


# ─────────────────────────────────────────────────────────────────────────────
# ROLLING HELPER
# ─────────────────────────────────────────────────────────────────────────────

def _rolling(df: pd.DataFrame, team_col: str, stat_col: str,
             window: int, new_name: str) -> pd.Series:
    return (
        df.groupby(team_col)[stat_col]
        .transform(
            lambda x: x.shift(1)
                       .rolling(window, min_periods=1)  # ← always 1
                       .mean()
        )
        .rename(new_name)
    )

# ─────────────────────────────────────────────────────────────────────────────
# ELO
# ─────────────────────────────────────────────────────────────────────────────

def _compute_elo(df: pd.DataFrame) -> pd.DataFrame:
    elo: dict = {}
    home_elos, away_elos = [], []
    for _, row in df.iterrows():
        h, a = row["home_team"], row["away_team"]
        r_h  = elo.get(h, ELO_DEFAULT)
        r_a  = elo.get(a, ELO_DEFAULT)
        home_elos.append(r_h)
        away_elos.append(r_a)
        e_h  = 1 / (1 + 10 ** ((r_a - r_h) / 400))
        s_h  = 1.0 if row["ftr"] == "H" else (0.5 if row["ftr"] == "D" else 0.0)
        elo[h] = r_h + ELO_K * (s_h - e_h)
        elo[a] = r_a + ELO_K * ((1 - s_h) - (1 - e_h))
    df["home_elo"] = home_elos
    df["away_elo"] = away_elos
    df["elo_diff"] = df["home_elo"] - df["away_elo"]
    return df


# ─────────────────────────────────────────────────────────────────────────────
# PI-RATINGS (Constantinou & Fenton, 2012)
# Separate home/away attack+defence ratings updated on goal margin
# Proven to outperform Elo on EPL and generate +EV vs bookmakers
# ─────────────────────────────────────────────────────────────────────────────

def _compute_pi_ratings(df: pd.DataFrame,
                         gamma: float = 0.036,
                         lam: float   = 0.5) -> pd.DataFrame:
    """
    gamma : learning rate (0.036 = optimal per Constantinou & Fenton)
    lam   : home advantage decay factor
    Each team has 4 ratings: home_atk, home_def, away_atk, away_def
    """
    pi: dict = {}   # {team: {hc: , hd: , ac: , ad: }}

    h_hc, h_hd, a_ac, a_ad = [], [], [], []
    h_atk_diff, h_def_diff  = [], []

    def get(team):
        return pi.get(team, {"hc": 0.0, "hd": 0.0, "ac": 0.0, "ad": 0.0})

    for _, row in df.iterrows():
        h    = row["home_team"]
        a    = row["away_team"]
        fthg = float(row.get("fthg") or 0)
        ftag = float(row.get("ftag") or 0)

        rh = get(h)
        ra = get(a)

        # Store pre-match ratings (no leakage)
        h_hc.append(rh["hc"])
        h_hd.append(rh["hd"])
        a_ac.append(ra["ac"])
        a_ad.append(ra["ad"])
        h_atk_diff.append(rh["hc"] - ra["ad"])   # home attack vs away defence
        h_def_diff.append(rh["hd"] - ra["ac"])   # home defence vs away attack

        # Expected goals
        exp_h = 10 ** (rh["hc"] - ra["ad"])
        exp_a = 10 ** (ra["ac"] - rh["hd"])

        # Update ratings
        pi[h] = {
            "hc": rh["hc"] + gamma * (fthg - exp_h),
            "hd": rh["hd"] + gamma * (exp_a  - ftag),
            "ac": rh["ac"] + gamma * lam * (fthg - exp_h),
            "ad": rh["ad"] + gamma * lam * (exp_a  - ftag),
        }
        pi[a] = {
            "ac": ra["ac"] + gamma * (ftag - exp_a),
            "ad": ra["ad"] + gamma * (exp_h  - fthg),
            "hc": ra["hc"] + gamma * lam * (ftag - exp_a),
            "hd": ra["hd"] + gamma * lam * (exp_h  - fthg),
        }

    df["h_pi_hc"]      = h_hc          # home team home-attack rating
    df["h_pi_hd"]      = h_hd          # home team home-defence rating
    df["a_pi_ac"]      = a_ac          # away team away-attack rating
    df["a_pi_ad"]      = a_ad          # away team away-defence rating
    df["pi_atk_diff"]  = h_atk_diff    # home attack vs away defence
    df["pi_def_diff"]  = h_def_diff    # home defence vs away attack
    df["pi_total_diff"]= [a - b for a, b in zip(h_atk_diff, h_def_diff)]
    return df


# ─────────────────────────────────────────────────────────────────────────────
# SEASON CONTEXT
# ─────────────────────────────────────────────────────────────────────────────

def _add_season_context(df: pd.DataFrame) -> pd.DataFrame:
    def derive_season(d: pd.Timestamp) -> str:
        yr = d.year
        return (f"{str(yr)[2:]}/{str(yr+1)[2:]}"
                if d.month >= 8
                else f"{str(yr-1)[2:]}/{str(yr)[2:]}")
    df["season_label"]   = df["date"].apply(derive_season)
    df["home_matchweek"] = df.groupby(["season_label", "home_team"]).cumcount() + 1
    df["away_matchweek"] = df.groupby(["season_label", "away_team"]).cumcount() + 1
    df["matchweek"]      = ((df["home_matchweek"] + df["away_matchweek"]) / 2).round()
    return df


# ─────────────────────────────────────────────────────────────────────────────
# H2H WIN RATE
# ─────────────────────────────────────────────────────────────────────────────

def _compute_h2h(df: pd.DataFrame, window: int = 5) -> pd.Series:
    df = df.reset_index(drop=True)  # ← add this line at the top
    df["_pair"] = df.apply(
        lambda r: "__".join(sorted([r["home_team"], r["away_team"]])), axis=1
    )
    h2h_rates = pd.Series(0.5, index=df.index)
    for _, grp in df.groupby("_pair"):
        idx = grp.index.tolist()
        for i, ix in enumerate(idx):
            past = grp.iloc[max(0, i - window): i]
            if past.empty:
                continue
            home = df.at[ix, "home_team"]
            wins = (
                ((past["home_team"] == home) & (past["ftr"] == "H")).sum() +
                ((past["away_team"] == home) & (past["ftr"] == "A")).sum()
            )
            h2h_rates[ix] = wins / len(past)
    df.drop(columns=["_pair"], inplace=True)
    return h2h_rates

# ─────────────────────────────────────────────────────────────────────────────
# JOIN HELPERS — xG, POSSESSION, SQUAD (these were missing from your file)
# ─────────────────────────────────────────────────────────────────────────────

def _add_xg_features(df: pd.DataFrame, xg: pd.DataFrame) -> pd.DataFrame:
    if xg.empty:
        logger.warning("xg_data empty — skipping xG features")
        return df

    merged = df.merge(
        xg[["date","home_team","away_team","home_xg","away_xg","home_npxg","away_npxg"]],
        on=["date","home_team","away_team"], how="left"
    )
    for w in [3, 5]:
        merged[f"h_xg_{w}"]   = _rolling(merged, "home_team", "home_xg",   w, f"h_xg_{w}")
        merged[f"a_xg_{w}"]   = _rolling(merged, "away_team", "away_xg",   w, f"a_xg_{w}")
        merged[f"h_npxg_{w}"] = _rolling(merged, "home_team", "home_npxg", w, f"h_npxg_{w}")
        merged[f"a_npxg_{w}"] = _rolling(merged, "away_team", "away_npxg", w, f"a_npxg_{w}")
    merged["xgd_match"] = merged["home_xg"] - merged["away_xg"]
    merged["h_xgd_5"]   = _rolling(merged, "home_team", "xgd_match", 5, "h_xgd_5")

    # ✅ Fill xG NaNs with goals-based proxies for pre-xG seasons
    for w in [3, 5]:
        merged[f"h_xg_{w}"]   = merged[f"h_xg_{w}"].fillna(merged[f"h_goals_scored_{w}"])
        merged[f"a_xg_{w}"]   = merged[f"a_xg_{w}"].fillna(merged[f"a_goals_scored_{w}"])
        merged[f"h_npxg_{w}"] = merged[f"h_npxg_{w}"].fillna(merged[f"h_goals_scored_{w}"])
        merged[f"a_npxg_{w}"] = merged[f"a_npxg_{w}"].fillna(merged[f"a_goals_scored_{w}"])
    merged["h_xgd_5"] = merged["h_xgd_5"].fillna(
        merged["h_goals_scored_5"] - merged["a_goals_scored_5"]
    )

    merged.drop(columns=["home_xg","away_xg","home_npxg","away_npxg","xgd_match"],
                errors="ignore", inplace=True)
    return merged


def _add_parity_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Parity Index: low difference = likely draw.
    Uses xG when available, falls back to goals.
    Also adds clean sheet proxy for draw detection.
    """
    # xG parity (best signal for draws)
    if "h_xg_5" in df.columns and "a_xg_5" in df.columns:
        df["xg_parity_5"] = (
            df["h_xg_5"].fillna(df["h_goals_scored_5"]) -
            df["a_xg_5"].fillna(df["a_goals_scored_5"])
        ).abs()

    # Goals parity (always available — full 15-season coverage)
    df["goals_parity_3"] = (df["h_goals_scored_3"] - df["a_goals_scored_3"]).abs()
    df["goals_parity_5"] = (df["h_goals_scored_5"] - df["a_goals_scored_5"]).abs()

    # Defensive parity — low combined conceded = likely low-scoring draw
    df["def_parity_5"] = (
        df["h_goals_conceded_5"].fillna(0) +
        df["a_goals_conceded_5"].fillna(0)
    )

    # Form parity — similar form = more likely draw
    df["form_parity_5"] = (df["h_form_5"] - df["a_form_5"]).abs()

    # Pi-rating parity (total match balance)
    if "pi_total_diff" in df.columns:
        df["pi_parity"] = df["pi_total_diff"].abs()

    return df

def _add_draw_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Team-specific draw propensity features.
    Must be called AFTER rolling goals/form are computed (STEP 2).
    """
    # Rolling draw indicator (1 = draw, 0 = win/loss)
    df["_is_draw"] = (df["ftr"] == "D").astype(float)

    # Home team draw rate over last 5 and 10 matches
    df["h_draw_rate_5"] = (
        df.groupby("home_team")["_is_draw"]
        .transform(lambda x: x.shift(1).rolling(5, min_periods=1).mean())
        .fillna(0.24)
    )
    df["h_draw_rate_10"] = (
        df.groupby("home_team")["_is_draw"]
        .transform(lambda x: x.shift(1).rolling(10, min_periods=1).mean())
        .fillna(0.24)
    )

    # Away team draw rate over last 5 and 10 matches
    df["a_draw_rate_5"] = (
        df.groupby("away_team")["_is_draw"]
        .transform(lambda x: x.shift(1).rolling(5, min_periods=1).mean())
        .fillna(0.24)
    )
    df["a_draw_rate_10"] = (
        df.groupby("away_team")["_is_draw"]
        .transform(lambda x: x.shift(1).rolling(10, min_periods=1).mean())
        .fillna(0.24)
    )

    # Combined draw propensity — both teams' tendency to draw
    df["draw_propensity"] = (df["h_draw_rate_5"] + df["a_draw_rate_5"]) / 2

    # Elo parity — 1.0 = perfectly equal teams, draw more likely
    df["elo_parity"] = 1 / (1 + df["elo_diff"].abs())

    # H2H draw rate — % of past H2H meetings that ended draw
    df["_pair"] = df.apply(
        lambda r: "__".join(sorted([r["home_team"], r["away_team"]])), axis=1
    )
    h2h_draw = pd.Series(0.24, index=df.index)
    for _, grp in df.groupby("_pair"):
        idx = grp.index.tolist()
        for i, ix in enumerate(idx):
            past = grp.iloc[max(0, i - 5): i]
            if not past.empty:
                h2h_draw[ix] = (past["ftr"] == "D").mean()
    df["h2h_draw_rate"] = h2h_draw
    df.drop(columns=["_is_draw", "_pair"], inplace=True)

    return df


def _add_possession_features(df: pd.DataFrame, poss: pd.DataFrame) -> pd.DataFrame:
    if poss.empty:
        logger.warning("match_stats empty — skipping possession features")
        return df
    merged = df.merge(
        poss[["date","home_team","away_team","home_possession","away_possession"]],
        on=["date","home_team","away_team"], how="left"
    )
    for w in [3, 5]:
        merged[f"h_poss_{w}"] = _rolling(merged, "home_team", "home_possession", w, f"h_poss_{w}")
        merged[f"a_poss_{w}"] = _rolling(merged, "away_team", "away_possession", w, f"a_poss_{w}")
    merged.drop(columns=["home_possession","away_possession"], errors="ignore", inplace=True)
    return merged


def _add_squad_features(df: pd.DataFrame, squad: pd.DataFrame) -> pd.DataFrame:
    if squad.empty:
        logger.warning("player_minutes empty — skipping squad features")
        return df
    df = df.merge(
        squad.rename(columns={
            "team": "home_team", "squad_avg_xg": "h_squad_xg",
            "squad_avg_xa": "h_squad_xa", "squad_avg_npxg": "h_squad_npxg",
            "squad_total_goals": "h_squad_goals", "squad_total_ast": "h_squad_ast",
            "squad_avg_min": "h_squad_min",
        }),
        left_on=["season_label","home_team"], right_on=["season","home_team"],
        how="left"
    ).drop(columns=["season"], errors="ignore")

    df = df.merge(
        squad.rename(columns={
            "team": "away_team", "squad_avg_xg": "a_squad_xg",
            "squad_avg_xa": "a_squad_xa", "squad_avg_npxg": "a_squad_npxg",
            "squad_total_goals": "a_squad_goals", "squad_total_ast": "a_squad_ast",
            "squad_avg_min": "a_squad_min",
        }),
        left_on=["season_label","away_team"], right_on=["season","away_team"],
        how="left"
    ).drop(columns=["season"], errors="ignore")

    squad_feature_cols = [
        "h_squad_xg","h_squad_xa","h_squad_npxg",
        "h_squad_goals","h_squad_ast","h_squad_min",
        "a_squad_xg","a_squad_xa","a_squad_npxg",
        "a_squad_goals","a_squad_ast","a_squad_min",
    ]
    for col in squad_feature_cols:
        if col not in df.columns:
            continue
        # Fill using season-level median, not global median
        df[col] = df.groupby("season_label")[col].transform(
            lambda x: x.fillna(x.median())
        )
        # For seasons with NO data at all (entire season is NaN),
        # fall back to global median as last resort
        global_median = df[col].median()
        df[col] = df[col].fillna(global_median)

    df["squad_xg_diff"] = df["h_squad_xg"].fillna(0) - df["a_squad_xg"].fillna(0)
    return df

def _add_home_advantage(df: pd.DataFrame) -> pd.DataFrame:
    df["_home_win"] = (df["ftr"] == "H").astype(float)
    df["_away_win"] = (df["ftr"] == "A").astype(float)

    df["home_win_rate_hist"] = (
        df.groupby("home_team")["_home_win"]
        .transform(lambda x: x.shift(1).expanding().mean())
        .fillna(0.45)  # ← EPL home win base rate
    )
    df["away_win_rate_hist"] = (
        df.groupby("away_team")["_away_win"]
        .transform(lambda x: x.shift(1).expanding().mean())
        .fillna(0.29)  # ← EPL away win base rate
    )
    df.drop(columns=["_home_win","_away_win"], inplace=True)
    return df


def _add_odds_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert opening odds to implied probabilities.
    These encode market wisdom about team quality.
    """
    logger.info(f"  Odds debug — b365h in df: {'b365h' in df.columns} | "
                f"b365d in df: {'b365d' in df.columns} | "
                f"sample b365h: {df['b365h'].dropna().head(3).tolist() if 'b365h' in df.columns else 'N/A'}")
    if "b365h" not in df.columns:
        return df

    df["b365h"] = pd.to_numeric(df["b365h"], errors="coerce")
    df["b365d"] = pd.to_numeric(df["b365d"], errors="coerce")
    df["b365a"] = pd.to_numeric(df["b365a"], errors="coerce")

    # Raw implied probs (include vig)
    df["odds_impl_h"] = 1 / df["b365h"]
    df["odds_impl_d"] = 1 / df["b365d"]
    df["odds_impl_a"] = 1 / df["b365a"]

    # Vig-adjusted fair probabilities
    total = df["odds_impl_h"] + df["odds_impl_d"] + df["odds_impl_a"]
    df["odds_fair_h"] = df["odds_impl_h"] / total
    df["odds_fair_d"] = df["odds_impl_d"] / total
    df["odds_fair_a"] = df["odds_impl_a"] / total

    # Market-implied home advantage
    df["odds_home_edge"] = df["odds_fair_h"] - df["odds_fair_a"]

    return df

def build_live_features(home: str, away: str, live_odds: dict) -> pd.DataFrame:
    """Build a single-row feature vector using all available Supabase tables."""
    import json
    from pathlib import Path
    sb = get_supabase()

    # ── 1. Fetch recent match results ────────────────────────────────
    def fetch_recent(team: str, n: int = 10) -> pd.DataFrame:
        rows = (sb.table("match_results")
                  .select("*")
                  .or_(f"home_team.eq.{team},away_team.eq.{team}")
                  .order("date", desc=True)
                  .limit(n)
                  .execute().data)
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    def compute_match_stats(team: str, prefix: str) -> dict:
        df = fetch_recent(team, 10)
        if df.empty:
            return {}
        stats = {}

        def goals_scored(row):
            return row["fthg"] if row["home_team"] == team else row["ftag"]
        def goals_conceded(row):
            return row["ftag"] if row["home_team"] == team else row["fthg"]
        def form_pts(row):
            r = row.get("ftr")
            if row["home_team"] == team:
                return 1 if r == "H" else (0.5 if r == "D" else 0)
            return 1 if r == "A" else (0.5 if r == "D" else 0)

        df["_scored"]   = df.apply(goals_scored, axis=1).fillna(0)
        df["_conceded"] = df.apply(goals_conceded, axis=1).fillna(0)
        df["_form"]     = df.apply(form_pts, axis=1)
        df["_draw"]     = (df["ftr"] == "D").astype(int)

        for n in [3, 5, 10]:
            s = df.head(n)
            stats[f"{prefix}_goals_scored_{n}"]   = round(s["_scored"].mean(), 3)
            stats[f"{prefix}_goals_conceded_{n}"] = round(s["_conceded"].mean(), 3)
            stats[f"{prefix}_form_{n}"]           = round(s["_form"].mean(), 3)

        df5 = df.head(5)
        def side_col(home_col, away_col):
            return df5.apply(
                lambda r: r.get(home_col, 0) if r["home_team"] == team else r.get(away_col, 0),
                axis=1
            ).fillna(0)

        stats[f"{prefix}_sot_5"]        = round(side_col("hst", "ast").mean(), 3)
        stats[f"{prefix}_corners_5"]    = round(side_col("hc", "ac").mean(), 3)
        stats[f"{prefix}_cards_5"]      = round(side_col("hy", "ay").mean(), 3)
        stats[f"{prefix}_draw_rate_5"]  = round(df.head(5)["_draw"].mean(), 3)
        stats[f"{prefix}_draw_rate_10"] = round(df["_draw"].mean(), 3)
        return stats

    # ── 2. xG data (last 5 matches) ──────────────────────────────────
    def compute_xg_stats(team: str, prefix: str) -> dict:
        rows = (sb.table("xg_data")
                  .select("*")
                  .or_(f"home_team.eq.{team},away_team.eq.{team}")
                  .order("date", desc=True)
                  .limit(5)
                  .execute().data)
        if not rows:
            return {}
        df = pd.DataFrame(rows)
        stats = {}

        def xg_for(row):
            return row["home_xg"] if row["home_team"] == team else row["away_xg"]
        def xg_against(row):
            return row["away_xg"] if row["home_team"] == team else row["home_xg"]
        def npxg_for(row):
            return row["home_npxg"] if row["home_team"] == team else row["away_npxg"]

        df["_xgf"]   = df.apply(xg_for, axis=1).fillna(0)
        df["_xga"]   = df.apply(xg_against, axis=1).fillna(0)
        df["_npxgf"] = df.apply(npxg_for, axis=1).fillna(0)

        for n in [3, 5]:
            s = df.head(n)
            stats[f"{prefix}_xg_{n}"]       = round(s["_xgf"].mean(), 3)
            stats[f"{prefix}_xg_against_{n}"] = round(s["_xga"].mean(), 3)
            stats[f"{prefix}_npxg_{n}"]     = round(s["_npxgf"].mean(), 3)

        return stats

    # ── 3. Possession data (last 5 matches) ──────────────────────────
    def compute_possession(team: str, prefix: str) -> dict:
        rows = (sb.table("match_stats")
                  .select("*")
                  .or_(f"home_team.eq.{team},away_team.eq.{team}")
                  .order("date", desc=True)
                  .limit(5)
                  .execute().data)
        if not rows:
            return {}
        df = pd.DataFrame(rows)

        def poss_for(row):
            return row["home_possession"] if row["home_team"] == team else row["away_possession"]

        df["_poss"] = df.apply(poss_for, axis=1).fillna(50.0)
        return {f"{prefix}_possession_5": round(df["_poss"].mean(), 3)}

    # ── 4. ELO ratings ────────────────────────────────────────────────
    elo_path = Path("models/saved/elo_ratings.json")
    elo      = json.loads(elo_path.read_text()) if elo_path.exists() else {}
    home_elo   = elo.get(home, 1500)
    away_elo   = elo.get(away, 1500)
    elo_diff   = home_elo - away_elo
    elo_parity = round(max(0, 1 - abs(elo_diff) / 400), 4)

    # ── 5. Odds features ──────────────────────────────────────────────
    total          = (1/live_odds["b365h"]) + (1/live_odds["b365d"]) + (1/live_odds["b365a"])
    odds_fair_h    = round((1/live_odds["b365h"]) / total, 4)
    odds_fair_d    = round((1/live_odds["b365d"]) / total, 4)
    odds_fair_a    = round((1/live_odds["b365a"]) / total, 4)
    odds_home_edge = round(odds_fair_h - odds_fair_a, 4)

    # ── 6. Fetch all stats ────────────────────────────────────────────
    h_match = compute_match_stats(home, "h")
    a_match = compute_match_stats(away, "a")
    h_xg    = compute_xg_stats(home, "h")
    a_xg    = compute_xg_stats(away, "a")
    h_poss  = compute_possession(home, "h")
    a_poss  = compute_possession(away, "a")

    # ── 7. Assemble row ───────────────────────────────────────────────
    row = {
        **h_match, **a_match,
        **h_xg,    **a_xg,
        **h_poss,  **a_poss,
        "home_elo":        home_elo,
        "away_elo":        away_elo,
        "elo_diff":        elo_diff,
        "elo_parity":      elo_parity,
        "draw_propensity": round(
            (h_match.get("h_draw_rate_5", 0.24) + a_match.get("a_draw_rate_5", 0.24)) / 2, 4
        ),
        "odds_fair_h":     odds_fair_h,
        "odds_fair_d":     odds_fair_d,
        "odds_fair_a":     odds_fair_a,
        "odds_home_edge":  odds_home_edge,
        "matchweek":       0,
        "is_derby":        0,
        "home_days_rest":  7,
        "away_days_rest":  7,
    }
    return pd.DataFrame([row])

# ─────────────────────────────────────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

def engineer_features(df: pd.DataFrame | None = None) -> pd.DataFrame:
    if df is None:
        logger.info("Loading all data sources from Supabase...")
        df    = load_matches()
        xg    = load_xg()
        poss  = load_possession()
        squad = load_squad_strength()
    else:
        # ✅ FIXED: always attempt to load secondary sources
        # even when df is passed in from pipeline/train
        logger.info("df provided — loading secondary sources from Supabase...")
        try:
            xg    = load_xg()
        except Exception as e:
            logger.warning(f"xg_data load failed: {e} — xG features will be skipped")
            xg    = pd.DataFrame()
        try:
            poss  = load_possession()
        except Exception as e:
            logger.warning(f"match_stats load failed: {e} — possession features will be skipped")
            poss  = pd.DataFrame()
        try:
            squad = load_squad_strength()
        except Exception as e:
            logger.warning(f"player_minutes load failed: {e} — squad features will be skipped")
            squad = pd.DataFrame()

    df = df.copy()
    logger.info(f"Base matches loaded: {len(df)} rows")

    # STEP 1: Points
    df["home_pts"] = df["ftr"].map({"H": 3, "D": 1, "A": 0}).fillna(0)
    df["away_pts"] = df["ftr"].map({"A": 3, "D": 1, "H": 0}).fillna(0)

    # STEP 2: Rolling match features
    for w in ROLLING_WINDOWS:
        df[f"h_goals_scored_{w}"]   = _rolling(df, "home_team", "fthg",     w, f"h_goals_scored_{w}")
        df[f"h_goals_conceded_{w}"] = _rolling(df, "home_team", "ftag",     w, f"h_goals_conceded_{w}")
        df[f"a_goals_scored_{w}"]   = _rolling(df, "away_team", "ftag",     w, f"a_goals_scored_{w}")
        df[f"a_goals_conceded_{w}"] = _rolling(df, "away_team", "fthg",     w, f"a_goals_conceded_{w}")
        df[f"h_form_{w}"]           = _rolling(df, "home_team", "home_pts", w, f"h_form_{w}")
        df[f"a_form_{w}"]           = _rolling(df, "away_team", "away_pts", w, f"a_form_{w}")
    for w in [5]:
        df[f"h_sot_{w}"]     = _rolling(df, "home_team", "hst", w, f"h_sot_{w}")
        df[f"a_sot_{w}"]     = _rolling(df, "away_team", "ast", w, f"a_sot_{w}")
        df[f"h_corners_{w}"] = _rolling(df, "home_team", "hc",  w, f"h_corners_{w}")
        df[f"a_corners_{w}"] = _rolling(df, "away_team", "ac",  w, f"a_corners_{w}")
        df[f"h_cards_{w}"]   = _rolling(df, "home_team", "hy",  w, f"h_cards_{w}")
        df[f"a_cards_{w}"]   = _rolling(df, "away_team", "ay",  w, f"a_cards_{w}")

    # STEP 3: Elo
    df = _compute_elo(df)

    # STEP 3b: Pi-ratings (replaces Elo as primary rating system)
    df = _compute_pi_ratings(df) 

    # STEP 4: Season context
    df = _add_season_context(df)

    # STEP 5: xG features
    df = _add_xg_features(df, xg)

    # STEP 5b: Parity features (draw signal)
    df = _add_parity_features(df)

    # STEP 5c: Draw propensity features  ← ADD THIS
    df = _add_draw_features(df)

    # STEP 6: Possession features
    df = _add_possession_features(df, poss)

    # STEP 7: Squad features
    df = _add_squad_features(df, squad)

    # STEP 8: Days rest
    df = df.sort_values("date")
    df["home_days_rest"] = (
        df.groupby("home_team")["date"]
        .transform(lambda x: x.diff().dt.days.shift(1).fillna(7))
    )
    df["away_days_rest"] = (
        df.groupby("away_team")["date"]
        .transform(lambda x: x.diff().dt.days.shift(1).fillna(7))
    )

    # STEP 9: Cumulative points
    df["home_cumpts"] = (
        df.groupby(["season_label","home_team"])["home_pts"]
        .transform(lambda x: x.cumsum().shift(1).fillna(0))
    )
    df["away_cumpts"] = (
        df.groupby(["season_label","away_team"])["away_pts"]
        .transform(lambda x: x.cumsum().shift(1).fillna(0))
    )

    # STEP 9B: Home advantage
    df = _add_home_advantage(df)

    # STEP 10: Derby flag — use football-data.co.uk short names
    BIG_SIX = {"Arsenal","Chelsea","Liverpool","Man City","Man United","Tottenham"}
    df["is_derby"] = (
        df["home_team"].isin(BIG_SIX) & df["away_team"].isin(BIG_SIX)
    ).astype(int)

    # STEP 11: H2H win rate
    df["h2h_home_win_rate"] = _compute_h2h(df, window=5)

    # STEP 11b: Opening odds features
    df = _add_odds_features(df)

    # STEP 11c: Draw-signal features
    # These must come AFTER STEP 12's rolling fill, not before
    df["cumpts_diff"]      = (df["home_cumpts"] - df["away_cumpts"]).abs()
    df["sot_balance"]      = (df["h_sot_5"] - df["a_sot_5"]).abs()
    # combined_goals_5 depends on rolling cols — compute after fills
    df["combined_goals_5"] = df["h_goals_scored_5"].fillna(0) + df["a_goals_scored_5"].fillna(0)
    
    # STEP 12: Fill remaining NaNs with safe defaults before saving
    # Rolling stats — fill first-gameweek NaNs with 0 (no prior history)
    rolling_cols = [c for c in df.columns if any(
        k in c for k in ["goals_scored","goals_conceded","form","sot","corners","cards","xg","npxg","xgd","poss"]
    )]
    for col in rolling_cols:
        if df[col].isna().any():
            df[col] = df[col].fillna(0)

    # Parity features — depend on rolling cols, fill after rolling is clean
        parity_cols = [
        "xg_parity_5", "goals_parity_3", "goals_parity_5",
        "form_parity_5", "def_parity_5", "pi_parity",
        # ← add new draw features here
        "h_draw_rate_5", "a_draw_rate_5",
        "h_draw_rate_10", "a_draw_rate_10",
        "h2h_draw_rate", "draw_propensity", "elo_parity",
    ]
    for col in parity_cols:
        if col in df.columns:
            df[col] = df[col].fillna(0.24 if "draw" in col or "propensity" in col
                                     else 0)
            
    # Odds features — fill missing seasons with EPL base rates
    odds_fill = {
        "odds_fair_h":    0.45,   # EPL home win base rate
        "odds_fair_d":    0.24,   # EPL draw base rate
        "odds_fair_a":    0.29,   # EPL away win base rate
        "odds_home_edge": 0.16,   # typical home edge
    }
    for col, default in odds_fill.items():
        if col in df.columns:
            df[col] = df[col].fillna(default)

   
    # STEP 13: Cleanup — only drop rows with no result label
    df = df.dropna(subset=["ftr"])
    logger.info(f"Feature engineering complete: {len(df)} rows × {len(df.columns)} columns")
    return df

def build_and_save(output_path: str | None = None) -> pd.DataFrame:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out = Path(output_path) if output_path else PROCESSED_DIR / "features.parquet"
    df  = engineer_features()
    df.to_parquet(out, index=False)
    logger.info(f"✅ Feature matrix saved → {out}  ({len(df)} rows × {len(df.columns)} cols)")
    return df