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
COLUMNS = (
    "Thoi gian truoc khi chinh (s)",
    "Goc quay",
    "Thoi gian sau khi chinh (s)",
)


async def read_zf_values(
    host: str,
    port: int,
    transport: str,
    timeout: float,
    csv_path: str | Path,
    start: int = START,
    end: int = END,
) -> list[list[int]]:
    """Doc ZF<start>-ZF<end>, luu CSV va phan loai theo goc. Tra ve danh sach dong."""
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
            for base in range(start, end + 1, GROUP_SIZE):
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
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(COLUMNS)
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
            writer.writerow(COLUMNS)
            writer.writerows(groups[angle])

    return rows


async def read_bounds(
    host: str,
    port: int,
    transport: str,
    timeout: float,
    upper_device: str | None = None,
    lower_device: str | None = None,
) -> tuple[int | None, int | None]:
    """Doc gia tri tai 2 bien word (ZF/DM/EM/...) lam bien tren/duoi. Tra ve (upper, lower)."""
    if not upper_device and not lower_device:  # Khong khai bao bien nao -> khong doc.
        return None, None

    options = hl.HostLinkConnectionOptions(
        host,
        port=port,
        transport=transport,
        timeout=timeout,
        plc_profile="keyence:kv-8000",
    )

    client = await hl.open_and_connect(options)
    try:
        async with client:
            async def _read_one(device: str) -> int | None:
                """Doc 1 word (S-int16) tai bat ky bien word nao (ZF, DM, EM, ...)."""
                value = await client.read(device, data_format=".S")
                return int(value) if isinstance(value, (int, float)) else None

            upper = await _read_one(upper_device) if upper_device else None
            lower = await _read_one(lower_device) if lower_device else None
    finally:
        await client.close()

    return upper, lower


# Bien chua so offset (dia chi gian tiep) + danh sach cac gia tri can doc.
OFFSET_INDEX_DEVICE = "EM120"  # EM120 chua so offset; dia chi thuc = DM<base> + EM120.
OFFSET_READ_ITEMS = (
    ("all_fast", "Offset all fast", 40500),
    ("all_slow", "Offset all slow", 40502),
    ("fast10", "Offset fast 10", 40504),
    ("fast20", "Offset fast 20", 40506),
    ("fast30", "Offset fast 30", 40508),
    ("fast40", "Offset fast 40", 40510),
    ("fast50", "Offset fast 50", 40512),
    ("fast60", "Offset fast 60", 40514),
    ("fast70", "Offset fast 70", 40516),
    ("slow10", "Offset slow 10", 40518),
    ("slow20", "Offset slow 20", 40520),
    ("slow30", "Offset slow 30", 40522),
    ("slow40", "Offset slow 40", 40524),
    ("slow50", "Offset slow 50", 40526),
    ("slow60", "Offset slow 60", 40528),
    ("slow70", "Offset slow 70", 40530),
)


async def read_offsets(
    host: str,
    port: int,
    transport: str,
    timeout: float,
) -> tuple[int, dict[str, int | None]]:
    """Doc cac gia tri offset S-int32 theo dia chi gian tiep DMxxxx + EM120 (EM120 cung S-int32)."""
    options = hl.HostLinkConnectionOptions(
        host,
        port=port,
        transport=transport,
        timeout=timeout,
        plc_profile="keyence:kv-8000",
    )

    client = await hl.open_and_connect(options)
    try:
        async with client:
            index_value = await client.read(OFFSET_INDEX_DEVICE, data_format=".L")  # EM120 cung S-int32.
            offset = int(index_value) if isinstance(index_value, (int, float)) else 0

            values: dict[str, int | None] = {}
            for key, _label, base in OFFSET_READ_ITEMS:
                value = await client.read(f"DM{base + offset}", data_format=".L")  # .L = S-int32 (2 word).
                values[key] = int(value) if isinstance(value, (int, float)) else None
    finally:
        await client.close()

    return offset, values


async def write_offsets(
    host: str,
    port: int,
    transport: str,
    timeout: float,
    offset: int,
    values: dict[str, int],
) -> None:
    """Ghi cac gia tri offset S-int32 (da sua) xuong DM{base+offset}."""
    options = hl.HostLinkConnectionOptions(
        host,
        port=port,
        transport=transport,
        timeout=timeout,
        plc_profile="keyence:kv-8000",
    )

    client = await hl.open_and_connect(options)
    try:
        async with client:
            for key, _label, base in OFFSET_READ_ITEMS:
                value = values.get(key)
                if value is None:  # Khong co gia tri moi cho muc nay -> bo qua.
                    continue
                await client.write(f"DM{base + offset}", value, data_format=".L")  # Ghi S-int32 (2 word).
    finally:
        await client.close()


async def clear_angle(
    host: str,
    port: int,
    transport: str,
    timeout: float,
    start: int,
    end: int,
    angle: int,
) -> int:
    """Ghi 0 xuong cac nhom 3 word ZF co goc quay == angle. Tra ve so nhom da xoa."""
    options = hl.HostLinkConnectionOptions(
        host,
        port=port,
        transport=transport,
        timeout=timeout,
        plc_profile="keyence:kv-8000",
    )

    client = await hl.open_and_connect(options)
    cleared = 0
    try:
        async with client:
            for base in range(start, end + 1, GROUP_SIZE):
                values = await client.read_consecutive(f"ZF{base}", GROUP_SIZE, data_format=".S")
                row = np.asarray(values, dtype=np.int16)
                if np.all(row == np.int16(0)):  # Gap du lieu -> dung.
                    break
                if int(row[1]) == angle:  # Goc quay trung -> xoa bang cach ghi 0.
                    await client.write_consecutive(f"ZF{base}", [0, 0, 0], data_format=".S")
                    cleared += 1
    finally:
        await client.close()

    return cleared


def remove_angle_local(csv_path: str | Path, angle_dir: str | Path, angle: int) -> None:
    """Xoa cac dong co goc quay == angle khoi CSV va xoa file goc_<angle>.csv (khong dung PLC)."""
    csv_path = Path(csv_path)
    if csv_path.exists():  # Loai bo cac dong cua goc nay trong zf_values.csv.
        values = np.genfromtxt(csv_path, delimiter=",", skip_header=1)
        if values.ndim == 1:
            values = values.reshape(1, -1)
        if values.ndim == 2 and values.shape[1] == 3:
            kept = values[values[:, 1] != angle].astype(int).tolist()
            with open(csv_path, "w", newline="", encoding="utf-8-sig") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(COLUMNS)
                writer.writerows(kept)

    goc_file = Path(angle_dir) / f"goc_{angle}.csv"  # Xoa file rieng cua goc nay.
    if goc_file.exists():
        goc_file.unlink()


WRITE_CHUNK = 900  # So word ghi trong 1 lenh WRS (duoi gioi han 1000 cua KV-8000).


async def clear_all(
    host: str,
    port: int,
    transport: str,
    timeout: float,
    start: int,
    end: int,
) -> None:
    """Ghi 0 xuong toan bo dai ZF (start..end) - xoa tat ca du lieu."""
    total = end - start + 1
    if total <= 0:  # Dai rong -> khong lam gi.
        return

    options = hl.HostLinkConnectionOptions(
        host,
        port=port,
        transport=transport,
        timeout=timeout,
        plc_profile="keyence:kv-8000",
    )

    client = await hl.open_and_connect(options)
    try:
        async with client:
            for i in range(0, total, WRITE_CHUNK):  # Ghi 0 theo tung khoi de nhanh.
                n = min(WRITE_CHUNK, total - i)
                await client.write_consecutive(f"ZF{start + i}", [0] * n, data_format=".S")
    finally:
        await client.close()


def clear_local(csv_path: str | Path, angle_dir: str | Path) -> None:
    """Xoa zf_values.csv va tat ca file goc_*.csv (khong dung PLC)."""
    csv_path = Path(csv_path)
    if csv_path.exists():
        csv_path.unlink()

    angle_dir = Path(angle_dir)
    if angle_dir.exists():
        for old_file in angle_dir.glob("goc_*.csv"):
            old_file.unlink()
