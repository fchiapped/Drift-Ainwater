import argparse
from pipeline_drift import DriftPipeline


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline de detección de drift en series de tiempo"
    )
    parser.add_argument("input_csv", help="Ruta al CSV de entrada")
    parser.add_argument(
        "--config",
        required=True,
        help="Archivo de configuración JSON para el detector de drift",
    )
    parser.add_argument(
        "--output-dir",
        default="output_drift",
        help="Directorio de salida (se creará si no existe)",
    )
    parser.add_argument(
        "--columns",
        nargs="+",
        default=None,
        help=(
            "Columnas específicas a procesar. "
            "Si no se especifica y no se usa --all, se procesan todas las columnas "
            "numéricas presentes en el config."
        ),
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Procesar todas las columnas numéricas definidas en el config",
    )

    args = parser.parse_args()

    # Determinar columnas a procesar
    if args.all or args.columns is None:
        columns_to_process = None  # None → todas las columnas definidas en config
    else:
        columns_to_process = args.columns

    pipeline = DriftPipeline(
        input_csv=args.input_csv,
        output_dir=args.output_dir,
        config_path=args.config,
        columns_to_process=columns_to_process,
    )
    pipeline.run()


if __name__ == "__main__":
    main()
