#!/usr/bin/env python3
"""Convert simple rectangle txt files to GDSII.

Rows use:
    x1 y1 x2 y2 layer_num label

If label is missing or "None", no GDS TEXT is emitted for that rectangle.
Any other label is written as-is at the rectangle center.
"""

from __future__ import annotations

import argparse
import math
import struct
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Rect:
    x1: float
    y1: float
    x2: float
    y2: float
    layer: int
    label: str = "None"


def float_to_gds_real(value: float) -> bytes:
    if value == 0:
        return b"\0" * 8
    sign = 0x80 if value < 0 else 0
    value = abs(value)
    exponent = int(math.floor(math.log(value, 16))) + 1
    mantissa = value / (16**exponent)
    while mantissa >= 1:
        mantissa /= 16
        exponent += 1
    while mantissa < 1 / 16:
        mantissa *= 16
        exponent -= 1
    mantissa_int = int(round(mantissa * (1 << 56)))
    if mantissa_int >= (1 << 56):
        mantissa_int //= 16
        exponent += 1
    return bytes([sign | ((exponent + 64) & 0x7F)]) + mantissa_int.to_bytes(7, "big")


def record(record_type: int, data_type: int, payload: bytes = b"") -> bytes:
    if len(payload) % 2:
        payload += b"\0"
    return struct.pack(">HBB", len(payload) + 4, record_type, data_type) + payload


def int2_record(record_type: int, values: list[int]) -> bytes:
    return record(record_type, 0x02, struct.pack(f">{len(values)}h", *values))


def int4_record(record_type: int, values: list[int]) -> bytes:
    return record(record_type, 0x03, struct.pack(f">{len(values)}i", *values))


def real8_record(record_type: int, values: list[float]) -> bytes:
    return record(record_type, 0x05, b"".join(float_to_gds_real(v) for v in values))


def string_record(record_type: int, value: str) -> bytes:
    return record(record_type, 0x06, value.encode("ascii", errors="replace"))


def timestamp() -> list[int]:
    return [2026, 7, 1, 0, 0, 0, 2026, 7, 1, 0, 0, 0]


def read_txt(path: Path) -> list[Rect]:
    rects: list[Rect] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("%") or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        x1, y1, x2, y2 = map(float, parts[:4])
        layer = int(parts[4])
        label = " ".join(parts[5:]) if len(parts) > 5 else "None"
        rects.append(Rect(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2), layer, label))
    return rects


def write_gds(rects: list[Rect], path: Path, name: str) -> None:
    unit_um = 0.001
    unit_m = 1e-6
    db_unit_m = unit_um * 1e-6
    data = bytearray()
    name = name.upper()[:32]
    data += int2_record(0x00, [600])
    data += int2_record(0x01, timestamp())
    data += string_record(0x02, name)
    data += real8_record(0x03, [db_unit_m / unit_m, db_unit_m])
    data += int2_record(0x05, timestamp())
    data += string_record(0x06, name)

    for rect in rects:
        x1 = round(rect.x1 / unit_um)
        y1 = round(rect.y1 / unit_um)
        x2 = round(rect.x2 / unit_um)
        y2 = round(rect.y2 / unit_um)
        data += record(0x08, 0x00)
        data += int2_record(0x0D, [rect.layer])
        data += int2_record(0x0E, [0])
        data += int4_record(0x10, [x1, y1, x2, y1, x2, y2, x1, y2, x1, y1])
        data += record(0x11, 0x00)

        if rect.label and rect.label != "None":
            data += record(0x0C, 0x00)
            data += int2_record(0x0D, [rect.layer])
            data += int2_record(0x16, [0])
            data += int4_record(0x10, [round((x1 + x2) / 2), round((y1 + y2) / 2)])
            data += string_record(0x19, rect.label)
            data += record(0x11, 0x00)

    data += record(0x07, 0x00)
    data += record(0x04, 0x00)
    path.write_bytes(bytes(data))


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert txt to GDSII without inferring labels.")
    parser.add_argument("txt")
    parser.add_argument("gds", nargs="?")
    args = parser.parse_args()
    in_path = Path(args.txt)
    out_path = Path(args.gds) if args.gds else in_path.with_suffix(".gds")
    write_gds(read_txt(in_path), out_path, in_path.stem)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
