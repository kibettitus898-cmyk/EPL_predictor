from pydantic import BaseModel

class PredictionRequest(BaseModel):
    home_team: str
    away_team: str
    season: str = "2526"
    home_odd:  float | None = None   # optional — enables +EV analysis
    draw_odd:  float | None = None
    away_odd:  float | None = None

class PredictionResponse(BaseModel):
    home_team: str
    away_team: str
    predicted_outcome: str      # "H" | "D" | "A"
    prob_home_win: float
    prob_draw: float
    prob_away_win: float
    confidence: float
    model_version: str
    probabilities: dict          # {"H": 0.48, "D": 0.28, "A": 0.24}
    predicted:    str            # "H", "D", or "A"
    label:         str
    confidence:   float
    ev_analysis:  dict | None = None  # populated when odds are provided
