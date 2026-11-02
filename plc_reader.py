r"""Doc du lieu ZF tu PLC KEYENCE KV va luu file CSV + phan loai theo goc.

Module nay duoc dung boi ca read_data_rework.py (CLI) va dashboard_rework.py (GUI).
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import hostlink as hl

START = 10000
END = 16000
GROUP_SIZE = 3


async def read_zf_values(
    host: str,
    port: int,
    transport: str,
    timeout: float,
    csv_path: str | Path,
) -> list[list[int]]:
    """Doc ZF10000-ZF16000, luu CSV va phan loai theo goc. Tra ve danh sach dong."""
    options = hl.HostLinkConnectionOptions(
        host,
        port=port,
        transport=transport,
        timeout=timeout,
        plc_profile="keyence:kv-8000",
    )

    client = await hl.open_and_connect(options)
    rows: list[list[int]] = []
    try:
        async with client:
            for base in range(START, END + 1, GROUP_SIZE):
                values = await client.read_consecutive(
                    f"ZF{base}", GROUP_SIZE, data_format=".S"
                )
                row = np.asarray(values, dtype=np.int16)
                if row.shape != (GROUP_SIZE,):
                    raise RuntimeError(
                        f"PLC tra ve {row.size} gia tri thay vi {GROUP_SIZE} tai ZF{base}"
                    )
                if np.all(row == np.int16(0)):
                    break
                rows.append([int(value) for value in row])
    finally:
        await client.close()

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    columns = (
        "Thoi gian truoc khi chinh (s)",
        "Goc quay",
        "Thoi gian sau khi chinh (s)",
    )
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(columns)
        writer.writerows(rows)

    # Phan loai theo goc quay
    group_dir = csv_path.parent / "zf_by_angle"
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

    return rows
