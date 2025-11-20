from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any

import numpy as np
import pandas as pd

from funciones_drift import run_drift_all_multi_metric


@dataclass
class DriftDetectorConfig:
    metric: str = "ks"              # "psi", "ks" o "wasserstein"
    strategy: str = "golden"        # "decay", "golden", "seasonal"
    window: str = "24H"             # tamaño de ventana, ej. "12H", "24H"
    threshold: Optional[float] = None  # umbral; si None, usa defaults de backend
    min_points: int = 5             # mínimo de puntos por ventana


class DriftDetector:
    """
    Envoltura simple sobre run_drift_all_multi_metric para una sola variable.

    Dado un DataFrame indexado por date_time y una columna numérica,
    calcula:

    - drift_label (bool) por timestamp.
    - score_{metric} por timestamp (estadístico de la ventana que lo contiene).
    """

    def __init__(self, config: DriftDetectorConfig) -> None:
        self.config = config

    def _run_windows(self, df_var: pd.DataFrame, variable: str) -> pd.DataFrame:
        """
        Ejecuta run_drift_all_multi_metric para una sola variable y un solo set
        (window, strategy, metric).
        """
        metric = self.config.metric
        thr_dict: Optional[Dict[str, float]] = None
        if self.config.threshold is not None:
            thr_dict = {metric: self.config.threshold}

        df_windows = run_drift_all_multi_metric(
            df=df_var,
            windows=(self.config.window,),
            strategies=(self.config.strategy,),
            metrics=(metric,),
            thresholds=thr_dict,
            min_points=self.config.min_points,
        )

        # Filtrar solo la variable/métrica de interés
        df_win_sub = df_windows[
            (df_windows["variable"] == variable)
            & (df_windows["metric"] == metric)
        ].copy()

        return df_win_sub

    def detect_for_variable(self, df_var: pd.DataFrame, variable: str) -> pd.DataFrame:
        """
        df_var: DataFrame con índice datetime y UNA columna = variable.
        Retorna DataFrame con:

        - date_time
        - value
        - drift_label (bool)
        - score_{metric} (float)
        """
        if variable not in df_var.columns:
            raise ValueError(f"La columna '{variable}' no está en df_var.columns")

        if not isinstance(df_var.index, pd.DatetimeIndex):
            raise TypeError("df_var debe estar indexado por un DatetimeIndex")

        idx = df_var.index
        metric = self.config.metric

        df_win = self._run_windows(df_var=df_var, variable=variable)

        # Series de salida
        drift_flag = pd.Series(False, index=idx)
        score = pd.Series(np.nan, index=idx, dtype="float64")

        # Marcar drift por timestamp, usando las ventanas detectadas
        for _, row in df_win.iterrows():
            if not bool(row.get("drift_flag", False)):
                continue

            t0 = row["t0"]
            t1 = row["t1"]
            stat_val = row.get("stat_value", np.nan)

            mask = (idx >= t0) & (idx <= t1)
            if not mask.any():
                continue

            # Actualizar drift_flag
            drift_flag.loc[mask] = True

            # Actualizar score: nos quedamos con el máximo por timestamp
            current_vals = score.loc[mask].to_numpy()
            new_vals = np.where(
                np.isnan(current_vals),
                stat_val,
                np.maximum(current_vals, stat_val),
            )
            score.loc[mask] = new_vals

        out = pd.DataFrame(
            {
                "date_time": idx,
                "value": df_var[variable].to_numpy(),
                "drift_label": drift_flag.to_numpy(),
                f"score_{metric}": score.to_numpy(),
            }
        )

        return out
