#!/usr/bin/env python3
"""Convert GDSII rectangles and existing TEXT labels to a simple txt format."""

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


@dataclass
class Text:
    x: float
    y: float
    layer: int
    label: str


def gds_real_to_float(raw: bytes) -> float:
    if raw == b"\0" * 8:
        return 0.0
    sign = -1 if raw[0] & 0x80 else 1
    exponent = (raw[0] & 0x7F) - 64
    mantissa = int.from_bytes(raw[1:], "big") / float(1 << 56)
    return sign * mantissa * (16**exponent)


def read_records(path: Path):
    data = path.read_bytes()
    pos = 0
    while pos < len(data):
        length, record_type, data_type = struct.unpack(">HBB", data[pos : pos + 4])
        yield record_type, data_type, data[pos + 4 : pos + length]
        pos += length


def ints2(raw: bytes) -> list[int]:
    return list(struct.unpack(f">{len(raw) // 2}h", raw)) if raw else []


def ints4(raw: bytes) -> list[int]:
    return list(struct.unpack(f">{len(raw) // 4}i", raw)) if raw else []


def read_gds(path: Path) -> tuple[str, list[Rect], list[Text]]:
    unit_um = 0.001
    name = path.stem
    rects: list[Rect] = []
    texts: list[Text] = []
    current: dict[str, object] | None = None

    for record_type, _data_type, raw in read_records(path):
        if record_type in (0x02, 0x06):
            text = raw.rstrip(b"\0").decode("ascii", errors="replace")
            if text:
                name = text
        elif record_type == 0x03 and len(raw) >= 16:
            db_unit_m = gds_real_to_float(raw[8:16])
            unit_um = db_unit_m * 1e6
        elif record_type == 0x08:
            current = {"kind": "boundary", "layer": 0}
        elif record_type == 0x0C:
            current = {"kind": "text", "layer": 0, "label": ""}
        elif current is not None and record_type == 0x0D:
            current["layer"] = ints2(raw)[0]
        elif current is not None and record_type == 0x10:
            coords = ints4(raw)
            points = [(coords[i] * unit_um, coords[i + 1] * unit_um) for i in range(0, len(coords), 2)]
            current["points"] = points
        elif current is not None and record_type == 0x19:
            current["label"] = raw.rstrip(b"\0").decode("ascii", errors="replace")
        elif current is not None and record_type == 0x11:
            points = current.get("points", [])
            layer = int(current.get("layer", 0))
            if current["kind"] == "boundary" and points:
                xs = [p[0] for p in points]  # type: ignore[index]
                ys = [p[1] for p in points]  # type: ignore[index]
                rects.append(Rect(min(xs), min(ys), max(xs), max(ys), layer))
            elif current["kind"] == "text" and points:
                x, y = points[0]  # type: ignore[index]
                texts.append(Text(x, y, layer, str(current.get("label", ""))))
            current = None

    for text in texts:
        for rect in rects:
            if (
                rect.layer == text.layer
                and rect.x1 - 1e-9 <= text.x <= rect.x2 + 1e-9
                and rect.y1 - 1e-9 <= text.y <= rect.y2 + 1e-9
                and rect.label == "None"
            ):
                rect.label = text.label or "None"
                break
    return name, rects, texts


def write_txt(name: str, rects: list[Rect], path: Path) -> None:
    lines = [
        f"% {name}. Unit: um.",
        "% x1 y1 x2 y2 layer_num label",
    ]
    for rect in rects:
        label = rect.label if rect.label else "None"
        lines.append(f"{rect.x1:.4f} {rect.y1:.4f} {rect.x2:.4f} {rect.y2:.4f} {rect.layer:d} {label}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert GDSII to txt without inferring labels.")
    parser.add_argument("gds")
    parser.add_argument("txt", nargs="?")
    args = parser.parse_args()
    in_path = Path(args.gds)
    out_path = Path(args.txt) if args.txt else in_path.with_suffix(".txt")
    name, rects, _texts = read_gds(in_path)
    write_txt(name, rects, out_path)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
