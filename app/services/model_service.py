import joblib
import numpy as np
import pandas as pd
from pathlib import Path

MODEL_DIR = Path("models/saved")

def load_model():
    """Load the main ensemble model."""
    return joblib.load(MODEL_DIR / "ensemble.pkl")

def load_imputer():
    """Load the feature imputer."""
    return joblib.load(MODEL_DIR / "imputer.pkl")

def load_feature_names() -> list:
    """Load expected feature names in correct order."""
    return joblib.load(MODEL_DIR / "feature_names.pkl")

def predict_proba(model, features: pd.DataFrame) -> list[float]:
    imputer       = load_imputer()
    feature_names = load_feature_names()
    features      = features.reindex(columns=feature_names)
    
    # ✅ Keep as DataFrame with column names — fixes sklearn warning
    features_imputed = pd.DataFrame(
        imputer.transform(features),
        columns=feature_names
    )
    probs = model.predict_proba(features_imputed)[0]
    return probs.tolist()