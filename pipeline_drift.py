from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

import json
import datetime as dt

import numpy as np
import pandas as pd

from funciones_drift import (
    ref_decay_prefix_mass,
    ref_golden,
    ref_seasonal,
    score_numeric_series)

from drift_thresholds import DriftThresholdConfig, effective_threshold

THRESHOLD_CFG = DriftThresholdConfig()


@dataclass
class DriftConfig:
    method: str = "wasserstein"          # "psi", "ks" o "wasserstein"
    strategy: str = "decay"              # "decay", "golden", "seasonal"
    window: str = "12h"                  # tamaño de ventana
    threshold: Optional[float] = None    # umbral; si None se usan defaults
    min_points: int = 60                  # mínimo de puntos por ventana


def run_drift_univariate(series: pd.Series, cfg: DriftConfig) -> pd.DataFrame:
    if series.empty:
        return pd.DataFrame(
            columns=["t0", "t1", "drift_flag", "episode_id", "stat_value", "threshold", "state"]
        )

    if not isinstance(series.index, pd.DatetimeIndex):
        raise ValueError("run_drift_univariate espera que el índice sea DatetimeIndex.")

    df = series.to_frame(name="value").sort_index()

    w = pd.to_timedelta(cfg.window)
    t_min, t_max = df.index.min(), df.index.max()
    if pd.isna(t_min) or pd.isna(t_max):
        return pd.DataFrame(
            columns=["t0", "t1", "drift_flag", "episode_id", "stat_value", "threshold", "state"]
        )

    t_ends = pd.date_range(t_min + w, t_max, freq=cfg.window)
    if len(t_ends) == 0:
        return pd.DataFrame(
            columns=["t0", "t1", "drift_flag", "episode_id", "stat_value", "threshold", "state"]
        )

    state = "NORMAL"
    current_episode = 0

    rows = []

    for t_end in t_ends:
        t0 = t_end - w

        df_hist = df.loc[: t0 - pd.Timedelta(microseconds=1)]
        df_cur = df.loc[t0:t_end]

        if df_hist.empty or df_cur.empty or len(df_cur) < cfg.min_points:
            rows.append(
                {
                    "t0": t0,
                    "t1": t_end,
                    "drift_flag": False,
                    "episode_id": np.nan,
                    "stat_value": None,
                    "threshold": None,
                    "state": state,
                }
            )
            continue

        # Referencia según estrategia, usando SOLO historial hasta t0
        if cfg.strategy == "decay":
            ref_global = ref_decay_prefix_mass(df_hist, now=t_end)
        elif cfg.strategy == "golden":
            ref_global = ref_golden(df_hist)
        elif cfg.strategy == "seasonal":
            ref_global = ref_seasonal(df_hist, current_end=t_end)
        else:
            raise ValueError(f"Estrategia desconocida: {cfg.strategy!r}")

        if ref_global is None or ref_global.empty:
            ref_global = df_hist

        ref_series = ref_global["value"].dropna()
        cur_series = df_cur["value"].dropna()

        if ref_series.empty or cur_series.empty or len(cur_series) < cfg.min_points:
            rows.append(
                {
                    "t0": t0,
                    "t1": t_end,
                    "drift_flag": False,
                    "episode_id": np.nan,
                    "stat_value": None,
                    "threshold": None,
                    "state": state,
                }
            )
            continue

        stat_val = score_numeric_series(ref_series, cur_series, cfg.method)

        thr = effective_threshold(
            method=cfg.method,
            ref_series=ref_series,
            cfg=THRESHOLD_CFG,
            thr_override=cfg.threshold,
        )

        # --- Nueva lógica de estado sin histéresis ---
        if stat_val is None or np.isnan(stat_val):
            drift_flag = False
        else:
            drift_flag = bool(stat_val >= thr)

        if drift_flag:
            # si recién entramos en drift, abrimos nuevo episodio
            if state == "NORMAL":
                current_episode += 1
            state = "DRIFT"
        else:
            # en cuanto no hay drift, cerramos episodio
            state = "NORMAL"

        rows.append(
            {
                "t0": t0,
                "t1": t_end,
                "drift_flag": drift_flag,
                "episode_id": current_episode if drift_flag else np.nan,
                "stat_value": float(stat_val) if stat_val is not None else None,
                "threshold": float(thr),
                "state": state,
            }
        )

    return pd.DataFrame(rows)


def windows_to_point_flags(windows_df: pd.DataFrame, index: pd.DatetimeIndex) -> pd.Series:
    flags = pd.Series(False, index=index)

    if windows_df.empty:
        return flags

    for _, row in windows_df.iterrows():
        if bool(row.get("drift_flag", False)):
            t0 = row["t0"]
            t1 = row["t1"]
            flags.loc[t0:t1] = True

    return flags


class DriftPipeline:
    def __init__(
        self,
        input_csv: Path,
        output_root: Path,
        config_path: Optional[Path] = None,
        variables: Optional[Sequence[str]] = None,
    ) -> None:
        self.input_csv = Path(input_csv)
        self.output_root = Path(output_root)
        self.config_path = Path(config_path) if config_path is not None else None
        self.variables = list(variables) if variables is not None else None

        self._config: Optional[Dict[str, Any]] = None

    # Config Helpers

    def _load_config(self) -> Dict[str, Any]:
        if self.config_path is None:
            return {
                "global": {
                    "method": "wasserstein",
                    "strategy": "decay",
                    "window": "12h",
                    "threshold": None,
                    "min_points": 60,
                }
            }

        if not self.config_path.exists():
            raise FileNotFoundError(
                f"No se encontró el archivo de configuración: {self.config_path}"
            )

        with self.config_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("El archivo de configuración debe contener un objeto JSON.")
        return data

    def _build_cfg_for_var(self, var_name: str) -> DriftConfig:
        if self._config is None:
            self._config = self._load_config()

        global_cfg: Dict[str, Any] = self._config.get("global", {})
        var_overrides: Dict[str, Any] = (
            self._config.get("variables", {}).get(var_name, {})
        )

        merged: Dict[str, Any] = {
            "method": global_cfg.get("method", "wasserstein"),
            "strategy": global_cfg.get("strategy", "decay"),
            "window": str(global_cfg.get("window", "12h")).lower(),
            "threshold": global_cfg.get("threshold", None),
            "min_points": int(global_cfg.get("min_points", 60)),
        }

        for k, v in var_overrides.items():
            if k == "window":
                merged[k] = str(v).lower()
            elif k in ("min_points"):
                merged[k] = int(v)
            else:
                merged[k] = v

        return DriftConfig(**merged)

    # Main Execution
    def run(self) -> None:
        print("Iniciando DriftPipeline...")

        self.output_root.mkdir(parents=True, exist_ok=True)
        ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = self.output_root / f"{self.input_csv.stem}_{ts}"
        run_dir.mkdir(parents=True, exist_ok=True)

        self._config = self._load_config()

        print(f"Leyendo datos desde: {self.input_csv}")
        df_raw = pd.read_csv(self.input_csv)

        if "date_time" not in df_raw.columns:
            raise ValueError("El CSV de entrada debe tener una columna 'date_time'.")

        df_raw["date_time"] = pd.to_datetime(df_raw["date_time"], errors="coerce")
        df_raw = (
            df_raw.dropna(subset=["date_time"])
            .sort_values("date_time")
            .set_index("date_time")
        )

        # Variables numéricas
        numeric_cols = df_raw.select_dtypes(include="number").columns.tolist()
        if not numeric_cols:
            raise ValueError("No se encontraron columnas numéricas en el CSV de entrada.")

        if self.variables is not None:
            variables = [c for c in self.variables if c in numeric_cols]
        else:
            variables = numeric_cols

        if not variables:
            raise ValueError("No hay variables válidas para procesar drift.")

        print("Variables a procesar:", ", ".join(variables))
        print(f"Directorio de salida: {run_dir}")

        effective_var_cfg: Dict[str, Any] = {}

        for var in variables:
            print(f"\nProcesando variable: {var}")
            series = df_raw[var].dropna()

            cfg = self._build_cfg_for_var(var)
            effective_var_cfg[var] = asdict(cfg)

            win_results = run_drift_univariate(series, cfg)

            win_dir = run_dir / "Windows"
            win_dir.mkdir(parents=True, exist_ok=True)
            win_csv_path = win_dir / f"{var}_windows.csv"
            win_results.to_csv(win_csv_path, index=False)

            drift_flags = windows_to_point_flags(win_results, df_raw.index)

            out_df = pd.DataFrame(
                {
                    "date_time": df_raw.index,
                    "value": df_raw[var].values,
                    "has_drift": drift_flags.reindex(df_raw.index, fill_value=False)
                    .astype(bool)
                    .values,
                }
            )

            flags_dir = run_dir / "Flags"
            flags_dir.mkdir(parents=True, exist_ok=True)
            out_csv_path = flags_dir / f"{var}.csv"
            out_df.to_csv(out_csv_path, index=False)
            print(f"  → Guardado: {out_csv_path.name}")


        run_config_effective = {
            "input_csv": str(self.input_csv),
            "run_dir": str(run_dir),
            "generated_at": dt.datetime.now().isoformat(),
            "global": self._config.get("global", {}),
            "variables": effective_var_cfg,
        }

        run_config_path = run_dir / "config_used.json"
        with run_config_path.open("w", encoding="utf-8") as f:
            json.dump(run_config_effective, f, indent=2, ensure_ascii=False)
        print(f"\n📝 Configuración efectiva de la corrida guardada en: {run_config_path}")

        print("\n✅ Pipeline de drift terminado.")
        print(f"Resultados en: {run_dir}")