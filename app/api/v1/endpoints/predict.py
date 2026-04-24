import logging
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from fastapi import APIRouter, HTTPException

from app.schemas.prediction import PredictionRequest, PredictionResponse
from app.services.feature_service import load_matches, engineer_features, get_current_elo
from app.ml.features.feature_columns import FEATURE_COLS
from app.services.ev_service import find_value_bets, format_ev_report
from app.services.odds_service import get_upcoming_epl_fixtures, get_b365_odds, normalise_name, calculate_ev
from app.utils.team_utils import normalise_team

logger     = logging.getLogger(__name__)
router     = APIRouter()
MODELS_DIR = Path("models/saved")


# ── Load once at startup ──────────────────────────────────────────────────────
try:
    _model      = joblib.load(MODELS_DIR / "ensemble.pkl")
    _imputer    = joblib.load(MODELS_DIR / "imputer.pkl")
    _feat_names = joblib.load(MODELS_DIR / "feature_names.pkl")
    logger.info("✅ Models loaded successfully")
except FileNotFoundError as e:
    logger.error(f"❌ Model file missing: {e}. Run train_model.py first.")
    _model = _imputer = _feat_names = None


# ── Kelly criterion helper (Adjustment 2) ────────────────────────────────────
def _kelly_pct(prob: float, odd: float) -> float:
    """Kelly criterion as a percentage, capped at 15%."""
    edge = (prob * odd) - 1
    if edge <= 0 or odd <= 1:
        return 0.0
    return round(min((edge / (odd - 1)) * 100, 15), 2)


# ── Shared prediction logic ───────────────────────────────────────────────────
def _run_prediction(home_team: str, away_team: str,
                    home_odd: float = None, draw_odd: float = None,
                    away_odd: float = None) -> dict:
    """Core prediction logic shared by /predict and /upcoming."""

    home_norm = normalise_team(home_team) or home_team
    away_norm = normalise_team(away_team) or away_team

    home_elo = get_current_elo(home_norm)
    away_elo = get_current_elo(away_norm)

    parquet = Path("data/processed/features.parquet")
    if parquet.exists():
        df = pd.read_parquet(parquet)
    else:
        logger.info("Parquet not found — building features from Supabase...")
        df = load_matches()
        df = engineer_features(df)

    home_row     = df[df["home_team"] == home_norm].tail(1)
    away_as_away = df[df["away_team"] == away_norm]
    away_as_home = df[df["home_team"] == away_norm]

    if home_row.empty:
        raise ValueError(f"'{home_team}' not found. Check spelling.")
    if away_as_away.empty and away_as_home.empty:
        raise ValueError(f"'{away_team}' not found. Check spelling.")

    away_row = away_as_away.tail(1) if not away_as_away.empty else away_as_home.tail(1)

    home_row = home_row.copy()
    away_row = away_row.copy()
    home_row["home_elo"] = home_elo
    away_row["away_elo"] = away_elo

    feat_cols = _feat_names if _feat_names else FEATURE_COLS
    row = {}
    for col in feat_cols:
        if col.startswith("h_") or col in ["home_elo", "home_cumpts",
                                            "home_days_rest", "home_win_rate_hist",
                                            "h_pi_hc", "h_pi_hd", "home_matchweek"]:
            row[col] = home_row.iloc[0].get(col, np.nan)
        elif col.startswith("a_") or col in ["away_elo", "away_cumpts",
                                              "away_days_rest", "away_win_rate_hist",
                                              "a_pi_ac", "a_pi_ad", "away_matchweek"]:
            row[col] = away_row.iloc[0].get(col, np.nan)
        else:
            row[col] = home_row.iloc[0].get(col, np.nan)

    if home_odd and draw_odd and away_odd:
        total = (1/home_odd) + (1/draw_odd) + (1/away_odd)
        row["odds_fair_h"]    = (1/home_odd) / total
        row["odds_fair_d"]    = (1/draw_odd) / total
        row["odds_fair_a"]    = (1/away_odd) / total
        row["odds_home_edge"] = row["odds_fair_h"] - row["odds_fair_a"]

    X     = pd.DataFrame([row])[feat_cols]
    X_imp = pd.DataFrame(_imputer.transform(X), columns=feat_cols)

    proba = _model.predict_proba(X_imp)[0]
    probs = {
        "H": round(float(proba[0]), 4),
        "D": round(float(proba[1]), 4),
        "A": round(float(proba[2]), 4),
    }
    predicted  = max(probs, key=probs.get)
    confidence = round(probs[predicted], 4)

    ev_result = None
    if home_odd and draw_odd and away_odd:
        ev_result = find_value_bets(
            model_probs=probs,
            home_odd=home_odd,
            draw_odd=draw_odd,
            away_odd=away_odd,
        )

    return {
        "probabilities": probs,
        "predicted":     predicted,
        "label":         {"H": "Home Win", "D": "Draw", "A": "Away Win"}[predicted],
        "confidence":    confidence,
        "ev_analysis":   ev_result,
    }


# ── POST / (prefix="/predict" in router.py → resolves to POST /predict) ───────
@router.post("/predict")
def predict(req: PredictionRequest):
    if _model is None:
        raise HTTPException(status_code=503,
            detail="Model not loaded. Run: python scripts/train_model.py")
    try:
        result = _run_prediction(
            home_team=req.home_team,
            away_team=req.away_team,
            home_odd=req.home_odd,
            draw_odd=req.draw_odd,
            away_odd=req.away_odd,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if req.home_odd and req.draw_odd and req.away_odd:
        logger.info(format_ev_report(result["ev_analysis"], req.home_team, req.away_team))

    return {
        "home_team": req.home_team,
        "away_team": req.away_team,
        **result,
    }


# ── GET /upcoming (prefix="/predict" → resolves to GET /predict/upcoming) ─────
@router.get("/predict/upcoming")
def predict_upcoming(limit: int = 20):
    """
    Fetch upcoming EPL fixtures from OddsPapi, run ensemble model,
    return predictions + EV + Kelly % per outcome. No ESPN needed.
    """
    if _model is None:
        raise HTTPException(status_code=503,
            detail="Model not loaded. Run: python scripts/train_model.py")

    try:
        fixtures = get_upcoming_epl_fixtures()
    except Exception as e:
        raise HTTPException(status_code=502,
            detail=f"Failed to fetch fixtures from OddsPapi: {e}")

    results = []

    for fix in fixtures[:limit]:
        # Adjustment 3 — guard missing fixture ID
        fixture_id = fix.get("id") or fix.get("fixtureId")
        if not fixture_id:
            logger.warning(f"Fixture missing ID, skipping: {fix}")
            continue

        home = normalise_name(fix.get("participant1Name", ""))
        away = normalise_name(fix.get("participant2Name", ""))
        date = fix.get("startTime") or fix.get("startDate") or fix.get("date", "")

        if not home or not away:
            continue

        odds = get_b365_odds(fixture_id)
        if not odds:
            logger.warning(f"No odds for {home} vs {away} — skipping")
            continue

        try:
            result = _run_prediction(
                home_team=home,
                away_team=away,
                home_odd=odds["b365h"],
                draw_odd=odds["b365d"],
                away_odd=odds["b365a"],
            )

            ev_h = calculate_ev(result["probabilities"]["H"], odds["b365h"])
            ev_d = calculate_ev(result["probabilities"]["D"], odds["b365d"])
            ev_a = calculate_ev(result["probabilities"]["A"], odds["b365a"])
            vig  = round((1/odds["b365h"]) + (1/odds["b365d"]) + (1/odds["b365a"]) - 1, 4)

            # Adjustment 2 — kelly_pct included in every outcome
            all_outcomes = [
                {
                    "outcome":     "H",
                    "model_prob":  result["probabilities"]["H"],
                    "decimal_odd": odds["b365h"],
                    "ev":          round(ev_h, 4),
                    "kelly_pct":   _kelly_pct(result["probabilities"]["H"], odds["b365h"]),
                    "is_value":    ev_h > 0.05,
                },
                {
                    "outcome":     "D",
                    "model_prob":  result["probabilities"]["D"],
                    "decimal_odd": odds["b365d"],
                    "ev":          round(ev_d, 4),
                    "kelly_pct":   _kelly_pct(result["probabilities"]["D"], odds["b365d"]),
                    "is_value":    ev_d > 0.05,
                },
                {
                    "outcome":     "A",
                    "model_prob":  result["probabilities"]["A"],
                    "decimal_odd": odds["b365a"],
                    "ev":          round(ev_a, 4),
                    "kelly_pct":   _kelly_pct(result["probabilities"]["A"], odds["b365a"]),
                    "is_value":    ev_a > 0.05,
                },
            ]

            value_bets = [o for o in all_outcomes if o["is_value"]]
            best_bet   = max(value_bets, key=lambda x: x["ev"]) if value_bets else None

            results.append({
                "fixture_id":    fixture_id,
                "date":          date,
                "home_team":     home,
                "away_team":     away,
                "b365":          {"h": odds["b365h"], "d": odds["b365d"], "a": odds["b365a"]},
                "probabilities": result["probabilities"],
                "predicted":     result["predicted"],
                "label":         result["label"],
                "confidence":    result["confidence"],
                "ev_analysis": {
                    "bookmaker_vig": vig,
                    "has_value":     len(value_bets) > 0,
                    "best_bet":      best_bet,
                    "value_bets":    value_bets,
                    "all_outcomes":  all_outcomes,
                },
            })

        except ValueError as e:
            logger.warning(f"Skipping {home} vs {away}: {e}")
            continue
        except Exception as e:
            logger.error(f"Unexpected error for {home} vs {away}: {e}")
            continue

    return results