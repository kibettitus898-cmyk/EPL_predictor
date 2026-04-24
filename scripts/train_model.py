"""
Trains an EPL match outcome classifier using the full feature matrix.

Pipeline:
  1. Load features.parquet (built by build_features.py)
  2. Encode target H/D/A → 0/1/2
  3. TimeSeriesSplit cross-validation (5 folds)
  4. Train CatBoost + Random Forest ensemble
  5. Evaluate on held-out final season (24/25)
  6. Save models → models/saved/
  7. Save evaluation report → models/saved/eval_report.json
"""
import sys, os, json, logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import joblib

from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.metrics import (
    accuracy_score, log_loss,
    classification_report, confusion_matrix
)
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

from catboost import CatBoostClassifier

from app.ml.features.feature_columns import FEATURE_COLS, TARGET_COL, LABEL_MAP
from app.ml.utils import impute
from app.ml.models.xgb_model import build_xgb
from app.ml.stacking import train_stacking_ensemble


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────────────────────────────────────
FEATURES_PATH = Path("data/processed/features.parquet")
MODELS_DIR    = Path("models/saved")
MODELS_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# LOAD & PREPARE
# ─────────────────────────────────────────────────────────────────────────────

def load_data() -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    if not FEATURES_PATH.exists():
        raise FileNotFoundError(
            f"Feature matrix not found at {FEATURES_PATH}. "
            "Run: python scripts/build_features.py"
        )

    df = pd.read_parquet(FEATURES_PATH)
    logger.info(f"Loaded feature matrix: {len(df)} rows × {len(df.columns)} columns")

    # ── 1. Sort chronologically FIRST — everything downstream depends on this ──
    if "date" in df.columns:
        df = df.sort_values("date").reset_index(drop=True)
        logger.info("Sorted by date ✅")
    elif "match_date" in df.columns:
        df = df.sort_values("match_date").reset_index(drop=True)
        logger.info("Sorted by match_date ✅")
    else:
        logger.warning("⚠️  No date column found — order not guaranteed")


    # ── 2. Resolve available features ─────────────────────────────────────────
    available = [c for c in FEATURE_COLS if c in df.columns]
    missing   = [c for c in FEATURE_COLS if c not in df.columns]
    if missing:
        logger.warning(f"Missing {len(missing)} declared features (skipped): {missing}")

    X = df[available].copy()
    y = df[TARGET_COL].map(LABEL_MAP)

    # ── 3. Drop rows with no target label ONLY ────────────────────────────────
    #    DO NOT dropna on X — impute() will handle feature NaNs downstream
    valid = y.notna()
    n_dropped_target = int((~valid).sum())
    if n_dropped_target:
        logger.warning(f"Dropped {n_dropped_target} rows with missing target (unmapped result)")

    X = X[valid].copy()
    y = y[valid].astype(int)
    df_full = df[valid].reset_index(drop=True)
    X = X.reset_index(drop=True)
    y = y.reset_index(drop=True)

    # ── 4. NaN audit (informational — NOT used to drop rows) ──────────────────
    nan_by_col = X.isna().sum().sort_values(ascending=False)
    nan_cols   = nan_by_col[nan_by_col > 0]

    if nan_cols.empty:
        logger.info("No NaN values in feature matrix ✅")
    else:
        logger.info(f"NaN audit — {len(nan_cols)} columns have missing values:")
        for col, count in nan_cols.head(20).items():
            pct = count / len(X) * 100
            logger.info(f"   {col:<45} {count:>5} NaNs  ({pct:.1f}%)")
        if len(nan_cols) > 20:
            logger.info(f"   ... and {len(nan_cols) - 20} more columns")

    rows_with_nan = int(X.isna().any(axis=1).sum())
    logger.info(
        f"Rows with ≥1 NaN feature : {rows_with_nan} "
        f"({rows_with_nan/len(X)*100:.1f}%)  → will be imputed, NOT dropped"
    )
    # ── Odds coverage check ───────────────────────────────────────────────────────
    odds_cols = ["odds_fair_h", "odds_fair_d", "odds_fair_a", "odds_home_edge"]
    for col in odds_cols:
        if col in df.columns:
            coverage = df[col].notna().mean()
            logger.info(f"  {col}: {coverage*100:.1f}% coverage")
        else:
            logger.warning(f"  {col}: MISSING from feature matrix")

    # ── 5. Warn if NaN rate is suspiciously high for key feature groups ────────
    _warn_high_nan(nan_by_col, threshold=0.30)

    # ── 6. Target distribution ────────────────────────────────────────────────
    dist = y.value_counts().rename({0: "H", 1: "D", 2: "A"}).sort_index()
    logger.info(f"Target distribution:\n{dist.to_string()}")
    logger.info(f"Final usable rows: {len(X)}")

    return X, y, df_full


def _warn_high_nan(nan_by_col: pd.Series, threshold: float = 0.30):
    """Fires a clear warning for feature groups that exceed the NaN threshold."""
    groups = {
        "xG":        [c for c in nan_by_col.index if "xg" in c or "npxg" in c],
        "Elo":       [c for c in nan_by_col.index if "elo" in c],
        "H2H":       [c for c in nan_by_col.index if "h2h" in c],
        "Squad":     [c for c in nan_by_col.index if "squad" in c],
        "Rolling":   [c for c in nan_by_col.index if "rolling" in c or "form" in c],
    }
    total_rows = nan_by_col.sum()  # approximation for context
    for group, cols in groups.items():
        if not cols:
            continue
        worst = nan_by_col[cols].max() if cols else 0
        if worst > threshold and total_rows > 0:
            logger.warning(
                f"⚠️  High NaN rate in [{group}] features "
                f"(worst: {worst/total_rows*100:.0f}%) — "
                f"check min_periods=1 in feature_service.py"
            )


# def impute(X_train: pd.DataFrame, X_test: pd.DataFrame):
#     X_train = X_train.copy()
#     X_test  = X_test.copy()

#     null_rates   = X_train.isna().mean()
#     all_nan_cols = null_rates[null_rates == 1.0].index.tolist()
#     if all_nan_cols:
#         logger.warning(f"Dropping {len(all_nan_cols)} all-NaN cols: {all_nan_cols}")
#         X_train    = X_train.drop(columns=all_nan_cols)
#         X_test     = X_test.drop(columns=all_nan_cols, errors="ignore")
#         null_rates = null_rates.drop(index=all_nan_cols)

#     sparse_cols = null_rates[null_rates > 0.15].index.tolist()
#     if sparse_cols:
#         train_indicators = pd.DataFrame(
#             {f"{c}_present": X_train[c].notna().astype(int) for c in sparse_cols},
#             index=X_train.index
#         )
#         test_indicators = pd.DataFrame(
#             {f"{c}_present": X_test[c].notna().astype(int) for c in sparse_cols},
#             index=X_test.index
#         )
#         X_train = pd.concat([X_train, train_indicators], axis=1)
#         X_test  = pd.concat([X_test,  test_indicators],  axis=1)
#         logger.info(f"Added {len(sparse_cols)} missingness indicator columns")

#     imp = SimpleImputer(strategy="median")
#     X_train_imp = pd.DataFrame(
#         imp.fit_transform(X_train), columns=X_train.columns
#     )
#     X_test_imp = pd.DataFrame(
#         imp.transform(X_test), columns=X_train.columns
#     )
#     return X_train_imp, X_test_imp, imp


# ─────────────────────────────────────────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────────────────────────────────────────

def build_rf() -> RandomForestClassifier:
    return RandomForestClassifier(
        n_estimators=500,
        max_depth=12,
        min_samples_split=20,
        min_samples_leaf=10,
        max_features="sqrt",
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )


def build_catboost() -> CatBoostClassifier:
    return CatBoostClassifier(
        iterations=600,
        learning_rate=0.05,
        depth=5,
        loss_function="MultiClass",
        eval_metric="Accuracy",
        class_weights=[1.0, 1.3, 1.0],   # upweight draws (hardest to predict)
        random_seed=42,
        verbose=0,
    )

def build_catboost_draw() -> CatBoostClassifier:
    """Draw-specialist variant — shallower trees, heavier draw weight."""
    return CatBoostClassifier(
        iterations=800,
        learning_rate=0.03,
        depth=4,                         # shallower = less majority-class overfit
        loss_function="MultiClass",
        eval_metric="Accuracy",
        class_weights=[1.0, 3.5, 1.0],  # aggressive draw upweight
        random_seed=7,
        verbose=0,
    )


# ─────────────────────────────────────────────────────────────────────────────
# EVALUATION HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def evaluate(name: str, model, X_test: pd.DataFrame,
             y_test: pd.Series) -> dict:
    y_pred  = model.predict(X_test)
    y_proba = model.predict_proba(X_test)
    y_proba = y_proba / y_proba.sum(axis=1, keepdims=True)

    acc  = round(accuracy_score(y_test, y_pred), 4)
    ll   = round(log_loss(y_test, y_proba), 4)
    cr   = classification_report(
        y_test, y_pred,
        target_names=["Home Win", "Draw", "Away Win"],
        output_dict=True
    )

    logger.info(f"\n{'='*50}")
    logger.info(f"  {name}")
    logger.info(f"  Accuracy : {acc:.4f}")
    logger.info(f"  Log Loss : {ll:.4f}")
    logger.info(f"\n{classification_report(y_test, y_pred, target_names=['Home Win','Draw','Away Win'])}")

    cm = confusion_matrix(y_test, y_pred)
    logger.info(f"Confusion Matrix:\n{cm}")

    return {
        "model":           name,
        "accuracy":        acc,
        "log_loss":        ll,
        "classification":  cr,
        "confusion_matrix": cm.tolist(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# CROSS-VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

def cross_validate(model, X: pd.DataFrame, y: pd.Series,
                   name: str, n_splits: int = 5,
                   n_jobs: int = -1) -> float:
    tscv   = TimeSeriesSplit(n_splits=n_splits)
    scores = cross_val_score(model, X, y, cv=tscv,
                             scoring="accuracy", n_jobs=n_jobs)  # ← use param
    logger.info(f"{name} CV accuracy: "
                f"{scores.mean():.4f} ± {scores.std():.4f}  "
                f"| folds: {[round(s,4) for s in scores]}")
    return scores.mean()


# ─────────────────────────────────────────────────────────────────────────────
# FEATURE IMPORTANCE
# ─────────────────────────────────────────────────────────────────────────────

def log_feature_importance(model, feature_names: list, top_n: int = 20):
    if hasattr(model, "feature_importances_"):
        imp = pd.Series(model.feature_importances_, index=feature_names)
    elif hasattr(model, "get_feature_importance"):
        imp = pd.Series(
            model.get_feature_importance(),
            index=feature_names
        )
    else:
        return

    top = imp.nlargest(top_n)
    logger.info(f"\nTop {top_n} features:\n{top.to_string()}")

    # Save to CSV
    imp.sort_values(ascending=False).to_csv(
        MODELS_DIR / "feature_importance.csv", header=["importance"]
    )


# ─────────────────────────────────────────────────────────────────────────────
# MAIN TRAINING PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

def train():
    logger.info("=" * 60)
    logger.info("  EPL MATCH OUTCOME TRAINER")
    logger.info("=" * 60)

    # ── 1. Load data ──────────────────────────────────────────────────────────
    X, y, df_full = load_data()

    # ── 2. Temporal train/test split ─────────────────────────────────────────
    # Holdout: last full season (24/25) — never seen during training
    holdout_mask = df_full["season_label"] == "24/25"
    if holdout_mask.sum() < 100:
        logger.warning("24/25 holdout has <100 rows — using last 380 rows instead")
        holdout_mask = pd.Series(False, index=df_full.index)
        holdout_mask.iloc[-380:] = True

    X_train, X_test = X[~holdout_mask], X[holdout_mask]
    y_train, y_test = y[~holdout_mask], y[holdout_mask]

    logger.info(f"Train: {len(X_train)} rows | Holdout (24/25): {len(X_test)} rows")

    # ── 3. Impute missing values ──────────────────────────────────────────────
    X_train_imp, X_test_imp, imputer = impute(X_train, X_test)

    # ── 4. Build models ───────────────────────────────────────────────────────
    rf  = build_rf()
    cb  = build_catboost()
    xgb  = build_xgb()

    # In train_model.py — replace the entire SMOTE block (step 4b):

    # ── 4b. No SMOTE — RF uses class_weight="balanced", CatBoost uses class_weights ──
    # SMOTE + class_weight="balanced" double-compensate and hurt accuracy
    # Draw imbalance is handled at model level, not data level
    X_train_bal, y_train_bal = X_train_imp, y_train  # passthrough
    logger.info(f"Class distribution (no SMOTE): {pd.Series(y_train).value_counts().rename({0:'H',1:'D',2:'A'}).to_dict()}")

    # ── 5. Cross-validation on PRE-SMOTE data (no synthetic samples in CV) ───
    # CV must use original data — SMOTE only applies to final training fit
    logger.info("\nRunning TimeSeriesSplit cross-validation (5 folds)...")
    rf_cv   = cross_validate(rf,   X_train_imp, y_train, "RandomForest")
    cb_cv   = cross_validate(cb,   X_train_imp, y_train, "CatBoost")
    xgb_cv = cross_validate(xgb, X_train_imp, y_train, "XGBoost")

        # ── 6. Final fit on full training set ─────────────────────────────────────
    logger.info("\nFitting final models on full training set...")
    rf.fit(X_train_imp, y_train)
    xgb.fit(X_train_imp, y_train)
    cb.fit(X_train_imp, y_train)

    # ── 7. Soft-voting ensemble (fast baseline) ───────────────────────────────
    ensemble = VotingClassifier(
        estimators=[("rf", rf), ("xgb", xgb), ("cb", cb)],
        voting="soft",
        weights=[0.50, 0.30, 0.20],
    )
    ensemble.fit(X_train_imp, y_train)

    # ── 8. Holdout evaluation — base models + soft ensemble ───────────────────
    logger.info("\n" + "=" * 60)
    logger.info("  HOLDOUT EVALUATION (Season 24/25)")
    logger.info("=" * 60)

    results = []
    for name, model in [("RandomForest", rf), ("XGBoost", xgb),
                        ("CatBoost", cb), ("Ensemble", ensemble)]:
        res = evaluate(name, model, X_test_imp, y_test)
        res["cv_accuracy"] = (
            rf_cv  if name == "RandomForest" else
            xgb_cv if name == "XGBoost"      else
            cb_cv
        )
        results.append(res)

    # ── 9. OOF STACKING (replaces soft voting as best model) ─────────────────
    logger.info("\nBuilding OOF Stacking Ensemble...")
    base_models = {"RF": build_rf(), "XGB": build_xgb(), "CB": build_catboost()}
    stack_result = train_stacking_ensemble(
        base_models  = base_models,
        X_train      = X_train_imp,
        y_train      = y_train,
        X_test       = X_test_imp,
        y_test       = y_test,
        n_splits     = 7,
    )

    # ── 10. Save all models ───────────────────────────────────────────────────
    logger.info("\nSaving models...")
    joblib.dump(rf,                            MODELS_DIR / "random_forest.pkl")
    joblib.dump(xgb,                           MODELS_DIR / "xgboost.pkl")
    joblib.dump(cb,                            MODELS_DIR / "catboost.pkl")
    joblib.dump(ensemble,                      MODELS_DIR / "ensemble.pkl")
    joblib.dump(stack_result["meta_model"],    MODELS_DIR / "stacking_meta.pkl")
    joblib.dump(stack_result["base_models"],   MODELS_DIR / "stacking_base_models.pkl")
    joblib.dump(imputer,                       MODELS_DIR / "imputer.pkl")
    joblib.dump(X_train_imp.columns.tolist(),  MODELS_DIR / "feature_names.pkl")

    logger.info(f"  ✅ Models saved → {MODELS_DIR}/")

    # ── 11. Save eval report ──────────────────────────────────────────────────
    report = {
        "trained_at":     datetime.now().isoformat(),
        "train_rows":     len(X_train),
        "holdout_rows":   len(X_test),
        "features_used":  len(X_train_imp.columns),
        "models":         [
            {k: v for k, v in r.items() if k != "confusion_matrix"}
            for r in results
        ]
    }
    with open(MODELS_DIR / "eval_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)

    logger.info(f"  ✅ Eval report saved → {MODELS_DIR}/eval_report.json")


    # — 12. Save ELO ratings ————————————————————————————————
    final_elo = {}
    if "home_elo" in df_full.columns:
        for team in df_full["home_team"].unique():
            home_mask = df_full["home_team"] == team
            away_mask = df_full["away_team"] == team
            if home_mask.any():
                final_elo[team] = float(df_full.loc[home_mask, "home_elo"].iloc[-1])
            elif away_mask.any():
                final_elo[team] = float(df_full.loc[away_mask, "away_elo"].iloc[-1])
        with open("models/saved/elo_ratings.json", "w") as f:
            json.dump(final_elo, f, indent=2)
        logger.info(f"✅ ELO ratings saved → models/saved/elo_ratings.json ({len(final_elo)} teams)")
    else:
        logger.warning("⚠️ home_elo not in df_full — ELO not saved. Check engineer_features()")
    # ── 13. Final summary ─────────────────────────────────────────────────────
        # Include stacking in best model selection
        # ── Best model selection including stacking ───────────────────────────────
    stack_entry = {
        "model":    "StackingEnsemble",
        "accuracy": stack_result.get("test_accuracy",
                    stack_result.get("accuracy", 0.0)),   # handles both key names
        "log_loss": stack_result.get("log_loss",
                    stack_result.get("test_log_loss", 0.0)),  # handles both key names
    }
    all_results = results + [stack_entry]
    best = max(all_results, key=lambda r: r["accuracy"])

    logger.info("\n" + "=" * 60)
    logger.info(f"  BEST MODEL   : {best['model']}")
    logger.info(f"  ACCURACY     : {best['accuracy']:.4f} ({best['accuracy']*100:.1f}%)")
    logger.info(f"  LOG LOSS     : {best['log_loss']:.4f}")
    logger.info("=" * 60)

    target_met = best["accuracy"] >= 0.62
    logger.info(f"  62% TARGET   : {'✅ MET' if target_met else '❌ NOT YET'}")

    return best["accuracy"]




if __name__ == "__main__":
    acc = train()
    sys.exit(0 if acc >= 0.60 else 1)