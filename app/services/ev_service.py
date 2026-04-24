"""
+EV Comparator — compares model probabilities against bookmaker odds
to identify value bets.

EV Formula:
    EV = (model_prob × decimal_odds) - 1
    EV > 0  →  value bet (bet this)
    EV < 0  →  no value  (skip)

Kelly Criterion stake:
    f = (b × p - q) / b
    b = decimal_odds - 1
    p = model_prob
    q = 1 - p
"""
import logging
import pandas as pd

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# CORE EV CALCULATION
# ─────────────────────────────────────────────────────────────────────────────

def decimal_to_prob(odd: float) -> float:
    """Convert decimal odds to implied probability (includes bookmaker margin)."""
    return 1 / odd if odd > 1 else 0.0


def remove_vig(home_odd: float, draw_odd: float, away_odd: float) -> dict:
    """
    Strip bookmaker margin to get fair probabilities.
    Returns fair probs that sum to 1.0.
    """
    raw   = [decimal_to_prob(o) for o in [home_odd, draw_odd, away_odd]]
    total = sum(raw)
    vig   = total - 1.0
    fair  = [p / total for p in raw]
    return {
        "vig":           round(vig, 4),
        "fair_home":     round(fair[0], 4),
        "fair_draw":     round(fair[1], 4),
        "fair_away":     round(fair[2], 4),
    }


def compute_ev(model_prob: float, decimal_odd: float) -> float:
    """
    Expected Value as a fraction of stake.
    EV = (model_prob × decimal_odds) - 1
    +EV means bet has positive long-run expectation.
    """
    return round((model_prob * decimal_odd) - 1, 4)


def kelly_stake(model_prob: float, decimal_odd: float,
                fraction: float = 0.25) -> float:
    """
    Fractional Kelly criterion stake as % of bankroll.
    fraction=0.25 = quarter Kelly (safer, standard for sports betting).
    Returns 0 if bet has no edge.
    """
    b = decimal_odd - 1
    q = 1 - model_prob
    kelly = (b * model_prob - q) / b
    return round(max(0, kelly * fraction) * 100, 2)  # as % of bankroll


# ─────────────────────────────────────────────────────────────────────────────
# MAIN COMPARATOR
# ─────────────────────────────────────────────────────────────────────────────

def find_value_bets(
    model_probs: dict,          # {"H": 0.48, "D": 0.28, "A": 0.24}
    home_odd:    float,         # decimal odds e.g. 2.10
    draw_odd:    float,         # decimal odds e.g. 3.40
    away_odd:    float,         # decimal odds e.g. 3.60
    min_ev:      float = 0.02,  # minimum EV threshold (4% edge)
    min_prob:    float = 0.20,  # ignore outcomes with <15% model probability
) -> dict:
    """
    Core +EV function. Returns value bets with EV, Kelly stake, and recommendation.

    Args:
        model_probs : dict from prediction endpoint {"H": p, "D": p, "A": p}
        home_odd    : bookmaker decimal odds for home win
        draw_odd    : bookmaker decimal odds for draw
        away_odd    : bookmaker decimal odds for away win
        min_ev      : minimum edge to flag as value (default 4%)
        min_prob    : minimum model probability to consider (filters noise)

    Returns:
        dict with value bets and full analysis
    """
    outcomes = {
        "H": {"odd": home_odd, "label": "Home Win"},
        "D": {"odd": draw_odd, "label": "Draw"},
        "A": {"odd": away_odd, "label": "Away Win"},
    }

    # Strip vig to get fair market probs
    fair = remove_vig(home_odd, draw_odd, away_odd)
    vig  = fair.pop("vig")

    value_bets = []
    all_analysis = []

    for key, data in outcomes.items():
        model_p  = model_probs.get(key, 0)
        _key_map = {"H": "fair_home", "D": "fair_draw", "A": "fair_away"}
        market_p = fair[_key_map[key]]
        ev       = compute_ev(model_p, data["odd"])
        edge     = round(model_p - market_p, 4)
        kelly    = kelly_stake(model_p, data["odd"])

        analysis = {
            "outcome":    data["label"],
            "model_prob": round(model_p, 4),
            "market_prob":market_p,
            "edge":       edge,           # positive = model sees more value
            "decimal_odd":data["odd"],
            "ev":         ev,
            "kelly_%":    kelly,
            "is_value":   ev >= min_ev and model_p >= min_prob,
        }
        all_analysis.append(analysis)

        if analysis["is_value"]:
            value_bets.append(analysis)

    # Sort by EV descending
    value_bets.sort(key=lambda x: x["ev"], reverse=True)

    return {
        "bookmaker_vig":  vig,
        "value_bets":     value_bets,
        "all_outcomes":   all_analysis,
        "has_value":      len(value_bets) > 0,
        "best_bet":       value_bets[0] if value_bets else None,
    }


def format_ev_report(ev_result: dict, home_team: str, away_team: str) -> str:
    """Pretty-print EV analysis for logging/API response."""
    lines = [
        f"\n{'='*55}",
        f"  +EV ANALYSIS: {home_team} vs {away_team}",
        f"  Bookmaker Vig: {ev_result['bookmaker_vig']*100:.1f}%",
        f"{'='*55}",
    ]
    for o in ev_result["all_outcomes"]:
        flag = "✅ VALUE" if o["is_value"] else "❌"
        lines.append(
            f"  {o['outcome']:<12} "
            f"Model:{o['model_prob']*100:.1f}%  "
            f"Market:{o['market_prob']*100:.1f}%  "
            f"Edge:{o['edge']*100:+.1f}%  "
            f"EV:{o['ev']*100:+.1f}%  "
            f"Kelly:{o['kelly_%']:.1f}%  "
            f"{flag}"
        )
    if ev_result["best_bet"]:
        b = ev_result["best_bet"]
        lines.append(f"\n  🎯 BEST BET: {b['label'] if 'label' in b else b['outcome']} "
                     f"@ {b['decimal_odd']} "
                     f"(EV: +{b['ev']*100:.1f}%, Kelly: {b['kelly_%']:.1f}% bankroll)")
    else:
        lines.append(f"\n  ⚠️  NO VALUE FOUND — skip this match")
    lines.append("=" * 55)
    return "\n".join(lines)