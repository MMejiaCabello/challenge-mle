"""Train the delay model and persist it as a joblib artifact."""

from pathlib import Path

import pandas as pd

from challenge.model import MODEL_PATH, DelayModel

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "data.csv"


def main() -> None:
    data = pd.read_csv(DATA_PATH, low_memory=False)
    model = DelayModel()
    features, target = model.preprocess(data=data, target_column="delay")
    model.fit(features=features, target=target)
    model.save()
    print(f"Model saved to {MODEL_PATH}")


if __name__ == "__main__":
    main()
