r"""Giao diện 1 cửa sổ: hiển thị biểu đồ theo từng góc quay + nút đọc lại dữ liệu PLC.

Chạy:
    .\.venv\Scripts\python.exe dashboard_rework.py
"""

from __future__ import annotations

import asyncio
import sys
import threading
from pathlib import Path

import matplotlib

matplotlib.use("TkAgg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import tkinter as tk
from tkinter import ttk

from plc_reader import read_zf_values

COL_BEFORE = "#1f6feb"
COL_AFTER = "#e8710a"
COL_UPPER = "#7b1fa2"
COL_LOWER = "#e65100"
COL_CENTER = "#2e7d32"


def _load(path: Path) -> np.ndarray:
    values = np.genfromtxt(path, delimiter=",", skip_header=1)
    return values.reshape(1, -1) if values.ndim == 1 else values


def _percentages(after: np.ndarray, upper: float, lower: float) -> tuple[float, float, float]:
    total = after.size
    if total == 0:
        return 0.0, 0.0, 0.0
    ok = float(np.sum((after >= lower) & (after <= upper))) / total * 100.0
    slow = float(np.sum(after > upper)) / total * 100.0
    fast = float(np.sum(after < lower)) / total * 100.0
    return ok, slow, fast


class Dashboard(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Rework Auto - Biểu đồ theo góc quay")
        self.geometry("1500x900")
        self.base_dir = (
            Path(sys.executable).resolve().parent
            if getattr(sys, "frozen", False)
            else Path(__file__).resolve().parent
        )
        self.angle_dir = self.base_dir / "zf_by_angle"

        self._build_controls()
        self._build_layout()

        self.upper_var.trace_add("write", lambda *a: self.refresh_plots())
        self.lower_var.trace_add("write", lambda *a: self.refresh_plots())
        self.refresh_plots()

    # ---- Xây dựng giao diện -------------------------------------------------

    def _build_controls(self) -> None:
        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")

        self.host_var = tk.StringVar(value="192.168.100.200")
        self.port_var = tk.StringVar(value="8501")
        self.transport_var = tk.StringVar(value="tcp")
        self.start_var = tk.StringVar(value="10000")
        self.end_var = tk.StringVar(value="16000")
        self.upper_var = tk.StringVar(value="140")
        self.lower_var = tk.StringVar(value="120")
        self.metrics_var = tk.StringVar(value="OK: -  Slow: -  Fast: -")
        self.status_var = tk.StringVar(value="Sẵn sàng.")

        ttk.Label(top, text="Host:").pack(side="left")
        ttk.Entry(top, textvariable=self.host_var, width=18).pack(side="left", padx=4)
        ttk.Label(top, text="Port:").pack(side="left")
        ttk.Entry(top, textvariable=self.port_var, width=8).pack(side="left", padx=4)
        ttk.Label(top, text="Transport:").pack(side="left")
        ttk.Combobox(top, textvariable=self.transport_var, values=["tcp", "udp"], width=7).pack(side="left", padx=4)
        ttk.Label(top, text="ZF từ:").pack(side="left")
        ttk.Entry(top, textvariable=self.start_var, width=7).pack(side="left", padx=4)
        ttk.Label(top, text="ZF đến:").pack(side="left")
        ttk.Entry(top, textvariable=self.end_var, width=7).pack(side="left", padx=4)
        ttk.Label(top, text="Biên trên:").pack(side="left")
        ttk.Entry(top, textvariable=self.upper_var, width=7).pack(side="left", padx=4)
        ttk.Label(top, text="Biên dưới:").pack(side="left")
        ttk.Entry(top, textvariable=self.lower_var, width=7).pack(side="left", padx=4)

        self.update_btn = ttk.Button(top, text="Đọc & cập nhật PLC", command=self.start_update)
        self.update_btn.pack(side="left", padx=8)
        ttk.Label(top, textvariable=self.metrics_var).pack(side="left", padx=8)
        ttk.Label(top, textvariable=self.status_var).pack(side="left", padx=8)

    def _build_layout(self) -> None:
        self.fig, self.axes = plt.subplots(4, 3, figsize=(14, 9))
        self.fig.tight_layout(rect=(0, 0, 1, 0.96))
        content = ttk.Frame(self)
        content.pack(fill="both", expand=True)

        left = ttk.Frame(content)
        left.pack(side="left", fill="both", expand=True)
        self.canvas = FigureCanvasTkAgg(self.fig, master=left)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        right = ttk.Frame(content, width=420)
        right.pack(side="right", fill="y", padx=8, pady=8)
        ttk.Label(right, text="Tỷ lệ theo góc quay", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self._build_table(right)

    def _build_table(self, parent: tk.Widget) -> None:
        container = tk.Frame(parent)
        container.pack(fill="both", expand=True)
        self.table_canvas = tk.Canvas(container, highlightthickness=0)
        self.table_scroll = ttk.Scrollbar(container, orient="vertical", command=self.table_canvas.yview)
        self.table_inner = tk.Frame(self.table_canvas)
        self.table_inner.bind(
            "<Configure>", lambda e: self.table_canvas.configure(scrollregion=self.table_canvas.bbox("all"))
        )
        self.table_canvas.create_window((0, 0), window=self.table_inner, anchor="nw")
        self.table_canvas.configure(yscrollcommand=self.table_scroll.set)
        self.table_canvas.pack(side="left", fill="both", expand=True)
        self.table_scroll.pack(side="right", fill="y")
        for j in range(5):
            self.table_inner.columnconfigure(j, weight=1, minsize=78)

    # ---- Đọc PLC (luồng riêng) ---------------------------------------------

    def start_update(self) -> None:
        self.update_btn.config(state="disabled")
        self.status_var.set("Đang đọc PLC...")
        threading.Thread(target=self._update_worker, daemon=True).start()

    def _update_worker(self) -> None:
        try:
            asyncio.run(
                read_zf_values(
                    self.host_var.get().strip(), int(self.port_var.get().strip()),
                    self.transport_var.get().strip(), 3.0, self.base_dir / "zf_values.csv",
                    start=int(self.start_var.get()), end=int(self.end_var.get()),
                )
            )
            self.after(0, lambda: self._finish_update(True, "Cập nhật thành công."))
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            self.after(0, lambda: self._finish_update(False, message))

    def _finish_update(self, ok: bool, message: str) -> None:
        self.update_btn.config(state="normal")
        self.status_var.set(("OK: " if ok else "LỖI: ") + (message.splitlines()[-1] if message else ""))
        if ok:
            self.refresh_plots()

    # ---- Vẽ lại biểu đồ + bảng ---------------------------------------------

    def _bounds(self) -> tuple[float | None, float | None]:
        try:
            return float(self.upper_var.get()), float(self.lower_var.get())
        except ValueError:
            return None, None

    def _angle_files(self) -> list[Path]:
        return sorted(self.angle_dir.glob("goc_*.csv")) if self.angle_dir.exists() else []

    def refresh_plots(self) -> None:
        upper, lower = self._bounds()
        files = self._angle_files()

        for ax in self.axes.flat:
            ax.clear()
            ax.set_visible(False)

        for ax, path in zip(self.axes.flat, files):
            try:
                values = _load(path)
                before, angle, after = values[:, 0], values[:, 1], values[:, 2]
            except Exception:  # noqa: BLE001
                continue
            ax.set_visible(True)
            idx = np.arange(before.size)
            ax.plot(idx, before, color=COL_BEFORE, lw=1.0)
            ax.plot(idx, after, color=COL_AFTER, lw=1.0)
            if upper is not None:
                ax.axhline(upper, color=COL_UPPER, linestyle="--", linewidth=1.2)
            if lower is not None:
                ax.axhline(lower, color=COL_LOWER, linestyle=":", linewidth=1.2)
            if upper is not None and lower is not None:
                ax.axhline((upper + lower) / 2.0, color=COL_CENTER, linewidth=1.5)
            ax.set_title(f"Góc {int(angle[0]) if angle.size else 0} (n={before.size})", fontsize=9)
            ax.set_xlabel("Mẫu", fontsize=8)
            ax.set_ylabel("s", fontsize=8)
            ax.grid(alpha=0.3)
            ax.tick_params(labelsize=8)

        self._refresh_metrics(upper, lower)
        self._refresh_table(upper, lower, files)

        self.fig.suptitle("Biểu đồ theo từng góc quay", fontsize=14, fontweight="bold")
        self.fig.tight_layout(rect=(0, 0, 1, 0.95))
        self.canvas.draw()

    def _refresh_metrics(self, upper: float | None, lower: float | None) -> None:
        try:
            after = _load(self.base_dir / "zf_values.csv")[:, 2]
            if upper is not None and lower is not None:
                ok, slow, fast = _percentages(after, upper, lower)
                self.metrics_var.set(
                    f"OK (trong 2 biên): {ok:.1f}%   Slow (trên biên trên): {slow:.1f}%   "
                    f"Fast (dưới biên dưới): {fast:.1f}%"
                )
                return
        except Exception:  # noqa: BLE001
            pass
        self.metrics_var.set("OK: -  Slow: -  Fast: -")

    def _refresh_table(self, upper: float | None, lower: float | None, files: list[Path]) -> None:
        for child in self.table_inner.winfo_children():
            child.destroy()

        for j, text in enumerate(["Góc", "Số mẫu", "OK %", "Slow %", "Fast %"]):
            tk.Label(
                self.table_inner, text=text, relief="solid", borderwidth=1,
                bg="#d9d9d9", font=("Segoe UI", 9, "bold"),
            ).grid(row=0, column=j, sticky="nsew")

        if upper is None or lower is None:
            return

        row_idx = 1
        for path in files:
            try:
                values = _load(path)
                after = values[:, 2]
                if after.size == 0:
                    continue
                ok, slow, fast = _percentages(after, upper, lower)
                angle_value = int(values[0, 1])
            except Exception:  # noqa: BLE001
                continue
            cells = [
                (str(angle_value), "#ffffff", "#000000"),
                (str(after.size), "#000000", "#ffffff"),
                (f"{ok:.1f}", COL_CENTER, "#ffffff"),
                (f"{slow:.1f}", COL_UPPER, "#ffffff"),
                (f"{fast:.1f}", COL_LOWER, "#ffffff"),
            ]
            for j, (text, bg, fg) in enumerate(cells):
                tk.Label(
                    self.table_inner, text=text, relief="solid", borderwidth=1,
                    bg=bg, fg=fg, font=("Segoe UI", 9),
                ).grid(row=row_idx, column=j, sticky="nsew")
            row_idx += 1


if __name__ == "__main__":
    Dashboard().mainloop()
