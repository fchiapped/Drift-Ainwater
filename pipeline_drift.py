from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import datetime as dt
import json
import pandas as pd

from detectors import DriftConfig, detect_drift_univariate



@dataclass
class VariableConfig:
    enabled: bool = True


class DriftPipeline:
    def __init__(
        self,
        input_csv: str | Path,
        output_dir: str | Path = "output",
        config_path: str | Path = "config/config_drift.json",
        columns: Optional[Iterable[str]] = None,
    ) -> None:
        self.input_csv = Path(input_csv)
        self.output_dir = Path(output_dir)
        self.config_path = Path(config_path)
        self.columns_cli = list(columns) if columns is not None else None

        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._df: Optional[pd.DataFrame] = None
        self._config: Dict = {}

    # ------------------------------------------------------------------
    # Carga de datos y configuración

    def _load_data(self) -> pd.DataFrame:
        if not self.input_csv.exists():
            raise FileNotFoundError(f"No se encontró el CSV de entrada: {self.input_csv}")

        df_raw = pd.read_csv(self.input_csv)

        if "date_time" not in df_raw.columns:
            raise ValueError(
                f"El CSV de entrada debe tener una columna 'date_time'. "
                f"Columnas encontradas: {list(df_raw.columns)}"
            )

        df_raw["date_time"] = pd.to_datetime(df_raw["date_time"], errors="coerce")
        df_raw = (
            df_raw
            .dropna(subset=["date_time"])
            .sort_values("date_time")
            .set_index("date_time")
        )

        # Solo columnas numéricas
        df = df_raw.select_dtypes(include="number").copy()
        if df.empty:
            raise ValueError("No se encontraron columnas numéricas para procesar.")

        self._df = df
        return df

    def _load_config(self) -> dict:
        cfg_path = self.config_path or (Path("config") / "config_drift.json")

        if not cfg_path.exists():
            raise FileNotFoundError(
                f"No se encontró archivo de configuración: {cfg_path}\n"
                "Puedes generarlo con:\n"
                f"  python generar_config_drift.py --output {cfg_path}\n"
                "O bien puedes indicar otro archivo con el flag --config."
            )

        with open(cfg_path, "r", encoding="utf-8") as f:
            return json.load(f)

        cfg.setdefault("global", {})
        cfg.setdefault("variables", {})

        # Defaults globales
        g = cfg["global"]
        g.setdefault("metric", "wasserstein")
        g.setdefault("strategy", "decay")
        g.setdefault("window", "12h")
        g.setdefault("threshold", 0.2)
        g.setdefault("min_points", 5)

        self._config = cfg
        return cfg

    # ------------------------------------------------------------------
    # Helpers sobre config

    def _enabled_variables_from_config(self, numeric_cols: List[str]) -> List[str]:

        var_cfg: Dict = self._config.get("variables", {})
        enabled = []
        for col in numeric_cols:
            cfg_col = var_cfg.get(col, {})
            if cfg_col.get("enabled", True):
                enabled.append(col)
        return enabled

    def _build_cfg_for_var(self, var: str) -> DriftConfig:
        g = dict(self._config.get("global", {}))
        var_cfg = self._config.get("variables", {}).get(var, {})
        local = {**g, **{k: v for k, v in var_cfg.items() if k != "enabled"}}

        return DriftConfig(
            metric=str(local.get("metric", "wasserstein")),
            strategy=str(local.get("strategy", "decay")),
            window=str(local.get("window", "12h")),
            threshold=float(local.get("threshold", 0.2)),
            min_points=int(local.get("min_points", 5)),
            hysteresis_windows=int(local.get("hysteresis_windows", 2)),
        )

    # ------------------------------------------------------------------
    # Ejecución completa

    def run(self) -> None:
        df = self._df if self._df is not None else self._load_data()
        cfg = self._config if self._config else self._load_config()

        numeric_cols = list(df.columns)

        if self.columns_cli:
            cols_to_process = [c for c in self.columns_cli if c in numeric_cols]
            if not cols_to_process:
                raise ValueError(
                    f"Ninguna de las columnas pedidas por --columns está en el CSV. "
                    f"Columnas numéricas disponibles: {numeric_cols}"
                )
        else:
            # Usar columnas habilitadas en el config
            cols_to_process = self._enabled_variables_from_config(numeric_cols)
            if not cols_to_process:
                raise ValueError(
                    "Ninguna columna está habilitada en el archivo de configuración.\n"
                    "Revisa la sección 'variables' o usa --columns para forzar alguna."
                )

        run_name = f"{self.input_csv.stem}_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        run_dir = self.output_dir / run_name
        run_dir.mkdir(parents=True, exist_ok=True)

        print(f"➡️  CSV de entrada : {self.input_csv}")
        print(f"➡️  Config usado   : {self.config_path}")
        print(f"➡️  Output base    : {self.output_dir.resolve()}")
        print(f"➡️  Carpeta corrida: {run_dir.resolve()}")
        print(f"➡️  Columnas a procesar ({len(cols_to_process)}): {cols_to_process}")

        run_config_effective: Dict = {
            "input_csv": str(self.input_csv),
            "config_path": str(self.config_path),
            "global": cfg.get("global", {}),
            "variables": {},
        }

        for var in cols_to_process:
            print(f"\n[DriftPipeline] Procesando variable: {var}")
            series_df = df[[var]]

            var_cfg = self._build_cfg_for_var(var)
            print(
                f"   Estrategia={var_cfg.strategy}, "
                f"Métrica={var_cfg.metric}, "
                f"Ventana={var_cfg.window}, "
                f"Umbral={var_cfg.threshold}"
            )

            has_drift = detect_drift_univariate(series_df, var_cfg)

            # DataFrame de salida
            out_df = pd.DataFrame({
                "date_time": series_df.index,
                var: series_df[var].values,
                "has_drift": has_drift.astype(bool).values,
            })

            var_csv_path = run_dir / f"{var}_drift.csv"
            out_df.to_csv(var_csv_path, index=False)
            print(f"   ✅ CSV guardado en: {var_csv_path}")

            run_config_effective["variables"][var] = {
                "enabled": self._config.get("variables", {}).get(var, {}).get("enabled", True),
                "effective": vars(var_cfg),
            }

        run_config_path = run_dir / "config_used.json"
        with run_config_path.open("w", encoding="utf-8") as f:
            json.dump(run_config_effective, f, indent=2, ensure_ascii=False)
        print(f"\n📝 Configuración efectiva de la corrida guardada en: {run_config_path}")