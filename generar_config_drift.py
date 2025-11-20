import argparse
import json
from pathlib import Path

import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera un archivo de configuración JSON para el detector de drift."
    )
    parser.add_argument(
        "input_csv",
        type=str,
        help="Ruta al CSV de entrada (debe contener una columna 'date_time').",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="config/config_drift.json",
        help="Ruta del archivo JSON de salida (por defecto: config/config_drift.json).",
    )
    parser.add_argument(
        "--metric",
        type=str,
        default="ks",
        help="Métrica por defecto (psi, ks, wasserstein). Por defecto: ks",
    )
    parser.add_argument(
        "--strategy",
        type=str,
        default="golden",
        help="Estrategia de referencia (decay, golden, seasonal). Por defecto: golden",
    )
    parser.add_argument(
        "--window",
        type=str,
        default="24h",
        help="Tamaño de ventana para el detector. Por defecto: 24h",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.2,
        help="Umbral de la métrica. Por defecto: 0.2",
    )
    parser.add_argument(
        "--min-points",
        type=int,
        default=5,
        help="Número mínimo de puntos en la ventana actual. Por defecto: 5",
    )

    args = parser.parse_args()

    input_path = Path(args.input_csv)
    output_path = Path(args.output)

    if not input_path.exists():
        raise FileNotFoundError(f"No se encontró el CSV de entrada: {input_path}")

    df_raw = pd.read_csv(input_path)

    if "date_time" not in df_raw.columns:
        raise ValueError(
            f"El CSV de entrada debe tener una columna 'date_time'. "
            f"Columnas encontradas: {list(df_raw.columns)}"
        )

    numeric_df = df_raw.drop(columns=["date_time"], errors="ignore").select_dtypes(include="number")
    numeric_cols = list(numeric_df.columns)

    if not numeric_cols:
        raise ValueError("No se encontraron columnas numéricas en el CSV.")

    config = {
        "global": {
            "metric": args.metric,
            "strategy": args.strategy,
            "window": args.window,
            "threshold": args.threshold,
            "min_points": args.min_points,
        },
        "variables": {
            col: {"enabled": True} for col in numeric_cols
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"✅ Configuración generada en: {output_path}")
    print(f"   Columnas numéricas habilitadas: {numeric_cols}")


if __name__ == "__main__":
    main()
