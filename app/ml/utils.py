"""
Shared ML utilities — importable by both train_model.py and model modules
without circular imports.
"""
import logging
import pandas as pd
from sklearn.impute import SimpleImputer

logger = logging.getLogger(__name__)


def impute(X_train: pd.DataFrame, X_test: pd.DataFrame):
    X_train = X_train.copy()
    X_test  = X_test.copy()

    # Pre-fill to avoid empty-slice warnings on sparse CV folds
    train_medians = X_train.median()
    X_train = X_train.fillna(train_medians).fillna(0)
    X_test  = X_test.fillna(train_medians).fillna(0)

    null_rates   = X_train.isna().mean()
    all_nan_cols = null_rates[null_rates == 1.0].index.tolist()
    if all_nan_cols:
        logger.warning(f"Dropping {len(all_nan_cols)} all-NaN cols: {all_nan_cols}")
        X_train = X_train.drop(columns=all_nan_cols)
        X_test  = X_test.drop(columns=all_nan_cols, errors="ignore")
        null_rates = null_rates.drop(index=all_nan_cols)

    sparse_cols = null_rates[null_rates > 0.15].index.tolist()
    if sparse_cols:
        train_indicators = pd.DataFrame(
            {f"{c}_present": X_train[c].notna().astype(int) for c in sparse_cols},
            index=X_train.index
        )
        test_indicators = pd.DataFrame(
            {f"{c}_present": X_test[c].notna().astype(int) for c in sparse_cols},
            index=X_test.index
        )
        X_train = pd.concat([X_train, train_indicators], axis=1)
        X_test  = pd.concat([X_test,  test_indicators],  axis=1)
        logger.info(f"Added {len(sparse_cols)} missingness indicator columns")

    imp = SimpleImputer(strategy="median")
    X_train_imp = pd.DataFrame(
        imp.fit_transform(X_train), columns=X_train.columns
    )
    X_test_imp = pd.DataFrame(
        imp.transform(X_test), columns=X_train.columns
    )
    return X_train_imp, X_test_imp, imp