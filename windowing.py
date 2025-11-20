# windowing.py
from typing import List, Tuple

import pandas as pd


def generate_windows(
    series: pd.Series, window_size: str, step_size: str
) -> List[pd.Series]:
    """
    Genera ventanas de una serie con tamaño y paso en formato offset pandas (ej: '6H').
    Devuelve una lista de series indexadas por date_time.
    """
    series = series.sort_index()
    windows = []

    start = series.index.min()
    end = series.index.max()

    current_start = start

    while current_start < end:
        current_end = current_start + pd.Timedelta(window_size)
        window = series.loc[current_start:current_end]

        if not window.empty:
            windows.append(window)

        current_start = current_start + pd.Timedelta(step_size)

    return windows


def windows_to_episodes(
    windows_df: pd.DataFrame,
    min_consecutive: int = 2,
    max_gap: int = 1,
) -> pd.DataFrame:
    """
    Agrupa ventanas etiquetadas como DRIFT en episodios.
    Se espera que windows_df tenga columnas:
        - window_index (int)
        - window_start (datetime)
        - window_end (datetime)
        - state ('NORMAL' / 'DRIFT')
    """
    drift_rows = windows_df[windows_df["state"] == "DRIFT"].copy()

    episodes: List[Tuple[int, int]] = []
    if drift_rows.empty:
        return pd.DataFrame(
            columns=["episode_id", "start_time", "end_time", "num_windows"]
        )

    indices = drift_rows["window_index"].to_list()

    start_idx = indices[0]
    last_idx = indices[0]

    for idx in indices[1:]:
        if idx - last_idx <= max_gap + 1:
            last_idx = idx
        else:
            episodes.append((start_idx, last_idx))
            start_idx = idx
            last_idx = idx

    episodes.append((start_idx, last_idx))

    # Filtrar por mínimo de ventanas consecutivas
    episodes = [ep for ep in episodes if ep[1] - ep[0] + 1 >= min_consecutive]

    rows = []
    for ep_id, (w_start, w_end) in enumerate(episodes, start=1):
        ep_windows = windows_df[
            (windows_df["window_index"] >= w_start)
            & (windows_df["window_index"] <= w_end)
        ]

        rows.append(
            {
                "episode_id": ep_id,
                "start_time": ep_windows["window_start"].min(),
                "end_time": ep_windows["window_end"].max(),
                "num_windows": len(ep_windows),
            }
        )

    return pd.DataFrame(rows)