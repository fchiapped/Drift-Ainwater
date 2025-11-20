# pipeline_drift.py
from pathlib import Path
from typing import Dict, Any, Tuple

import pandas as pd

from drift_detectors import NumericDriftDetector
from windowing import generate_windows, windows_to_episodes


class DriftPipeline:
    def __init__(self, config: Dict[str, Any], output_dir: Path):
        self.config = config
        self.output_dir = output_dir

    def _build_detector(self, var_cfg: Dict[str, Any]) -> NumericDriftDetector:
        thresholds = var_cfg.get("thresholds", {})
        return NumericDriftDetector(thresholds=thresholds)

    def run_for_variable(
        self, series: pd.Series, var_name: str
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        var_cfg = self.config[var_name]

        window_size = var_cfg.get("window_size", "6H")
        step_size = var_cfg.get("step_size", "1H")
        agg_cfg = var_cfg.get("aggregate_episodes", {})
        min_consecutive = agg_cfg.get("min_consecutive_windows", 2)
        max_gap = agg_cfg.get("max_gap_windows", 1)

        detector = self._build_detector(var_cfg)

        series = series.dropna()
        series.index = pd.to_datetime(series.index)

        windows = generate_windows(series, window_size=window_size, step_size=step_size)

        rows = []
        for idx, win in enumerate(windows):
            if win.empty:
                continue

            # Estrategia simple: referencia = primeras N observaciones (puedes cambiarlo
            # por golden/decay/seasonal según var_cfg['baseline_strategy'])
            ref = series.loc[: win.index.min()]
            cur = win

            result = detector.run(ref, cur)

            row = {
                "window_index": idx,
                "window_start": win.index.min(),
                "window_end": win.index.max(),
                "n_ref": len(ref),
                "n_cur": len(cur),
                "state": "DRIFT" if result.is_drift else "NORMAL",
            }
            row.update(result.metrics)
            rows.append(row)

        windows_df = pd.DataFrame(rows)

        episodes_df = windows_to_episodes(
            windows_df,
            min_consecutive=min_consecutive,
            max_gap=max_gap,
        )

        return windows_df, episodes_df