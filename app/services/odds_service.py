import os
import requests
import logging
import time
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

ODDSPAPI_KEY      = os.getenv("ODDSPAPI_KEY")
BASE_URL          = "https://api.oddspapi.io/v4"
EPL_TOURNAMENT_ID = 17


# ── Fetch upcoming EPL fixtures ───────────────────────────────────────────────
def get_upcoming_epl_fixtures() -> list[dict]:
    resp = requests.get(f"{BASE_URL}/odds-by-tournaments", params={
        "apiKey":        ODDSPAPI_KEY,
        "bookmaker":     "bet365",
        "tournamentIds": EPL_TOURNAMENT_ID,
        "oddsFormat":    "decimal",
        "verbosity":     2,
    }, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    # Unwrap if response is a dict envelope
    if isinstance(data, dict):
        for key in ("fixtures", "data", "results", "events"):
            if key in data and isinstance(data[key], list):
                logger.info(f"Unwrapped fixtures from key '{key}': {len(data[key])} found")
                return data[key]
        # Last resort — return first list value found
        for val in data.values():
            if isinstance(val, list):
                logger.info(f"Unwrapped fixtures from first list value: {len(val)} found")
                return val
        logger.warning(f"Unexpected response shape: {list(data.keys())}")
        return []

    # Already a list
    logger.info(f"Fixtures returned as list: {len(data)} found")
    return data


# ── Fetch B365 1X2 odds for a single fixture ─────────────────────────────────
def get_b365_odds(fixture_id: str) -> dict | None:
    """
    Fetch B365 1X2 (Home/Draw/Away) odds for a fixture.
    NOTE: marketActive=False does NOT mean odds are unavailable —
    it only means the market is not open for new bets (normal pre-match).
    We intentionally ignore marketActive and parse prices directly.
    """
    time.sleep(1.5)  # respect OddsPapi rate limit

    try:
        resp = requests.get(f"{BASE_URL}/odds", params={
            "apiKey":     ODDSPAPI_KEY,
            "fixtureId":  fixture_id,
            "bookmakers": "bet365",
            "oddsFormat": "decimal",
        }, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.HTTPError as e:
        logger.warning(f"HTTP error fetching odds for fixture {fixture_id}: {e}")
        return None
    except requests.exceptions.RequestException as e:
        logger.warning(f"Request failed for fixture {fixture_id}: {e}")
        return None

    try:
        markets = data["bookmakerOdds"]["bet365"]["markets"]
    except (KeyError, TypeError):
        logger.warning(f"No bet365 markets in response for fixture {fixture_id}")
        return None

    # ── Helper: extract exactly 3 valid prices from an outcomes dict ──────────
    def _extract_prices(outcomes: dict) -> list[float]:
        prices = []
        for k in outcomes.keys():
            try:
                p = float(outcomes[k]["players"]["0"]["price"])
                if p > 1.0:
                    prices.append(p)
            except (KeyError, TypeError, ValueError):
                continue
        return prices

    market_outcomes = None

    # ── 1. Try standard 1X2 market key "101" first ───────────────────────────
    if "101" in markets:
        outcomes = markets["101"].get("outcomes", {})
        prices   = _extract_prices(outcomes)
        if len(prices) == 3:
            market_outcomes = outcomes
            logger.info(f"Fixture {fixture_id} → market 101 (1X2) matched")

    # ── 2. Fallback: scan all markets for exactly 3 valid prices ─────────────
    if not market_outcomes:
        for mkey, mval in markets.items():
            outcomes = mval.get("outcomes", {})
            prices   = _extract_prices(outcomes)
            if len(prices) == 3:
                market_outcomes = outcomes
                logger.info(f"Fixture {fixture_id} → fallback market key '{mkey}' matched")
                break

    if not market_outcomes:
        logger.warning(f"No valid 1X2 market found for fixture {fixture_id}")
        return None

    # ── 3. Extract final prices in order (H, D, A) ───────────────────────────
    final_prices = _extract_prices(market_outcomes)
    if len(final_prices) != 3:
        logger.warning(f"Price extraction failed for fixture {fixture_id}: {final_prices}")
        return None

    h, d, a = final_prices
    logger.info(f"Fixture {fixture_id} → B365: H={h} D={d} A={a}")
    return {"b365h": h, "b365d": d, "b365a": a}


# ── EV calculation ────────────────────────────────────────────────────────────
def calculate_ev(model_prob: float, decimal_odd: float) -> float:
    """Expected value: (prob × odd) - 1. Positive = value bet."""
    return round((model_prob * decimal_odd) - 1, 4)


# ── Team name normalisation ───────────────────────────────────────────────────
def normalise_name(name: str) -> str:
    """Map OddsPapi team names to football-data.co.uk format used in the DB."""
    return TEAM_NAME_MAP.get(name, name)


TEAM_NAME_MAP = {
    "AFC Bournemouth":          "Bournemouth",
    "Arsenal FC":               "Arsenal",
    "Aston Villa":              "Aston Villa",
    "Brentford FC":             "Brentford",
    "Brighton & Hove Albion":   "Brighton",
    "Burnley FC":               "Burnley",
    "Chelsea FC":               "Chelsea",
    "Crystal Palace":           "Crystal Palace",
    "Everton FC":               "Everton",
    "Fulham FC":                "Fulham",
    "Ipswich Town":             "Ipswich",
    "Leeds United":             "Leeds",
    "Leicester City":           "Leicester",
    "Liverpool FC":             "Liverpool",
    "Luton Town":               "Luton",
    "Manchester City":          "Man City",
    "Manchester United":        "Man United",
    "Newcastle United":         "Newcastle",
    "Nottingham Forest":        "Nott'm Forest",
    "Queens Park Rangers":      "QPR",
    "Sheffield United":         "Sheffield United",
    "Southampton FC":           "Southampton",
    "Sunderland AFC":           "Sunderland",
    "Tottenham Hotspur":        "Tottenham",
    "Watford FC":               "Watford",
    "West Bromwich Albion":     "West Brom",
    "West Ham United":          "West Ham",
    "Wolverhampton Wanderers":  "Wolves",
    "Norwich City":             "Norwich",
    "Swansea City":             "Swansea",
    "Cardiff City":             "Cardiff",
    "Stoke City":               "Stoke",
    "Wigan Athletic":           "Wigan",
    "Huddersfield Town":        "Huddersfield",
    "Hull City":                "Hull",
    "Middlesbrough":            "Middlesbrough",
    "Blackburn Rovers":         "Blackburn",
    "Blackpool":                "Blackpool",
    "Birmingham City":          "Birmingham",
    "Bolton Wanderers":         "Bolton",
    "Reading":                  "Reading",
    # Short names (as OddsPapi sometimes returns them)
    "Sunderland":               "Sunderland",
    "Nottingham":               "Nott'm Forest",
    "Brighton":                 "Brighton",
    "Bournemouth":              "Bournemouth",
    "Wolves":                   "Wolves",
    "Spurs":                    "Tottenham",
}