"""Train, evaluate and forecast.

Three scorers are compared on the same time-based split:
  * persistence: recent state-based deaths (a no-learning baseline),
  * logistic regression on standardised features,
  * histogram gradient boosting.
The one with the best average precision on the validation period is refitted on all
labelled months and used for the forecast. Test metrics are reported for all three.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import config
from .features import FEATURES


def make_models(seed=42):
    return {
        "logistic_regression": make_pipeline(
            SimpleImputer(strategy="median"), StandardScaler(),
            LogisticRegression(max_iter=2000, class_weight=None),
        ),
        "gradient_boosting": HistGradientBoostingClassifier(
            max_iter=300, learning_rate=0.05, max_leaf_nodes=31, l2_regularization=1.0,
            random_state=seed,
        ),
    }


def usable_features(frame):
    """Features with at least one observed value (e.g. World Bank columns may be missing)."""
    return [f for f in FEATURES if frame[f].notna().any()]


def split(frame):
    labelled = frame.dropna(subset=["target"])
    train_end = pd.Period(config.TRAIN_END, "M")
    valid_end = pd.Period(config.VALID_END, "M")
    train = labelled[labelled["month"] <= train_end]
    valid = labelled[(labelled["month"] > train_end) & (labelled["month"] <= valid_end)]
    test = labelled[labelled["month"] > valid_end]
    return train, valid, test


def persistence_score(frame):
    """Baseline: squash recent deaths into 0..1 (monotone, so ranking metrics are fair)."""
    return 1 - np.exp(-np.expm1(frame["sb_3m"]) / config.TARGET_DEATHS)


def metrics(y_true, score):
    y_true = np.asarray(y_true)
    if len(np.unique(y_true)) < 2:
        return {"roc_auc": None, "average_precision": None, "brier": None, "n": int(len(y_true)),
                "positives": int(y_true.sum())}
    return {
        "roc_auc": round(float(roc_auc_score(y_true, score)), 4),
        "average_precision": round(float(average_precision_score(y_true, score)), 4),
        "brier": round(float(brier_score_loss(y_true, np.clip(score, 0, 1))), 4),
        "n": int(len(y_true)),
        "positives": int(y_true.sum()),
    }


def evaluate(frame, seed=42):
    train, valid, test = split(frame)
    cols = usable_features(frame)
    results = {"persistence": {
        "validation": metrics(valid["target"], persistence_score(valid)),
        "test": metrics(test["target"], persistence_score(test)),
    }}
    for name, model in make_models(seed).items():
        model.fit(train[cols], train["target"].astype(int))
        results[name] = {
            "validation": metrics(valid["target"], model.predict_proba(valid[cols])[:, 1]),
        }
        # Refit on train + validation before scoring the untouched test period.
        refit = make_models(seed)[name]
        both = pd.concat([train, valid])
        refit.fit(both[cols], both["target"].astype(int))
        results[name]["test"] = metrics(test["target"], refit.predict_proba(test[cols])[:, 1])

    learned = [n for n in results if n != "persistence"]
    best = max(learned, key=lambda n: results[n]["validation"]["average_precision"] or 0)
    periods = {
        "train": [str(train["month"].min()), str(train["month"].max())],
        "validation": [str(valid["month"].min()), str(valid["month"].max())],
        "test": [str(test["month"].min()), str(test["month"].max())],
    }
    return results, best, periods


def risk_band(probability):
    for lower, label in config.RISK_BANDS:
        if probability >= lower:
            return label
    return config.RISK_BANDS[-1][1]


def forecast(frame, model_name, seed=42):
    """Fit the chosen model on every labelled month and score the latest month."""
    cols = usable_features(frame)
    labelled = frame.dropna(subset=["target"])
    model = make_models(seed)[model_name]
    model.fit(labelled[cols], labelled["target"].astype(int))
    latest_month = frame["month"].max()
    latest = frame[frame["month"] == latest_month].copy()
    latest["probability"] = model.predict_proba(latest[cols])[:, 1]
    latest["band"] = latest["probability"].map(risk_band)
    return latest.sort_values("probability", ascending=False), latest_month
