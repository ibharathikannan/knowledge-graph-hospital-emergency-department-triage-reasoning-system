"""
Loads the trained severity model and exposes a clean predict_severity()
interface -- the only function the rest of the app needs to know about.
"""
from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd

MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "severity_model.joblib"
FEATURES = ["respiratory_rate", "spo2", "heart_rate", "systolic_bp", "temperature", "age"]

_model = None


def _get_model():
    global _model
    if _model is None:
        _model = joblib.load(MODEL_PATH)
    return _model


def predict_severity(vitals: dict) -> float:
    """Given raw vitals, return the model's P(severe) as a float 0-1."""
    model = _get_model()
    row = pd.DataFrame([{f: vitals[f] for f in FEATURES}])
    probability = model.predict_proba(row)[0, 1]
    return float(probability)