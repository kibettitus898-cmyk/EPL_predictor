"""
Trains, evaluates, saves, and loads the EPL Random Forest model.
Two-stage approach: first predict Draw vs Non-Draw, then Home vs Away.
"""
import logging
import os
import joblib
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import TimeSeriesSplit, RandomizedSearchCV
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, accuracy_score
from scipy.stats import randint
from app.ml.features.feature_columns import FEATURE_COLS, TARGET_COL

logger = logging.getLogger(__name__)

MODEL_PATH = "models/saved/rf_epl_model.joblib"
ENCODER_PATH = "models/saved/label_encoder.joblib"
VERSION = "1.0.0"

def train(df: pd.DataFrame) -> dict:
    from app.ml.utils import impute   # import your existing impute()

    available_feat_cols = [c for c in FEATURE_COLS if c in df.columns]
    missing_cols = [c for c in FEATURE_COLS if c not in df.columns]
    if missing_cols:
        logger.warning(f"⚠️ {len(missing_cols)} feature cols missing: {missing_cols[:5]}...")

    df = df.dropna(subset=[TARGET_COL])   # ✅ already correct, keep as-is
    logger.info(f"🔢 RF training rows after dropna: {len(df)}")
    logger.info(f"Training rows: {len(df)}")

    X = df[available_feat_cols]
    y = df[TARGET_COL]
    weights = df.get("time_weight", pd.Series(np.ones(len(df)), index=df.index))

    # ✅ Split FIRST, then impute (no data leakage)
    from sklearn.model_selection import train_test_split
    X_tr, X_te, y_tr, y_te, w_tr, w_te = train_test_split(
        X, y, weights, test_size=0.2, random_state=42, shuffle=False
    )
    X_tr, X_te, imp = impute(X_tr, X_te)   # ← fills xG NaNs, adds _present cols

    tscv = TimeSeriesSplit(n_splits=5)
    param_dist = {
        "n_estimators": randint(300, 1000),
        "max_depth": randint(8, 20),
        "min_samples_split": randint(10, 25),
        "min_samples_leaf": randint(5, 15),
        "max_features": ["sqrt", "log2"],
    }
    base_rf = RandomForestClassifier(class_weight="balanced", random_state=42, n_jobs=-1)
    search = RandomizedSearchCV(
        base_rf, param_dist, n_iter=80, cv=tscv,
        scoring="accuracy", n_jobs=-1, random_state=42
    )
    search.fit(X_tr, y_tr, sample_weight=w_tr)   # ← train on imputed X_tr
    best = search.best_estimator_

    # Evaluate on held-out test set (not last fold)
    preds = best.predict(X_te)
    acc = accuracy_score(y_te, preds)
    report = classification_report(y_te, preds, output_dict=True)

    os.makedirs("models/saved", exist_ok=True)
    joblib.dump(best, MODEL_PATH)
    joblib.dump(imp, "models/saved/rf_imputer.joblib")   # save for inference
    logger.info(f"Model saved → {MODEL_PATH} | Accuracy: {acc:.4f}")

    return {"accuracy": round(acc, 4), "best_params": search.best_params_, "report": report}

def load_model() -> RandomForestClassifier:
    return joblib.load(MODEL_PATH)

def predict_match(home_features: dict) -> dict:
    model = load_model()
    X = pd.DataFrame([home_features])[FEATURE_COLS]
    proba = model.predict_proba(X)[0]
    classes = model.classes_          # alphabetical: A, D, H
    class_map = {c: p for c, p in zip(classes, proba)}
    predicted = classes[np.argmax(proba)]
    return {
        "predicted_outcome": predicted,
        "prob_home_win": round(class_map.get("H", 0), 4),
        "prob_draw":     round(class_map.get("D", 0), 4),
        "prob_away_win": round(class_map.get("A", 0), 4),
        "confidence":    round(float(np.max(proba)), 4),
        "model_version": VERSION,
    }
