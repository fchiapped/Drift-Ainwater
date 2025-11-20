# drift_detectors.py
from dataclasses import dataclass
from typing import Dict, Any

import numpy as np
import pandas as pd

import funciones_drift  # <- tu módulo existente


@dataclass
class DriftResult:
    metrics: Dict[str, float]
    is_drift: bool


class DriftDetector:
    """Interfaz genérica para detectores de drift."""

    def __init__(self, thresholds: Dict[str, float]):
        self.thresholds = thresholds

    def compute_metrics(self, ref: pd.Series, cur: pd.Series) -> Dict[str, float]:
        raise NotImplementedError

    def is_drift(self, metrics: Dict[str, float]) -> bool:
        for k, v in metrics.items():
            if k in self.thresholds:
                thr = self.thresholds[k]
                # Caso especial p-value: drift si p <= thr
                if "pvalue" in k.lower():
                    if v <= thr:
                        return True
                else:
                    if v >= thr:
                        return True
        return False

    def run(self, ref: pd.Series, cur: pd.Series) -> DriftResult:
        metrics = self.compute_metrics(ref, cur)
        return DriftResult(metrics=metrics, is_drift=self.is_drift(metrics))


class NumericDriftDetector(DriftDetector):
    """
    Detector que usa PSI, KS, Wasserstein y Mann-Whitney.
    Asume que tus funciones en funciones_drift toman (ref, cur) y devuelven un valor.
    """

    def compute_metrics(self, ref: pd.Series, cur: pd.Series) -> Dict[str, float]:
        ref = ref.dropna()
        cur = cur.dropna()

        if len(ref) == 0 or len(cur) == 0:
            return {
                "psi": np.nan,
                "ks": np.nan,
                "wasserstein": np.nan,
                "mannwhitney_pvalue": np.nan,
            }

        psi = funciones_drift.psi_numeric(ref, cur)
        ks_stat, ks_p = funciones_drift.ks_numeric(ref, cur)
        wass = funciones_drift.wasserstein_numeric(ref, cur)
        mwu_stat, mwu_p = funciones_drift.mannwhitney_numeric(ref, cur)

        return {
            "psi": float(psi),
            "ks": float(ks_stat),
            "ks_pvalue": float(ks_p),
            "wasserstein": float(wass),
            "mannwhitney_pvalue": float(mwu_p),
        }