#!/usr/bin/env python3
"""Render a reviewed JSON rectangle specification as an AutoLDM layout text file."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path


LABEL_RE = re.compile(r"^(?:None|[A-Za-z_][A-Za-z0-9_]*)$")
REQUIRED_KEYS = ("x1", "y1", "x2", "y2", "layer")


def number(item: object, key: str, index: int) -> float:
    try:
        value = float(item)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"rectangles[{index}].{key} must be a number") from exc
    if not math.isfinite(value):
        raise ValueError(f"rectangles[{index}].{key} must be finite")
    return value


def load_spec(path: Path) -> tuple[str, str, list[str], list[tuple[float, float, float, float, int, str]]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("spec root must be a JSON object")
    name = str(payload.get("cell_name", "")).strip()
    if not name or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name):
        raise ValueError("cell_name must start with a letter and contain only letters, digits, and underscores")
    unit = str(payload.get("unit", "um")).strip()
    if unit != "um":
        raise ValueError("AutoLDM layout specifications currently require unit=um")
    comments = payload.get("comments", [])
    if not isinstance(comments, list) or not all(isinstance(item, str) for item in comments):
        raise ValueError("comments must be a list of strings")
    raw_rectangles = payload.get("rectangles")
    if not isinstance(raw_rectangles, list) or not raw_rectangles:
        raise ValueError("rectangles must be a non-empty list")

    rectangles: list[tuple[float, float, float, float, int, str]] = []
    seen: set[tuple[float, float, float, float, int, str]] = set()
    for index, item in enumerate(raw_rectangles):
        if not isinstance(item, dict) or any(key not in item for key in REQUIRED_KEYS):
            raise ValueError(f"rectangles[{index}] must contain {', '.join(REQUIRED_KEYS)}")
        x1, y1, x2, y2 = (number(item[key], key, index) for key in REQUIRED_KEYS[:4])
        try:
            layer = int(item["layer"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"rectangles[{index}].layer must be an integer") from exc
        label = str(item.get("label", "None"))
        if not LABEL_RE.fullmatch(label):
            raise ValueError(f"rectangles[{index}].label is invalid: {label!r}")
        if x2 <= x1 or y2 <= y1:
            raise ValueError(f"rectangles[{index}] must have positive width and height")
        row = (x1, y1, x2, y2, layer, label)
        if row in seen:
            raise ValueError(f"rectangles[{index}] duplicates an earlier rectangle")
        seen.add(row)
        rectangles.append(row)
    return name, unit, comments, rectangles


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--precision", type=int, default=4)
    args = parser.parse_args()
    if not 3 <= args.precision <= 9:
        raise ValueError("precision must be between 3 and 9 decimal places")
    name, unit, comments, rectangles = load_spec(args.spec)
    lines = [f"% {name.upper()}_LAYOUT. Unit: {unit}.", "% x1 y1 x2 y2 layer_num label"]
    lines.extend(f"% {comment}" for comment in comments)
    if comments:
        lines.append("")
    format_string = f"{{:.{args.precision}f}}"
    previous_layer: int | None = None
    for x1, y1, x2, y2, layer, label in rectangles:
        if previous_layer is not None and layer != previous_layer:
            lines.append("")
        lines.append(
            " ".join((
                format_string.format(x1), format_string.format(y1),
                format_string.format(x2), format_string.format(y2),
                str(layer), label,
            ))
        )
        previous_layer = layer
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"Wrote AutoLDM layout: {args.output.resolve()}")
    print(f"Rectangles: {len(rectangles)}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"render_layout error: {exc}", file=sys.stderr)
        sys.exit(1)
