from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class DriftThresholdConfig:
    psi: float = 0.25               # umbral fijo para PSI
    ks: float = 0.15                # umbral fijo para KS
    wasserstein_factor: float = 0.6 # umbral = factor * std(ref)

    # Fallbacks
    min_fallback: float = 0.25
    fallback_std: float = 0.5

def effective_threshold(
    method: str,
    ref_series: pd.Series,
    cfg: DriftThresholdConfig,
    thr_override: float | None,
) -> float:

    method = str(method).lower()

    if thr_override is not None:
        return float(thr_override)

    if method == "psi":
        return float(cfg.psi)

    if method == "ks":
        return float(cfg.ks)

    if method == "wasserstein":
        ref_std = pd.to_numeric(ref_series, errors="coerce").dropna().std()
        if pd.isna(ref_std) or ref_std <= 0:
            return float(cfg.fallback_std)
        return float(ref_std * cfg.wasserstein_factor)

    return float(cfg.min_fallback)
