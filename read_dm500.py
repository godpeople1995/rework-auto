r"""Đọc giá trị DM500 từ PLC KEYENCE KV-8000 qua KV Host Link.

Cài đặt (đã có sẵn trong .venv):
    python -m pip install plc-comm-kv-hostlink

Chạy:
    .\.venv\Scripts\python.exe read_dm500.py
    .\.venv\Scripts\python.exe read_dm500.py --host 192.168.100.200 --port 8501

Tham số:
    --host       IP của PLC (mặc định 192.168.100.200)
    --port       Cổng Host Link (mặc định 8501)
    --transport  tcp hoặc udp (mặc định tcp)
    --profile    profile PLC (mặc định keyence:kv-8000)
    --device     địa chỉ cần đọc (mặc định DM500)
    --timeout    timeout mỗi request, giây (mặc định 3.0)

Ghi chú: thông báo trên console dùng ASCII (không dấu) để tránh lỗi
UnicodeEncodeError trên Windows console dùng codepage cp1252/cp437.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import struct

import hostlink as hl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Doc DM500 tu PLC KEYENCE KV-8000 (Host Link)")
    parser.add_argument("--host", default="192.168.100.200", help="IP cua PLC")
    parser.add_argument("--port", type=int, default=8501, help="Cong Host Link")
    parser.add_argument("--transport", default="tcp", choices=["tcp", "udp"], help="Giao thuc")
    parser.add_argument(
        "--profile",
        default="keyence:kv-8000",
        choices=hl.available_plc_profiles(),
        help="Profile PLC",
    )
    parser.add_argument("--device", default="DM500", help="Dia chi can doc")
    parser.add_argument("--timeout", type=float, default=3.0, help="Timeout moi request (giay)")
    return parser.parse_args()


def next_device_name(device: str) -> str:
    """DM500 -> DM501 (dung de hien thi word ke tiep)."""
    return re.sub(r"(\d+)$", lambda m: str(int(m.group(1)) + 1), device, count=1)


async def read_and_print(args: argparse.Namespace) -> int:
    options = hl.HostLinkConnectionOptions(
        args.host,
        port=args.port,
        transport=args.transport,
        timeout=args.timeout,
        plc_profile=args.profile,
    )

    print(f"Ket noi {args.transport}://{args.host}:{args.port}  ({args.profile}) ...")
    try:
        client = await hl.open_and_connect(options)
    except Exception as exc:  # noqa: BLE001 - in thong bao than thien cho nguoi dung
        print(f"[LOI] Khong ket noi duoc PLC: {type(exc).__name__}: {exc}")
        print("Kiem tra: IP/port, PLC da bat Host Link chua, firewall, day mang.")
        return 1

    try:
        async with client:
            # --- 1. Doc tho: 1 word (16-bit) tai DM500 ---
            words = await hl.read_words_single_request(client, args.device, 1)
            word = words[0]
            print(f"\n{args.device} (word tho, hex)      : 0x{word:04X}")

            # --- 2. Dien giai cung gia tri theo cac kieu khac nhau ---
            u16 = await hl.read_typed(client, args.device, "U")  # unsigned 16-bit
            s16 = await hl.read_typed(client, args.device, "S")  # signed 16-bit
            print(f"{args.device} (U - uint16)          : {u16}")
            print(f"{args.device} (S - int16)            : {s16}")
            print(f"{args.device} (bit)                  : {word:016b}")

            # --- 3. Doc 2 word lien tiep DM500-DM501 cho kieu 32-bit ---
            two = await hl.read_words_single_request(client, args.device, 2)
            u32 = two[0] | (two[1] << 16)  # little-endian word order
            s32 = struct.unpack("<i", struct.pack("<I", u32))[0]
            f32 = struct.unpack("<f", struct.pack("<I", u32))[0]
            print(f"{args.device}-{next_device_name(args.device)} (D - uint32)          : {u32}")
            print(f"   (L - int32)  : {s32}")
            print(f"   (F - float32): {f32:.6g}")

            return 0
    except hl.HostLinkError as exc:
        print(f"[LOI] PLC tra loi khi doc {args.device}: {type(exc).__name__}: {exc}")
        return 2
    finally:
        await client.close()


def main() -> int:
    return asyncio.run(read_and_print(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
