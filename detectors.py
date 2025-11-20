from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from funciones_drift import (
    ref_decay_prefix_mass,
    ref_golden,
    ref_seasonal,
    _score_numeric_series,
)


@dataclass
class DriftConfig:
    metric: str = "ks"          # "psi", "ks" o "wasserstein"
    strategy: str = "golden"    # "decay", "golden" o "seasonal"
    window: str = "24h"         # tamaño de ventana (ej. "6h", "24h")
    threshold: float = 0.2      # umbral de la métrica
    min_points: int = 5         # puntos mínimos en ventana actual
    hysteresis_windows: int = 2 # ventanas "normales" para cerrar drift


def _build_reference(
    df_hist: pd.DataFrame,
    now: pd.Timestamp,
    strategy: str,
) -> pd.DataFrame:

    if df_hist.empty:
        return df_hist

    if strategy == "decay":
        ref = ref_decay_prefix_mass(df_hist, now=now)
    elif strategy == "golden":
        ref = ref_golden(df_hist)
    elif strategy == "seasonal":
        ref = ref_seasonal(df_hist, current_end=now)
    else:
        raise ValueError(f"Estrategia desconocida: {strategy!r}")

    if ref is None or ref.empty:
        ref = df_hist
    return ref


def _effective_threshold(cfg: DriftConfig, ref_series: pd.Series) -> float:

    thr = cfg.threshold
    if cfg.metric.lower() == "wasserstein":
        # Si viene como None o NaN → usar 0.5 * std(ref) como fallback
        if thr is None or (isinstance(thr, float) and np.isnan(thr)):
            std_ref = pd.to_numeric(ref_series, errors="coerce").dropna().std()
            if pd.isna(std_ref):
                return 0.5
            return float(0.5 * std_ref)
    return float(thr)


def detect_drift_univariate(
    df: pd.DataFrame,
    cfg: DriftConfig,
) -> pd.Series:
    
    if df.empty:
        raise ValueError("El DataFrame de entrada está vacío.")

    if df.index.dtype != "datetime64[ns]":
        raise ValueError("El índice del DataFrame debe ser datetime (ya indexado en 'date_time').")

    if len(df.columns) != 1:
        raise ValueError("detect_drift_univariate espera exactamente UNA columna numérica.")

    col = df.columns[0]
    s = df[col]

    drift_flags = pd.Series(False, index=df.index)

    w = pd.to_timedelta(cfg.window)
    t_min, t_max = df.index.min(), df.index.max()
    if pd.isna(t_min) or pd.isna(t_max):
        return drift_flags

    t_ends = pd.date_range(t_min + w, t_max, freq=cfg.window)

    in_drift = False
    normal_count = 0

    for t_end in t_ends:
        t0 = t_end - w

        df_hist = df.loc[: t0 - pd.Timedelta(microseconds=1)]
        df_cur = df.loc[t0:t_end]

        if df_hist.empty or df_cur.empty:
            continue

        cur_series = df_cur[col].dropna()
        if cur_series.size < cfg.min_points:
            continue

        ref_df = _build_reference(df_hist, now=t_end, strategy=cfg.strategy)
        if col not in ref_df.columns:
            ref_series = df_hist[col].dropna()
        else:
            ref_series = ref_df[col].dropna()

        if ref_series.empty:
            continue

        # Valor de la métrica
        stat = _score_numeric_series(ref_series, cur_series, cfg.metric)
        if stat is None or np.isnan(stat):
            drift_now = False
        else:
            thr = _effective_threshold(cfg, ref_series)
            drift_now = bool(stat >= thr)

        if drift_now:
            in_drift = True
            normal_count = 0
        else:
            if in_drift:
                normal_count += 1
                if normal_count >= cfg.hysteresis_windows:
                    in_drift = False
                    normal_count = 0

        if in_drift:
            drift_flags.loc[t0:t_end] = True

    return drift_flags
