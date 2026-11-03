"""Tiện ích dùng chung cho các script vẽ biểu đồ."""

from __future__ import annotations

from pathlib import Path

import numpy as np

COL_BEFORE = "#1f6feb"
COL_AFTER = "#e8710a"
FONT_FAMILY = ["Segoe UI", "Arial", "DejaVu Sans"]


def load_data(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Đọc CSV 3 cột, trả về (thời gian trước, góc quay, thời gian sau)."""
    values = np.genfromtxt(path, delimiter=",", skip_header=1)
    if values.ndim == 1:
        values = values.reshape(1, -1)
    if values.ndim != 2 or values.shape[1] != 3:
        raise ValueError(f"{path} phải có 3 cột dữ liệu")
    return values[:, 0], values[:, 1], values[:, 2]
