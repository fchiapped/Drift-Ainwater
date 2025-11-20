# main.py
import argparse
import json
from pathlib import Path

import pandas as pd

from pipeline_drift import DriftPipeline


def parse_args():
    parser = argparse.ArgumentParser(
        description="Pipeline de detección de drift en series de tiempo"
    )
    parser.add_argument("csv_path", type=str, help="Ruta al CSV de datos (con date_time)")
    parser.add_argument(
        "--config",
        type=str,
        default="config_drift.json",
        help="Archivo de configuración de drift",
    )
    parser.add_argument(
        "--columns",
        nargs="*",
        help="Columnas específicas a procesar (si se omite, procesa todas las del config)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Directorio donde guardar resultados",
    )
    return parser.parse_args()


def load_data(csv_path: str) -> pd.DataFrame:
    csv_path = Path(csv_path)

    # Detección simple de encoding
    for enc in ("utf-8", "latin1"):
        try:
            df = pd.read_csv(csv_path, encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise UnicodeError("No se pudo leer el CSV con utf-8 ni latin1")

    if "date_time" not in df.columns:
        raise ValueError("El CSV debe contener una columna 'date_time'")

    df["date_time"] = pd.to_datetime(df["date_time"])
    df = df.sort_values("date_time").reset_index(drop=True)
    return df


def main():
    args = parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        config = json.load(f)

    df = load_data(args.csv_path)

    # Si no se pasan columnas, usamos todas las definidas en el config
    if args.columns:
        variables = args.columns
    else:
        variables = list(config.keys())

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    pipeline = DriftPipeline(config=config, output_dir=output_dir)

    for var in variables:
        if var not in df.columns:
            print(f"⚠️  Variable '{var}' no está en el CSV, se salta.")
            continue

        if var not in config:
            print(f"⚠️  Variable '{var}' no tiene configuración en {args.config}, se salta.")
            continue

        print(f"\n🚀 Procesando variable: {var}")
        series = df.set_index("date_time")[var]
        windows_df, episodes_df = pipeline.run_for_variable(series, var_name=var)

        # Guardar resultados
        windows_path = output_dir / f"{var}_windows.csv"
        episodes_path = output_dir / f"{var}_episodes.csv"

        windows_df.to_csv(windows_path, index=False)
        episodes_df.to_csv(episodes_path, index=False)

        print(f"   ✅ Ventanas → {windows_path}")
        print(f"   ✅ Episodios → {episodes_path}")


if __name__ == "__main__":
    main()
