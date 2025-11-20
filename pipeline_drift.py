from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, Iterable, Optional, List

import pandas as pd

from detectors import DriftDetector, DriftDetectorConfig


class DriftPipeline:
    """
    Pipeline principal de detección de drift.

    - Lee un CSV con columna 'date_time' y columnas numéricas.
    - Aplica un detector (métrica + estrategia + ventana) por variable.
    - Guarda un CSV por variable y un CSV largo combinado con todas.
    - Guarda además un JSON por variable con la configuración usada.
    """

    def __init__(
        self,
        input_csv: str | Path,
        output_dir: str | Path,
        config_path: str | Path,
        columns_to_process: Optional[List[str]] = None,
    ) -> None:
        self.input_csv = Path(input_csv)
        self.output_dir = Path(output_dir)
        self.config_path = Path(config_path)
        self.columns_to_process = columns_to_process

        self.config: Dict[str, Any] = {}
        self.df: pd.DataFrame = pd.DataFrame()

    # ------------------------- Carga de datos & config -------------------------

    def _load_data(self) -> None:
        if not self.input_csv.exists():
            raise FileNotFoundError(f"No se encontró el archivo: {self.input_csv}")

        df_raw = pd.read_csv(self.input_csv)

        if "date_time" not in df_raw.columns:
            raise ValueError(
                "El CSV de entrada debe tener una columna llamada 'date_time' "
                "(esto se documenta como requisito del pipeline)."
            )

        df_raw["date_time"] = pd.to_datetime(df_raw["date_time"], errors="coerce")
        df_raw = (
            df_raw.dropna(subset=["date_time"])
            .sort_values("date_time")
            .set_index("date_time")
        )

        # Sólo dejamos columnas numéricas
        df_num = df_raw.select_dtypes(include="number").copy()
        if df_num.empty:
            raise ValueError(
                "No se encontraron columnas numéricas en el CSV de entrada."
            )

        self.df = df_num

    def _load_config(self) -> None:
        if not self.config_path.exists():
            raise FileNotFoundError(f"No se encontró el archivo de config: {self.config_path}")

        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

    # ------------------------- Selección de variables -------------------------

    def _select_variables(self) -> Dict[str, Dict[str, Any]]:
        """
        Devuelve dict {variable: config_específica} a procesar.

        - Parte desde columnas numéricas presentes en self.df.
        - Se intersectan con las variables definidas en el config JSON.
        - Aplica filtro columns_to_process (si no es None).
        - Respeta flag 'enabled' por variable (si existe).
        """
        if "variables" not in self.config:
            raise ValueError("El config JSON debe tener una clave 'variables'.")

        cfg_vars: Dict[str, Any] = self.config["variables"]
        numeric_cols = set(self.df.columns)

        # Sólo consideramos variables que están en df y en config
        candidate_vars = numeric_cols.intersection(cfg_vars.keys())

        if not candidate_vars:
            raise ValueError(
                "No hay intersección entre columnas numéricas del CSV "
                "y las variables definidas en el config."
            )

        # Filtro por --columns (si se especificó)
        if self.columns_to_process is not None:
            requested = set(self.columns_to_process)
            candidate_vars = candidate_vars.intersection(requested)
            if not candidate_vars:
                raise ValueError(
                    "Ninguna de las columnas pedidas en --columns está presente "
                    "tanto en el CSV como en el config."
                )

        selected: Dict[str, Dict[str, Any]] = {}
        for var in sorted(candidate_vars):
            v_cfg = cfg_vars.get(var, {})
            if v_cfg.get("enabled", True) is False:
                continue
            selected[var] = v_cfg

        if not selected:
            raise ValueError(
                "Todas las variables candidatas están deshabilitadas (enabled = false) "
                "o no hay ninguna variable seleccionada."
            )

        return selected

    # ------------------------- Helpers de config -------------------------

    def _get_global_param(self, name: str, default: Any = None) -> Any:
        return self.config.get("global", {}).get(name, default)

    def _build_detector_config_for_var(self, var: str, var_cfg: Dict[str, Any]) -> DriftDetectorConfig:
        """
        Mezcla parámetros globales + overrides de la variable.
        """
        metric = var_cfg.get("metric", self._get_global_param("metric", "ks"))
        strategy = var_cfg.get("strategy", self._get_global_param("strategy", "golden"))
        window = var_cfg.get("window", self._get_global_param("window", "24H"))

        # threshold y min_points pueden venir en global o por variable
        threshold = var_cfg.get("threshold", self._get_global_param("threshold", None))
        min_points = var_cfg.get("min_points", self._get_global_param("min_points", 5))

        return DriftDetectorConfig(
            metric=metric,
            strategy=strategy,
            window=window,
            threshold=threshold,
            min_points=min_points,
        )

    # ------------------------- Ejecución principal -------------------------

    def run(self) -> None:
        """
        Ejecuta el pipeline completo:

        - carga data y config
        - selecciona variables
        - corre detector por variable
        - guarda outputs CSV + JSON
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._load_data()
        self._load_config()

        selected_vars = self._select_variables()

        print(f"🏁 CSV de entrada: {self.input_csv}")
        print(f"📄 Config:         {self.config_path}")
        print(f"📂 Output dir:     {self.output_dir}")
        print("🔎 Variables a procesar:", ", ".join(sorted(selected_vars.keys())))

        all_long_rows = []

        for var, var_cfg in selected_vars.items():
            print(f"\n=== Procesando variable: {var} ===")

            det_cfg = self._build_detector_config_for_var(var, var_cfg)
            detector = DriftDetector(det_cfg)

            df_var = self.df[[var]].copy()
            df_out = detector.detect_for_variable(df_var=df_var, variable=var)

            # Guardar CSV por variable
            var_csv_path = self.output_dir / f"{var}_drift.csv"
            df_out.to_csv(var_csv_path, index=False)
            print(f"  ✅ CSV guardado: {var_csv_path}")

            # Guardar JSON con config usada para esta variable
            var_json_path = self.output_dir / f"{var}_config.json"
            cfg_used = {
                "variable": var,
                "input_csv": str(self.input_csv),
                "config_file": str(self.config_path),
                "detector": {
                    "metric": det_cfg.metric,
                    "strategy": det_cfg.strategy,
                    "window": det_cfg.window,
                    "threshold": det_cfg.threshold,
                    "min_points": det_cfg.min_points,
                },
            }
            with open(var_json_path, "w", encoding="utf-8") as f:
                json.dump(cfg_used, f, indent=2, ensure_ascii=False)
            print(f"  📄 Config usada guardada en: {var_json_path}")

            # Para el CSV largo, agregamos columna variable
            df_long = df_out.copy()
            df_long["variable"] = var
            all_long_rows.append(df_long)

        # CSV largo combinado (todas las variables)
        if all_long_rows:
            df_long_all = pd.concat(all_long_rows, ignore_index=True)
            long_csv_path = self.output_dir / "drift_results_long.csv"
            df_long_all.to_csv(long_csv_path, index=False)
            print(f"\n📊 CSV combinado guardado en: {long_csv_path}")
        else:
            print("⚠️ No se generó ningún resultado (lista de variables vacía o errores previos).")
