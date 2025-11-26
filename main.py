"""
Módulo principal para ejecutar el pipeline de drift univariado.

Este archivo define una interfaz de línea de comandos (CLI) que permite:

Argumento posicional:
    - input_csv: ruta al CSV con 'date_time' + variables numéricas.

Argumentos opcionales:
    - --output_dir      : Directorio raíz donde se guardarán los resultados.
    - --config          : Archivo JSON con parámetros globales (método, estrategia, ventanas...).
    - --columns         : Lista de variables a procesar (si no se entrega, se procesan todas).
    - --plateau_vars    : Variables a las que se aplicará la máscara para eliminar mesetas extremas.
    - --cyclical_vars   : Variables marcadas como cíclicas (p.ej. ciclos diarios); 
                          fuerzan automáticamente strategy='seasonal'.

Notas:
    • Los umbrales viven en drift_thresholds.py.
    • Las configuraciones operativas se controlan vía config_drift.json.
    • plateau_vars y cyclical_vars se definen EXCLUSIVAMENTE desde CLI
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

    # ---------------------------------------------------------------
    # Argumento posicional obligatorio
    # ---------------------------------------------------------------
    parser.add_argument(
        "input_csv",
        help="Ruta al CSV de entrada con columna 'date_time' y variables numéricas.",
    )

    # ---------------------------------------------------------------
    # Argumentos opcionales
    # ---------------------------------------------------------------

    # Directorio de salida
    parser.add_argument(
        "--output_dir",
        default="output",
        help="Directorio raíz donde se guardarán los resultados. (default: ./output)",
    )

    # Archivo de configuración (JSON)
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Ruta al archivo JSON de configuración (opcional).",
    )

    # Subconjunto de variables a procesar
    parser.add_argument(
        "--columns",
        type=str,
        nargs="+",
        default=None,
        help="Procesar solo estas columnas numéricas (opcional).",
    )

    # Variables con mesetas extremas
    parser.add_argument(
        "--plateau_vars",
        type=str,
        nargs="+",
        default=None,
        help=(
            "Variables a las que se aplicará la máscara de mesetas extremas "
            "(útil para ON/OFF o largos tramos en cero)."
        ),
    )

    # Variables cíclicas
    parser.add_argument(
        "--cyclical_vars",
        type=str,
        nargs="+",
        default=None,
        help=(
            "Variables cíclicas (p.ej., caudales con ciclos diarios). "
            "Fuerza strategy='seasonal' y ajusta automáticamente los parámetros "
            "para ciclos completos."
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
