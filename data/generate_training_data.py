"""
Generates synthetic labeled patient data to train the severity model.
Run: python data/generate_training_data.py
"""
import numpy as np
import pandas as pd

RNG = np.random.default_rng(42)
N = 2000


def main():
    respiratory_rate = RNG.normal(18, 4, N).clip(8, 40)
    spo2 = RNG.normal(95, 4, N).clip(70, 100)
    heart_rate = RNG.normal(85, 15, N).clip(40, 180)
    systolic_bp = RNG.normal(122, 18, N).clip(70, 200)
    temperature = RNG.normal(37.0, 0.8, N).clip(34, 41)
    age = RNG.integers(18, 95, N)

    # A NEWS2-style intuition: each vital contributes risk the further it
    # strays from normal. Weights are hand-picked, not clinically tuned --
    # good enough to give the model real signal to learn from.
    risk_score = (
        0.06 * (respiratory_rate - 16)
        + 0.10 * (94 - spo2)
        + 0.02 * np.abs(heart_rate - 80)
        + 0.015 * np.abs(systolic_bp - 120)
        + 0.6 * np.abs(temperature - 37.0)
        + 0.01 * age
        - 3.0  # baseline offset so an "average" patient sits at low risk
    )
    probability = 1 / (1 + np.exp(-risk_score))
    severe = RNG.binomial(1, probability)

    df = pd.DataFrame({
        "respiratory_rate": respiratory_rate.round(1),
        "spo2": spo2.round(1),
        "heart_rate": heart_rate.round(0),
        "systolic_bp": systolic_bp.round(0),
        "temperature": temperature.round(1),
        "age": age,
        "severe": severe,
    })
    df.to_csv("data/training_patients.csv", index=False)
    print(df.head())
    print("\nsevere rate:", df["severe"].mean())


if __name__ == "__main__":
    main()