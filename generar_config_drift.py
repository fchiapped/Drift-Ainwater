import json
from pathlib import Path
import argparse

DEFAULT_CONFIG = {
    "global": {
        "metric": "wasserstein",
        "strategy": "decay",
        "window": "12H",
        "threshold": None,
        "min_points": 5
    }
}

def main():
    parser = argparse.ArgumentParser(
        description="Genera un archivo de configuración genérico para drift."
    )
    parser.add_argument(
        "--output", default="config/config_drift.json",
        help="Ruta donde guardar el archivo JSON (por defecto: config/config_drift.json)"
    )

    args = parser.parse_args()

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w") as f:
        json.dump(DEFAULT_CONFIG, f, indent=2)

    print(f"✅ Configuración global creada en: {out_path}")
    print("   (No depende del CSV, no lista columnas — es genérica.)")

if __name__ == "__main__":
    main()
