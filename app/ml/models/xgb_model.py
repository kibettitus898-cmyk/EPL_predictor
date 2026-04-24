from xgboost import XGBClassifier

def build_xgb() -> XGBClassifier:
    return XGBClassifier(
        n_estimators=400,
        learning_rate=0.05,
        max_depth=4,
        subsample=0.8,
        colsample_bytree=0.7,
        reg_alpha=0.1,             # ← add L1 regularisation
        reg_lambda=1.5,            # ← add L2 regularisation
        use_label_encoder=False,
        eval_metric="mlogloss",
        scale_pos_weight=1,
        random_state=42,
        n_jobs=-1,          # XGBoost doesn't have the OpenMP deadlock
        verbosity=0,
    )