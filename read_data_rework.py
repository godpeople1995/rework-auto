r"""Doc cac gia tri S-int16 tu ZF10000 den ZF16000 theo nhom 3.

Moi dong gom 3 cot:
    ZF(10000 + 3*n), ZF(10001 + 3*n), ZF(10002 + 3*n)

Chuong trinh dung lai khi mot nhom 3 gia tri lien ke deu bang 0.

Chay:
    .\.venv\Scripts\python.exe read_data_rework.py
    .\.venv\Scripts\python.exe read_data_rework.py --host 192.168.100.200
"""

from __future__ import annotations

import argparse
import asyncio
import csv

import numpy as np
import hostlink as hl


START = 10000
END = 16000
GROUP_SIZE = 3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Doc ZF10000-ZF16000 kieu S-int16, 3 cot, dung khi gap 3 so 0"
    )
    parser.add_argument("--host", default="192.168.100.200", help="IP cua PLC")
    parser.add_argument("--port", type=int, default=8501, help="Cong Host Link")
    parser.add_argument("--transport", choices=["tcp", "udp"], default="tcp")
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument(
        "--csv",
        default="zf_values.csv",
        help="Ten file CSV dau ra (mac dinh zf_values.csv)",
    )
    return parser.parse_args()


async def read_zf_values(args: argparse.Namespace) -> int:
    options = hl.HostLinkConnectionOptions(
        args.host,
        port=args.port,
        transport=args.transport,
        timeout=args.timeout,
        plc_profile="keyence:kv-8000",
    )

    print(f"Ket noi {args.transport}://{args.host}:{args.port} (keyence:kv-8000) ...")
    try:
        client = await hl.open_and_connect(options)
    except Exception as exc:  # noqa: BLE001
        print(f"[LOI] Khong ket noi duoc PLC: {type(exc).__name__}: {exc}")
        return 1

    columns = (
        "Thoi gian truoc khi chinh (s)",
        "Goc quay",
        "Thoi gian sau khi chinh (s)",
    )
    print(f"\n{columns[0]:>10} | {columns[1]:>10} | {columns[2]:>10}")
    print("-" * 38)

    rows: list[list[int]] = []
    try:
        async with client:
            for base in range(START, END + 1, GROUP_SIZE):
                # Doc dung 3 word S-int16 trong mot request Host Link.
                # read_words_single_request la U-int16, nen o day dung truc tiep
                # read_consecutive voi data_format='.S' de giu dau am dung.
                values = await client.read_consecutive(
                    f"ZF{base}", GROUP_SIZE, data_format=".S"
                )
                row = np.asarray(values, dtype=np.int16)

                if row.shape != (GROUP_SIZE,):
                    print(f"[LOI] PLC tra ve {row.size} gia tri thay vi 3 tai ZF{base}.")
                    return 2

                # Dung truoc khi in nhom ket thuc [0, 0, 0].
                if np.all(row == np.int16(0)):
                    print(f"Dung doc tai ZF{base}: gap 3 gia tri lien ke bang 0.")
                    break

                rows.append([int(value) for value in row])
                print(f"ZF{base:05d}: {int(row[0]):10d} | {int(row[1]):10d} | {int(row[2]):10d}")
            else:
                print(f"Da doc den ZF{END}; khong gap nhom [0, 0, 0].")
    except hl.HostLinkError as exc:
        print(f"[LOI] PLC tra loi khi doc: {type(exc).__name__}: {exc}")
        return 2
    finally:
        await client.close()

    with open(args.csv, "w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(columns)
        writer.writerows(
            [
                [int(row[0]), int(row[1]), int(row[2])] for row in rows
            ]
        )
    print(f"Da luu {len(rows)} dong vao {args.csv}.")

    # Phan loai theo goc quay: moi goc mot file rieng
    from pathlib import Path

    group_dir = Path("zf_by_angle")
    group_dir.mkdir(exist_ok=True)
    for old_file in group_dir.glob("goc_*.csv"):
        old_file.unlink()

    groups: dict[int, list[list[int]]] = {}
    for row in rows:
        groups.setdefault(int(row[1]), []).append(
            [int(row[0]), int(row[1]), int(row[2])]
        )

    for angle in sorted(groups):
        group_path = group_dir / f"goc_{angle}.csv"
        with open(group_path, "w", newline="", encoding="utf-8-sig") as group_file:
            writer = csv.writer(group_file)
            writer.writerow(columns)
            writer.writerows(groups[angle])
    print(f"Da phan loai {len(groups)} goc quay vao thu muc {group_dir}/")

    return 0


def main() -> int:
    return asyncio.run(read_zf_values(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
