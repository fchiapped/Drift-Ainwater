"""
Módulo principal para ejecutar el pipeline de drift univariado.

Este archivo define una interfaz de línea de comandos (CLI) que permite:

- Seleccionar el CSV de entrada (posicional):
    python main.py data/planta.csv

- (Opcional) Seleccionar un directorio raíz para los resultados:
    --output_dir output

- (Opcional) Entregar un archivo JSON de configuración generado por
  `generar_config_drift.py`:
    --config config/config_drift.json

- (Opcional) Procesar solo columnas específicas:
    --columns var_1 var_2 ...

- (Opcional) Aplicar la máscara de mesetas extremas a ciertas variables:
    --plateau_vars "Nivel Ecualizador 1 (Tk 30m3)"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pipeline_drift import DriftPipeline


# ============================================================
#  Verificación de entorno
# ============================================================

def check_environment() -> None:
    """
    Verifica que las dependencias mínimas estén instaladas.

    - numpy y pandas son obligatorios.
    - scipy es opcional, pero necesario si se usan KS o Wasserstein.
    """
    try:
        import numpy
        import pandas
    except Exception as exc:
        raise RuntimeError(
            "ERROR: Este pipeline requiere 'numpy' y 'pandas' instalados."
        ) from exc

    try:
        import scipy
    except ImportError:
        print(
            "⚠️  Advertencia: 'scipy' no está instalado. "
            "Los métodos 'ks' y 'wasserstein' pueden no funcionar.",
            file=sys.stderr,
        )


# ============================================================
#  CLI
# ============================================================

def build_parser() -> argparse.ArgumentParser:
    """
    Construye y retorna un parser de argumentos para la CLI.
    """
    parser = argparse.ArgumentParser(
        description="Ejecuta el pipeline de detección de drift univariado."
    )

    # Argumento posicional: ruta al CSV
    parser.add_argument(
        "input_csv",
        help="Ruta al CSV de entrada con columna 'date_time' y variables numéricas.",
    )

    parser.add_argument(
        "--output_dir",
        default="output",
        help="Directorio raíz donde se generarán los resultados. "
             "Por defecto: ./output",
    )

    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Ruta a archivo JSON de configuración (opcional).",
    )

    parser.add_argument(
        "--columns",
        type=str,
        nargs="+",
        default=None,
        help="Lista opcional de columnas numéricas a procesar. "
             "Si no se especifica, se procesan todas.",
    )

    parser.add_argument(
        "--plateau_vars",
        type=str,
        nargs="+",
        default=None,
        help=(
            "Lista de variables a las que se les eliminarán mesetas en valores "
            "extremos (por ejemplo, variables ON/OFF o con largos tramos en cero)."
        ),
    )

    parser.add_argument(
        "--cyclical_vars",
        type=str,
        nargs="+",
        default=None,
        help=(
            "Lista de variables cíclicas (p.ej. caudales con ciclo diario). "
            "Para estas variables se recomienda usar estrategia 'seasonal' "
            "con parámetros de ciclo en config_drift.json."
        ),
    )
    return parser
# ============================================================
#  Ejecución principal
# ============================================================

def main() -> None:
    """
    Punto de entrada ejecutable para el pipeline.

     - Verifica entorno y dependencias.
     - Parsea argumentos de la CLI.
     - Construye el DriftPipeline.
     - Ejecuta el pipeline completo.
    """
    check_environment()
    parser = build_parser()
    args = parser.parse_args()

    pipeline = DriftPipeline(
        input_csv=Path(args.input_csv),
        output_root=Path(args.output_dir),
        config_path=Path(args.config) if args.config else None,
        variables=args.columns,
        plateau_vars=args.plateau_vars,    # <-- NUEVO
        cyclical_vars=args.cyclical_vars,  # <-- NUEVO
    )

    pipeline.run()

# ============================================================
#  Entrada estándar
# ============================================================

if __name__ == "__main__":
    main()
