r"""Giao diện 1 cửa sổ: hiển thị biểu đồ theo từng góc quay + nút đọc lại dữ liệu PLC.

Chạy:
    .\.venv\Scripts\python.exe dashboard_rework.py

Giao diện tự co giãn để vừa với mọi kích thước màn hình:
- Cửa sổ mở đúng kích thước màn hình (không cố định 1500x900).
- Thanh điều khiển tự xuống dòng khi cửa sổ hẹp.
- Vùng biểu đồ/bảng tách bằng PanedWindow, kéo được để chia tỷ lệ.
- Biểu đồ tự vẽ lại (tight_layout) khi thay đổi kích thước cửa sổ.

Các tính năng phụ:
- Nút "Đọc liên tục (5s)": đọc PLC lặp lại mỗi 5 giây.
- Tự nhớ IP/cấu hình gần nhất (lưu vào file cấu hình trong thư mục người dùng).
"""

from __future__ import annotations  # Cho phép ghi chú kiểu (type hint) kiểu mới như "str | None".

import asyncio          # Chạy hàm đọc PLC bất đồng bộ (async) trong luồng riêng.
import json             # Lưu/đọc file cấu hình (nhớ IP gần nhất).
import math             # Tính toán (ceil) cho mục tiêu tỷ lệ %.
import sys              # Kiểm tra app có đang chạy dạng "đóng gói" (frozen/exe) hay không.
import threading        # Tạo luồng phụ để đọc PLC mà không làm đứng giao diện.
from pathlib import Path  # Làm việc với đường dẫn file/thư mục.

import matplotlib        # Thư viện vẽ biểu đồ.

matplotlib.use("TkAgg")  # Chọn "backend" TkAgg để vẽ biểu đồ nhúng vào cửa sổ Tkinter.

import matplotlib.pyplot as plt  # Giao diện vẽ biểu đồ kiểu MATLAB.
import numpy as np               # Tính toán mảng số (đọc dữ liệu CSV).
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # Cầu nối đưa biểu đồ vào Tkinter.
from matplotlib.lines import Line2D  # Dùng để tạo các mẫu đường trong chú thích màu (legend).

import tkinter as tk          # Thư viện giao diện đồ họa Tkinter.
from tkinter import ttk       # Các widget "tema" (hiện đại hơn) của Tkinter.
from tkinter import messagebox  # Hộp thoại xác nhận (trước khi xoá dữ liệu).

from plc_reader import (  # Hàm đọc/ghi PLC.
    OFFSET_READ_ITEMS,
    clear_all,
    clear_angle,
    clear_local,
    read_bounds,
    read_offsets,
    read_zf_values,
    remove_angle_local,
    write_offsets,
)

# ---- Các màu dùng chung cho biểu đồ --------------------------------------
COL_BEFORE = "#1f6feb"  # Màu xanh dương: đường "trước khi chỉnh".
COL_AFTER = "#e8710a"   # Màu cam: đường "sau khi chỉnh".
COL_UPPER = "#7b1fa2"   # Màu tím: liên quan đến slow (biên trên, nét đứt --).
COL_LOWER = "#e8710a"   # Màu cam: liên quan đến fast (biên dưới, nét chấm :).
COL_CENTER = "#2e7d32"  # Màu xanh lá: đường trung tâm (giữa 2 biên).

FONT_FAMILY = ["Segoe UI", "Arial", "DejaVu Sans"]  # Danh sách font ưu tiên (có tiếng Việt).
plt.rcParams["font.family"] = FONT_FAMILY            # Áp font này cho mọi biểu đồ.
plt.rcParams["axes.unicode_minus"] = False           # Hiển thị đúng dấu trừ "-" (không bị lỗi font).

# Vùng bố cục biểu đồ: chừa chỗ cho tiêu đề phía trên và chú thích màu phía dưới.
LAYOUT_RECT = (0.0, 0.05, 1.0, 0.98)

# File lưu cấu hình (nhớ IP/cổng/địa chỉ ZF gần nhất) — đặt trong thư mục người dùng.
CONFIG_PATH = Path.home() / ".rework_auto_config.json"
AUTO_INTERVAL_MS = 5000  # Chu kỳ đọc liên tục (5 giây).


def _load(path: Path) -> np.ndarray:
    """Đọc file CSV thành mảng 2 chiều numpy (bỏ dòng tiêu đề)."""
    values = np.genfromtxt(path, delimiter=",", skip_header=1)  # Đọc CSV, bỏ dòng header.
    return values.reshape(1, -1) if values.ndim == 1 else values  # Đảm bảo luôn là mảng 2D.


def _percentages(after: np.ndarray, upper: float, lower: float) -> tuple[float, float, float]:
    """Tính % số mẫu OK / Slow / Fast so với 2 biên trên-dưới."""
    total = after.size  # Tổng số mẫu.
    if total == 0:      # Không có mẫu nào thì trả về 0 hết.
        return 0.0, 0.0, 0.0
    ok = float(np.sum((after >= lower) & (after <= upper))) / total * 100.0   # Nằm trong khoảng 2 biên.
    slow = float(np.sum(after > upper)) / total * 100.0                        # Vượt biên trên.
    fast = float(np.sum(after < lower)) / total * 100.0                        # Dưới biên dưới.
    return ok, slow, fast


class FlowFrame(tk.Frame):
    """Frame sắp xếp các widget con theo dòng, tự xuống dòng khi hết chiều ngang."""

    def __init__(self, master: tk.Widget, **kwargs) -> None:
        super().__init__(master, **kwargs)  # Khởi tạo Frame cha bình thường.
        self._items: list[tuple[tk.Widget, int]] = []  # Danh sách (widget, khoảng cách phải).
        self.bind("<Configure>", self._reflow)          # Khi frame đổi kích thước -> sắp xếp lại.

    def add(self, widget: tk.Widget, padx: int = 8) -> None:
        """Thêm một widget vào danh sách cần sắp xếp (chưa đặt vị trí ngay)."""
        self._items.append((widget, padx))  # Lưu widget và khoảng cách ngang sau nó.

    def _reflow(self, _event=None) -> None:
        """Xếp các widget thành nhiều dòng, xuống dòng khi không còn chỗ ngang."""
        if getattr(self, "_reflowing", False):  # Đang sắp xếp rồi thì bỏ qua (chống đệ quy).
            return
        width = self.winfo_width()  # Chiều rộng hiện tại của frame (pixel).
        if width <= 1 or not self._items:  # Chưa có kích thước thật hoặc không có gì -> bỏ qua.
            return
        self._reflowing = True  # Đánh dấu đang sắp xếp để tránh gọi lại đệ quy.
        try:
            for widget, _ in self._items:
                widget.grid_forget()  # Xóa vị trí cũ của tất cả widget.

            col = 0  # Cột hiện tại (bắt đầu từ 0).
            row = 0  # Dòng hiện tại.
            x = 0    # Vị trí ngang đang dùng (để biết khi nào xuống dòng).
            for widget, padx in self._items:
                req_w = widget.winfo_reqwidth()  # Chiều rộng "mong muốn" của widget.
                if col > 0 and x + req_w > width:  # Nếu widget này vượt quá chiều rộng -> xuống dòng.
                    col = 0      # Về cột đầu.
                    row += 1     # Xuống dòng mới.
                    x = 0        # Reset vị trí ngang.
                widget.grid(row=row, column=col, sticky="w", padx=(0, padx), pady=3)  # Đặt widget vào ô.
                x += req_w + padx  # Cộng dồn chiều ngang đã dùng.
                col += 1           # Sang cột kế tiếp.
        finally:
            self._reflowing = False  # Bỏ cờ (dù có lỗi cũng phải bỏ).


class Dashboard(tk.Tk):
    def __init__(self) -> None:
        super().__init__()  # Khởi tạo cửa sổ Tk gốc.
        self.title("Rework Auto - Biểu đồ theo góc quay")  # Tiêu đề cửa sổ.
        self._resize_job: str | None = None  # Lưu ID job "after" đang chờ vẽ lại (để hủy được).
        self._auto_job: str | None = None    # Lưu ID job "after" của chu kỳ đọc liên tục.
        self.auto_running = False  # Đang bật chế độ đọc liên tục hay không.
        self._reading = False      # Đang có 1 lần đọc PLC hay chưa (tránh chồng lặp).
        self._writing = False      # Đang ghi offset xuống PLC hay chưa.
        self._offset_value: int | None = None  # Giá trị EM120 (offset) đọc được lần gần nhất.
        self.selected_angle: int | None = None  # Góc đang được chọn (để tô đậm biểu đồ tương ứng).
        self._angle_to_ax: dict[int, object] = {}  # Ánh xạ góc -> biểu đồ con.

        # Xác định thư mục gốc của ứng dụng (chứa dữ liệu CSV):
        self.base_dir = (
            Path(sys.executable).resolve().parent          # Nếu chạy dạng file .exe -> thư mục chứa exe.
            if getattr(sys, "frozen", False)               # "frozen" = đang chạy dạng đóng gói (PyInstaller).
            else Path(__file__).resolve().parent           # Bình thường -> thư mục chứa file code này.
        )
        self.angle_dir = self.base_dir / "zf_by_angle"  # Thư mục chứa file CSV theo từng góc quay.

        self._fit_to_screen()   # Đặt kích thước cửa sổ theo màn hình.
        self._build_controls()  # Dựng thanh điều khiển phía trên.
        self._build_layout()    # Dựng vùng biểu đồ + bảng.

        self.protocol("WM_DELETE_WINDOW", self._on_close)  # Khi bấm nút X -> gọi _on_close.

        self.upper_var.trace_add("write", lambda *a: self.refresh_plots())  # Đổi biên trên -> vẽ lại.
        self.lower_var.trace_add("write", lambda *a: self.refresh_plots())  # Đổi biên dưới -> vẽ lại.
        self.refresh_plots()  # Vẽ biểu đồ lần đầu tiên.

    def _on_close(self) -> None:
        """Hủy các job đang chờ, lưu cấu hình rồi mới đóng cửa sổ."""
        for job in (self._resize_job, self._auto_job):  # Hủy cả job vẽ lại và job đọc liên tục.
            if job is not None:
                try:
                    self.after_cancel(job)  # Hủy job.
                except Exception:  # noqa: BLE001
                    pass  # Bỏ qua nếu job đã chạy/hủy rồi.
        self._resize_job = None
        self._auto_job = None
        self.auto_running = False  # Tắt cờ đọc liên tục.
        self._save_config()  # Lưu IP/cấu hình gần nhất trước khi thoát.
        self.destroy()  # Đóng cửa sổ, kết thúc ứng dụng.

    # ---- Lưu / đọc cấu hình (nhớ IP gần nhất) ------------------------------

    def _load_config(self) -> dict:
        """Đọc file cấu hình đã lưu, trả về dict (rỗng nếu không có/lỗi)."""
        try:
            if CONFIG_PATH.exists():  # Chỉ đọc nếu file tồn tại.
                return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass  # File hỏng/không đọc được -> bỏ qua.
        return {}

    def _save_config(self) -> None:
        """Lưu các thông số kết nối hiện tại vào file cấu hình."""
        try:
            data = {  # Gom các giá trị cần nhớ.
                "host": self.host_var.get().strip(),
                "port": self.port_var.get().strip(),
                "transport": self.transport_var.get().strip(),
                "start": self.start_var.get().strip(),
                "end": self.end_var.get().strip(),
                "upper_device": self.upper_device_var.get().strip(),
                "lower_device": self.lower_device_var.get().strip(),
            }
            CONFIG_PATH.write_text(  # Ghi ra file (đảm bảo tiếng Việt không lỗi).
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:  # noqa: BLE001
            pass  # Không ghi được (quyền/thư mục) -> bỏ qua, không làm hỏng app.

    # ---- Định kích thước theo màn hình --------------------------------------

    def _fit_to_screen(self) -> None:
        """Mở cửa sổ chiếm phần lớn màn hình, thu nhỏ lại nếu màn hình bé."""
        self.update_idletasks()  # Cập nhật hình học để đọc được kích thước màn hình.
        sw = self.winfo_screenwidth()   # Chiều rộng màn hình (pixel).
        sh = self.winfo_screenheight()  # Chiều cao màn hình (pixel).
        w = min(1600, max(760, int(sw * 0.92)))  # Rộng ~92% màn hình, trong khoảng 760..1600.
        h = min(1000, max(520, int(sh * 0.88)))  # Cao ~88% màn hình, trong khoảng 520..1000.
        x = max(0, (sw - w) // 2)  # Căn giữa theo chiều ngang.
        y = max(0, (sh - h) // 2)  # Căn giữa theo chiều dọc.
        self.geometry(f"{w}x{h}+{x}+{y}")  # Áp vị trí + kích thước cho cửa sổ.
        self.minsize(min(720, sw), min(480, sh))  # Kích thước tối thiểu (không co nhỏ hơn).

    # ---- Xây dựng giao diện -------------------------------------------------

    def _build_controls(self) -> None:
        """Dựng thanh điều khiển phía trên (các ô nhập + nút)."""
        top = ttk.Frame(self, padding=8)  # Khung chứa toàn bộ thanh điều khiển.
        top.pack(fill="x")                # Khung chiếm hết chiều ngang cửa sổ.
        flow = FlowFrame(top)             # Khung "tự xuống dòng" chứa các ô nhập.
        flow.pack(fill="x")               # Cũng chiếm hết chiều ngang.

        # Các biến lưu giá trị người dùng nhập (gắn với ô nhập).
        cfg = self._load_config()  # Đọc cấu hình đã lưu (nếu có) để nhớ IP gần nhất.
        self.host_var = tk.StringVar(value=cfg.get("host", "192.168.100.200"))  # Địa chỉ IP PLC.
        self.port_var = tk.StringVar(value=cfg.get("port", "8501"))             # Cổng kết nối.
        self.transport_var = tk.StringVar(value=cfg.get("transport", "tcp"))    # Giao thức tcp/udp.
        self.start_var = tk.StringVar(value=cfg.get("start", "10000"))          # Địa chỉ ZF bắt đầu.
        self.end_var = tk.StringVar(value=cfg.get("end", "16000"))              # Địa chỉ ZF kết thúc.
        self.upper_var = tk.StringVar(value="140")             # Giá trị biên trên (cập nhật từ PLC khi đọc).
        self.lower_var = tk.StringVar(value="120")             # Giá trị biên dưới (cập nhật từ PLC khi đọc).
        self.upper_device_var = tk.StringVar(value=cfg.get("upper_device", ""))  # Biến word chứa biên trên (ZF/DM/EM...).
        self.lower_device_var = tk.StringVar(value=cfg.get("lower_device", ""))  # Biến word chứa biên dưới (ZF/DM/EM...).
        self.metrics_var = tk.StringVar(value="OK: -  Slow: -  Fast: -")  # Dòng tổng kết tỷ lệ.
        self.status_var = tk.StringVar(value="Sẵn sàng.")      # Dòng trạng thái.

        def field(label: str, var: tk.StringVar, width: int) -> ttk.Frame:
            """Tạo một nhóm gồm nhãn + ô nhập, trả về khung chứa chúng."""
            box = ttk.Frame(flow)                              # Khung nhỏ chứa 1 cặp nhãn + ô.
            ttk.Label(box, text=label).pack(side="left")       # Nhãn nằm bên trái.
            ttk.Entry(box, textvariable=var, width=width).pack(side="left", padx=(4, 0))  # Ô nhập kế bên.
            return box  # Trả khung nhỏ để FlowFrame sắp xếp.

        flow.add(field("Host:", self.host_var, 18))  # Ô nhập địa chỉ Host.
        flow.add(field("Port:", self.port_var, 8))   # Ô nhập cổng.

        transport_box = ttk.Frame(flow)  # Nhóm riêng cho "Transport" (dùng Combobox chọn tcp/udp).
        ttk.Label(transport_box, text="Transport:").pack(side="left")  # Nhãn.
        ttk.Combobox(
            transport_box, textvariable=self.transport_var, values=["tcp", "udp"], width=7
        ).pack(side="left", padx=(4, 0))  # Combobox thả xuống chọn giao thức.
        flow.add(transport_box)  # Thêm nhóm Transport vào dòng.

        flow.add(field("ZF từ:", self.start_var, 7))      # Địa chỉ ZF bắt đầu.
        flow.add(field("ZF đến:", self.end_var, 7))       # Địa chỉ ZF kết thúc.
        flow.add(field("Biên trên (word):", self.upper_device_var, 10))  # Biến word chứa biên trên (ZF/DM/EM...).
        flow.add(field("Biên dưới (word):", self.lower_device_var, 10))  # Biến word chứa biên dưới (ZF/DM/EM...).

        self.update_btn = ttk.Button(flow, text="Đọc & cập nhật PLC", command=self.start_update)  # Nút đọc 1 lần.
        flow.add(self.update_btn)  # Thêm nút vào dòng.
        self.auto_btn = ttk.Button(flow, text="Đọc liên tục (5s)", command=self.toggle_auto)  # Nút bật/tắt đọc liên tục.
        flow.add(self.auto_btn)  # Thêm nút vào dòng.
        self.clear_btn = ttk.Button(flow, text="Xóa tất cả", command=self.delete_all)  # Nút xóa toàn bộ dải ZF.
        flow.add(self.clear_btn)  # Thêm nút vào dòng.
        self.advise_btn = ttk.Button(flow, text="AI tư vấn", command=self.advise)  # Nút tư vấn góc cần chỉnh.
        flow.add(self.advise_btn)  # Thêm nút vào dòng.
        flow.add(ttk.Label(flow, textvariable=self.metrics_var))  # Nhãn hiển thị tỷ lệ OK/Slow/Fast.
        flow.add(ttk.Label(flow, textvariable=self.status_var))   # Nhãn hiển thị trạng thái.

    def _build_layout(self) -> None:
        """Dựng vùng chính: biểu đồ (trái) + bảng tỷ lệ (phải)."""
        self.fig, self.axes = plt.subplots(4, 3, figsize=(14, 9))  # Tạo lưới 4x3 = 12 biểu đồ con.
        self.fig.tight_layout(rect=LAYOUT_RECT)  # Nén bố cục (chừa chỗ tiêu đề + chú thích màu).

        paned = ttk.PanedWindow(self, orient="horizontal")  # Khung chia đôi (trái/phải) kéo được.
        paned.pack(fill="both", expand=True)                # Khung lấp đầy phần còn lại của cửa sổ.

        left = ttk.Frame(paned)       # Vùng bên trái chứa biểu đồ.
        paned.add(left, weight=3)     # Trái chiếm tỷ lệ 3 (co giãn mạnh hơn).
        self.canvas = FigureCanvasTkAgg(self.fig, master=left)  # Nhúng figure matplotlib vào Tkinter.
        canvas_widget = self.canvas.get_tk_widget()  # Lấy widget Tk tương ứng của canvas.
        canvas_widget.pack(fill="both", expand=True)  # Widget lấp đầy vùng trái.
        canvas_widget.bind("<Configure>", self._on_resize)  # Khi vùng trái đổi kích thước -> vẽ lại.

        right = ttk.Frame(paned)  # Vùng bên phải chứa bảng.
        paned.add(right, weight=1)  # Phải chiếm tỷ lệ 1.
        self._build_offset_panel(right)  # Panel hiển thị các giá trị offset (địa chỉ gián tiếp).
        ttk.Label(right, text="Tỷ lệ theo góc quay", font=("Segoe UI", 10, "bold")).pack(
            anchor="w", padx=4, pady=(4, 0)  # Tiêu đề của bảng.
        )
        self._build_table(right)  # Dựng bảng tỷ lệ bên trong vùng phải.

    def _build_offset_panel(self, parent: tk.Widget) -> None:
        """Panel hiển thị + sửa + ghi các giá trị offset (địa chỉ gián tiếp DMxxxx + EM120)."""
        panel = ttk.LabelFrame(parent, text="Offset chỉnh (gián tiếp EM120)", padding=4)
        panel.pack(fill="x", padx=4, pady=(4, 0))

        self.offset_index_var = tk.StringVar(value="EM120 = -")  # Hiển thị giá trị EM120.
        self.offset_vars = {key: tk.StringVar(value="") for key, _l, _b in OFFSET_READ_ITEMS}  # Ô giá trị (sửa được).
        self.offset_label_vars = {key: tk.StringVar(value=label + ":") for key, label, _b in OFFSET_READ_ITEMS}  # Nhãn + địa chỉ.
        self.offset_bases = {key: base for key, _l, base in OFFSET_READ_ITEMS}  # Địa chỉ DM gốc (để cộng EM120).
        self.offset_labels = {key: label for key, label, _b in OFFSET_READ_ITEMS}  # Tên hiển thị.

        ttk.Label(panel, textvariable=self.offset_index_var).grid(row=0, column=0, columnspan=4, sticky="w")

        items = list(OFFSET_READ_ITEMS)
        half = (len(items) + 1) // 2  # Số dòng mỗi cột (chia đôi danh sách).
        for i, (key, _label, _base) in enumerate(items):
            col = 0 if i < half else 2  # Nửa đầu -> cột trái, nửa sau -> cột phải.
            row = (i % half) + 1        # Hàng tương ứng trong mỗi cột.
            color = COL_LOWER if "fast" in key else COL_UPPER  # fast -> cam, slow -> tím.
            tk.Label(panel, textvariable=self.offset_label_vars[key], fg=color).grid(  # Nhãn màu theo loại.
                row=row, column=col, sticky="w", padx=(0, 4)
            )
            ttk.Entry(panel, textvariable=self.offset_vars[key], width=9, justify="right").grid(
                row=row, column=col + 1, sticky="e", padx=(0, 12)
            )
        panel.columnconfigure(1, weight=1)
        panel.columnconfigure(3, weight=1)

        # Nút ghi các giá trị đã sửa xuống PLC.
        self.write_btn = ttk.Button(panel, text="Ghi offset vào PLC", command=self.start_write_offsets)
        self.write_btn.grid(row=half + 1, column=0, columnspan=4, sticky="ew", pady=(6, 0))

    def _build_table(self, parent: tk.Widget) -> None:
        """Dựng bảng có thanh cuộn dọc + ngang bên trong vùng cha."""
        container = tk.Frame(parent)  # Khung chứa canvas + thanh cuộn.
        container.pack(fill="both", expand=True, padx=4, pady=4)

        self.table_canvas = tk.Canvas(container, highlightthickness=0)  # Canvas để cuộn nội dung bảng.
        self.table_vscroll = ttk.Scrollbar(container, orient="vertical", command=self.table_canvas.yview)  # Thanh cuộn dọc.
        self.table_hscroll = ttk.Scrollbar(container, orient="horizontal", command=self.table_canvas.xview)  # Thanh cuộn ngang.
        self.table_inner = tk.Frame(self.table_canvas)  # Khung con nằm trong canvas (chứa các ô bảng).
        self.table_inner.bind("<Configure>", self._on_table_configure)  # Khi khung con đổi kích thước -> cập nhật vùng cuộn.

        self._table_window = self.table_canvas.create_window((0, 0), window=self.table_inner, anchor="nw")  # Đặt khung con vào canvas.
        self.table_canvas.bind("<Configure>", self._on_table_canvas_configure)  # Khi canvas đổi kích thước -> co giãn bảng.
        self.table_canvas.configure(
            yscrollcommand=self.table_vscroll.set, xscrollcommand=self.table_hscroll.set  # Nối canvas với 2 thanh cuộn.
        )

        # Sắp xếp canvas và 2 thanh cuộn theo lưới:
        self.table_canvas.grid(row=0, column=0, sticky="nsew")   # Canvas ở góc trên-trái.
        self.table_vscroll.grid(row=0, column=1, sticky="ns")     # Thanh cuộn dọc bên phải.
        self.table_hscroll.grid(row=1, column=0, sticky="ew")     # Thanh cuộn ngang phía dưới.
        container.rowconfigure(0, weight=1)     # Hàng 0 co giãn theo chiều dọc.
        container.columnconfigure(0, weight=1)  # Cột 0 co giãn theo chiều ngang.

        for j in range(6):  # 6 cột dữ liệu (Góc, Góc sau offset, Số mẫu, OK%, Slow%, Fast%).
            self.table_inner.columnconfigure(j, weight=1, minsize=64)
        self.table_inner.columnconfigure(6, weight=0, minsize=44)  # Cột nút "Xóa".  # Mỗi cột rộng tối thiểu 64px.

    # ---- Điều chỉnh khi thay đổi kích thước ----------------------------------

    def _on_resize(self, _event=None) -> None:
        """Vẽ lại biểu đồ sau khi cửa sổ đổi kích thước (debounce 120ms)."""
        if self._resize_job is not None:      # Nếu có job cũ đang chờ.
            self.after_cancel(self._resize_job)  # Hủy job cũ.
        self._resize_job = self.after(120, self._relayout_figure)  # Lên lịch vẽ lại sau 120ms.

    def _relayout_figure(self) -> None:
        self._resize_job = None  # Job đã chạy -> xóa tham chiếu.
        try:
            self.fig.tight_layout(rect=LAYOUT_RECT)  # Tính lại bố cục biểu đồ theo kích thước mới.
        except Exception:  # noqa: BLE001 - kích thước 0 khi cửa sổ đang thu nhỏ
            pass  # Bỏ qua lỗi khi cửa sổ quá nhỏ.
        self.canvas.draw_idle()  # Yêu cầu vẽ lại khi hệ thống rảnh.

    def _on_table_canvas_configure(self, event) -> None:
        """Bảng co giãn theo chiều rộng canvas (nếu đủ chỗ), nếu hẹp thì cuộn ngang."""
        width = max(event.width, self.table_inner.winfo_reqwidth())  # Lấy chiều rộng cần thiết (tối thiểu bằng nội dung).
        self.table_canvas.itemconfigure(self._table_window, width=width)  # Áp chiều rộng cho khung con trong canvas.
        self._on_table_configure()  # Cập nhật vùng cuộn.

    def _on_table_configure(self, _event=None) -> None:
        self.table_canvas.configure(scrollregion=self.table_canvas.bbox("all"))  # Cập nhật phạm vi cuộn theo nội dung.

    # ---- Đọc PLC (luồng riêng) ---------------------------------------------

    def start_update(self) -> None:
        """Khi bấm nút 'Đọc & cập nhật PLC': đọc 1 lần."""
        self._read_once()

    def _read_once(self) -> None:
        """Bắt đầu 1 lần đọc PLC ở luồng nền (bỏ qua nếu đang đọc dở)."""
        if self._reading:  # Đang đọc dở -> không chồng lặp.
            return
        self._reading = True  # Đánh dấu đang đọc.
        self.update_btn.config(state="disabled")  # Vô hiệu nút để tránh bấm nhiều lần.
        self.status_var.set("Đang đọc PLC...")    # Báo trạng thái đang đọc.
        threading.Thread(target=self._update_worker, daemon=True).start()  # Chạy đọc PLC ở luồng nền.

    def toggle_auto(self) -> None:
        """Bật/tắt chế độ đọc liên tục mỗi 5 giây."""
        if self.auto_running:  # Đang bật -> tắt.
            self.auto_running = False
            if self._auto_job is not None:  # Hủy job đọc kế tiếp đang chờ.
                try:
                    self.after_cancel(self._auto_job)
                except Exception:  # noqa: BLE001
                    pass
                self._auto_job = None
            self.auto_btn.config(text="Đọc liên tục (5s)")  # Đổi lại nhãn nút.
            self.update_btn.config(state="normal")  # Bật lại nút đọc 1 lần.
            self.status_var.set("Đã dừng đọc liên tục.")
        else:  # Đang tắt -> bật.
            self.auto_running = True
            self.auto_btn.config(text="Dừng đọc liên tục")  # Đổi nhãn nút.
            self.update_btn.config(state="disabled")  # Tắt nút đọc 1 lần khi đang chạy liên tục.
            self._read_once()  # Đọc ngay lần đầu tiên.

    def _auto_tick(self) -> None:
        """Một mốc trong chu kỳ đọc liên tục (chạy sau khi lần trước kết thúc)."""
        self._auto_job = None  # Job đã chạy -> xóa tham chiếu.
        if not self.auto_running:  # Đã tắt chế độ -> dừng.
            return
        self._read_once()  # Đọc tiếp 1 lần.

    def _parse_device(self, var: tk.StringVar) -> str | None:
        """Trả về tên biến word (vd 'DM500', 'EM100', 'ZF20000') hoặc None nếu ô trống."""
        text = var.get().strip().upper()  # Bỏ khoảng trắng, viết hoa (thư viện tự phân biệt hoa/thường).
        return text or None

    def _update_worker(self) -> None:
        """Hàm chạy trong luồng riêng: đọc PLC (dữ liệu + biên + offset) và báo kết quả về giao diện."""
        try:
            async def _run() -> tuple[int | None, int | None, int, dict[str, int | None]]:
                await read_zf_values(  # Đọc dữ liệu ZF và lưu CSV.
                    self.host_var.get().strip(), int(self.port_var.get().strip()),  # Host, port (bỏ khoảng trắng).
                    self.transport_var.get().strip(), 3.0, self.base_dir / "zf_values.csv",  # Giao thức, timeout, file lưu.
                    start=int(self.start_var.get()), end=int(self.end_var.get()),  # Khoảng địa chỉ ZF.
                )
                # Đọc giá trị biên tại 2 biến word (nếu người dùng có khai báo).
                upper, lower = await read_bounds(
                    self.host_var.get().strip(), int(self.port_var.get().strip()),
                    self.transport_var.get().strip(), 3.0,
                    upper_device=self._parse_device(self.upper_device_var),
                    lower_device=self._parse_device(self.lower_device_var),
                )
                # Đọc 5 giá trị offset theo địa chỉ gián tiếp DMxxxx + EM120.
                offset, offsets = await read_offsets(
                    self.host_var.get().strip(), int(self.port_var.get().strip()),
                    self.transport_var.get().strip(), 3.0,
                )
                return upper, lower, offset, offsets

            upper, lower, offset, offsets = asyncio.run(_run())  # Chạy đến khi đọc xong.
            self.after(0, lambda: self._finish_update(True, "Cập nhật thành công.", upper, lower, offset, offsets))
        except Exception as exc:  # noqa: BLE001
            message = str(exc)  # Lấy nội dung lỗi.
            self.after(0, lambda: self._finish_update(False, message))  # Báo lỗi về giao diện.

    def _finish_update(
        self,
        ok: bool,
        message: str,
        upper: int | None = None,
        lower: int | None = None,
        offset: int | None = None,
        offsets: dict[str, int | None] | None = None,
    ) -> None:
        self._reading = False  # Hết 1 lần đọc.
        self.status_var.set(("OK: " if ok else "LỖI: ") + (message.splitlines()[-1] if message else ""))  # Hiện trạng thái.
        if ok:
            if upper is not None:  # Nếu đọc được biên trên từ PLC -> cập nhật vào ô biên.
                self.upper_var.set(str(upper))
            if lower is not None:  # Nếu đọc được biên dưới từ PLC -> cập nhật vào ô biên.
                self.lower_var.set(str(lower))
            if offset is not None and offsets is not None:  # Nếu đọc được offset -> cập nhật panel.
                self._offset_value = offset  # Nhớ EM120 để dùng khi ghi.
                self.offset_index_var.set(f"EM120 = {offset}")
                for key, var in self.offset_vars.items():
                    value = offsets.get(key)
                    base = self.offset_bases.get(key, 0)
                    label = self.offset_labels.get(key, key)
                    self.offset_label_vars[key].set(f"{label}: DM{base + offset}")  # Nhãn kèm địa chỉ thực.
                    var.set(str(value) if value is not None else "")  # Điền giá trị đọc được vào ô.
            self.refresh_plots()  # Đọc xong thì vẽ lại biểu đồ + bảng.
            self._save_config()  # Đọc thành công -> nhớ IP/cấu hình gần nhất.
        if self.auto_running:  # Đang chạy liên tục -> lên lịch đọc tiếp sau 5 giây.
            self._auto_job = self.after(AUTO_INTERVAL_MS, self._auto_tick)
        else:  # Chế độ đọc 1 lần -> bật lại nút đọc.
            self.update_btn.config(state="normal")

    # ---- Ghi offset đã sửa xuống PLC ----------------------------------------

    def start_write_offsets(self) -> None:
        """Đọc các ô giá trị, kiểm tra rồi ghi xuống PLC (địa chỉ DM{base}+EM120)."""
        if self._writing:  # Đang ghi dở -> bỏ qua.
            return
        if self._offset_value is None:  # Chưa đọc offset -> chưa biết địa chỉ.
            self.status_var.set("LỖI: Chưa đọc offset (EM120). Hãy bấm đọc PLC trước.")
            return

        values: dict[str, int] = {}
        for key, var in self.offset_vars.items():  # Gom các giá trị đã nhập.
            text = var.get().strip()
            if text == "" or text == "-":  # Ô trống -> bỏ qua (không ghi).
                continue
            try:
                values[key] = int(text)
            except ValueError:
                self.status_var.set(f"LỖI: Giá trị '{self.offset_labels.get(key, key)}' không phải số nguyên.")
                return
        for key, value in values.items():  # Kiểm tra khoảng S-int32.
            if not -0x80000000 <= value <= 0x7FFFFFFF:
                self.status_var.set(f"LỖI: Giá trị '{self.offset_labels.get(key, key)}' ngoài khoảng S-int32.")
                return
        if not values:  # Không có giá trị nào để ghi.
            self.status_var.set("Không có giá trị nào để ghi.")
            return

        self._writing = True
        self.write_btn.config(state="disabled")
        self.status_var.set("Đang ghi offset...")
        threading.Thread(target=self._write_worker, args=(self._offset_value, values), daemon=True).start()

    def _write_worker(self, offset: int, values: dict[str, int]) -> None:
        """Chạy ghi offset ở luồng nền để giao diện không bị đứng."""
        try:
            asyncio.run(
                write_offsets(
                    self.host_var.get().strip(), int(self.port_var.get().strip()),
                    self.transport_var.get().strip(), 3.0, offset, values,
                )
            )
            self.after(0, lambda: self._finish_write(True, "Ghi offset thành công."))
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            self.after(0, lambda: self._finish_write(False, message))

    def _finish_write(self, ok: bool, message: str) -> None:
        self._writing = False  # Hết 1 lần ghi.
        self.write_btn.config(state="normal")  # Bật lại nút ghi.
        self.status_var.set(("OK: " if ok else "LỖI: ") + (message.splitlines()[-1] if message else ""))

    # ---- Vẽ lại biểu đồ + bảng ---------------------------------------------

    def _bounds(self) -> tuple[float | None, float | None]:
        """Đọc giá trị biên trên/dưới (trả None nếu người dùng nhập không phải số)."""
        try:
            return float(self.upper_var.get()), float(self.lower_var.get())  # Chuyển chuỗi sang số.
        except ValueError:
            return None, None  # Nhập sai -> không có biên hợp lệ.

    def _angle_files(self) -> list[Path]:
        """Liệt kê các file CSV theo góc quay (goc_*.csv) theo thứ tự tên."""
        return sorted(self.angle_dir.glob("goc_*.csv")) if self.angle_dir.exists() else []

    def _corrected_angle(self, angle: float) -> float | None:
        """Góc sau khi trừ offset: góc âm dùng 'all fast', góc dương dùng 'all slow' (offset đơn vị /100)."""
        if angle < 0:
            key = "all_fast"
        elif angle > 0:
            key = "all_slow"
        else:
            return float(angle)  # Góc 0 -> không trừ offset.
        try:
            offset = float(self.offset_vars[key].get())
        except (KeyError, ValueError):
            return None  # Chưa có offset hợp lệ -> không tính được.
        return float(angle) - offset / 100.0

    def refresh_plots(self) -> None:
        """Vẽ lại toàn bộ 12 biểu đồ con + cập nhật số liệu + bảng."""
        upper, lower = self._bounds()  # Lấy biên trên/dưới.
        files = self._angle_files()    # Danh sách file theo góc.
        self._angle_to_ax = {}         # Ánh xạ góc -> biểu đồ con (để tô đậm khi chọn).

        for ax in self.axes.flat:  # Duyệt toàn bộ 12 biểu đồ con.
            ax.clear()              # Xóa nội dung cũ.
            ax.set_visible(False)   # Ẩn tạm (chỉ bật cho biểu đồ có dữ liệu).

        for ax, path in zip(self.axes.flat, files):  # Ghép từng biểu đồ với từng file.
            try:
                values = _load(path)  # Đọc CSV.
                before, angle, after = values[:, 0], values[:, 1], values[:, 2]  # Tách 3 cột.
            except Exception:  # noqa: BLE001
                continue  # File lỗi -> bỏ qua.
            ax.set_visible(True)  # Bật biểu đồ con này.
            idx = np.arange(before.size)  # Trục x = chỉ số mẫu 0,1,2,...
            ax.plot(idx, before, color=COL_BEFORE, lw=1.0, marker="o", ms=3)  # Vẽ đường + chấm "trước".
            ax.plot(idx, after, color=COL_AFTER, lw=1.0, marker="o", ms=3)    # Vẽ đường + chấm "sau".
            if upper is not None:
                ax.axhline(upper, color=COL_UPPER, linestyle="--", linewidth=1.2)  # Vẽ đường biên trên (nét đứt).
            if lower is not None:
                ax.axhline(lower, color=COL_LOWER, linestyle=":", linewidth=1.2)   # Vẽ đường biên dưới (nét chấm).
            if upper is not None and lower is not None:
                ax.axhline((upper + lower) / 2.0, color=COL_CENTER, linewidth=1.5)  # Vẽ đường trung tâm.
            raw_angle = int(angle[0]) if angle.size else 0  # Góc gốc trong dải ZF.
            self._angle_to_ax[raw_angle] = ax  # Ghi nhớ biểu đồ con theo góc.
            corrected = self._corrected_angle(raw_angle)    # Góc sau khi trừ offset.
            if corrected is None:
                ax.set_title(f"Góc {raw_angle} (n={before.size})", fontsize=9)
            else:
                ax.set_title(f"Góc {raw_angle} → {corrected:.2f} (n={before.size})", fontsize=9)  # Tiêu đề biểu đồ con.
            ax.set_xlabel("Mẫu", fontsize=8)  # Nhãn trục x.
            ax.set_ylabel("s", fontsize=8)    # Nhãn trục y (giây).
            ax.grid(alpha=0.3)                # Lưới mờ.
            ax.tick_params(labelsize=8)       # Cỡ chữ số trên trục.

        self._apply_selection_highlight()       # Tô đậm biểu đồ của góc đang chọn.
        self._refresh_metrics(upper, lower)     # Cập nhật dòng tổng kết OK/Slow/Fast.
        self._refresh_table(upper, lower, files)  # Cập nhật bảng tỷ lệ theo góc.

        self._add_legend()  # Thêm chú thích màu cho các đường vẽ.

        self.fig.suptitle("Biểu đồ theo từng góc quay", fontsize=14, fontweight="bold")  # Tiêu đề lớn.
        self.fig.tight_layout(rect=LAYOUT_RECT)  # Nén lại bố cục.
        self.canvas.draw()  # Vẽ ngay lên màn hình.

    def _apply_selection_highlight(self) -> None:
        """Tô đậm viền biểu đồ con của góc đang được chọn."""
        sel = self.selected_angle
        for angle_value, ax in self._angle_to_ax.items():
            selected = sel is not None and angle_value == sel
            color = "#d32f2f" if selected else "#888888"  # Đỏ đậm khi chọn, xám nhạt khi không.
            width = 2.5 if selected else 1.0
            for spine in ax.spines.values():
                spine.set_color(color)
                spine.set_linewidth(width)

    def _add_legend(self) -> None:
        """Thêm 1 chú thích màu chung cho biết mỗi đường vẽ tượng trưng cho gì."""
        handles = [  # Danh sách (mẫu đường + nhãn) cho chú thích.
            Line2D([0], [0], color=COL_BEFORE, lw=1.5, label="Trước khi chỉnh"),
            Line2D([0], [0], color=COL_AFTER, lw=1.5, label="Sau khi chỉnh"),
            Line2D([0], [0], color=COL_UPPER, lw=1.2, linestyle="--", label="Biên trên"),
            Line2D([0], [0], color=COL_LOWER, lw=1.2, linestyle=":", label="Biên dưới"),
            Line2D([0], [0], color=COL_CENTER, lw=1.5, label="Trung tâm (giữa 2 biên)"),
        ]
        for leg in list(self.fig.legends):  # Xóa chú thích cũ (nếu có) để không bị chồng.
            leg.remove()
        self.fig.legend(  # Đặt chú thích ở giữa, phía dưới biểu đồ, xếp 1 hàng.
            handles=handles, loc="lower center", bbox_to_anchor=(0.5, 0.0),
            ncol=5, fontsize=8, frameon=False,
        )

    def _refresh_metrics(self, upper: float | None, lower: float | None) -> None:
        """Tính và hiển thị tỷ lệ OK/Slow/Fast trên toàn bộ dữ liệu."""
        try:
            after = _load(self.base_dir / "zf_values.csv")[:, 2]  # Lấy cột "sau khi chỉnh".
            if upper is not None and lower is not None:  # Chỉ khi có đủ 2 biên hợp lệ.
                ok, slow, fast = _percentages(after, upper, lower)  # Tính %.
                self.metrics_var.set(  # Hiện lên nhãn.
                    f"OK (trong 2 biên): {ok:.1f}%   Slow (trên biên trên): {slow:.1f}%   "
                    f"Fast (dưới biên dưới): {fast:.1f}%"
                )
                return
        except Exception:  # noqa: BLE001
            pass  # Không đọc được file hoặc lỗi -> hiện dấu gạch ngang.
        self.metrics_var.set("OK: -  Slow: -  Fast: -")

    def _refresh_table(self, upper: float | None, lower: float | None, files: list[Path]) -> None:
        """Dựng lại bảng tỷ lệ theo từng góc quay."""
        for child in self.table_inner.winfo_children():
            child.destroy()  # Xóa toàn bộ ô cũ trong bảng.

        for j, text in enumerate(["Góc", "Góc sau offset", "Số mẫu", "OK %", "Slow %", "Fast %"]):  # Dòng tiêu đề bảng.
            tk.Label(
                self.table_inner, text=text, relief="solid", borderwidth=1,
                bg="#d9d9d9", font=("Segoe UI", 9, "bold"),
            ).grid(row=0, column=j, sticky="nsew")  # Đặt tiêu đề ở hàng 0.
        tk.Label(  # Cột tiêu đề cho nút xóa.
            self.table_inner, text="", relief="solid", borderwidth=1, bg="#d9d9d9",
        ).grid(row=0, column=6, sticky="nsew")

        if upper is None or lower is None:  # Không có biên -> không có dữ liệu %, dừng ở tiêu đề.
            return

        row_idx = 1  # Bắt đầu ghi dữ liệu từ hàng 1 (hàng 0 là tiêu đề).
        for path in files:  # Duyệt từng file theo góc.
            try:
                values = _load(path)  # Đọc CSV.
                after = values[:, 2]  # Cột "sau".
                if after.size == 0:   # Không có mẫu -> bỏ qua.
                    continue
                ok, slow, fast = _percentages(after, upper, lower)  # Tính %.
                angle_value = int(values[0, 1])  # Góc quay (giá trị cột 2 của dòng đầu).
            except Exception:  # noqa: BLE001
                continue  # Lỗi -> bỏ qua dòng này.
            corrected = self._corrected_angle(angle_value)  # Góc sau khi trừ offset.
            corrected_text = "-" if corrected is None else f"{corrected:.2f}"
            selected_bg = "#ffe0b2" if self.selected_angle == angle_value else "#ffffff"  # Nền khi dòng được chọn.
            cells = [  # Danh sách các ô trong 1 hàng: (nội dung, màu nền, màu chữ).
                (str(angle_value), selected_bg, "#000000"),
                (corrected_text, selected_bg, "#000000"),
                (str(after.size), "#000000", "#ffffff"),
                (f"{ok:.1f}", COL_CENTER, "#ffffff"),
                (f"{slow:.1f}", COL_UPPER, "#ffffff"),
                (f"{fast:.1f}", COL_LOWER, "#ffffff"),
            ]
            for j, (text, bg, fg) in enumerate(cells):  # Vẽ từng ô.
                lbl = tk.Label(
                    self.table_inner, text=text, relief="solid", borderwidth=1,
                    bg=bg, fg=fg, font=("Segoe UI", 9), cursor="hand2",
                )
                lbl.grid(row=row_idx, column=j, sticky="nsew")  # Đặt ô vào đúng hàng/cột.
                if j in (0, 1):  # Bấm vào ô "Góc"/"Góc sau offset" -> chọn biểu đồ tương ứng.
                    lbl.bind("<Button-1>", lambda e, a=angle_value: self.select_angle(a))
            # Nút xóa góc này (ghi 0 xuống PLC).
            ttk.Button(
                self.table_inner, text="Xóa", width=5,
                command=lambda a=angle_value: self.delete_angle(a),
            ).grid(row=row_idx, column=6, sticky="nsew", padx=1, pady=1)
            row_idx += 1  # Sang hàng kế tiếp.

    def select_angle(self, angle: int) -> None:
        """Chọn 1 góc (từ bảng) -> tô đậm biểu đồ con tương ứng."""
        self.selected_angle = angle
        self.after(0, self.refresh_plots)  # Vẽ lại (hoãn để tránh destroy widget đang xử lý sự kiện).

    # ---- Xoá 1 góc (ghi 0 xuống PLC) ---------------------------------------

    def delete_angle(self, angle: int) -> None:
        """Xác nhận rồi ghi 0 xuống các nhóm ZF của góc này trên PLC."""
        if self._reading or self._writing:  # Đang đọc/ghi dở -> bỏ qua.
            self.status_var.set("Đang bận (đọc/ghi PLC), thử lại sau.")
            return
        if not messagebox.askyesno(  # Hỏi xác nhận trước khi xoá.
            "Xác nhận xoá",
            f"Xoá toàn bộ dữ liệu góc {angle} trên PLC (ghi 0 vào các địa chỉ ZF)?",
        ):
            return  # Người dùng bấm "Không".

        self.status_var.set(f"Đang xoá góc {angle} trên PLC...")
        threading.Thread(target=self._delete_worker, args=(angle,), daemon=True).start()

    def _delete_worker(self, angle: int) -> None:
        """Chạy xoá góc ở luồng nền (ghi 0 xuống PLC) rồi cập nhật dữ liệu cục bộ."""
        try:
            cleared = asyncio.run(
                clear_angle(
                    self.host_var.get().strip(), int(self.port_var.get().strip()),
                    self.transport_var.get().strip(), 3.0,
                    int(self.start_var.get()), int(self.end_var.get()), angle,
                )
            )
            self.after(0, lambda: self._finish_delete(angle, cleared))
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            self.after(0, lambda: self._finish_delete(angle, 0, False, message))

    def _finish_delete(self, angle: int, cleared: int, ok: bool = True, message: str = "") -> None:
        if ok:
            remove_angle_local(self.base_dir / "zf_values.csv", self.angle_dir, angle)  # Cập nhật CSV + xoá file góc.
            self.refresh_plots()  # Vẽ lại biểu đồ + bảng.
            self.status_var.set(f"OK: Đã xoá {cleared} nhóm của góc {angle} trên PLC.")
        else:
            self.status_var.set("LỖI: " + (message.splitlines()[-1] if message else ""))

    # ---- Xoá tất cả dữ liệu trong dải ZF -------------------------------------

    def delete_all(self) -> None:
        """Xác nhận rồi ghi 0 xuống toàn bộ dải ZF đã khai báo trên PLC."""
        if self._reading or self._writing:  # Đang đọc/ghi dở -> bỏ qua.
            self.status_var.set("Đang bận (đọc/ghi PLC), thử lại sau.")
            return
        if not messagebox.askyesno(  # Hỏi xác nhận trước khi xoá.
            "Xác nhận xoá tất cả",
            "Xoá TẤT CẢ dữ liệu trong dải ZF đã khai báo trên PLC (ghi 0 toàn bộ)?",
        ):
            return  # Người dùng bấm "Không".

        self.status_var.set("Đang xoá tất cả dữ liệu trên PLC...")
        threading.Thread(target=self._delete_all_worker, daemon=True).start()

    def _delete_all_worker(self) -> None:
        """Chạy xoá toàn bộ dải ZF ở luồng nền rồi xoá dữ liệu cục bộ."""
        try:
            asyncio.run(
                clear_all(
                    self.host_var.get().strip(), int(self.port_var.get().strip()),
                    self.transport_var.get().strip(), 3.0,
                    int(self.start_var.get()), int(self.end_var.get()),
                )
            )
            self.after(0, lambda: self._finish_delete_all(True, ""))
        except Exception as exc:  # noqa: BLE001
            self.after(0, lambda: self._finish_delete_all(False, str(exc)))

    def _finish_delete_all(self, ok: bool, message: str = "") -> None:
        if ok:
            clear_local(self.base_dir / "zf_values.csv", self.angle_dir)  # Xoá CSV + các file góc.
            self.refresh_plots()  # Vẽ lại (giờ không còn dữ liệu).
            self.status_var.set("OK: Đã xoá tất cả dữ liệu trong dải ZF.")
        else:
            self.status_var.set("LỖI: " + (message.splitlines()[-1] if message else ""))

    # ---- AI tư vấn góc cần chỉnh -------------------------------------------

    def advise(self) -> None:
        """Phân tích dữ liệu và tư vấn góc nên chỉnh để đạt tỷ lệ OK 85%."""
        upper, lower = self._bounds()  # Lấy biên trên/dưới.
        if upper is None or lower is None:
            self._show_advice("AI tư vấn", "Cần đặt biên trên/dưới hợp lệ trước khi tư vấn.")
            return
        files = self._angle_files()  # Danh sách file theo góc.
        if not files:
            self._show_advice("AI tư vấn", "Chưa có dữ liệu. Hãy đọc PLC trước.")
            return

        stats: list[tuple[int, int, int, int, int]] = []  # (góc, tổng, OK, Slow, Fast).
        total_ok = 0
        total_n = 0
        for path in files:  # Gom số liệu từng góc.
            try:
                values = _load(path)
                angle = int(values[0, 1])
                after = values[:, 2]
            except Exception:  # noqa: BLE001
                continue
            n = int(after.size)
            if n == 0:
                continue
            ok = int(np.sum((after >= lower) & (after <= upper)))
            slow = int(np.sum(after > upper))
            fast = int(np.sum(after < lower))
            stats.append((angle, n, ok, slow, fast))
            total_ok += ok
            total_n += n

        if total_n == 0:
            self._show_advice("AI tư vấn", "Không có mẫu nào để phân tích.")
            return

        current_pct = total_ok / total_n * 100.0
        target_ok = math.ceil(0.85 * total_n)  # Số mẫu OK cần để đạt 85%.
        need = max(0, target_ok - total_ok)

        lines = [
            f"Tổng OK hiện tại: {current_pct:.1f}%  ({total_ok}/{total_n} mẫu)",
            f"Mục tiêu: 85%  →  cần {target_ok} mẫu OK",
            "",
        ]
        if need == 0:
            lines.append("Đã đạt mục tiêu 85%. Không cần thay đổi.")
        else:
            lines.append(f"Cần đưa thêm khoảng {need} mẫu vào vùng OK.")
            lines.append("")
            lines.append("Các góc nên ưu tiên chỉnh (nhiều mẫu ngoài biên nhất):")
            lines.append("")
            ranked = sorted(stats, key=lambda s: s[3] + s[4], reverse=True)  # Theo tổng Slow+Fast giảm dần.
            idx = 1
            cum = 0
            for angle, n, ok, slow, fast in ranked:
                out = slow + fast
                if out == 0:
                    continue
                fast_key = f"fast{angle}"
                slow_key = f"slow{angle}"
                if fast >= slow:  # Chủ yếu lệch về fast -> chỉnh offset fast.
                    action = f"chỉnh 'offset fast {angle}'" if fast_key in self.offset_vars else "chỉnh 'offset all fast'"
                else:  # Chủ yếu lệch về slow -> chỉnh offset slow.
                    action = f"chỉnh 'offset slow {angle}'" if slow_key in self.offset_vars else "chỉnh 'offset all slow'"
                lines.append(f"{idx}. Góc {angle}: {n} mẫu (OK {ok}, Slow {slow}, Fast {fast}) → {action}")
                idx += 1
                cum += out
                if cum >= need:  # Đủ số mẫu cần bù thì dừng gợi ý.
                    break
            lines.append("")
            lines.append("Gợi ý: chỉnh từ góc đầu tiên, sau đó đọc lại và bấm 'AI tư vấn' để kiểm tra tiến độ.")

        self._show_advice("AI tư vấn góc cần chỉnh", "\n".join(lines))

    def _show_advice(self, title: str, text: str) -> None:
        """Hiển thị kết quả tư vấn trong cửa sổ có thanh cuộn."""
        win = tk.Toplevel(self)
        win.title(title)
        win.geometry("560x420")
        win.transient(self)  # Cửa sổ phụ (luôn nằm trên cửa sổ chính).

        body = tk.Text(win, wrap="word", font=("Segoe UI", 10), padx=12, pady=12)
        scroll = ttk.Scrollbar(win, orient="vertical", command=body.yview)
        body.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        body.pack(side="left", fill="both", expand=True)

        body.insert("1.0", text)
        body.configure(state="disabled")  # Chỉ đọc.

        ttk.Button(win, text="Đóng", command=win.destroy).pack(side="bottom", pady=8)


if __name__ == "__main__":  # Chỉ chạy khi chạy trực tiếp file này (không phải khi import).
    Dashboard().mainloop()  # Tạo cửa sổ và chạy vòng lặp sự kiện của Tkinter.
