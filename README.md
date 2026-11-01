# KV HOSTLINK (Python) — KEYENCE KV Host Link

Giao tiếp PLC KEYENCE dòng KV qua Host Link (Upper Link) bằng Python.

## Thông tin thư viện

| Mục | Giá trị |
| --- | --- |
| Tên gói trên PyPI | `plc-comm-kv-hostlink` (bản 4.2.0) |
| Tên cũ (đã đổi tên) | `kv-hostlink` (1.2.1) — không dùng nữa |
| Tên import trong code | `import hostlink` |
| Yêu cầu | Python >= 3.10 |
| Repo | https://github.com/fa-yoshinobu/plc-comm-hostlink-python |
| Tài liệu | https://fa-yoshinobu.github.io/plc-comm-docs-site/hostlink/python/GETTING_STARTED/ |

## Cài đặt

Môi trường ảo đã được tạo sẵn trong `.venv`:

```powershell
# Kích hoạt môi trường (PowerShell)
.\.venv\Scripts\Activate.ps1

# Cài lại / cập nhật thư viện
python -m pip install -r requirements.txt
```

Cài toàn cục (không khuyến nghị):

```powershell
python -m pip install plc-comm-kv-hostlink
```

## Kiểm tra nhanh

```powershell
.\.venv\Scripts\python.exe -c "import hostlink; print(hostlink.__version__)"
```

## Chạy ví dụ

```powershell
# Đọc 10 word từ DM500 của PLC KV-8000 tại 192.168.100.200:8501
.\.venv\Scripts\python.exe main.py --host 192.168.100.200 --port 8501 --profile keyence:kv-8000
```

### Doc ZF10000-ZF16000 theo 3 cot

File `read_zf10000_16000.py` doc moi lan mot nhom 3 word kieu `S` (int16):

```text
ZF10000 | ZF10001 | ZF10002
ZF10003 | ZF10004 | ZF10005
...
```

Chuong trinh dung `numpy` va dung truoc khi in nhom dau tien co ca 3 gia tri bang 0:

```powershell
.\.venv\Scripts\python.exe read_zf10000_16000.py
```

Dia chi mac dinh la `192.168.100.200:8501`, PLC profile `keyence:kv-8000`.

### Vẽ biểu đồ và phân tích

```powershell
.\.venv\Scripts\python.exe plot_zf_values.py
```

Tạo ra:

- `zf_analysis.png` — 6 biểu đồ: chuỗi thời gian trước/sau, góc quay, tương quan góc–trước, góc–sau, chênh lệch, phân bố
- `zf_angle_summary.csv` — bảng trung bình theo từng góc quay

Đơn vị: 2 cột thời gian tính bằng **giây (s)**, góc quay tính bằng **độ (°)**.

Tham số:

- `--host` IP PLC
- `--port` cổng Host Link (mặc định `8501`)
- `--transport` `tcp` hoặc `udp`
- `--profile` profile PLC: `keyence:kv-nano`, `keyence:kv-3000`, `keyence:kv-5000`, `keyence:kv-7000`, `keyence:kv-8000`, `keyence:kv-x500` (thêm hậu tố `-xym` nếu dùng thiết bị X/Y/M)
- `--device`, `--count` địa chỉ bắt đầu và số word cần đọc

## Đoạn code tối thiểu

```python
import asyncio
import hostlink as hl

async def main() -> None:
    options = hl.HostLinkConnectionOptions(
        "192.168.100.200",
        port=8501,
        transport="tcp",
        plc_profile="keyence:kv-8000",
    )
    client = await hl.open_and_connect(options)
    async with client:
        words = await hl.read_words_single_request(client, "DM100", 10)
        print(words)

        await hl.write_words_single_request(client, "DM300", [1234])
        value = await hl.read_typed(client, "DM200", "D")  # uint32
        print(value)

asyncio.run(main())
```

## Kiểu dữ liệu cho `read_typed` / `write_typed`

| Mã | Ý nghĩa |
| --- | --- |
| `U` | unsigned 16-bit |
| `S` | signed 16-bit |
| `D` | unsigned 32-bit |
| `L` | signed 32-bit |
| `F` | float32 |
| `H` | hex 16-bit (chuỗi) |

## Ghi chú

- Địa chỉ dùng dạng `DM100`, `EM100`, `MR100`, `X0`, `Y0`... (không ghép kiểu như `DM100.D` khi dùng helper).
- Cần bật Host Link (Upper Link) trên PLC và mở đúng cổng/port tương ứng.
- File `.vscode/settings.json` đã trỏ interpreter về `.venv` để VS Code tự nhận môi trường.
