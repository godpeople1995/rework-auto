r"""Reset (force OFF) bit R100 tren PLC KEYENCE KV qua Host Link.

Chay:
    .\.venv\Scripts\python.exe reset_r100.py
    .\.venv\Scripts\python.exe reset_r100.py --host 192.168.0.5 --port 8501
"""

from __future__ import annotations

import argparse
import asyncio

import hostlink as hl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Force reset bit R100 tren PLC KEYENCE KV")
    parser.add_argument("--host", default="192.168.0.5", help="IP cua PLC")
    parser.add_argument("--port", type=int, default=8501, help="Cong Host Link (mac dinh 8501)")
    parser.add_argument("--transport", default="tcp", choices=["tcp", "udp"], help="Giao thuc")
    parser.add_argument(
        "--profile",
        default="keyence:kv-8000",
        choices=hl.available_plc_profiles(),
        help="Profile PLC",
    )
    parser.add_argument("--timeout", type=float, default=3.0, help="Timeout moi request (giay)")
    parser.add_argument("--device", default="R100", help="Bit can reset (mac dinh R100)")
    return parser.parse_args()


async def main() -> int:
    args = parse_args()

    options = hl.HostLinkConnectionOptions(
        args.host,
        port=args.port,
        transport=args.transport,
        timeout=args.timeout,
        plc_profile=args.profile,
    )

    print(f"Dang ket noi {args.transport}://{args.host}:{args.port} ({args.profile}) ...")
    try:
        client = await hl.open_and_connect(options)
    except Exception as exc:  # noqa: BLE001
        print(f"[LOI] Khong ket noi duoc PLC: {type(exc).__name__}: {exc}")
        print("Kiem tra: IP/port, PLC da bat Host Link chua, firewall, day mang.")
        return 1

    try:
        async with client:
            # Force reset (RS) bit - ghi 0 xuong bit relay R100
            await client.forced_reset(args.device)
            print(f"Da force reset {args.device} = OFF")
            # Doc lai de xac nhan
            val = await hl.read_typed(client, args.device, "BIT")
            print(f"Doc lai {args.device} = {val}")
    except Exception as exc:  # noqa: BLE001
        print(f"[LOI] Khong reset duoc {args.device}: {type(exc).__name__}: {exc}")
        return 1
    finally:
        await client.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))