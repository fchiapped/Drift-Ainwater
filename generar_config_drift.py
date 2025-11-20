# generar_config_drift.py
import argparse
import json
from pathlib import Path

import pandas as pd


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generar config_drift.json con configuración por defecto"
    )
    parser.add_argument("csv_path", type=str, help="Ruta al CSV de datos")
    parser.add_argument(
        "--output",
        type=str,
        default="config_drift.json",
        help="Nombre del archivo de salida",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Sobrescribir archivo existente sin preguntar",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    csv_path = Path(args.csv_path)
    out_path = Path(args.output)

    if out_path.exists() and not args.overwrite:
        raise SystemExit(
            f"{out_path} ya existe. Usa --overwrite si quieres sobrescribir."
        )

    df = pd.read_csv(csv_path, nrows=10)  # basta una muestra
    cols = [c for c in df.columns if c != "date_time"]

    # Config por defecto (ajústala a tus defaults reales)
    default_cfg = {
        "window_size": "6H",
        "step_size": "1H",
        "baseline_strategy": "golden",
        "metrics": ["psi", "ks", "wasserstein", "mannwhitney"],
        "thresholds": {
            "psi": 0.2,
            "ks": 0.1,
            "wasserstein": 0.5,
            "mannwhitney_pvalue": 0.05,
        },
        "min_window_size": 30,
        "aggregate_episodes": {
            "min_consecutive_windows": 2,
            "max_gap_windows": 1,
        },
    }

    config = {col: default_cfg for col in cols}

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"✅ Configuración generada en {out_path}")


if __name__ == "__main__":
    main()
