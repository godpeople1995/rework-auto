r"""Doc cac gia tri S-int16 tu ZF<start> den ZF<end> theo nhom 3.

Chay:
    .\.venv\Scripts\python.exe read_data_rework.py
    .\.venv\Scripts\python.exe read_data_rework.py --host 192.168.100.200
    .\.venv\Scripts\python.exe read_data_rework.py --start 10000 --end 16000
"""

from __future__ import annotations

import argparse
import asyncio

from plc_reader import read_zf_values


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Doc ZF<start>-ZF<end> kieu S-int16, 3 cot, dung khi gap 3 so 0"
    )
    parser.add_argument("--host", default="192.168.100.200", help="IP cua PLC")
    parser.add_argument("--port", type=int, default=8501, help="Cong Host Link")
    parser.add_argument("--transport", choices=["tcp", "udp"], default="tcp")
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument(
        "--start", type=int, default=10000,
        help="Dia chi ZF bat dau doc (mac dinh 10000)",
    )
    parser.add_argument(
        "--end", type=int, default=16000,
        help="Dia chi ZF ket thuc doc (mac dinh 16000)",
    )
    parser.add_argument(
        "--csv",
        default="zf_values.csv",
        help="Ten file CSV dau ra (mac dinh zf_values.csv)",
    )
    return parser.parse_args()


async def main_async(args: argparse.Namespace) -> int:
    try:
        rows = await read_zf_values(
            args.host, args.port, args.transport, args.timeout, args.csv,
            start=args.start, end=args.end,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[LOI] {type(exc).__name__}: {exc}")
        return 1

    print(f"Da luu {len(rows)} dong vao {args.csv}.")
    print(f"Da phan loai theo goc quay vao zf_by_angle/")
    return 0


def main() -> int:
    return asyncio.run(main_async(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
