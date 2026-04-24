from lightgbm import LGBMClassifier

def build_lgbm() -> LGBMClassifier:
    return LGBMClassifier(
        n_estimators=500,
        learning_rate=0.05,
        max_depth=6,
        num_leaves=31,
        min_child_samples=20,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=None,
        is_unbalance=False,
        random_state=42,
        n_jobs=1,
        verbose=-1,
    )