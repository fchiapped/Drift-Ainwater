import argparse
import json
from pathlib import Path


DEFAULT_CONFIG = {
    "global": {
        "metric": "wasserstein",     # "psi", "ks" o "wasserstein"
        "strategy": "decay",         # "decay", "golden", "seasonal"
        "window": "12h",             # tamaño de ventana
        "threshold": None,           # umbral explícito (None → usar defaults por métrica)
        "min_points": 60,             # mínimo de puntos por ventana
   },
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Genera un archivo de configuración genérico para drift "
            "(bloque 'global', opcionalmente parametrizable por CLI)."
        )
    )

    parser.add_argument(
        "--output",
        default="config/config_drift.json",
        help="Ruta donde guardar el archivo JSON "
             "(por defecto: config/config_drift.json)",
    )

    parser.add_argument(
        "--metric",
        type=str,
        choices=["psi", "ks", "wasserstein"],
        help="Métrica global a usar (psi, ks o wasserstein). "
             "Si no se especifica, se usa la del DEFAULT_CONFIG.",
    )

    parser.add_argument(
        "--strategy",
        type=str,
        choices=["decay", "golden", "seasonal"],
        help="Estrategia de referencia global (decay, golden, seasonal).",
    )

    parser.add_argument(
        "--window",
        type=str,
        help="Tamaño de ventana global (ej: '12h', '24h', '6h').",
    )

    parser.add_argument(
        "--threshold",
        type=float,
        help="Umbral global explícito para la métrica. "
             "Si no se entrega, se usan los defaults de drift_thresholds.py.",
    )

    parser.add_argument(
        "--min-points",
        type=int,
        help="Mínimo de puntos por ventana para evaluar drift.",
    )

    parser.add_argument(
        "--hysteresis-windows",
        type=int,
        help="Número de ventanas consecutivas sin drift para cerrar un episodio.",
    )

    args = parser.parse_args()

    # Partimos del DEFAULT_CONFIG y aplicamos overrides si vienen por CLI
    config = DEFAULT_CONFIG.copy()
    global_cfg = config["global"].copy()

    if args.metric is not None:
        global_cfg["metric"] = args.metric
    if args.strategy is not None:
        global_cfg["strategy"] = args.strategy
    if args.window is not None:
        global_cfg["window"] = args.window
    if args.threshold is not None:
        global_cfg["threshold"] = float(args.threshold)
    if args.min_points is not None:
        global_cfg["min_points"] = int(args.min_points)
    if args.hysteresis_windows is not None:
        global_cfg["hysteresis_windows"] = int(args.hysteresis_windows)

    config["global"] = global_cfg

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"✅ Configuración global creada en: {out_path}")
    print("   Contenido global:")
    print(json.dumps(config["global"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
