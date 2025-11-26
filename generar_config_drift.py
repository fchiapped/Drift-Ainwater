"""
Generador de archivo de configuración para el detector de drift univariado.

Este módulo crea un archivo JSON que define los parámetros operativos del
pipeline (pero NO decide umbrales ni qué variables son cíclicas).

Estructura principal del JSON:
    - global:
        • method    : métrica global ("psi", "ks" o "wasserstein").
        • strategy  : estrategia global ("decay", "golden" o "seasonal").
        • window    : tamaño de ventana (ej.: "12h", "24h").
        • min_points: mínimo de puntos por ventana.

    - seasonal_defaults:
        • cycle_hours : ciclo base en horas (típicamente 24.0).
        • cycles_back : cuántos ciclos hacia atrás usar como referencia.
        • band_frac   : ancho relativo de banda de fase (reservado / avanzado).

    - plateau_defaults:
        • abs_eps, rel_eps, min_share, low_quantile, high_quantile
          Parámetros por defecto para la máscara de mesetas extremas.

    - variables:
        • Espacio para overrides por variable (normalmente vacío).
          Permite cambiar método/estrategia/ventana para variables específicas.

Importante:
    • Los UMBRALES se configuran en drift_thresholds.py (no en este JSON).
    • Qué variables son cíclicas o tienen mesetas se define solo vía CLI en main.py
      con --cyclical_vars y --plateau_vars, respectivamente.
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
        "cycle_hours": 24.0,        # ciclo típico diario
        "cycles_back": 10,          # cuántos ciclos hacia atrás para referencia
        "band_frac": 0.15           # ancho relativo de la banda de fase (reservado)
    },

    # Defaults globales para la máscara de mesetas extremas (plateau)
    "plateau_defaults": {
        "abs_eps": 0.5, # Tolerancia mínima absoluta alrededor del extremo
        "rel_eps": 0.01, # Tolerancia relativa (fracción del rango)
        "min_share": 0.05, # Fracción mínima de puntos en el extremo para activar la lógica
        "low_quantile": 0.02, # Cuantil usado para cortar la “cola baja” cuando hay meseta en el mínimo
        "high_quantile": 0.98, # Cuantil usado para cortar la “cola alta” cuando hay meseta en el máximo
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

    Uso típico:
        python generar_config_drift.py \
            --output config/config_drift.json \
            --method wasserstein \
            --strategy decay \
            --window "12h" \
            --min-points 60 \
            --cycle-hours 24 \
            --cycles-back 10 \
            --plateau-abs-eps 0.5

    Parámetros disponibles (todos opcionales):

      • --output <path>
            Ruta del archivo JSON a generar.
            (default: config/config_drift.json)

      • --method {psi, ks, wasserstein}
            Métrica global para detección de drift.

      • --strategy {decay, golden, seasonal}
            Estrategia global de referencia.

      • --window <str>
            Tamaño global de ventana (ej.: "12h", "24h").

      • --min-points <int>
            Mínimo de puntos por ventana para evaluar drift.

      • Parámetros estacionales (solo relevantes si se usa "seasonal"):
            --cycle-hours <float>
            --cycles-back <int>
            --band-frac <float>

      • Parámetros de la máscara de mesetas extremas:
            --plateau-abs-eps <float>
            --plateau-rel-eps <float>
            --plateau-min-share <float>
            --plateau-low-quantile <float>
            --plateau-high-quantile <float>


    Los parámetros entregados por CLI (si se entregan) sobre-escriben los
    valores del bloque "global", "seasonal_defaults" o "plateau_defaults"
    
    Este script:
        - SOLO genera el JSON operativo para el pipeline.
        - NO define umbrales (ver drift_thresholds.py).
        - NO define qué variables son cíclicas ni cuáles usan máscara plateau;
          eso se especifica únicamente desde la CLI de main.py.
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
        help="Ancho relativo de banda de fase alrededor del ciclo (default: 0.10).",
    )

    # ----- Defaults plateau (opcionales) -----
    parser.add_argument(
        "--plateau-abs-eps",
        type=float,
        help="Tolerancia mínima absoluta alrededor del extremo para mesetas.",
    )
    parser.add_argument(
        "--plateau-rel-eps",
        type=float,
        help="Tolerancia relativa (fracción del rango) para mesetas.",
    )
    parser.add_argument(
        "--plateau-min-share",
        type=float,
        help="Fracción mínima de puntos en el extremo para activar la lógica plateau.",
    )
    parser.add_argument(
        "--plateau-low-quantile",
        type=float,
        help="Cuantil para cortar cola baja en meseta mínima.",
    )
    parser.add_argument(
        "--plateau-high-quantile",
        type=float,
        help="Cuantil para cortar cola alta en meseta máxima.",
    )

    args = parser.parse_args()

    # Partimos del DEFAULT_CONFIG (copia superficial)
    config = {
        "global": DEFAULT_CONFIG["global"].copy(),
        "seasonal_defaults": DEFAULT_CONFIG["seasonal_defaults"].copy(),
        "plateau_defaults": DEFAULT_CONFIG["plateau_defaults"].copy(),
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
    # plateau_defaults
    # -------------------------
    plateau_cfg = config["plateau_defaults"]

    if args.plateau_abs_eps is not None:
        plateau_cfg["abs_eps"] = float(args.plateau_abs_eps)
    if args.plateau_rel_eps is not None:
        plateau_cfg["rel_eps"] = float(args.plateau_rel_eps)
    if args.plateau_min_share is not None:
        plateau_cfg["min_share"] = float(args.plateau_min_share)
    if args.plateau_low_quantile is not None:
        plateau_cfg["low_quantile"] = float(args.plateau_low_quantile)
    if args.plateau_high_quantile is not None:
        plateau_cfg["high_quantile"] = float(args.plateau_high_quantile)


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
    print("📄 plateau_defaults:")
    print(json.dumps(config["plateau_defaults"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
