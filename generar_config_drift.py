from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def build_default_config_from_csv(csv_path: Path) -> dict:
    df = pd.read_csv(csv_path, nrows=2000)  # sample para detectar tipos

    if "date_time" not in df.columns:
        print(
            "⚠️ Aviso: el CSV no tiene columna 'date_time'. "
            "Igualmente se generará el config, pero el pipeline requerirá esa columna."
        )

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    if not numeric_cols:
        raise ValueError("No se encontraron columnas numéricas en el CSV para armar el config.")

    config = {
        "global": {
            # Defaults razonables; los puedes ajustar
            "metric": "ks",
            "strategy": "golden",
            "window": "24H",
            "threshold": 0.20,
            "min_points": 5,
        },
        "variables": {},
    }

    for col in numeric_cols:
        config["variables"][col] = {
            "enabled": True,
            # Si quisieras overridear por variable:
            # "metric": "ks",
            # "strategy": "golden",
            # "window": "24H",
            # "threshold": 0.20,
        }

    return config


def main():
    parser = argparse.ArgumentParser(
        description="Generar archivo de configuración JSON para el pipeline de drift."
    )
    parser.add_argument("input_csv", help="Ruta al CSV de entrada")
    parser.add_argument(
        "--output",
        default="config_drift.json",
        help="Ruta del archivo JSON a generar (default: config_drift.json)",
    )

    args = parser.parse_args()

    csv_path = Path(args.input_csv)
    if not csv_path.exists():
        raise FileNotFoundError(f"No se encontró el CSV: {csv_path}")

    cfg = build_default_config_from_csv(csv_path)

    output_path = Path(args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

    print(f"✅ Config JSON generado en: {output_path}")
    print("   Revisa y ajusta los parámetros globales y por variable según lo que necesites.")


if __name__ == "__main__":
    main()
