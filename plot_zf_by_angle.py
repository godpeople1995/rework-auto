r"""Ve bieu do cho tung goc quay tu cac file trong zf_by_angle/.

Moi file goc_<goc>.csv se tao ra mot anh goc_<goc>.png.

Chay:
    .\.venv\Scripts\python.exe plot_zf_by_angle.py
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

plt.rcParams["font.family"] = ["Segoe UI", "Arial", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def load_data(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    values = np.genfromtxt(path, delimiter=",", skip_header=1)
    if values.ndim == 1:
        values = values.reshape(1, -1)
    if values.ndim != 2 or values.shape[1] != 3:
        raise ValueError(f"{path} phai co 3 cot du lieu")
    return values[:, 0], values[:, 1], values[:, 2]


def main() -> int:
    parser = argparse.ArgumentParser(description="Ve bieu do theo tung goc quay")
    parser.add_argument("--input-dir", default="zf_by_angle", help="Thu muc chua file theo goc")
    parser.add_argument("--out-dir", default="zf_angle_plots", help="Thu muc luu anh")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(input_dir.glob("goc_*.csv"))
    if not files:
        print(f"Khong tim thay file goc_*.csv trong {input_dir}")
        return 1

    for path in files:
        before, angle, after = load_data(path)
        idx = np.arange(before.size)
        angle_value = int(angle[0]) if angle.size else 0

        fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
        fig.suptitle(
            f"Góc quay {angle_value}° — thời gian trước / sau khi chỉnh",
            fontsize=13,
            fontweight="bold",
        )

        ax = axes[0]
        ax.plot(idx, before, color="#1f6feb", lw=1.2, marker="o", ms=3, label="Trước khi chỉnh")
        ax.plot(idx, after, color="#e8710a", lw=1.2, marker="o", ms=3, label="Sau khi chỉnh")
        ax.set_title("Theo thứ tự mẫu")
        ax.set_xlabel("Mẫu")
        ax.set_ylabel("Thời gian (s)")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)

        ax = axes[1]
        ax.hist(before, bins=20, alpha=0.55, color="#1f6feb", label=f"Trước (TB={before.mean():.1f})")
        ax.hist(after, bins=20, alpha=0.55, color="#e8710a", label=f"Sau (TB={after.mean():.1f})")
        ax.set_title("Phân bố thời gian")
        ax.set_xlabel("Thời gian (s)")
        ax.set_ylabel("Số mẫu")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)

        fig.tight_layout(rect=(0, 0, 1, 0.93))
        out_path = out_dir / f"goc_{angle_value}.png"
        fig.savefig(out_path, dpi=130)
        plt.close(fig)
        print(f"{path.name}: {before.size} mau -> {out_path}")

    print(f"\nDa ve {len(files)} bieu do vao {out_dir}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
