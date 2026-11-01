r"""Vẽ biểu đồ và phân tích mối quan hệ giữa góc quay với thời gian trước/sau khi chỉnh.

Dữ liệu: zf_values.csv (3 cột: thời gian trước, góc quay, thời gian sau).

Chạy:
    .\.venv\Scripts\python.exe plot_zf_values.py
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
    if values.ndim != 2 or values.shape[1] != 3:
        raise ValueError(f"{path} phai co 3 cot du lieu")
    return values[:, 0], values[:, 1], values[:, 2]


def fit(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    """Hoi quy tuyen tinh y = a*x + b, tra ve (a, b, r)."""
    a, b = np.polyfit(x, y, 1)
    r = float(np.corrcoef(x, y)[0, 1])
    return float(a), float(b), r


def main() -> int:
    parser = argparse.ArgumentParser(description="Ve bieu do ZF10000-ZF16000")
    parser.add_argument("--csv", default="zf_values.csv", help="File du lieu dau vao")
    parser.add_argument("--out", default="zf_analysis.png", help="File anh dau ra")
    parser.add_argument("--summary", default="zf_angle_summary.csv", help="File tom tat theo goc")
    args = parser.parse_args()

    before, angle, after = load_data(Path(args.csv))
    delta = after - before
    idx = np.arange(before.size)

    a_before, b_before, r_before = fit(angle, before)
    a_after, b_after, r_after = fit(angle, after)
    a_delta, b_delta, r_delta = fit(angle, delta)

    fig, axes = plt.subplots(2, 3, figsize=(17, 9))
    fig.suptitle(
        "Phân tích góc quay và thời gian trước / sau khi chỉnh (ZF10000–ZF16000, thời gian: giây)",
        fontsize=14,
        fontweight="bold",
    )

    # (1) Chuoi thoi gian
    ax = axes[0, 0]
    ax.plot(idx, before, color="#1f6feb", lw=0.6, alpha=0.35, label="Từng mẫu")
    ax.plot(idx, after, color="#e8710a", lw=0.6, alpha=0.35)
    w = 51
    if before.size >= w:
        kernel = np.ones(w) / w
        ax.plot(idx, np.convolve(before, kernel, mode="same"), color="#1f6feb", lw=2, label="Trung bình trượt 51 mẫu")
        ax.plot(idx, np.convolve(after, kernel, mode="same"), color="#e8710a", lw=2)
    ax.set_title("Thời gian trước và sau khi chỉnh theo thứ tự đọc")
    ax.set_xlabel("Mẫu")
    ax.set_ylabel("Thời gian (s)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)

    # (2) Góc quay theo thứ tự đọc
    ax = axes[0, 1]
    ax.step(idx, angle, where="mid", color="#7b1fa2", lw=0.8)
    ax.set_title("Góc quay theo thứ tự đọc")
    ax.set_xlabel("Mẫu")
    ax.set_ylabel("Góc quay")
    ax.grid(alpha=0.3)

    # (3) Truoc chinh vs goc
    ax = axes[0, 2]
    ax.scatter(angle, before, s=10, alpha=0.35, color="#1f6feb", edgecolors="none")
    xs = np.linspace(angle.min(), angle.max(), 100)
    ax.plot(xs, a_before * xs + b_before, color="#b00020", lw=2,
            label=f"y = {a_before:.4f}x + {b_before:.1f}\nr = {r_before:.3f}, R² = {r_before**2:.3f}")
    ax.set_title("Trước khi chỉnh: phụ thuộc mạnh vào góc")
    ax.set_xlabel("Góc quay")
    ax.set_ylabel("Thời gian trước khi chỉnh (s)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="upper left")

    # (4) Sau chinh vs goc
    ax = axes[1, 0]
    ax.scatter(angle, after, s=10, alpha=0.35, color="#e8710a", edgecolors="none")
    ax.axhline(after.mean(), color="#b00020", lw=2,
               label=f"Trung bình = {after.mean():.1f}\nr = {r_after:.3f}, R² = {r_after**2:.3f}")
    ax.set_title("Sau khi chỉnh: gần như không phụ thuộc góc")
    ax.set_xlabel("Góc quay")
    ax.set_ylabel("Thời gian sau khi chỉnh (s)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="upper left")

    # (5) Delta vs goc
    ax = axes[1, 1]
    ax.scatter(angle, delta, s=10, alpha=0.35, color="#2e7d32", edgecolors="none")
    ax.plot(xs, a_delta * xs + b_delta, color="#b00020", lw=2,
            label=f"y = {a_delta:.4f}x + {b_delta:.1f}\nr = {r_delta:.3f}")
    ax.axhline(0, color="black", lw=0.8, ls="--")
    ax.set_title("Chênh lệch (sau − trước) theo góc")
    ax.set_xlabel("Góc quay")
    ax.set_ylabel("Sau − trước (s)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="upper right")

    # (6) Phan bo
    ax = axes[1, 2]
    bins = np.arange(0, 180, 5)
    ax.hist(before, bins=bins, alpha=0.55, color="#1f6feb", label=f"Trước (σ={before.std():.1f})")
    ax.hist(after, bins=bins, alpha=0.55, color="#e8710a", label=f"Sau (σ={after.std():.1f})")
    ax.set_title("Phân bố thời gian trước / sau")
    ax.set_xlabel("Thời gian (s)")
    ax.set_ylabel("Số mẫu")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)

    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(args.out, dpi=130)
    print(f"Da luu bieu do: {args.out}")

    # Bang tom tat theo tung goc
    rows = []
    for value in np.unique(angle):
        mask = angle == value
        rows.append(
            [
                int(value),
                int(mask.sum()),
                round(float(before[mask].mean()), 2),
                round(float(after[mask].mean()), 2),
                round(float(delta[mask].mean()), 2),
            ]
        )
    with open(args.summary, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Goc quay", "So mau", "TB truoc (s)", "TB sau (s)", "TB sau - truoc (s)"])
        writer.writerows(rows)
    print(f"Da luu tom tat: {args.summary}")

    print(f"\nSo mau: {before.size}")
    print(f"Truoc (s): TB={before.mean():.2f}  SD={before.std():.2f}  min={before.min():.0f}  max={before.max():.0f}")
    print(f"Goc  (do): TB={angle.mean():.2f}  SD={angle.std():.2f}  min={angle.min():.0f}  max={angle.max():.0f}")
    print(f"Sau  (s) : TB={after.mean():.2f}  SD={after.std():.2f}  min={after.min():.0f}  max={after.max():.0f}")
    print(f"Tuong quan goc-truoc: r={r_before:.4f} (R2={r_before**2:.4f})")
    print(f"Tuong quan goc-sau  : r={r_after:.4f} (R2={r_after**2:.4f})")
    print(f"Tuong quan goc-delta: r={r_delta:.4f}")
    print(f"Hoi quy truoc = {a_before:.5f}*goc + {b_before:.2f}")
    print(f"Hoi quy sau   = {a_after:.5f}*goc + {b_after:.2f}")
    print(f"Ty le sau trong 120..140: {((after >= 120) & (after <= 140)).mean():.1%}")
    print(f"Ty le truoc trong 120..140: {((before >= 120) & (before <= 140)).mean():.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
