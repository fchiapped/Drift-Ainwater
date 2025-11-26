"""
Módulo de umbrales para detección de drift univariado.

Centraliza la política de decisión:
- Umbrales por defecto para cada métrica (PSI, KS, Wasserstein)
- Cálculo de umbrales dinámicos a partir de la serie de referencia

La idea central es:
  - PSI y KS usan umbrales fijos
  - Wasserstein usa un umbral proporcional a la dispersión histórica
    (factor * std), y si la serie es demasiado constante o vacía,
    se aplica un fallback simple
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


# ============================================================
#  Configuración de umbrales
# ============================================================

@dataclass
# Configuración global de umbrales para el detector de drift
class DriftThresholdConfig:
    psi: float = 0.30
    ks: float = 0.20
    wasserstein_factor: float = 0.60

# Determina el umbral a usar según la métrica y la dispersión histórica
def effective_threshold(
    method: str,
    ref_series: pd.Series,
    cfg: DriftThresholdConfig,
) -> float:

    method = str(method).lower().strip()

    if method == "psi":
        return float(cfg.psi)

    if method == "ks":
        return float(cfg.ks)

    if method == "wasserstein":
        # Convertimos a numérico y limpiamos NaN
        ref = pd.to_numeric(ref_series, errors="coerce").dropna()

        # Si la referencia es prácticamente vacía → fallback
        if ref.empty:
            # Fallback simple para evitar threshold = 0
            return 0.10

        std = float(ref.std())

        # Si la serie es casi constante o std es inválida → fallback
        if (not np.isfinite(std)) or std < 1e-6:
            return 0.10

        # Caso normal: threshold dinámico
        return float(cfg.wasserstein_factor * std)
    # Si no se reconoce el método, usar PSI como default
    return float(cfg.psi)