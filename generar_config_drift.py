"""
Generador de archivo de configuración para el detector de drift univariado.

Este módulo crea un archivo JSON que define los parámetros operativos del
pipeline:

- Método estadístico global (psi, ks o wasserstein)
- Estrategia global de referencia (decay, golden, seasonal)
- Tamaño de ventana
- Mínimo de puntos por ventana
- Parámetros por defecto para estrategias estacionales (seasonal_defaults)

NOTA:
- Qué variables son cíclicas NO se define aquí, sino vía CLI en main.py
  usando --cyclical_vars.
"""

import argparse
import json
from pathlib import Path


# ============================================================
#  Configuración por defecto
# ============================================================

DEFAULT_CONFIG = {
    "global": {
        "method": "wasserstein",   # "psi", "ks" o "wasserstein"
        "strategy": "decay",       # "decay", "golden", "seasonal"
        "window": "12h",           # tamaño de ventana
        "min_points": 60           # mínimo de puntos por ventana
    },

    # Defaults para cualquier variable cuya estrategia sea "seasonal"
    "seasonal_defaults": {
        "cycle_hours": 24.0,       # ciclo típico diario
        "cycles_back": 20,         # cuántos ciclos hacia atrás para referencia
        "band_frac": 0.15          # ancho relativo de la banda de fase
    },

    # Espacio para overrides manuales por variable (normalmente vacío)
    "variables": {}
}


# ============================================================
#  Generación del archivo JSON
# ============================================================

def main() -> None:
    """
    Genera un archivo JSON de configuración para el pipeline de drift.

    Si el usuario entrega parámetros por CLI (por ejemplo, --window "24h"),
    estos reemplazan los valores del bloque global o seasonal_defaults.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Genera un archivo de configuración para el detector de drift "
            "(solo parámetros operativos; los umbrales viven en drift_thresholds.py)."
        )
    )

    parser.add_argument(
        "--output",
        default="config/config_drift.json",
        help="Ruta donde guardar el archivo JSON (por defecto: config/config_drift.json).",
    )

    # ----- Bloque global -----
    parser.add_argument(
        "--method",
        type=str,
        choices=["psi", "ks", "wasserstein"],
        help="Métrica global a usar.",
    )

    parser.add_argument(
        "--strategy",
        type=str,
        choices=["decay", "golden", "seasonal"],
        help="Estrategia de referencia global.",
    )

    parser.add_argument(
        "--window",
        type=str,
        help="Tamaño de ventana global (ej: '12h', '24h', '6h').",
    )

    parser.add_argument(
        "--min-points",
        type=int,
        help="Mínimo de puntos por ventana para evaluar drift.",
    )

    # ----- Defaults estacionales (opcionales) -----
    parser.add_argument(
        "--cycle-hours",
        type=float,
        help="Ciclo base en horas para estrategias 'seasonal' (default: 24.0).",
    )

    parser.add_argument(
        "--cycles-back",
        type=int,
        help="Número de ciclos hacia atrás para referencia estacional (default: 20).",
    )

    parser.add_argument(
        "--band-frac",
        type=float,
        help="Ancho relativo de banda de fase alrededor del ciclo (default: 0.15).",
    )

    args = parser.parse_args()

    # Partimos del DEFAULT_CONFIG (copia superficial)
    config = {
        "global": DEFAULT_CONFIG["global"].copy(),
        "seasonal_defaults": DEFAULT_CONFIG["seasonal_defaults"].copy(),
        "variables": {}
    }

    # -------------------------
    # Bloque global
    # -------------------------
    global_cfg = config["global"]

    if args.method is not None:
        global_cfg["method"] = args.method

    if args.strategy is not None:
        global_cfg["strategy"] = args.strategy

    if args.window is not None:
        global_cfg["window"] = args.window

    if args.min_points is not None:
        global_cfg["min_points"] = int(args.min_points)

    # -------------------------
    # seasonal_defaults
    # -------------------------
    seasonal_cfg = config["seasonal_defaults"]

    if args.cycle_hours is not None:
        seasonal_cfg["cycle_hours"] = float(args.cycle_hours)

    if args.cycles_back is not None:
        seasonal_cfg["cycles_back"] = int(args.cycles_back)

    if args.band_frac is not None:
        seasonal_cfg["band_frac"] = float(args.band_frac)

    # -------------------------
    # Guardar archivo
    # -------------------------
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"✅ Archivo de configuración creado en: {out_path}")
    print("📄 Contenido del bloque global:")
    print(json.dumps(config["global"], indent=2, ensure_ascii=False))
    print("📄 seasonal_defaults:")
    print(json.dumps(config["seasonal_defaults"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
