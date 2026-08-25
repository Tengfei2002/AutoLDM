#!/usr/bin/env python3
"""Analyze and validate AutoLDM rectangle layouts against a working reference."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


TOL = 1.0e-6
LABEL_RE = re.compile(r"^(?:None|[A-Za-z_][A-Za-z0-9_]*)$")


@dataclass(frozen=True)
class Rect:
    x1: float
    y1: float
    x2: float
    y2: float
    layer: int
    label: str
    line: int

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2.0

    @property
    def positive(self) -> bool:
        return self.width > TOL and self.height > TOL

    def canonical(self) -> tuple[float, float, float, float, int, str]:
        return (round(self.x1, 9), round(self.y1, 9), round(self.x2, 9), round(self.y2, 9), self.layer, self.label)


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    detail: str


def close(a: float, b: float, tolerance: float = TOL) -> bool:
    return abs(a - b) <= tolerance


def parse_layout(path: Path) -> list[Rect]:
    rows: list[Rect] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("%"):
            continue
        parts = stripped.split()
        if len(parts) not in {5, 6}:
            raise ValueError(f"{path}:{line_number}: expected 5 or 6 columns, got {len(parts)}")
        try:
            x1, y1, x2, y2 = (float(token) for token in parts[:4])
            layer = int(parts[4])
        except ValueError as exc:
            raise ValueError(f"{path}:{line_number}: invalid coordinate or layer") from exc
        label = parts[5] if len(parts) == 6 else "None"
        if not all(math.isfinite(value) for value in (x1, y1, x2, y2)):
            raise ValueError(f"{path}:{line_number}: coordinates must be finite")
        if x2 < x1 or y2 < y1:
            raise ValueError(f"{path}:{line_number}: reversed rectangle coordinates")
        if not LABEL_RE.fullmatch(label):
            raise ValueError(f"{path}:{line_number}: invalid label {label!r}")
        rows.append(Rect(x1, y1, x2, y2, layer, label, line_number))
    if not rows:
        raise ValueError(f"{path}: no layout rows")
    return rows


def positive_on(rows: Iterable[Rect], layer: int) -> list[Rect]:
    return [row for row in rows if row.layer == layer and row.positive]


def bounds(rows: Iterable[Rect]) -> tuple[float, float, float, float]:
    values = list(rows)
    if not values:
        raise ValueError("cannot calculate bounds of an empty layer")
    return (
        min(row.x1 for row in values),
        min(row.y1 for row in values),
        max(row.x2 for row in values),
        max(row.y2 for row in values),
    )


def effective_cell_x_bounds(rows: Iterable[Rect]) -> tuple[float, float]:
    """Return the positive-area X span, excluding the two power rails themselves."""
    values = [
        row
        for row in rows
        if row.positive
        and not (row.layer == 19 and row.label.upper() == "VSS")
        and not (row.layer == 53 and row.label.upper() == "VDD")
    ]
    if not values:
        raise ValueError("cannot calculate effective cell X bounds without non-rail positive-area shapes")
    return min(row.x1 for row in values), max(row.x2 for row in values)


def normalized_phase(value: float, pitch: float) -> float:
    remainder = value % pitch
    return 0.0 if close(remainder, 0.0) or close(remainder, pitch) else remainder


def mode(values: Iterable[float]) -> float:
    rounded = [round(value, 9) for value in values]
    if not rounded:
        raise ValueError("cannot calculate a mode from no values")
    counts = Counter(rounded)
    return sorted(counts, key=lambda value: (-counts[value], value))[0]


def layer_summary(rows: list[Rect]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for layer in sorted({row.layer for row in rows}):
        layer_rows = [row for row in rows if row.layer == layer]
        positive = [row for row in layer_rows if row.positive]
        item: dict[str, object] = {
            "layer": layer,
            "count": len(layer_rows),
            "positive_count": len(positive),
            "labels": [row.label for row in layer_rows if row.label != "None"],
        }
        if positive:
            x1, y1, x2, y2 = bounds(positive)
            item.update({"x_min": x1, "y_min": y1, "x_max": x2, "y_max": y2})
        result.append(item)
    return result


def infer_reference(rows: list[Rect]) -> dict[str, object]:
    boundary = positive_on(rows, 1)
    gates = positive_on(rows, 7)
    if not boundary or not gates:
        raise ValueError("reference must contain positive layer-1 boundary and layer-7 gate rectangles")
    bx1, by1, bx2, by2 = bounds(boundary)
    tile_width = mode(row.width for row in boundary)
    gate_width = mode(row.width for row in gates)
    gate_height = mode(row.height for row in gates)
    gate_centers = sorted(row.cx for row in gates)
    pitches = [right - left for left, right in zip(gate_centers, gate_centers[1:]) if right - left > TOL]
    gate_pitch = mode(pitches) if pitches else tile_width
    gate_phase = (gate_centers[0] - bx1) % gate_pitch

    sd_contacts = [
        row for row in rows
        if row.layer in {16, 51} and row.positive and "_SD_" in row.label
    ]
    contact_phase = mode(normalized_phase(row.cx - bx1, gate_pitch) for row in sd_contacts) if sd_contacts else 0.0

    rails: dict[str, dict[str, float | int]] = {}
    for name, layer in (("VSS", 19), ("VDD", 53)):
        candidates = [row for row in rows if row.layer == layer and row.label.upper() == name and row.positive]
        if not candidates:
            raise ValueError(f"reference has no labeled {name} rail on layer {layer}")
        rail_x1 = min(row.x1 for row in candidates)
        rail_x2 = max(row.x2 for row in candidates)
        rails[name] = {
            "layer": layer,
            "height": mode(row.height for row in candidates),
            "y1": mode(row.y1 for row in candidates),
            "y2": mode(row.y2 for row in candidates),
            "coverage": (rail_x2 - rail_x1) / (bx2 - bx1),
        }

    layer_dimensions: dict[str, list[list[float]]] = {}
    for layer in sorted({row.layer for row in rows}):
        dimensions = sorted({(round(row.width, 9), round(row.height, 9)) for row in positive_on(rows, layer)})
        layer_dimensions[str(layer)] = [[width, height] for width, height in dimensions]

    return {
        "boundary": {"x1": bx1, "y1": by1, "x2": bx2, "y2": by2, "tile_width": tile_width},
        "gate": {"width": gate_width, "height": gate_height, "pitch": gate_pitch, "phase": gate_phase},
        "contact_phase": contact_phase,
        "rails": rails,
        "layer_dimensions": layer_dimensions,
    }


def grid_distance(value: float, phase: float, pitch: float) -> float:
    quotient = round((value - phase) / pitch)
    return abs(value - (phase + quotient * pitch))


def validate(reference: list[Rect], candidate: list[Rect], required_ports: list[str]) -> list[Finding]:
    contract = infer_reference(reference)
    findings: list[Finding] = []
    candidate_boundary = positive_on(candidate, 1)
    candidate_gates = positive_on(candidate, 7)
    if not candidate_boundary:
        return [Finding("ERROR", "BOUNDARY.MISSING", "candidate has no positive layer-1 boundary")]
    if not candidate_gates:
        findings.append(Finding("ERROR", "GATE.MISSING", "candidate has no positive layer-7 gate"))

    for row in candidate:
        if not row.positive:
            findings.append(Finding("ERROR", "RECT.ZERO", f"line {row.line}: candidate rectangle has zero area"))

    bx1, by1, bx2, by2 = bounds(candidate_boundary)
    effective_x1, effective_x2 = effective_cell_x_bounds(candidate)
    tile_width = float(contract["boundary"]["tile_width"])
    span_tiles = (bx2 - bx1) / tile_width
    nearest_tiles = round(span_tiles)
    if nearest_tiles < 1 or not close(span_tiles, nearest_tiles):
        findings.append(Finding(
            "ERROR", "BOUNDARY.GRID",
            f"boundary width {bx2 - bx1:.6f} is not an integer multiple of reference tile {tile_width:.6f}",
        ))
    elif len(candidate_gates) != nearest_tiles:
        findings.append(Finding(
            "ERROR", "BOUNDARY.GATE_COUNT",
            f"boundary spans {nearest_tiles} reference tiles but contains {len(candidate_gates)} gates",
        ))

    gate = contract["gate"]
    pitch = float(gate["pitch"])
    gate_phase = bx1 + float(gate["phase"])
    for row in candidate_gates:
        if not close(row.width, float(gate["width"])) or not close(row.height, float(gate["height"])):
            findings.append(Finding(
                "ERROR", "GATE.DIMENSION",
                f"line {row.line}: gate is {row.width:.6f}x{row.height:.6f}; reference is "
                f"{float(gate['width']):.6f}x{float(gate['height']):.6f}",
            ))
        if grid_distance(row.cx, gate_phase, pitch) > TOL:
            findings.append(Finding(
                "ERROR", "GATE.GRID",
                f"line {row.line}: gate center x={row.cx:.6f} is off reference phase {gate_phase:.6f} pitch {pitch:.6f}",
            ))

    contact_phase = bx1 + float(contract["contact_phase"])
    for row in candidate:
        if row.layer not in {16, 51} or not row.positive or row.label == "None":
            continue
        expected_phase: float | None = None
        code = ""
        if "_G_" in row.label:
            expected_phase, code = gate_phase, "CONTACT.GATE_GRID"
        elif "_SD_" in row.label:
            expected_phase, code = contact_phase, "CONTACT.SD_GRID"
        if expected_phase is not None and grid_distance(row.cx, expected_phase, pitch) > TOL:
            findings.append(Finding(
                "ERROR", code,
                f"line {row.line}: {row.label} center x={row.cx:.6f} is off reference grid",
            ))

    dimensions = contract["layer_dimensions"]
    for layer in (7, 16, 17, 18, 51, 52):
        allowed = [tuple(item) for item in dimensions.get(str(layer), [])]
        for row in positive_on(candidate, layer):
            if allowed and not any(close(row.width, width) and close(row.height, height) for width, height in allowed):
                findings.append(Finding(
                    "ERROR", "LAYER.DIMENSION",
                    f"line {row.line}: L{layer} size {row.width:.6f}x{row.height:.6f} is absent from reference templates {allowed}",
                ))

    for name, rail_info in contract["rails"].items():
        layer = int(rail_info["layer"])
        rails = [row for row in candidate if row.layer == layer and row.label.upper() == name and row.positive]
        if not rails:
            findings.append(Finding("ERROR", "RAIL.MISSING", f"missing {name} rail on layer {layer}"))
            continue
        rail_x1 = min(row.x1 for row in rails)
        rail_x2 = max(row.x2 for row in rails)
        if not close(rail_x1, effective_x1) or not close(rail_x2, effective_x2):
            findings.append(Finding(
                "ERROR", "RAIL.X_EXTENT",
                f"{name} X range {rail_x1:.6f}..{rail_x2:.6f} must equal the effective cell X range "
                f"{effective_x1:.6f}..{effective_x2:.6f}; rails may extend outside the L1 boundary",
            ))
        for row in rails:
            if not close(row.height, float(rail_info["height"])):
                findings.append(Finding(
                    "ERROR", "RAIL.HEIGHT",
                    f"line {row.line}: {name} height {row.height:.6f} differs from reference {float(rail_info['height']):.6f}",
                ))

    labels = {row.label.upper() for row in candidate if row.label != "None"}
    for port in required_ports:
        if port.upper() not in labels:
            findings.append(Finding("ERROR", "PORT.MISSING", f"required layout label {port} is absent"))

    referenced_layers = {row.layer for row in reference if row.positive}
    for layer in sorted({row.layer for row in candidate if row.positive} - referenced_layers):
        findings.append(Finding(
            "WARNING", "LAYER.NEW",
            f"candidate uses L{layer}, which is absent from the selected reference; verify it against the stack and rules",
        ))

    if not any(item.severity == "ERROR" for item in findings):
        findings.append(Finding("PASS", "REFERENCE.CONTRACT", "candidate satisfies the extracted reference-layout contract"))
    return findings


def print_findings(findings: list[Finding], as_json: bool) -> None:
    if as_json:
        print(json.dumps([asdict(item) for item in findings], ensure_ascii=False, indent=2))
        return
    for item in findings:
        print(f"{item.severity:<7} {item.code:<24} {item.detail}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    summarize_parser = subparsers.add_parser("summarize", help="print layer and inferred-grid summary")
    summarize_parser.add_argument("layout", type=Path)
    summarize_parser.add_argument("--json", action="store_true")

    validate_parser = subparsers.add_parser("validate", help="validate a candidate against a working reference")
    validate_parser.add_argument("--reference", required=True, type=Path)
    validate_parser.add_argument("--candidate", required=True, type=Path)
    validate_parser.add_argument("--ports", default="", help="comma-separated required layout labels")
    validate_parser.add_argument("--json", action="store_true")

    exact_parser = subparsers.add_parser("exact", help="compare two layout files after parsing")
    exact_parser.add_argument("expected", type=Path)
    exact_parser.add_argument("actual", type=Path)

    args = parser.parse_args()
    if args.command == "summarize":
        rows = parse_layout(args.layout)
        payload = {"layout": str(args.layout.resolve()), "layers": layer_summary(rows), "contract": infer_reference(rows)}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"Layout: {payload['layout']}")
            for item in payload["layers"]:
                print(
                    f"L{item['layer']:<3} count={item['count']:<3} positive={item['positive_count']:<3} "
                    f"labels={','.join(item['labels']) or '-'}"
                )
            print(json.dumps(payload["contract"], ensure_ascii=False, indent=2))
        return 0

    if args.command == "validate":
        ports = [item.strip() for item in args.ports.split(",") if item.strip()]
        findings = validate(parse_layout(args.reference), parse_layout(args.candidate), ports)
        print_findings(findings, args.json)
        return 2 if any(item.severity == "ERROR" for item in findings) else 0

    expected = Counter(row.canonical() for row in parse_layout(args.expected) if row.positive)
    actual = Counter(row.canonical() for row in parse_layout(args.actual) if row.positive)
    if expected == actual:
        print("PASS: parsed positive-area rectangles and labels are identical")
        return 0
    for row, count in (expected - actual).items():
        print(f"MISSING {count}x {row}")
    for row, count in (actual - expected).items():
        print(f"EXTRA   {count}x {row}")
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"layout_contract error: {exc}", file=sys.stderr)
        sys.exit(1)
