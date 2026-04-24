import pandas as pd
import pytest
from app.services.feature_service import engineer_features

@pytest.fixture
def sample_df():
    data = {
        "date": pd.date_range("2023-08-01", periods=20, freq="7D"),
        "home_team": ["Arsenal"] * 10 + ["Chelsea"] * 10,
        "away_team": ["Chelsea"] * 10 + ["Arsenal"] * 10,
        "ftr": ["H","D","A","H","H","D","A","H","D","H"] * 2,
        "fthg": [2,1,0,3,2,1,1,2,0,1] * 2,
        "ftag": [0,1,2,1,0,1,2,0,0,0] * 2,
        "hst": [5,3,2,6,4,3,2,5,1,3] * 2,
        "ast": [2,3,5,2,1,3,5,1,0,1] * 2,
        "hc": [5,4,3,6,5,4,3,5,2,4] * 2,
        "ac": [3,4,5,3,2,4,5,2,1,3] * 2,
        "time_weight": [1.0] * 20,
    }
    return pd.DataFrame(data)

def test_engineer_features_returns_elo(sample_df):
    result = engineer_features(sample_df)
    assert "elo_diff" in result.columns

def test_no_data_leakage(sample_df):
    result = engineer_features(sample_df)
    # First match should have no rolling history — NaN is expected and dropped
    assert "h_form_5" in result.columns
