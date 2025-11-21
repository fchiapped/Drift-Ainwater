import argparse
import sys
from pathlib import Path

from pipeline_drift import DriftPipeline


# ============================================================
# Chequeo básico de entorno (dependencias)
# ============================================================

def check_environment() -> None:
    """
    Verifica que las dependencias mínimas estén instaladas.
    - numpy, pandas: obligatorios (si faltan → aborta).
    - scipy: opcional pero recomendado (KS y Wasserstein).
    """
    required = ["numpy", "pandas"]
    optional = ["scipy"]

    missing_required = []
    missing_optional = []

    for mod in required:
        try:
            __import__(mod)
        except ImportError:
            missing_required.append(mod)

    for mod in optional:
        try:
            __import__(mod)
        except ImportError:
            missing_optional.append(mod)

    if not missing_required and not missing_optional:
        print("✅ Entorno OK: numpy, pandas y (opcional) scipy disponibles.")
        return

    if missing_required:
        print("\n⚠️ Faltan paquetes OBLIGATORIOS para ejecutar el pipeline:")
        print("   - " + ", ".join(missing_required))
        print("   Instálalos con, por ejemplo:\n")
        print("   pip install numpy pandas scipy\n")
        print("   (scipy es opcional, pero se incluye aquí por conveniencia.)")
        sys.exit(1)

    if "scipy" in missing_optional:
        print("\nℹ️ scipy NO está instalado.")
        print("   El pipeline seguirá funcionando, pero:")
        print("   - ks_numeric y wasserstein_numeric devolverán None.")
        print("   - Solo PSI estará completamente operativo.\n")
        print("   Para habilitar KS y Wasserstein instala:")
        print("   pip install scipy\n")


# ============================================================
# CLI principal
# ============================================================

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
        help=(
            "Archivo de configuración JSON para el detector de drift "
            "(por defecto: config/config_drift.json)"
        ),
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help=(
            "Directorio de salida (se creará si no existe). "
            "Por defecto: output"
        ),
    )

    parser.add_argument(
        "--columns",
        nargs="+",
        default=None,
        help=(
            "Columnas numéricas específicas a procesar. "
            "Si no se especifica, se usan todas las columnas numéricas del CSV."
        ),
    )

    args = parser.parse_args()

    # 1) Chequeo de entorno
    check_environment()

    # 2) Ejecutar pipeline
    pipeline = DriftPipeline(
        input_csv=args.input_csv,
        output_root=args.output_dir,
        config_path=args.config,
        variables=args.columns,
    )
    pipeline.run()


if __name__ == "__main__":
    main()
