"""
Pipeline de detección de drift univariado para series de tiempo.

Flujo general:

    CSV con date_time + variables numéricas
                │
                ▼
       DriftPipeline.run()
                │
                ├─ Para cada variable numérica:
                │    ├─ (Opcional) preprocesar mesetas extremas (plateau_vars)
                │    ├─ Config efectiva (global + overrides por variable)
                │    ├─ run_drift_univariate(...)
                │    │    ├─ Construcción de ventanas
                │    │    ├─ build_reference(...) según estrategia
                │    │    ├─ evaluate_window(...) (métrica + umbral)
                │    │    └─ detect_episodes(...) (episode_id + state)
                │    ├─ Guardar Windows/var_X_windows.csv
                │    └─ Guardar Flags/var_X.csv
                │
                └─ Guardar config_used.json con configuración efectiva

Responsabilidades:
- Este archivo NO define métricas ni estrategias de referencia:
  eso está en `funciones_drift.py`.
- Este archivo NO define umbrales:
  eso está en `drift_thresholds.py`.
- Solo orquesta el flujo, aplica el preprocesamiento de mesetas
  y arma los outputs.
"""


from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

import numpy as np
import pandas as pd

from funciones_drift import (
    ref_decay_prefix_mass,
    ref_golden,
    ref_seasonal_cycles,
    score_numeric_series,
)
from drift_thresholds import DriftThresholdConfig, effective_threshold


# Configuración global de umbrales (PSI, KS, Wasserstein)
THRESHOLD_CFG = DriftThresholdConfig()


# ============================================================
#  Helpers de referencia / evaluación / episodios
# ============================================================

def build_reference(
    df_hist: pd.DataFrame,    # Historial previo a la ventana actual
    strategy: str,            # "decay", "golden" o "seasonal"
    current_end: pd.Timestamp,
    cfg: Dict[str, Any] | None = None,  # Config opcional (para parámetros extra)
) -> pd.DataFrame:
    """
    Construye la referencia según la estrategia especificada.

    NOTA:
    - Para "seasonal" se asume que cfg ya contiene cycle_hours y cycles_back,
      típicamente provenientes de seasonal_defaults en el archivo JSON.
    """
    strategy = str(strategy).lower().strip()

    if df_hist.empty:
        return df_hist

    if strategy == "decay":
        ref = ref_decay_prefix_mass(df_hist, now=current_end)

    elif strategy == "golden":
        ref = ref_golden(df_hist)

    elif strategy == "seasonal":
        if cfg is None:
            raise ValueError(
                "build_reference(strategy='seasonal') requiere un cfg con "
                "'cycle_hours' y 'cycles_back'."
            )
        cycle_hours = float(cfg["cycle_hours"])
        cycles_back = int(cfg["cycles_back"])

        ref = ref_seasonal_cycles(
            df_hist,
            current_end=current_end,
            cycle_hours=cycle_hours,
            cycles_back=cycles_back,
        )

    else:
        raise ValueError(f"Estrategia de referencia desconocida: {strategy!r}")

    if ref is None or ref.empty:
        # Fallback: usar todo el historial si la estrategia no logra entregar nada
        return df_hist

    return ref


def evaluate_window(
    ref_series: pd.Series,
    cur_series: pd.Series,
    cfg: Dict[str, Any],
    thr_cfg: DriftThresholdConfig,
) -> tuple[Optional[float], Optional[float], bool]:
    """
    Evalúa el drift en una ventana específica.

    Calcula:
      - valor de la métrica (stat_value)
      - umbral efectivo (threshold)
      - flag de drift (True/False)
    """
    method = str(cfg["method"]).lower()

    # Métrica de drift
    stat_val = score_numeric_series(ref_series, cur_series, method)

    if stat_val is None or np.isnan(stat_val):
        return None, None, False

    # Umbral efectivo según método y dispersión histórica
    thr = effective_threshold(
        method=method,
        ref_series=ref_series,
        cfg=thr_cfg,
    )

    drift_flag = bool(stat_val >= thr)
    # (stat_value, threshold, drift_flag)
    return float(stat_val), float(thr), drift_flag


def detect_episodes(windows_df: pd.DataFrame) -> pd.DataFrame:
    """
    Asigna episode_id y estado ("NORMAL"/"DRIFT") a partir de drift_flag.
    """
    if windows_df.empty:
        windows_df = windows_df.copy()
        windows_df["episode_id"] = np.nan
        windows_df["state"] = []
        return windows_df

    state = "NORMAL"
    current_episode = 0
    episode_ids = []
    states = []

    for flag in windows_df["drift_flag"].astype(bool).tolist():
        if flag:
            if state == "NORMAL":
                current_episode += 1
            state = "DRIFT"
            episode_ids.append(current_episode)
            states.append("DRIFT")
        else:
            state = "NORMAL"
            episode_ids.append(np.nan)
            states.append("NORMAL")

    windows_df = windows_df.copy()
    windows_df["episode_id"] = episode_ids
    windows_df["state"] = states
    return windows_df


def windows_to_point_flags(
    windows_df: pd.DataFrame,
    index: pd.DatetimeIndex,
) -> pd.Series:
    """
    Proyecta los resultados a nivel de ventana a flags por timestamp.

    Devuelve una Serie booleana indexada por `index` con True en los
    timestamps que caen en ventanas marcadas con drift_flag=True.
    """
    flags = pd.Series(False, index=index)

    if windows_df.empty:
        return flags

    for _, row in windows_df.iterrows():
        if bool(row.get("drift_flag", False)):
            t0 = row["t0"]
            t1 = row["t1"]
            flags.loc[t0:t1] = True


    # Serie booleana con True en los timestamps que caen en ventanas marcadas con drift_flag=True
    return flags


# ============================================================
#  Núcleo univariado
# ============================================================

def run_drift_univariate(
    series: pd.Series,
    cfg: Dict[str, Any],
    thr_cfg: DriftThresholdConfig = THRESHOLD_CFG,
) -> pd.DataFrame:
    """
    Ejecuta la detección de drift univariado sobre una serie de tiempo.

    Construye ventanas de tamaño `cfg["window"]` (saltando exactamente
    ese tamaño cada vez), y evalúa drift en cada ventana.
    """
    if series.empty:
        return pd.DataFrame(
            columns=["t0", "t1", "drift_flag", "stat_value", "threshold", "episode_id", "state"]
        )

    if not isinstance(series.index, pd.DatetimeIndex):
        raise ValueError("run_drift_univariate espera que el índice sea un DatetimeIndex.")

    df = series.to_frame(name="value").sort_index()

    w = pd.to_timedelta(cfg["window"])
    t_min, t_max = df.index.min(), df.index.max()
    if pd.isna(t_min) or pd.isna(t_max):
        return pd.DataFrame(
            columns=["t0", "t1", "drift_flag", "stat_value", "threshold", "episode_id", "state"]
        )

    t_ends = pd.date_range(t_min + w, t_max, freq=cfg["window"])
    if len(t_ends) == 0:
        return pd.DataFrame(
            columns=["t0", "t1", "drift_flag", "stat_value", "threshold", "episode_id", "state"]
        )

    rows = []

    for t_end in t_ends:
        t0 = t_end - w

        df_hist = df.loc[: t0 - pd.Timedelta(microseconds=1)]
        df_cur = df.loc[t0:t_end]

        if df_hist.empty or df_cur.empty or len(df_cur) < cfg["min_points"]:
            rows.append(
                {"t0": t0, "t1": t_end, "drift_flag": False, "stat_value": None, "threshold": None}
            )
            continue

        # NUEVO: pasamos cfg a build_reference (para usar parámetros estacionales si existen)
        ref_df = build_reference(df_hist, cfg["strategy"], current_end=t_end, cfg=cfg)
        ref_series = ref_df["value"].dropna()
        cur_series = df_cur["value"].dropna()

        if ref_series.empty or cur_series.empty or len(cur_series) < cfg["min_points"]:
            rows.append(
                {"t0": t0, "t1": t_end, "drift_flag": False, "stat_value": None, "threshold": None}
            )
            continue

        stat_val, thr, drift_flag = evaluate_window(ref_series, cur_series, cfg, thr_cfg)

        rows.append(
            {
                "t0": t0,
                "t1": t_end,
                "drift_flag": bool(drift_flag),
                "stat_value": stat_val,
                "threshold": thr,
            }
        )

    windows_df = pd.DataFrame(rows)
    windows_df = detect_episodes(windows_df)

    return windows_df[
        ["t0", "t1", "drift_flag", "stat_value", "threshold", "episode_id", "state"]
    ]

# ============================================================
#  Máscara Variables ON/OFF en extremos
# ============================================================
def mask_plateau_extreme(
    series: pd.Series,       # Serie original
    abs_eps: float,          # Tolerancia mínima absoluta alrededor del extremo
    rel_eps: float,          # Tolerancia relativa (fracción del rango)
    min_share: float,        # Fracción mínima de puntos en el extremo para activar la lógica
    low_quantile: float,     # Cuantil para cortar la “cola baja” (meseta mínima)
    high_quantile: float,    # Cuantil para cortar la “cola alta” (meseta máxima)
) -> pd.Series:
    """
    Detecta una meseta dominante en el mínimo o máximo y elimina *toda*
    la franja cercana a ese extremo, devolviendo una serie con NaN en
    esos puntos (el índice se mantiene igual).

    Pensado para variables que presentan periodos de inactividad con largos
    tramos pegados al mínimo o máximo, donde solo interesa comparar el
    comportamiento "en operación".
    """
    s = series.dropna()
    if s.empty:
        return series

    minv = float(s.min())
    maxv = float(s.max())
    if not np.isfinite(minv) or not np.isfinite(maxv) or minv == maxv:
        return series

    rng = maxv - minv
    eps = max(abs_eps, rel_eps * rng)

    near_min = (s >= minv - eps) & (s <= minv + eps)
    near_max = (s >= maxv - eps) & (s <= maxv + eps)

    frac_min = near_min.mean()
    frac_max = near_max.mean()

    # Si no hay meseta fuerte en extremos, no tocamos nada
    if max(frac_min, frac_max) < min_share:
        return series

    if frac_min >= frac_max:
        # Meseta en el mínimo: eliminamos todo lo "muy abajo"
        resto = s[~near_min]
        if resto.empty:
            return series
        cutoff = resto.quantile(low_quantile)
        mask = s >= cutoff
    else:
        # Meseta en el máximo: eliminamos todo lo "muy arriba"
        resto = s[~near_max]
        if resto.empty:
            return series
        cutoff = resto.quantile(high_quantile)
        mask = s <= cutoff

    return series.where(mask)

# ============================================================
#  Clase principal de pipeline
# ============================================================

class DriftPipeline:
    """
    Clase principal del pipeline de drift.

    Uso típico:
        pipeline = DriftPipeline(
            input_csv=Path("data/planta.csv"),
            output_root=Path("output_drift"),
            config_path=Path("config/config_drift.json"),  # o None para autodetección
            variables=None,
            plateau_vars=None,
            cyclical_vars=None,
        )
        pipeline.run()
    """

    def __init__(
        self,
        input_csv: Path,
        output_root: Path,
        config_path: Optional[Path] = None,
        variables: Optional[Sequence[str]] = None,
        plateau_vars: Optional[Sequence[str]] = None,
        cyclical_vars: Optional[Sequence[str]] = None,
    ) -> None:

        self.input_csv = Path(input_csv)
        self.output_root = Path(output_root)

        # ======================================================
        #  Resolución de ruta de config (con autodetección)
        # ======================================================

        if config_path is not None:
            # Usuario entregó config explícita
            self.config_path = Path(config_path)
        else:
            # Buscar automáticamente un único JSON en carpeta config/
            config_dir = Path("config")
            if not config_dir.exists():
                raise ValueError(
                    "No se entregó --config y no existe carpeta 'config/'.\n"
                    "Debe crear un archivo de configuración usando:\n\n"
                    "  python generar_config_drift.py --output config/config_drift.json\n\n"
                    "O bien pasar explícitamente un archivo con:\n"
                    "  --config config/mi_config.json"
                )

            configs = list(config_dir.glob("*.json"))

            if len(configs) == 0:
                raise ValueError(
                    "No se entregó --config y no se encontró ningún archivo dentro de 'config/'.\n"
                    "Debe crear uno con:\n\n"
                    "  python generar_config_drift.py --output config/config_drift.json\n\n"
                    "O bien especificar manualmente con:\n"
                    "  --config config/archivo.json"
                )

            if len(configs) > 1:
                names = "\n  - ".join(str(c) for c in configs)
                raise ValueError(
                    "No se entregó --config y se encontraron múltiples archivos en 'config/'.\n"
                    "Seleccione uno explícitamente con:\n"
                    "  --config config/<archivo.json>\n\n"
                    f"Archivos encontrados:\n  - {names}"
                )

            self.config_path = configs[0]
            print(f"⚙️  Usando configuración detectada automáticamente: {self.config_path}")

        if not self.config_path.exists():
            raise FileNotFoundError(
                f"El archivo de configuración no existe: {self.config_path}\n"
                "Debe crearlo con:\n"
                "  python generar_config_drift.py --output config/config_drift.json"
            )

        if "config" not in str(self.config_path.parent):
            raise ValueError(
                f"El archivo de configuración debe estar dentro de la carpeta 'config/'.\n"
                f"Ruta recibida: {self.config_path}"
            )

        # Variables opcionales
        self.variables = list(variables) if variables is not None else None
        self.plateau_vars = set(plateau_vars) if plateau_vars else set()
        # 🔒 AQUÍ es donde se decide qué variables son cíclicas (solo CLI)
        self.cyclical_vars = set(cyclical_vars) if cyclical_vars else set()

        self._config: Optional[Dict[str, Any]] = None
    # --------------------------------------------------------
    #  Cargar config real desde JSON
    # --------------------------------------------------------
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Carga el archivo JSON de configuración (OBLIGATORIO).
        """
        with self.config_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError("El archivo de configuración debe ser un objeto JSON válido.")

        if "global" not in data:
            raise ValueError(
                "El archivo de configuración debe contener un bloque 'global' obligatorio."
            )

        return data

    def _build_cfg_for_var(self, var_name: str) -> Dict[str, Any]:

        """
        Construye la configuración efectiva para una variable.

        Mezcla:
        - Bloque global del JSON ("global")
        - Bloque opcional "seasonal_defaults" (para strategy='seasonal')
        - Overrides opcionales en config["variables"][var_name]

        Devuelve un diccionario con al menos:
        - method, strategy, window, min_points
        y puede incluir parámetros adicionales como:
        - cycle_hours, cycles_back, band_frac (para referencias estacionales)
        """
        if self._config is None:
            self._config = self._load_config()

        global_cfg: Dict[str, Any] = self._config.get("global", {})
        seasonal_defaults: Dict[str, Any] = self._config.get("seasonal_defaults", {})
        var_overrides: Dict[str, Any] = (
            self._config.get("variables", {}).get(var_name, {})
        )

        # Base: global
        merged: Dict[str, Any] = {
            "method": str(global_cfg.get("method", "wasserstein")),
            "strategy": str(global_cfg.get("strategy", "decay")),
            "window": str(global_cfg.get("window", "12h")).lower(),
            "min_points": int(global_cfg.get("min_points", 60)),
        }

        # Overrides por variable (incluye parámetros extra)
        for k, v in var_overrides.items():
            if k == "window":
                merged[k] = str(v).lower()
            elif k == "min_points":
                merged[k] = int(v)
            elif k in ("method", "strategy"):
                merged[k] = str(v)
            else:
                # parámetros extra como cycle_hours, band_frac, cycles_back, etc.
                merged[k] = v

        # Si la estrategia final es seasonal, aplicar defaults estacionales
        if merged["strategy"].lower() == "seasonal":
            for k, v in seasonal_defaults.items():
                merged.setdefault(k, v)

        return merged
    # --------------------------------------------------------
    #  Ejecución principal
    # --------------------------------------------------------
    def run(self) -> None:
        """
        Ejecuta el pipeline completo de drift para el CSV de entrada.
        """
        print("Iniciando DriftPipeline...")

        # Crear carpeta principal de salida
        self.output_root.mkdir(parents=True, exist_ok=True)
        ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = self.output_root / f"{self.input_csv.stem}_{ts}"
        run_dir.mkdir(parents=True, exist_ok=True)

        # Cargar configuración
        self._config = self._load_config()
        global_cfg: Dict[str, Any] = self._config.get("global", {})
        seasonal_defaults: Dict[str, Any] = self._config.get("seasonal_defaults", {})
        plateau_defaults: Dict[str, Any] = self._config.get("plateau_defaults", {})

        print(f"Leyendo datos desde: {self.input_csv}")
        df_raw = pd.read_csv(self.input_csv)

        if "date_time" not in df_raw.columns:
            raise ValueError("El CSV debe incluir una columna 'date_time'.")

        df_raw["date_time"] = pd.to_datetime(df_raw["date_time"], errors="coerce")
        df_raw = df_raw.dropna(subset=["date_time"]).sort_values("date_time")
        df_raw = df_raw.set_index("date_time")

        numeric_cols = df_raw.select_dtypes(include="number").columns.tolist()
        if not numeric_cols:
            raise ValueError("No hay columnas numéricas en el CSV de entrada.")

        if self.variables is not None:
            variables = [c for c in self.variables if c in numeric_cols]
        else:
            variables = numeric_cols

        if not variables:
            raise ValueError("No hay variables válidas para procesar drift.")

        print("Variables a procesar:", ", ".join(variables))
        print(f"Directorio de salida: {run_dir}")

        # Output dirs
        windows_dir = run_dir / "Windows"
        flags_dir = run_dir / "Flags"
        windows_dir.mkdir(parents=True, exist_ok=True)
        flags_dir.mkdir(parents=True, exist_ok=True)

        effective_var_cfg: Dict[str, Any] = {}

        for var in variables:
            print(f"\nProcesando variable: {var}")
            series = df_raw[var].dropna()

            # Plateau (definidas SOLO por CLI) 
            if var in self.plateau_vars:
                # Tomar parámetros SOLO desde plateau_defaults del JSON
                plateau_params = {}
                for key in ("abs_eps", "rel_eps", "min_share", "low_quantile", "high_quantile"):
                    if key in plateau_defaults:
                        plateau_params[key] = plateau_defaults[key]

                before = series.notna().sum()
                series = mask_plateau_extreme(series, **plateau_params)
                after = series.notna().sum()
                removed = before - after

                if removed > 0:
                    print(
                        f"  → Mask plateau aplicada a {var}: "
                        f"{removed} puntos ignorados ({removed / before:.1%})."
                    )
                else:
                    print("  → Mask plateau sin cambios.")

            # Config por variable 
            cfg = self._build_cfg_for_var(var)

            # Variables Cíclicas (definidas SOLO por CLI)
            if var in self.cyclical_vars:
                # Si la estrategia no es seasonal, la forzamos
                if cfg.get("strategy", "").lower() != "seasonal":
                    print(f"  → {var} marcada como cíclica; forzando strategy='seasonal'.")
                    cfg["strategy"] = "seasonal"

                # Asegurar parámetros estacionales desde seasonal_defaults (JSON)
                for k, v in seasonal_defaults.items():
                    cfg.setdefault(k, v)

                # Hacer coincidir ventana con el ciclo (para comparar ciclos completos)
                expected_window = f"{int(cfg['cycle_hours'])}h"
                if cfg.get("window") != expected_window:
                    print(
                        f"  → {var}: ajustando window de {cfg['window']} a {expected_window} "
                        "para que coincida con cycle_hours."
                    )
                    cfg["window"] = expected_window

                print(
                    f"  → Parámetros estacionales para {var}: "
                    f"cycle_hours={cfg['cycle_hours']}, "
                    f"cycles_back={cfg['cycles_back']}, "
                    f"window={cfg['window']}"
                )


            # Guardar diff vs global (no incluimos seasonal_defaults aquí)
            diff_cfg = {
                k: v for k, v in cfg.items()
                if v != global_cfg.get(k)
            }
            if diff_cfg:
                effective_var_cfg[var] = diff_cfg

            # ---------- 4) Ejecutar drift ----------
            win_results = run_drift_univariate(series, cfg, THRESHOLD_CFG)

            win_path = windows_dir / f"{var}_windows.csv"
            win_results.to_csv(win_path, index=False)
            print(f"  → Ventanas guardadas en: {win_path.name}")

            drift_flags = windows_to_point_flags(win_results, df_raw.index)

            out_df = pd.DataFrame({
                "date_time": df_raw.index,
                "value": df_raw[var],
                "has_drift": drift_flags.reindex(df_raw.index, fill_value=False).astype(bool)
            })

            out_path = flags_dir / f"{var}.csv"
            out_df.to_csv(out_path, index=False)
            print(f"  → Flags guardados en: {out_path.name}")

        # ---------- 5) Guardar configuración efectiva ----------
        run_config = {
            "input_csv": str(self.input_csv),
            "run_dir": str(run_dir),
            "generated_at": dt.datetime.now().isoformat(),
            "global": global_cfg,
            "seasonal_defaults": seasonal_defaults,
            "variables_overrides": effective_var_cfg,
            "variables_processed": variables,
            "plateau_vars": sorted(self.plateau_vars),  # ← viene solo de CLI
            "cyclical_vars": sorted(self.cyclical_vars),  # ← viene solo de CLI
        }

        with (run_dir / "config_used.json").open("w", encoding="utf-8") as f:
            json.dump(run_config, f, indent=2, ensure_ascii=False)

        print("\n📝 Configuración efectiva guardada.")
        print("✅ Pipeline de drift terminado.")
        print(f"Resultados en: {run_dir}")