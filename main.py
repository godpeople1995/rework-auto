r"""Vi du ket noi PLC KEYENCE KV qua Host Link (Upper Link) bang thu vien hostlink.

Chay:
    .\.venv\Scripts\python.exe main.py --host 192.168.100.200 --port 8501 --profile keyence:kv-8000

Thu vien: plc-comm-kv-hostlink (import name: hostlink)
"""

from __future__ import annotations

import argparse
import asyncio

import hostlink as hl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Doc/ghi thu PLC KEYENCE KV qua Host Link")
    parser.add_argument("--host", default="192.168.100.200", help="IP cua PLC")
    parser.add_argument("--port", type=int, default=8501, help="Cong Host Link (mac dinh 8501)")
    parser.add_argument("--transport", default="tcp", choices=["tcp", "udp"], help="Giao thuc")
    parser.add_argument(
        "--profile",
        default="keyence:kv-8000",
        choices=hl.available_plc_profiles(),
        help="Profile PLC",
    )
    parser.add_argument("--timeout", type=float, default=3.0, help="Timeout moi request (giay)")
    parser.add_argument("--device", default="DM500", help="Dia chi bat dau doc, vi du DM500")
    parser.add_argument("--count", type=int, default=10, help="So word can doc")
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
    except Exception as exc:  # noqa: BLE001 - chi de in thong bao than thien
        print(f"[LOI] Khong ket noi duoc PLC: {type(exc).__name__}: {exc}")
        print("Kiem tra: IP/port, PLC da bat Host Link chua, firewall, day mang.")
        return 1

    try:
        async with client:
            # 1) Doc nhieu word lien tiep trong 1 request
            words = await hl.read_words_single_request(client, args.device, args.count)
            print(f"{args.device} -> {args.count} word: {list(words)}")

            # 2) Doc kieu du lieu co y nghia (U/S/D/L/F/H)
            value = await hl.read_typed(client, "DM200", "D")
            print(f"DM200 (D - uint32) = {value}")

            # 3) Ghi thu 1 word (mo comment neu that su muon ghi xuong PLC)
            # await hl.write_words_single_request(client, "DM300", [1234])
            # print("Da ghi DM300 = 1234")
    finally:
        await client.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
