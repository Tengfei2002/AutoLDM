#!/usr/bin/env python3
"""Generate a layout/stack-aware DRC report for an AutoLDM ``*_gds.txt`` file.

The layout format currently contains axis-aligned rectangles.  This checker
therefore reports rectangle-safe rules (width, area, spacing, enclosure and
overlap) and supplements them with 3-D contact-recipe checks derived from the
same gate/spacer/S-D plan used by ``gen_sde.py``.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Tuple

from gen_sde import Builder, EPS, ExpressionResolver, Rect, parse_layout, parse_params, parse_relations, parse_stack


@dataclass(frozen=True)
class Rule:
    rule_id: str
    severity: str
    check: str
    options: Dict[str, str]
    line: int


@dataclass(frozen=True)
class Finding:
    status: str
    rule: Rule
    subject: str
    measured: float | None
    operator: str
    limit: float | None
    detail: str


def parse_rules(path: Path) -> List[Rule]:
    """Read ``rule ID SEVERITY CHECK key=value ...`` rows.

    ``relation`` rows intentionally remain in this file for gen_sde.py and
    are ignored here; this keeps the process-topology and DRC contracts next
    to one another without conflating their meanings.
    """
    rules: List[Rule] = []
    for number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        clean = raw_line.split("%", 1)[0].strip()
        if not clean or clean.lower().startswith("relation"):
            continue
        parts = clean.split()
        if len(parts) < 4 or parts[0].lower() != "rule":
            raise ValueError(f"Rule line {number}: use 'rule ID SEVERITY CHECK key=value ...'.")
        options: Dict[str, str] = {}
        for item in parts[4:]:
            if "=" not in item:
                raise ValueError(f"Rule line {number}: option '{item}' must use key=value.")
            key, value = item.split("=", 1)
            options[key.lower()] = value
        severity = parts[2].upper()
        if severity not in {"ERROR", "WARNING", "INFO"}:
            raise ValueError(f"Rule line {number}: severity must be ERROR, WARNING, or INFO.")
        rules.append(Rule(parts[1], severity, parts[3].lower(), options, number))
    return rules


def rects(layout: Dict[int, List[Rect]], layer: int) -> List[Rect]:
    return [rect for rect in layout.get(layer, []) if rect.area > EPS]


def overlap_area(left: Rect, right: Rect) -> float:
    return max(0.0, min(left.x2, right.x2) - max(left.x1, right.x1)) * max(0.0, min(left.y2, right.y2) - max(left.y1, right.y1))


def enclosure(outer: Rect, inner: Rect) -> float | None:
    if outer.x1 > inner.x1 + EPS or outer.y1 > inner.y1 + EPS or outer.x2 < inner.x2 - EPS or outer.y2 < inner.y2 - EPS:
        return None
    return min(inner.x1 - outer.x1, inner.y1 - outer.y1, outer.x2 - inner.x2, outer.y2 - inner.y2)


def spacing(first: Rect, second: Rect, axis: str) -> float | None:
    """Return edge spacing only when the perpendicular projections overlap."""
    if axis == "x":
        if min(first.y2, second.y2) - max(first.y1, second.y1) <= EPS:
            return None
        return max(second.x1 - first.x2, first.x1 - second.x2, 0.0)
    if min(first.x2, second.x2) - max(first.x1, second.x1) <= EPS:
        return None
    return max(second.y1 - first.y2, first.y1 - second.y2, 0.0)


def compare(measured: float, operator: str, limit: float) -> bool:
    if operator == ">=":
        return measured >= limit - EPS
    if operator == "<=":
        return measured <= limit + EPS
    raise ValueError(f"Unsupported comparison operator: {operator}")


def format_number(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.6f}"


class DRC:
    def __init__(self, layout: Dict[int, List[Rect]], stack, params: Dict[str, object], rules: Iterable[Rule]) -> None:
        self.layout, self.stack, self.params, self.rules = layout, stack, params, list(rules)
        self.resolver = ExpressionResolver(params)
        # Reuse gen_sde's exact row/spacer calculations.  This makes MD/BMD
        # classification in DRC match the generated 3-D device.
        self.builder = Builder(layout, stack, params, parse_relations(None))
        self.builder.build_device_stack()

    def number(self, rule: Rule, key: str) -> float:
        if key not in rule.options:
            raise ValueError(f"{rule.rule_id}: missing {key}=...")
        return float(self.resolver.resolve(rule.options[key]))

    @staticmethod
    def layer(rule: Rule, key: str) -> int:
        if key not in rule.options:
            raise ValueError(f"{rule.rule_id}: missing {key}=...")
        return int(float(rule.options[key]))

    def finding(self, rule: Rule, subject: str, measured: float, operator: str, limit: float, detail: str) -> Finding:
        return Finding("PASS" if compare(measured, operator, limit) else rule.severity, rule, subject, measured, operator, limit, detail)

    def min_width(self, rule: Rule) -> List[Finding]:
        layer, axis, limit = self.layer(rule, "layer"), rule.options.get("axis", "x").lower(), self.number(rule, "min")
        if axis not in {"x", "y"}:
            raise ValueError(f"{rule.rule_id}: axis must be x or y.")
        result = []
        for rect in rects(self.layout, layer):
            measured = rect.x2 - rect.x1 if axis == "x" else rect.y2 - rect.y1
            result.append(self.finding(rule, f"L{layer} line={rect.line}", measured, ">=", limit, f"{axis}-dimension"))
        return result or [Finding("INFO", rule, f"L{layer}", None, ">=", limit, "No non-zero-area shapes.")]

    def min_area(self, rule: Rule) -> List[Finding]:
        layer, limit = self.layer(rule, "layer"), self.number(rule, "min")
        return [self.finding(rule, f"L{layer} line={rect.line}", rect.area, ">=", limit, "rectangle area") for rect in rects(self.layout, layer)]

    def min_spacing(self, rule: Rule) -> List[Finding]:
        layer, axis, limit = self.layer(rule, "layer"), rule.options.get("axis", "x").lower(), self.number(rule, "min")
        shapes, result = rects(self.layout, layer), []
        for index, first in enumerate(shapes):
            for second in shapes[index + 1:]:
                measured = spacing(first, second, axis)
                if measured is not None:
                    result.append(self.finding(rule, f"L{layer} lines={first.line},{second.line}", measured, ">=", limit, f"{axis}-edge spacing"))
        return result or [Finding("INFO", rule, f"L{layer}", None, ">=", limit, "No comparable shape pair.")]

    def enclosure(self, rule: Rule) -> List[Finding]:
        outer_layer, inner_layer, limit = self.layer(rule, "outer"), self.layer(rule, "inner"), self.number(rule, "min")
        outers, result = rects(self.layout, outer_layer), []
        for inner in rects(self.layout, inner_layer):
            candidates = [(enclosure(outer, inner), outer) for outer in outers]
            valid = [(margin, outer) for margin, outer in candidates if margin is not None]
            if not valid:
                result.append(Finding(rule.severity, rule, f"L{inner_layer} line={inner.line}", None, ">=", limit, f"Not enclosed by any L{outer_layer} shape."))
                continue
            measured, outer = max(valid, key=lambda pair: pair[0])
            result.append(self.finding(rule, f"L{outer_layer} line={outer.line}, L{inner_layer} line={inner.line}", measured, ">=", limit, "minimum XY enclosure"))
        return result

    def z_landing(self, rule: Rule) -> List[Finding]:
        via, lower, upper, limit = self.layer(rule, "layer"), self.layer(rule, "lower"), self.layer(rule, "upper"), self.number(rule, "min")
        via_spec, lower_spec, upper_spec = self.stack[via], self.stack[lower], self.stack[upper]
        lower_overlap = min(via_spec.z1, lower_spec.z1) - max(via_spec.z0, lower_spec.z0)
        upper_overlap = min(via_spec.z1, upper_spec.z1) - max(via_spec.z0, upper_spec.z0)
        measured = min(lower_overlap, upper_overlap)
        return [self.finding(rule, f"L{via} between L{lower}/L{upper}", measured, ">=", limit, "minimum Z landing overlap; zero is a valid shared face")]

    def contact_recipe(self, rule: Rule) -> List[Finding]:
        layer, sd_name, gate_layer = self.layer(rule, "layer"), rule.options["sd"].lower(), self.layer(rule, "gate")
        side = rule.options.get("side", "top").lower()
        spec, gates = self.stack[layer], [gate for gate in rects(self.layout, gate_layer)]
        planned = self.builder.sd_plan[sd_name]
        result: List[Finding] = []
        for mask in rects(self.layout, layer):
            sd_hits = [(sd_rect, z0, z1) for _, sd_rect, z0, z1 in planned if overlap_area(mask, sd_rect) > EPS]
            gate_hits = [gate for gate in gates if overlap_area(mask, gate) > EPS]
            kind = "sd" if sd_hits else "gate" if gate_hits else "other"
            if kind == "sd":
                if side == "top":
                    measured = min(min(spec.z1, z1) - max(spec.z0, z0) for _, z0, z1 in sd_hits)
                else:
                    measured = min(min(spec.z1, z1) - max(spec.z0, z0) for _, z0, z1 in sd_hits)
                result.append(self.finding(rule, f"L{layer} line={mask.line} ({kind})", measured, ">=", 0.0, "S/D cap/landing Z contact"))
            elif kind == "gate":
                gate_spec = self.stack[gate_layer]
                key = "gate_z0" if side == "top" else "gate_z1"
                contact_edge = self.number(rule, key)
                measured = contact_edge - gate_spec.z1 if side == "top" else gate_spec.z0 - contact_edge
                result.append(self.finding(rule, f"L{layer} line={mask.line} ({kind})", measured, ">=", 0.0, "gate-extension edge; zero means face-aligned"))
            else:
                result.append(Finding("INFO", rule, f"L{layer} line={mask.line} (other)", None, ">=", None, "No planned S/D or gate overlap; ordinary contact."))
        return result

    def run(self) -> List[Finding]:
        handlers: Dict[str, Callable[[Rule], List[Finding]]] = {
            "min_width": self.min_width,
            "min_area": self.min_area,
            "min_spacing": self.min_spacing,
            "enclosure": self.enclosure,
            "z_landing": self.z_landing,
            "contact_recipe": self.contact_recipe,
        }
        output: List[Finding] = []
        for rule in self.rules:
            if rule.check not in handlers:
                raise ValueError(f"{rule.rule_id}: unsupported check '{rule.check}'.")
            output.extend(handlers[rule.check](rule))
        return output


def write_report(path: Path, layout_path: Path, findings: List[Finding]) -> None:
    counts = {status: sum(item.status == status for item in findings) for status in ("ERROR", "WARNING", "INFO", "PASS")}
    lines = [
        "AutoLDM DRC Report",
        f"Layout: {layout_path.name}",
        "Unit: um",
        f"Summary: ERROR={counts['ERROR']} WARNING={counts['WARNING']} INFO={counts['INFO']} PASS={counts['PASS']}",
        "",
    ]
    for item in findings:
        lines.append(f"{item.status:<7} {item.rule.rule_id:<20} {item.subject}")
        if item.measured is not None and item.limit is not None:
            margin = item.measured - item.limit if item.operator == ">=" else item.limit - item.measured
            lines.append(f"        measured={format_number(item.measured)}  requirement={item.operator}{format_number(item.limit)}  margin={margin:+.6f}")
        lines.append(f"        {item.detail}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Run AutoLDM rectangle and 3-D contact DRC checks.")
    parser.add_argument("layout", nargs="?", type=Path, default=root / "INPUT_MODEL" / "test_gds.txt")
    parser.add_argument("params", nargs="?", type=Path, default=root / "INPUT_MODEL" / "test_params.txt")
    parser.add_argument("stack", nargs="?", type=Path, default=root / "INPUT_MODEL" / "test_stacked.txt")
    parser.add_argument("rules", nargs="?", type=Path, default=root / "INPUT_MODEL" / "test_design_rules.txt")
    parser.add_argument("-o", "--output", type=Path, default=root / "OUTPUT" / "test_drc_report.txt")
    args = parser.parse_args()
    params = parse_params(str(args.params))
    stack = parse_stack(str(args.stack), params)
    findings = DRC(parse_layout(str(args.layout)), stack, params, parse_rules(args.rules)).run()
    write_report(args.output, args.layout, findings)
    print(f"DRC report written: {args.output}")
    return 2 if any(item.status == "ERROR" for item in findings) else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"DRC error: {exc}", file=sys.stderr)
        sys.exit(1)
