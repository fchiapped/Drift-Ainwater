import argparse
from pathlib import Path

from pipeline_drift import DriftPipeline


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pipeline de detección de drift en series de tiempo"
    )
    # CSV SIEMPRE obligatorio (no hay default)
    parser.add_argument(
        "input_csv",
        type=str,
        help="Ruta al CSV de entrada (debe contener una columna 'date_time')",
    )

    parser.add_argument(
        "--config",
        type=str,
        default="config/config_drift.json",
        help="Archivo de configuración JSON para el detector de drift "
             "(por defecto: config/config_drift.json)",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Directorio de salida (se creará si no existe). "
             "Por defecto: output",
    )

    parser.add_argument(
        "--columns",
        nargs="+",
        default=None,
        help=(
            "Columnas numéricas específicas a procesar. "
            "Si no se especifica, se usan las columnas habilitadas en el JSON."
        ),
    )

    args = parser.parse_args()

    pipeline = DriftPipeline(
        input_csv=args.input_csv,
        output_dir=args.output_dir,
        config_path=args.config,
        columns=args.columns,
    )
    pipeline.run()


if __name__ == "__main__":
    main()
