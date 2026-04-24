import pandas as pd
from app.services.ingest_service import clean_season, _get_season_label, _time_weight, SEASONS

def test_season_label():
    assert _get_season_label("2425") == "24/25"
    assert _get_season_label("1011") == "10/11"

def test_time_weight_most_recent():
    w = _time_weight(SEASONS[-1], len(SEASONS))
    assert abs(w - 1.0) < 0.01

def test_time_weight_oldest_less_than_recent():
    w_old = _time_weight(SEASONS[0], len(SEASONS))
    w_new = _time_weight(SEASONS[-1], len(SEASONS))
    assert w_old < w_new
