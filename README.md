# Rework Auto — Giao tiếp PLC KEYENCE KV (Host Link)

Đọc dữ liệu ZF10000–ZF16000 từ PLC KEYENCE KV qua Host Link (Upper Link), vẽ biểu đồ và hiển thị dashboard.

## Cài đặt

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Thư viện: [`plc-comm-kv-hostlink`](https://pypi.org/project/plc-comm-kv-hostlink/) (import name `hostlink`), Python >= 3.10.

## Chạy

```powershell
# Đọc dữ liệu ZF, lưu zf_values.csv + phân loại theo góc vào zf_by_angle/
.\.venv\Scripts\python.exe read_data_rework.py

# Vẽ biểu đồ
.\.venv\Scripts\python.exe plot.py values     # 6-panel phân tích tổng
.\.venv\Scripts\python.exe plot.py angles     # vẽ từng góc quay riêng

# Dashboard Tkinter (nút "Đọc & cập nhật PLC")
.\.venv\Scripts\python.exe dashboard_rework.py
```

Địa chỉ PLC mặc định `192.168.100.200:8501`, profile `keyence:kv-8000`. Khoảng đọc mặc định `ZF10000`–`ZF16000`, có thể đổi bằng `--start`/`--end`:

```powershell
.\.venv\Scripts\python.exe read_data_rework.py --start 10000 --end 16000
```

Xem thêm tùy chọn bằng `--help`. Trong dashboard, nhập khoảng đọc vào ô **"ZF từ"** / **"ZF đến"**.

| Script | Kết quả |
| --- | --- |
| `read_data_rework.py` | `zf_values.csv`, `zf_by_angle/goc_*.csv` |
| `plot.py values` | `zf_analysis.png`, `zf_angle_summary.csv` |
| `plot.py angles` | `zf_angle_plots/goc_*.png` |
| `dashboard_rework.py` | Cửa sổ GUI cập nhật trực tiếp |

## Cấu trúc

- `plc_reader.py` — lõi: đọc PLC + lưu CSV + phân loại theo góc
- `common.py` — tiện ích dùng chung (`load_data`, màu, font)
- `read_data_rework.py` — CLI đọc dữ liệu
- `plot.py` — vẽ biểu đồ (2 chế độ)
- `dashboard_rework.py` — GUI Tkinter
- `main.py` — ví dụ đọc/ghi PLC tối thiểu

## Ghi chú

- Cần bật Host Link (Upper Link) trên PLC và mở đúng cổng/port.
- Dữ liệu CSV/ảnh sinh ra khi chạy không được đưa lên Git (xem `.gitignore`).
