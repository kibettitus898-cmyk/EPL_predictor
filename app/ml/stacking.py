"""
Out-of-Fold stacking ensemble for EPL match outcome prediction.
Uses TimeSeriesSplit to avoid future data leakage.
"""
import copy
import logging
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    log_loss,
)
from sklearn.model_selection import TimeSeriesSplit

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────
MODEL_DIR = Path("models")
ENSEMBLE_FILENAME = "stacking_ensemble.joblib"


# ── 1. OOF Meta-Feature Builder ───────────────────────────────────────────────
def build_oof_meta_features(
    models: dict,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    n_splits: int = 5,
) -> np.ndarray:
    """
    Generate OOF probability predictions from each base model.

    Returns array of shape (n_train_rows, n_models * 3).
    Respects temporal order via TimeSeriesSplit.
    """
    tscv = TimeSeriesSplit(n_splits=n_splits)
    n_models = len(models)
    oof = np.zeros((len(X_train), n_models * 3))

    for fold_idx, (tr_idx, val_idx) in enumerate(tscv.split(X_train)):
        X_tr = X_train.iloc[tr_idx]
        X_val = X_train.iloc[val_idx]
        y_tr = y_train.iloc[tr_idx]

        logger.info(
            f"  OOF fold {fold_idx + 1}/{n_splits} "
            f"— train: {len(tr_idx)}, val: {len(val_idx)}"
        )

        col = 0
        for name, model in models.items():
            fold_model = copy.deepcopy(model)
            fold_model.fit(X_tr, y_tr)
            proba = fold_model.predict_proba(X_val)  # shape (val, 3)
            oof[val_idx, col : col + 3] = proba
            col += 3

    # Guard: warn if any OOF rows were never filled (e.g. first fold gap)
    unfilled = np.where(oof.sum(axis=1) == 0)[0]
    if len(unfilled):
        logger.warning(
            f"  {len(unfilled)} OOF rows have zero probabilities "
            "(likely first-fold gap). Filling with uniform 1/3."
        )
        oof[unfilled] = 1.0 / 3.0

    return oof


# ── 2. Meta-Learner Trainer ───────────────────────────────────────────────────
def build_meta_learner(
    oof: np.ndarray,
    y_train: pd.Series,
) -> LogisticRegression:
    """
    Train a regularised multinomial logistic regression on OOF predictions.

    C=0.1 keeps the meta-learner from over-fitting to base-model quirks.
    """
    meta = LogisticRegression(
        C=0.1,
        max_iter=1000,
        random_state=42,
        multi_class="multinomial",
        solver="lbfgs",
        class_weight=None,   # ← remove the draw weight
    )
    meta.fit(oof, y_train)
    oof_pred = meta.predict(oof)
    logger.info(
        f"  Meta-learner OOF accuracy : {accuracy_score(y_train, oof_pred):.4f}"
    )
    logger.info(
        f"  Meta-learner OOF log-loss : {log_loss(y_train, meta.predict_proba(oof)):.4f}"
    )
    return meta


# ── 3. Test Meta-Feature Builder ──────────────────────────────────────────────
def make_test_meta_features(
    models: dict,
    X_test: pd.DataFrame,
) -> np.ndarray:
    """
    Generate meta-features for the holdout set from final fitted base models.

    NOTE: base models must already be refitted on the full training set
    before calling this function.
    """
    parts = []
    for name, model in models.items():
        proba = model.predict_proba(X_test)  # shape (n_test, 3)
        parts.append(proba)
    return np.hstack(parts)  # shape (n_test, n_models * 3)


# ── 4. Calibrated Wrapper ─────────────────────────────────────────────────────
def calibrate_meta_learner(
    meta: LogisticRegression,
    oof: np.ndarray,
    y_train: pd.Series,
    method: str = "sigmoid",
) -> CalibratedClassifierCV:
    """
    Wrap the already-fitted meta-learner in sigmoid / Platt calibration.

    Uses cv='prefit' because the meta-learner was trained on OOF preds,
    so we must NOT re-cross-validate here to avoid data leakage.

    Parameters
    ----------
    method : 'isotonic'  — non-parametric, better with >1000 samples
             'sigmoid'   — Platt scaling, better with small datasets
    """
    calibrated = CalibratedClassifierCV(estimator=meta, cv="prefit", method=method)
    calibrated.fit(oof, y_train)
    logger.info(f"  Meta-learner calibrated with method='{method}'")
    return calibrated


# ── 5. Save / Load Helpers ────────────────────────────────────────────────────
def save_ensemble(artifact: dict, path: Optional[Path] = None) -> Path:
    """
    Persist the full ensemble artifact to disk via joblib.

    artifact keys expected:
        meta_model      : fitted (and optionally calibrated) meta-learner
        base_models     : dict of refitted base models
        feature_columns : list[str] used during training
        class_order     : list of class labels (e.g. ['A', 'D', 'H'])
        train_accuracy  : float
        train_log_loss  : float
        test_accuracy   : float
        test_log_loss   : float
    """
    path = path or MODEL_DIR / ENSEMBLE_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, path, compress=3)
    logger.info(f"  Ensemble saved → {path}")
    return path


def load_ensemble(path: Optional[Path] = None) -> dict:
    """Load a previously saved ensemble artifact from disk."""
    path = path or MODEL_DIR / ENSEMBLE_FILENAME
    if not path.exists():
        raise FileNotFoundError(f"No ensemble found at {path}")
    artifact = joblib.load(path)
    logger.info(f"  Ensemble loaded ← {path}")
    return artifact


# ── 6. Full Training Pipeline ─────────────────────────────────────────────────
def train_stacking_ensemble(
    base_models: dict,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    n_splits: int = 7,
    calibrate: bool = True,
    calibration_method: str = "sigmoid",
    save_path: Optional[Path] = None,
) -> dict:
    """
    Full OOF stacking pipeline with optional calibration and persistence.

    Parameters
    ----------
    base_models       : dict  e.g. {"RF": rf, "LGBM": lgbm, "CB": cb}
    X_train, y_train  : temporally-ordered training features + labels
    X_test, y_test    : holdout set (must be strictly after training period)
    n_splits          : number of TimeSeriesSplit folds
    calibrate         : whether to sigmoid/Platt-calibrate the meta-learner
    calibration_method: 'sigmoid' or 'sigmoid'
    save_path         : override default save location (optional)

    Returns
    -------
    dict with keys:
        meta_model, base_models, oof_array,
        test_accuracy, test_log_loss,
        y_pred, y_proba, class_order
    """
    logger.info("=" * 60)
    logger.info("  OOF STACKING ENSEMBLE")
    logger.info("=" * 60)

    # ── Step 1: OOF meta-features ─────────────────────────────────────────────
    logger.info("Step 1 — Generating OOF meta-features...")
    oof = build_oof_meta_features(base_models, X_train, y_train, n_splits)
    logger.info(f"  OOF meta-feature matrix: {oof.shape}")

    # ── Step 2: Meta-learner ──────────────────────────────────────────────────
    logger.info("Step 2 — Training meta-learner on OOF predictions...")
    meta = build_meta_learner(oof, y_train)

    # ── Step 3: Optional calibration ─────────────────────────────────────────
    if calibrate:
        logger.info("Step 3 — Calibrating meta-learner...")
        meta = calibrate_meta_learner(meta, oof, y_train, method=calibration_method)
    else:
        logger.info("Step 3 — Skipping calibration (calibrate=False)")

    # ── Step 4: Refit ALL base models on full training set ────────────────────
    logger.info("Step 4 — Refitting base models on full training set...")
    for name, model in base_models.items():
        model.fit(X_train, y_train)
        train_acc = accuracy_score(y_train, model.predict(X_train))
        logger.info(f"  ✅ {name} refitted | train acc: {train_acc:.4f}")

    # ── Step 5: Test meta-features ────────────────────────────────────────────
    logger.info("Step 5 — Generating test meta-features...")
    test_meta = make_test_meta_features(base_models, X_test)

    # ── Step 6: Evaluate on holdout ───────────────────────────────────────────
    logger.info("Step 6 — Evaluating stacking ensemble on holdout set...")
    y_pred = meta.predict(test_meta)
    y_proba = meta.predict_proba(test_meta)
    acc = accuracy_score(y_test, y_pred)
    ll = log_loss(y_test, y_proba)

    class_names = ["Home Win", "Draw", "Away Win"]   # ← hardcoded, safe

    logger.info(f"\n{'='*50}")
    logger.info(f"  Stacking Ensemble — Holdout Results")
    logger.info(f"  Accuracy  : {acc:.4f}")
    logger.info(f"  Log Loss  : {ll:.4f}")
    logger.info(f"\n{classification_report(y_test, y_pred, target_names=class_names)}")
    logger.info(f"\nConfusion Matrix:\n{confusion_matrix(y_test, y_pred)}")
    logger.info(f"{'='*50}")

    # ── Step 7: Base model individual scores for comparison ───────────────────
    logger.info("Step 7 — Individual base model scores on holdout:")
    for name, model in base_models.items():
        bm_pred = model.predict(X_test)
        bm_proba = model.predict_proba(X_test)
        bm_acc = accuracy_score(y_test, bm_pred)
        bm_ll = log_loss(y_test, bm_proba)
        logger.info(f"  {name:<10} acc: {bm_acc:.4f}  log-loss: {bm_ll:.4f}")

    # ── Step 8: Persist artifact ──────────────────────────────────────────────
    artifact = {
        "meta_model": meta,
        "base_models": base_models,
        "oof_array": oof,
        "feature_columns": list(X_train.columns),
        "class_order": class_names,
        "test_accuracy": acc,
        "test_log_loss": ll,
        "y_pred": y_pred,
        "y_proba": y_proba,
        "calibrated": calibrate,
        "calibration_method": calibration_method if calibrate else None,
        "n_splits": n_splits,
    }
    save_ensemble(artifact, save_path)

    return {
        "meta_model":  meta,
        "base_models": base_models,
        "oof":         oof,
        "accuracy":    acc,      # ← was "test_accuracy", rename to "accuracy"
        "log_loss":    ll,       # ← keep as is
    }


# ── 7. Inference Helper ───────────────────────────────────────────────────────
def predict_with_ensemble(
    artifact: dict,
    X: pd.DataFrame,
) -> dict:
    """
    Run inference on new data using a loaded ensemble artifact.

    Parameters
    ----------
    artifact : loaded via load_ensemble()
    X        : DataFrame with the same feature columns used during training

    Returns
    -------
    dict:
        predicted_class : np.ndarray of class labels
        probabilities   : np.ndarray shape (n, 3) — [Away, Draw, Home]
        class_order     : list of class label names
    """
    expected_cols = artifact["feature_columns"]
    missing = set(expected_cols) - set(X.columns)
    if missing:
        raise ValueError(f"Missing feature columns at inference: {missing}")

    X_aligned = X[expected_cols]
    test_meta = make_test_meta_features(artifact["base_models"], X_aligned)
    y_proba = artifact["meta_model"].predict_proba(test_meta)
    y_pred = artifact["meta_model"].predict(test_meta)

    return {
        "predicted_class": y_pred,
        "probabilities": y_proba,
        "class_order": artifact["class_order"],
    }