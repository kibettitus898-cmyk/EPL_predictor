import logging
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.services.odds_service import get_upcoming_epl_fixtures, get_b365_odds, calculate_ev, normalise_name
from app.services.feature_service import build_live_features
from app.services.model_service import load_model, predict_proba
 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

model = load_model()
print("✅ Ensemble model loaded")

fixtures = get_upcoming_epl_fixtures()
logger.info(f"Found {len(fixtures)} upcoming EPL fixtures")

for fix in fixtures:
    fixture_id = fix["fixtureId"]
    home = normalise_name(fix.get("participant1Name", str(fix["participant1Id"])))
    away = normalise_name(fix.get("participant2Name", str(fix["participant2Id"])))
    start_time = fix["startTime"]
    ...

    odds = get_b365_odds(fixture_id)     # ← separate API call per fixture

    if not odds:
        logger.warning(f"  ⚠️  No 1X2 odds for fixture {fixture_id}, skipping")
        continue

    print(f"\n{home} vs {away}  ({start_time})")
    print(f"  B365: H={odds['b365h']}  D={odds['b365d']}  A={odds['b365a']}")

    features = build_live_features(home, away, odds)
    probs    = predict_proba(model, features)  # [p_home, p_draw, p_away]

    ev_h = calculate_ev(probs[0], odds["b365h"])
    ev_d = calculate_ev(probs[1], odds["b365d"])
    ev_a = calculate_ev(probs[2], odds["b365a"])

    print(f"\n{'='*50}")
    print(f"  {home}  vs  {away}")
    print(f"  Model:  H={probs[0]:.1%}  D={probs[1]:.1%}  A={probs[2]:.1%}")
    print(f"  B365:   H={odds['b365h']}  D={odds['b365d']}  A={odds['b365a']}")
    print(f"  EV:     H={ev_h:+.3f}  D={ev_d:+.3f}  A={ev_a:+.3f}")
    if max(ev_h, ev_d, ev_a) > 0.05:
        best = ["Home", "Draw", "Away"][[ev_h, ev_d, ev_a].index(max(ev_h, ev_d, ev_a))]
        print(f"  🟢 VALUE BET → {best}")
    else:
        print(f"  🔴 No value — skip")