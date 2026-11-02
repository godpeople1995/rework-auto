r"""Giao dien 1 cua so: hien thi bieu do theo tung goc quay va nut cap nhat du lieu PLC.

Chay:
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


class Dashboard(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Rework Auto - Bieu do theo goc quay")
        self.geometry("1500x900")

        if getattr(sys, "frozen", False):
            self.base_dir = Path(sys.executable).resolve().parent
        else:
            self.base_dir = Path(__file__).resolve().parent
        self.angle_dir = self.base_dir / "zf_by_angle"

        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")

        ttk.Label(top, text="Host:").pack(side="left")
        self.host_var = tk.StringVar(value="192.168.100.200")
        ttk.Entry(top, textvariable=self.host_var, width=18).pack(side="left", padx=4)

        ttk.Label(top, text="Port:").pack(side="left")
        self.port_var = tk.StringVar(value="8501")
        ttk.Entry(top, textvariable=self.port_var, width=8).pack(side="left", padx=4)

        ttk.Label(top, text="Transport:").pack(side="left")
        self.transport_var = tk.StringVar(value="tcp")
        ttk.Combobox(top, textvariable=self.transport_var, values=["tcp", "udp"], width=7).pack(side="left", padx=4)

        ttk.Label(top, text="Bien tren:").pack(side="left")
        self.upper_var = tk.StringVar(value="140")
        ttk.Entry(top, textvariable=self.upper_var, width=7).pack(side="left", padx=4)

        ttk.Label(top, text="Bien duoi:").pack(side="left")
        self.lower_var = tk.StringVar(value="120")
        ttk.Entry(top, textvariable=self.lower_var, width=7).pack(side="left", padx=4)

        self.update_btn = ttk.Button(top, text="Doc & cap nhat PLC", command=self.start_update)
        self.update_btn.pack(side="left", padx=8)

        self.metrics_var = tk.StringVar(value="OK: -  Slow: -  Fast: -")
        ttk.Label(top, textvariable=self.metrics_var).pack(side="left", padx=8)

        self.status_var = tk.StringVar(value="San sang.")
        ttk.Label(top, textvariable=self.status_var).pack(side="left", padx=8)

        self.fig, self.axes = plt.subplots(4, 3, figsize=(14, 9))
        self.fig.tight_layout(rect=(0, 0, 1, 0.96))
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.canvas.draw()

        self.refresh_plots()

        self.upper_var.trace_add("write", lambda *args: self.refresh_plots())
        self.lower_var.trace_add("write", lambda *args: self.refresh_plots())

    def start_update(self) -> None:
        self.update_btn.config(state="disabled")
        self.status_var.set("Dang doc PLC...")
        thread = threading.Thread(target=self._update_worker, daemon=True)
        thread.start()

    def _update_worker(self) -> None:
        host = self.host_var.get().strip()
        port = self.port_var.get().strip()
        transport = self.transport_var.get().strip()
        csv_path = self.base_dir / "zf_values.csv"
        try:
            asyncio.run(
                read_zf_values(host, int(port), transport, 3.0, csv_path)
            )
            self.after(0, lambda: self._finish_update(True, "Cap nhat thanh cong."))
        except Exception as exc:  # noqa: BLE001
            self.after(0, lambda: self._finish_update(False, str(exc)))

    def _finish_update(self, ok: bool, message: str) -> None:
        self.update_btn.config(state="normal")
        self.status_var.set(("OK: " if ok else "LOI: ") + message.splitlines()[-1] if message else "")
        if ok:
            self.refresh_plots()

    def refresh_plots(self) -> None:
        files = sorted(self.angle_dir.glob("goc_*.csv")) if self.angle_dir.exists() else []
        for ax in self.axes.flat:
            ax.clear()
            ax.set_visible(False)

        for ax, path in zip(self.axes.flat, files):
            try:
                values = np.genfromtxt(path, delimiter=",", skip_header=1)
                if values.ndim == 1:
                    values = values.reshape(1, -1)
                before = values[:, 0]
                angle = values[:, 1]
                after = values[:, 2]
            except Exception:  # noqa: BLE001
                continue
            ax.set_visible(True)
            idx = np.arange(before.size)
            angle_value = int(angle[0]) if angle.size else 0
            ax.plot(idx, before, color="#1f6feb", lw=1.0, label="Truoc")
            ax.plot(idx, after, color="#e8710a", lw=1.0, label="Sau")

            # Ve bien tren, bien duoi va bien trung tam
            try:
                upper = float(self.upper_var.get())
                ax.axhline(upper, color="#7b1fa2", linestyle="--", linewidth=1.2, label="Bien tren")
            except ValueError:
                upper = None
            try:
                lower = float(self.lower_var.get())
                ax.axhline(lower, color="#e65100", linestyle=":", linewidth=1.2, label="Bien duoi")
            except ValueError:
                lower = None
            if upper is not None and lower is not None:
                center = (upper + lower) / 2.0
                ax.axhline(center, color="#2e7d32", linestyle="-", linewidth=1.5, label="Bien trung tam")

            ax.set_title(f"Goc {angle_value} (n={before.size})", fontsize=9)
            ax.set_xlabel("Mau", fontsize=8)
            ax.set_ylabel("s", fontsize=8)
            ax.grid(alpha=0.3)
            ax.tick_params(labelsize=8)

        # Tinh cac chi so % dua tren bien
        csv_path = self.base_dir / "zf_values.csv"
        try:
            data = np.genfromtxt(csv_path, delimiter=",", skip_header=1)
            if data.ndim == 1:
                data = data.reshape(1, -1)
            after = data[:, 2]
            upper = float(self.upper_var.get())
            lower = float(self.lower_var.get())
            total = after.size
            if total > 0:
                ok = float(np.sum((after >= lower) & (after <= upper))) / total * 100.0
                slow = float(np.sum(after > upper)) / total * 100.0
                fast = float(np.sum(after < lower)) / total * 100.0
                self.metrics_var.set(
                    f"OK (trong 2 bien): {ok:.1f}%   Slow (tren bien tren): {slow:.1f}%   Fast (duoi bien duoi): {fast:.1f}%"
                )
            else:
                self.metrics_var.set("OK: -  Slow: -  Fast: -")
        except Exception:  # noqa: BLE001
            self.metrics_var.set("OK: -  Slow: -  Fast: -")

        self.fig.suptitle("Bieu do theo tung goc quay", fontsize=14, fontweight="bold")
        self.fig.tight_layout(rect=(0, 0, 1, 0.95))
        self.canvas.draw()


if __name__ == "__main__":
    app = Dashboard()
    app.mainloop()
