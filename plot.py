r"""Vẽ biểu đồ phân tích dữ liệu ZF (gộp 2 chế độ).

Chạy:
    .\.venv\Scripts\python.exe plot.py values            # 6-panel phân tích tổng
    .\.venv\Scripts\python.exe plot.py angles            # vẽ từng góc quay riêng
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from common import COL_AFTER, COL_BEFORE, FONT_FAMILY, load_data

plt.rcParams["font.family"] = FONT_FAMILY
plt.rcParams["axes.unicode_minus"] = False


def fit(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    """Hồi quy tuyến tính y = a*x + b, trả về (a, b, r)."""
    a, b = np.polyfit(x, y, 1)
    return float(a), float(b), float(np.corrcoef(x, y)[0, 1])


def plot_values(args: argparse.Namespace) -> int:
    before, angle, after = load_data(Path(args.csv))
    delta = after - before
    idx = np.arange(before.size)

    a_before, b_before, r_before = fit(angle, before)
    a_after, b_after, r_after = fit(angle, after)
    a_delta, b_delta, r_delta = fit(angle, delta)

    fig, axes = plt.subplots(2, 3, figsize=(17, 9))
    fig.suptitle(
        "Phân tích góc quay và thời gian trước/sau khi chỉnh (ZF10000–ZF16000, giây)",
        fontsize=14,
        fontweight="bold",
    )

    # (1) Chuỗi thời gian
    ax = axes[0, 0]
    ax.plot(idx, before, color=COL_BEFORE, lw=0.6, alpha=0.35)
    ax.plot(idx, after, color=COL_AFTER, lw=0.6, alpha=0.35)
    if before.size >= 51:
        kernel = np.ones(51) / 51
        ax.plot(idx, np.convolve(before, kernel, mode="same"), color=COL_BEFORE, lw=2, label="Trung bình trượt 51 mẫu")
        ax.plot(idx, np.convolve(after, kernel, mode="same"), color=COL_AFTER, lw=2)
    ax.set_title("Thời gian trước và sau theo thứ tự đọc")
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

    # (3) Trước khi chỉnh vs góc
    ax = axes[0, 2]
    ax.scatter(angle, before, s=10, alpha=0.35, color=COL_BEFORE, edgecolors="none")
    xs = np.linspace(angle.min(), angle.max(), 100)
    ax.plot(xs, a_before * xs + b_before, color="#b00020", lw=2,
            label=f"y = {a_before:.4f}x + {b_before:.1f}\nr = {r_before:.3f}, R² = {r_before**2:.3f}")
    ax.set_title("Trước khi chỉnh: phụ thuộc mạnh vào góc")
    ax.set_xlabel("Góc quay")
    ax.set_ylabel("Thời gian trước (s)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="upper left")

    # (4) Sau khi chỉnh vs góc
    ax = axes[1, 0]
    ax.scatter(angle, after, s=10, alpha=0.35, color=COL_AFTER, edgecolors="none")
    ax.axhline(after.mean(), color="#b00020", lw=2,
               label=f"Trung bình = {after.mean():.1f}\nr = {r_after:.3f}, R² = {r_after**2:.3f}")
    ax.set_title("Sau khi chỉnh: gần như không phụ thuộc góc")
    ax.set_xlabel("Góc quay")
    ax.set_ylabel("Thời gian sau (s)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="upper left")

    # (5) Chênh lệch vs góc
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

    # (6) Phân bố
    ax = axes[1, 2]
    bins = np.arange(0, 180, 5)
    ax.hist(before, bins=bins, alpha=0.55, color=COL_BEFORE, label=f"Trước (σ={before.std():.1f})")
    ax.hist(after, bins=bins, alpha=0.55, color=COL_AFTER, label=f"Sau (σ={after.std():.1f})")
    ax.set_title("Phân bố thời gian trước/sau")
    ax.set_xlabel("Thời gian (s)")
    ax.set_ylabel("Số mẫu")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)

    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(args.out, dpi=130)
    print(f"Đã lưu biểu đồ: {args.out}")

    # Bảng tóm tắt theo góc
    rows = [
        [int(v), int((angle == v).sum()), round(float(before[angle == v].mean()), 2),
         round(float(after[angle == v].mean()), 2), round(float(delta[angle == v].mean()), 2)]
        for v in np.unique(angle)
    ]
    with open(args.summary, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Góc quay", "Số mẫu", "TB trước (s)", "TB sau (s)", "TB sau - trước (s)"])
        writer.writerows(rows)
    print(f"Đã lưu tóm tắt: {args.summary}")

    print(f"\nSố mẫu: {before.size}")
    print(f"Trước (s): TB={before.mean():.2f}  SD={before.std():.2f}  min={before.min():.0f}  max={before.max():.0f}")
    print(f"Góc  (độ): TB={angle.mean():.2f}  SD={angle.std():.2f}  min={angle.min():.0f}  max={angle.max():.0f}")
    print(f"Sau  (s) : TB={after.mean():.2f}  SD={after.std():.2f}  min={after.min():.0f}  max={after.max():.0f}")
    print(f"Tương quan góc-trước: r={r_before:.4f} (R²={r_before**2:.4f})")
    print(f"Tương quan góc-sau  : r={r_after:.4f} (R²={r_after**2:.4f})")
    print(f"Tương quan góc-delta: r={r_delta:.4f}")
    print(f"Hồi quy trước = {a_before:.5f}*góc + {b_before:.2f}")
    print(f"Hồi quy sau   = {a_after:.5f}*góc + {b_after:.2f}")
    print(f"Tỷ lệ sau trong 120..140: {((after >= 120) & (after <= 140)).mean():.1%}")
    print(f"Tỷ lệ trước trong 120..140: {((before >= 120) & (before <= 140)).mean():.1%}")
    return 0


def plot_angles(args: argparse.Namespace) -> int:
    input_dir = Path(args.input_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(input_dir.glob("goc_*.csv"))
    if not files:
        print(f"Không tìm thấy file goc_*.csv trong {input_dir}")
        return 1

    for path in files:
        before, angle, after = load_data(path)
        idx = np.arange(before.size)
        angle_value = int(angle[0]) if angle.size else 0

        fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
        fig.suptitle(f"Góc quay {angle_value}° — trước / sau khi chỉnh", fontsize=13, fontweight="bold")

        ax = axes[0]
        ax.plot(idx, before, color=COL_BEFORE, lw=1.2, marker="o", ms=3, label="Trước khi chỉnh")
        ax.plot(idx, after, color=COL_AFTER, lw=1.2, marker="o", ms=3, label="Sau khi chỉnh")
        ax.set_title("Theo thứ tự mẫu")
        ax.set_xlabel("Mẫu")
        ax.set_ylabel("Thời gian (s)")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)

        ax = axes[1]
        ax.hist(before, bins=20, alpha=0.55, color=COL_BEFORE, label=f"Trước (TB={before.mean():.1f})")
        ax.hist(after, bins=20, alpha=0.55, color=COL_AFTER, label=f"Sau (TB={after.mean():.1f})")
        ax.set_title("Phân bố thời gian")
        ax.set_xlabel("Thời gian (s)")
        ax.set_ylabel("Số mẫu")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)

        fig.tight_layout(rect=(0, 0, 1, 0.93))
        out_path = out_dir / f"goc_{angle_value}.png"
        fig.savefig(out_path, dpi=130)
        plt.close(fig)
        print(f"{path.name}: {before.size} mẫu -> {out_path}")

    print(f"\nĐã vẽ {len(files)} biểu đồ vào {out_dir}/")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Vẽ biểu đồ phân tích dữ liệu ZF")
    sub = parser.add_subparsers(dest="mode", required=True)

    p_values = sub.add_parser("values", help="6-panel phân tích tổng")
    p_values.add_argument("--csv", default="zf_values.csv", help="File dữ liệu đầu vào")
    p_values.add_argument("--out", default="zf_analysis.png", help="File ảnh đầu ra")
    p_values.add_argument("--summary", default="zf_angle_summary.csv", help="File tóm tắt theo góc")
    p_values.set_defaults(func=plot_values)

    p_angles = sub.add_parser("angles", help="Vẽ từng góc quay riêng")
    p_angles.add_argument("--input-dir", default="zf_by_angle", help="Thư mục chứa file theo góc")
    p_angles.add_argument("--out-dir", default="zf_angle_plots", help="Thư mục lưu ảnh")
    p_angles.set_defaults(func=plot_angles)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
