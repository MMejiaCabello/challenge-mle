from pathlib import Path
from typing import List, Tuple, Union

import pandas as pd
from sklearn.linear_model import LogisticRegression

FEATURES_COLS = [
    "OPERA_Latin American Wings",
    "MES_7",
    "MES_10",
    "OPERA_Grupo LATAM",
    "MES_12",
    "TIPOVUELO_I",
    "MES_4",
    "MES_11",
    "OPERA_Sky Airline",
    "OPERA_Copa Air",
]

class DelayModel:

    def __init__(
        self
    ):
        self._model = None # Model should be saved in this attribute.

    def preprocess(
        self,
        data: pd.DataFrame,
        target_column: str = None
    ) -> Union[Tuple[pd.DataFrame, pd.DataFrame], pd.DataFrame]:
        """
        Prepare raw data for training or predict.

        Args:
            data (pd.DataFrame): raw data.
            target_column (str, optional): if set, the target is returned.

        Returns:
            Tuple[pd.DataFrame, pd.DataFrame]: features and target.
            or
            pd.DataFrame: features.
        """
        data = self._add_engineered_columns(data)
        features = pd.concat(
            [
                pd.get_dummies(data["OPERA"], prefix="OPERA"),
                pd.get_dummies(data["TIPOVUELO"], prefix="TIPOVUELO"),
                pd.get_dummies(data["MES"], prefix="MES"),
            ],
            axis=1,
        )
        features = features.reindex(columns=FEATURES_COLS, fill_value=0)
        features = features.astype(int)

        if target_column is None:
            return features

        target = data[[target_column]].astype(int)
        return features, target

    def fit(
        self,
        features: pd.DataFrame,
        target: pd.DataFrame
    ) -> None:
        """
        Fit model with preprocessed data.

        Args:
            features (pd.DataFrame): preprocessed data.
            target (pd.DataFrame): target.
        """
        model = LogisticRegression(
            class_weight="balanced",
            max_iter=1000,
            random_state=42,
        )
        model.fit(features, target.values.ravel())
        self._model = model

    def predict(
        self,
        features: pd.DataFrame
    ) -> List[int]:
        """
        Predict delays for new flights.

        Args:
            features (pd.DataFrame): preprocessed data.
        
        Returns:
            (List[int]): predicted targets.
        """
        if self._model is None:
            self._fit_from_default_data()

        predictions = self._model.predict(features)
        return [int(prediction) for prediction in predictions]
    
    def _add_engineered_columns(self, data: pd.DataFrame) -> pd.DataFrame:
        data = data.copy()
        if "min_diff" not in data.columns and {"Fecha-I", "Fecha-O"}.issubset(data.columns):
            data["min_diff"] = self._make_min_diff(data)
        if "delay" not in data.columns and "min_diff" in data.columns:
            data["delay"] = (data["min_diff"] > 15).astype(int)
        if "high_season" not in data.columns and "Fecha-I" in data.columns:
            data["high_season"] = pd.to_datetime(data["Fecha-I"]).map(self._is_high_season)
        if "period_day" not in data.columns and "Fecha-I" in data.columns:
            data["period_day"] = pd.to_datetime(data["Fecha-I"]).map(self._get_period_day)
        return data

    @staticmethod
    def _make_min_diff(data: pd.DataFrame) -> pd.Series:
        fecha_i = pd.to_datetime(data["Fecha-I"])
        fecha_o = pd.to_datetime(data["Fecha-O"])
        return (fecha_o - fecha_i).dt.total_seconds() / 60

    @staticmethod
    def _is_high_season(date: pd.Timestamp) -> int:
        ranges = [
            ((12, 15), (12, 31)),
            ((1, 1), (3, 3)),
            ((7, 15), (7, 31)),
            ((9, 11), (9, 30)),
        ]
        current = (date.month, date.day)
        return int(any(start <= current <= end for start, end in ranges))

    @staticmethod
    def _get_period_day(date: pd.Timestamp) -> str:
        hour = date.hour
        if 5 <= hour < 12:
            return "morning"
        if 12 <= hour < 19:
            return "afternoon"
        return "night"

    def _fit_from_default_data(self) -> None:
        data_path = Path(__file__).resolve().parent.parent / "data" / "data.csv"
        data = pd.read_csv(data_path, low_memory=False)
        features, target = self.preprocess(data=data, target_column="delay")
        self.fit(features=features, target=target)
