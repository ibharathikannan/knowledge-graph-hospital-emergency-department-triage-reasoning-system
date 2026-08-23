"""
Trains the severity scoring model on the synthetic data from
data/generate_training_data.py, evaluates it, and saves it to disk.
Run: python train_model.py
"""
from pathlib import Path

import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split

FEATURES = ["respiratory_rate", "spo2", "heart_rate", "systolic_bp", "temperature", "age"]
MODEL_PATH = Path("models/severity_model.joblib")


def main():
    df = pd.read_csv("data/training_patients.csv")
    X = df[FEATURES]
    y = df["severe"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = LogisticRegression(max_iter=1000)
    model.fit(X_train, y_train)

    predicted_probabilities = model.predict_proba(X_test)[:, 1]
    predicted_labels = model.predict(X_test)

    print("accuracy:", accuracy_score(y_test, predicted_labels))
    print("roc_auc: ", roc_auc_score(y_test, predicted_probabilities))

    print("\nlearned weight per feature:")
    for feature, weight in zip(FEATURES, model.coef_[0]):
        print(f"  {feature:18s} {weight:+.3f}")

    MODEL_PATH.parent.mkdir(exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"\nsaved model to {MODEL_PATH}")


if __name__ == "__main__":
    main()