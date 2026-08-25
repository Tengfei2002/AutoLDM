"""Generate a validated Sentaurus SDE command file from an AutoLDM layout txt.

The input contract deliberately separates 2-D masks, process stack, device
parameters and layer relations.  It never interprets labels as connectivity.
"""

from __future__ import annotations

import argparse
import ast
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple


EPS = 1e-9
METALS = {"tungsten", "copper", "metal", "aluminum"}
DOMAIN_MARGIN_XY = 0.020
DOMAIN_MARGIN_Z = 0.020
MIN_FEATURE_SIZE = 0.001
MESH_ENGINE = "snmesh"
MESH_OPTIONS = "-a -c boxmethod"
SPECIAL_ROLES = {
    "domain_mask", "gate_mask", "device_marker", "md_contact_mask",
    "backside_sd_landing", "vertical_interconnect", "via", "backside_via",
}


def safe_name(value: object) -> str:
    value = "NONE" if value in (None, "", "None") else str(value)
    return re.sub(r"[^A-Za-z0-9_]", "_", value)


def label_suffix(value: object) -> Optional[str]:
    """Return the final underscore-delimited field of a non-empty layout label."""
    if value in (None, "", "None"):
        return None
    suffix = str(value).strip().rsplit("_", 1)[-1]
    return suffix or None


def is_via_role(role: str) -> bool:
    """Return whether a stack role classifies a region as a via."""
    return "via" in role.strip().lower().split("_")


def is_r_contact_excluded_role(role: str) -> bool:
    """Return whether an R-region is an internal conductor, not a terminal."""
    normalized = role.strip().lower()
    return is_via_role(normalized) or normalized in {"gate", "gate_mask"}


def fmt(value: float) -> str:
    return f"{float(value):.6f}"


class ExpressionResolver:
    """Small, safe arithmetic evaluator for $name and @<expr>@ syntax."""

    _var = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)|@([A-Za-z_][A-Za-z0-9_]*)@")
    _expr = re.compile(r"@<([^<>]+)>@")

    def __init__(self, values: Optional[Dict[str, object]] = None):
        self.values: Dict[str, object] = {}
        for key, value in (values or {}).items():
            self.set(key, value)

    def set(self, key: str, value: object) -> None:
        self.values[key] = value
        self.values[key.lower()] = value

    def _number(self, expression: str) -> float:
        tree = ast.parse(expression, mode="eval")

        def visit(node: ast.AST) -> float:
            if isinstance(node, ast.Expression):
                return visit(node.body)
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                return float(node.value)
            if isinstance(node, ast.Name):
                key = node.id if node.id in self.values else node.id.lower()
                if key not in self.values:
                    raise KeyError(node.id)
                return float(self.values[key])
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                return visit(node.operand) if isinstance(node.op, ast.UAdd) else -visit(node.operand)
            if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
                left, right = visit(node.left), visit(node.right)
                if isinstance(node.op, ast.Add):
                    return left + right
                if isinstance(node.op, ast.Sub):
                    return left - right
                if isinstance(node.op, ast.Mult):
                    return left * right
                return left / right
            raise ValueError(f"Unsafe numeric expression: {expression}")

        return visit(tree)

    def resolve(self, raw: str) -> object:
        text = str(raw).strip()
        lower = text.lower()
        if lower in {"true", "false"}:
            return lower == "true"

        def replace_expression(match: re.Match) -> str:
            return str(self._number(match.group(1)))

        text = self._expr.sub(replace_expression, text)

        def replace_variable(match: re.Match) -> str:
            key = match.group(1) or match.group(2)
            if key not in self.values and key.lower() not in self.values:
                raise KeyError(key)
            return str(self.values.get(key, self.values.get(key.lower())))

        text = self._var.sub(replace_variable, text)
        try:
            return float(text)
        except ValueError:
            if re.fullmatch(r"[0-9eE+\-*/(). _A-Za-z]+", text):
                try:
                    return self._number(text)
                except (KeyError, ValueError, ZeroDivisionError, SyntaxError):
                    pass
            return text


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
    def area(self) -> float:
        return max(0.0, self.x2 - self.x1) * max(0.0, self.y2 - self.y1)

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2

    def overlaps(self, other: "Rect") -> bool:
        return min(self.x2, other.x2) - max(self.x1, other.x1) > EPS and min(self.y2, other.y2) - max(self.y1, other.y1) > EPS

    def expanded(self, margin: float) -> "Rect":
        return Rect(self.x1 - margin, self.y1 - margin, self.x2 + margin, self.y2 + margin, self.layer, self.label, self.line)


@dataclass(frozen=True)
class LayerSpec:
    layer: int
    name: str
    role: str
    enabled: bool
    z0: float
    z1: float
    material: str
    dielectric: str
    policy: str


@dataclass
class Region:
    name: str
    material: str
    role: str
    body: str
    bbox: Tuple[float, float, float, float, float, float]
    line_index: int
    net_name: Optional[str] = None


@dataclass
class Report:
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    counts: Dict[str, int] = field(default_factory=dict)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def error(self, message: str) -> None:
        self.errors.append(message)

    def text(self) -> str:
        lines = ["AutoLDM geometry preflight"]
        lines += [f"WARNING: {x}" for x in self.warnings]
        lines += [f"ERROR: {x}" for x in self.errors]
        lines += [f"COUNT {key}={value}" for key, value in sorted(self.counts.items())]
        return "\n".join(lines)


def parse_params(path: str) -> Dict[str, object]:
    raw: Dict[str, str] = {}
    for number, line in enumerate(open(path, encoding="utf-8"), 1):
        clean = line.split("%", 1)[0].strip()
        if not clean:
            continue
        if "=" not in clean:
            raise ValueError(f"Invalid parameter line {number}: {line.strip()}")
        key, value = (part.strip() for part in clean.split("=", 1))
        raw[key] = value
    resolver, resolved, pending = ExpressionResolver(), {}, dict(raw)
    while pending:
        progressed = False
        for key in list(pending):
            try:
                value = resolver.resolve(pending[key])
            except KeyError:
                continue
            resolved[key] = value
            resolver.set(key, value)
            pending.pop(key)
            progressed = True
        if not progressed:
            raise ValueError("Unresolved parameters: " + ", ".join(sorted(pending)))
    return resolved


def parse_stack(path: str, params: Dict[str, object]) -> Dict[int, LayerSpec]:
    """Parse layer rows plus local ``define name = expression`` macros.

    Stack macros are resolved after device parameters and then injected into
    ``params`` as read-only inputs for the geometry builder.  Thus one stack
    variable can drive both layer Z values and a dependent recipe decision
    such as the safe gate-contact start height.
    """
    definitions: Dict[str, str] = {}
    layer_lines: List[Tuple[int, str]] = []
    for number, line in enumerate(open(path, encoding="utf-8"), 1):
        clean = line.split("%", 1)[0].strip()
        if not clean:
            continue
        if clean.lower().startswith("define"):
            match = re.fullmatch(r"define\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)", clean, re.IGNORECASE)
            if not match:
                raise ValueError(f"Stack line {number}: use 'define name = expression'.")
            key, value = match.group(1), match.group(2).strip()
            if key in definitions or key in params:
                raise ValueError(f"Stack line {number}: duplicate definition '{key}'.")
            definitions[key] = value
            continue
        layer_lines.append((number, clean))

    resolver = ExpressionResolver(params)
    pending = dict(definitions)
    while pending:
        progressed = False
        for key in list(pending):
            try:
                value = resolver.resolve(pending[key])
            except KeyError:
                continue
            params[key] = value
            resolver.set(key, value)
            pending.pop(key)
            progressed = True
        if not progressed:
            raise ValueError("Unresolved stack definitions: " + ", ".join(sorted(pending)))

    specs: Dict[int, LayerSpec] = {}
    for number, clean in layer_lines:
        parts = clean.split()
        if len(parts) != 9:
            raise ValueError(f"Stack line {number} needs 9 fields; got: {clean}")
        layer, name, role, enabled, z0, z1, material, dielectric, policy = parts
        z0v, z1v = float(resolver.resolve(z0)), float(resolver.resolve(z1))
        if z1v - z0v <= EPS:
            raise ValueError(f"Stack line {number}: z_max must exceed z_min")
        spec = LayerSpec(int(layer), name, role.lower(), str(resolver.resolve(enabled)).lower() == "true", z0v, z1v, material, dielectric, policy.lower())
        if spec.layer in specs:
            raise ValueError(f"Duplicate stack layer {spec.layer}")
        specs[spec.layer] = spec
    return specs


def parse_layout(path: str) -> Dict[int, List[Rect]]:
    layout: Dict[int, List[Rect]] = {}
    for number, line in enumerate(open(path, encoding="utf-8"), 1):
        clean = line.lstrip("\ufeff").split("%", 1)[0].strip()
        if not clean:
            continue
        parts = clean.split()
        if len(parts) < 5:
            raise ValueError(f"Layout line {number} needs x1 y1 x2 y2 layer [label]")
        x1, y1, x2, y2 = map(float, parts[:4])
        rect = Rect(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2), int(float(parts[4])), parts[5] if len(parts) > 5 else "None", number)
        layout.setdefault(rect.layer, []).append(rect)
    return layout


def parse_relations(path: Optional[str]) -> Dict[Tuple[str, str], str]:
    relations: Dict[Tuple[str, str], str] = {}
    if not path or not os.path.exists(path):
        return relations
    for number, line in enumerate(open(path, encoding="utf-8"), 1):
        clean = line.split("%", 1)[0].strip()
        if not clean:
            continue
        parts = clean.split()
        # A design-rules file may additionally contain ``rule`` directives
        # consumed by gen_drc_report.py.  SDE only needs the topology
        # relations, so deliberately leaves those executable DRC checks to
        # the dedicated report generator.
        if parts[0].lower() == "rule":
            continue
        if len(parts) != 4 or parts[0].lower() != "relation":
            raise ValueError(f"Rule line {number} must be: relation source_role target_role action")
        relations[(parts[1].lower(), parts[2].lower())] = parts[3].lower()
        relations[(parts[2].lower(), parts[1].lower())] = parts[3].lower()
    return relations


def sheet_ranges(value: object) -> List[Tuple[float, float]]:
    result = []
    for item in str(value).split(","):
        left, right = item.strip().split(":", 1)
        z0, z1 = float(left), float(right)
        if z1 - z0 <= EPS:
            raise ValueError(f"Invalid sheet range: {item}")
        result.append((z0, z1))
    return result


class SDEWriter:
    def __init__(self, c_variant: bool = False, metal_nets: Optional[Iterable[str]] = None) -> None:
        self.c_variant = c_variant
        self.metal_nets = set(metal_nets or [])
        self.metal_index = 0
        variant = "C" if c_variant else "R"
        self.lines = [f"; Generated by AutoLDM structural gen_sde.py ({variant} variant)", "(sde:clear)", '(sdegeo:set-default-boolean "ABA")']
        self.index = 0
        self.regions: List[Region] = []

    def comment(self, text: str) -> None:
        self.lines.append("; " + text)

    def metal_net_name(self, label: object) -> str:
        """Use the final field only when it was discovered among layout labels."""
        net_name = self.c_label_net_name(label)
        if net_name is not None:
            return net_name
        self.metal_index += 1
        return f"Metal_{self.metal_index}"

    def c_label_net_name(self, label: object) -> Optional[str]:
        """Return a recognized C net suffix, without allocating a fallback name."""
        suffix = label_suffix(label)
        return safe_name(suffix) if suffix in self.metal_nets else None

    def metal_region_name(self, region_name: str, label: object) -> str:
        """Use C net names but preserve complete R terminal labels as suffixes."""
        value = "" if label in (None, "", "None") else str(label).strip()
        if self.c_variant:
            return self.metal_net_name(value)
        if not value:
            return region_name
        clean_region, clean_label = safe_name(region_name), safe_name(value)
        return clean_region if clean_region.endswith(f"_{clean_label}") else f"{clean_region}_{clean_label}"

    def region_name(self, name: str, material: str, role: str, metal_display_name: Optional[str] = None) -> str:
        """Keep device names; name metals from their layout terminal and variant."""
        if self.c_variant and role == "dielectric":
            return ""
        if material.lower() in METALS and metal_display_name is not None:
            return metal_display_name
        return name

    def rename_region(self, region: Region, name: str) -> None:
        """Replace the emitted SDE region name while retaining its body and material."""
        if region.name == name:
            return
        old_token = f'"{region.name}"'
        line = self.lines[region.line_index]
        prefix, separator, suffix = line.rpartition(old_token)
        if not separator:
            raise ValueError(f"Cannot rename emitted region {region.body}: {region.name}")
        self.lines[region.line_index] = f'{prefix}"{name}"{suffix}'
        region.name = name

    def cuboid(self, name: str, rect: Rect, z0: float, z1: float, material: str, role: str, metal_label: object = None) -> Region:
        if rect.area <= EPS or z1 - z0 <= EPS:
            raise ValueError(f"Degenerate cuboid {name}")
        body = f"body_{self.index}"
        self.index += 1
        is_metal = material.lower() in METALS
        c_net_name = self.c_label_net_name(metal_label) if self.c_variant and is_metal else None
        metal_display_name = self.metal_region_name(name, metal_label) if is_metal else None
        emitted_name = self.region_name(name, material, role, metal_display_name)
        line_index = len(self.lines)
        self.lines.append(f'(define {body} (sdegeo:create-cuboid (position {fmt(rect.x1)} {fmt(rect.y1)} {fmt(z0)}) (position {fmt(rect.x2)} {fmt(rect.y2)} {fmt(z1)}) "{material}" "{emitted_name}"))')
        region = Region(emitted_name, material, role, body, (rect.x1, rect.y1, z0, rect.x2, rect.y2, z1), line_index, c_net_name)
        self.regions.append(region)
        return region

    def protected_cuboid(self, name: str, rect: Rect, z0: float, z1: float, material: str, role: str) -> Region:
        """Create a new solid without cutting an already-created device solid.

        ``BAB`` is Sentaurus' "old replaces new" Boolean mode.  It is used
        for contact masks and via masks: a layout rectangle may geometrically
        overlap a semiconductor core, but it must not erase that core merely
        because its mask was emitted later in the command file.
        """
        self.lines.append('(sdegeo:set-default-boolean "BAB")')
        region = self.cuboid(name, rect, z0, z1, material, role)
        self.lines.append('(sdegeo:set-default-boolean "ABA")')
        return region

    def octagonal_prism(self, name: str, rect: Rect, z0: float, z1: float, chamfer: float, material: str, role: str) -> Region:
        """Create the S/D with an octagonal *Y-Z* vertical cross-section.

        Transport is along X in this layout.  The top-view X-Y footprint must
        therefore remain the layout rectangle.  Four edges parallel to X are
        chamfered, which creates the requested eight-facet Y-Z S/D profile
        without changing the X-Y mask into an octagon.
        """
        c = min(chamfer, (rect.y2 - rect.y1) / 3, (z1 - z0) / 3)
        if c <= EPS:
            return self.cuboid(name, rect, z0, z1, material, role)
        region = self.cuboid(name, rect, z0, z1, material, role)
        xmid = (rect.x1 + rect.x2) / 2
        transport_edges = " ".join(
            f"(car (find-edge-id (position {fmt(xmid)} {fmt(y)} {fmt(z)})))"
            for y, z in ((rect.y1, z0), (rect.y2, z0), (rect.y2, z1), (rect.y1, z1))
        )
        self.lines.append(f"(sdegeo:chamfer (list {transport_edges}) {fmt(c)} #t)")
        return region

    def subtract(self, target: Region, cutter: Region) -> None:
        self.lines.append(f"(sdegeo:bool-subtract (list {target.body} {cutter.body}))")

    def unite(self, regions: Iterable[Region]) -> None:
        bodies = [region.body for region in regions]
        if len(bodies) > 1:
            self.lines.append("(sdegeo:bool-unite (list " + " ".join(bodies) + "))")

    def write(self, path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(self.lines) + "\n")


class Builder:
    def __init__(self, layout: Dict[int, List[Rect]], stack: Dict[int, LayerSpec], params: Dict[str, object], relations: Dict[Tuple[str, str], str], c_variant: bool = False):
        self.layout, self.stack, self.p, self.relations = layout, stack, params, relations
        metal_nets = {
            suffix
            for rects in layout.values()
            for rect in rects
            if rect.area > EPS
            for suffix in [label_suffix(rect.label)]
            if suffix is not None
        }
        self.writer, self.report = SDEWriter(c_variant=c_variant, metal_nets=metal_nets), Report()
        self.sd: Dict[str, List[Tuple[Rect, Region]]] = {"upper_sd": [], "lower_sd": []}
        self.sd_plan: Dict[str, List[Tuple[str, Rect, float, float]]] = {"upper_sd": [], "lower_sd": []}
        self.metal: List[Region] = []
        self.gates: List[Tuple[Rect, Region]] = []

    def value(self, key: str, default: Optional[object] = None) -> object:
        if key in self.p:
            return self.p[key]
        if default is not None:
            return default
        raise KeyError(f"Missing required parameter: {key}")

    def enabled(self, role: str) -> List[LayerSpec]:
        return [spec for spec in self.stack.values() if spec.enabled and spec.role == role]

    def boundary(self) -> Rect:
        candidates = [rect for layer, rects in self.layout.items() for rect in rects if rect.area > EPS and self.stack.get(layer, LayerSpec(0, "", "", False, 0, 0, "", "", "")).role == "domain_mask"]
        if not candidates:
            candidates = [rect for rects in self.layout.values() for rect in rects if rect.area > EPS]
            self.report.warn("No domain_mask geometry; using all valid layout rectangles as domain extent.")
        return Rect(min(x.x1 for x in candidates), min(x.y1 for x in candidates), max(x.x2 for x in candidates), max(x.y2 for x in candidates), 0, "DOMAIN", 0)

    def preflight(self) -> None:
        for layer, rects in self.layout.items():
            if layer not in self.stack:
                self.report.error(f"Layout layer {layer} has no stack classification.")
            for rect in rects:
                if rect.area <= EPS:
                    self.report.warn(f"Ignoring zero-area layout shape at line {rect.line}, layer {layer}.")
        for spec in self.stack.values():
            self.report.counts[f"layer_{spec.layer}_{spec.role}"] = len(self.layout.get(spec.layer, []))
        self.validate_controlled_z_overlaps()
        self.validate_md_recipe()

    def live_specs(self, role: str) -> List[LayerSpec]:
        return [spec for spec in self.enabled(role) if any(rect.area > EPS for rect in self.layout.get(spec.layer, []))]

    @staticmethod
    def z_overlap(first: LayerSpec, second: LayerSpec) -> float:
        return min(first.z1, second.z1) - max(first.z0, second.z0)

    def validate_controlled_z_overlaps(self) -> None:
        """Reject a stack edit that turns a declared metal landing into a Z gap."""
        checked = set()
        for (source, target), action in self.relations.items():
            key = tuple(sorted((source, target)))
            if action != "controlled_union" or key in checked:
                continue
            checked.add(key)
            sources, targets = self.live_specs(source), self.live_specs(target)
            if not sources or not targets:
                continue
            if not any(self.z_overlap(left, right) >= -EPS for left in sources for right in targets):
                self.report.error(f"Declared controlled_union {source} <-> {target} has a Z gap.")

    def validate_md_recipe(self) -> None:
        md_specs, via_specs = self.live_specs("md_contact_mask"), self.live_specs("via")
        if md_specs:
            gate_floor = max(z1 for _, z1 in sheet_ranges(self.value("upper_sheet_z"))) + float(self.value("high_k_thickness"))
            gate_md_z0 = float(self.value("md_gate_z0"))
            for spec in md_specs:
                if gate_md_z0 < gate_floor - EPS:
                    self.report.error(f"md_gate_z0={fmt(gate_md_z0)} cuts upper channel/high-k; it must be at least {fmt(gate_floor)}.")
                if gate_md_z0 >= spec.z1 - EPS:
                    self.report.error("md_gate_z0 must remain below the MD top Z.")
                for mask in self.layout.get(spec.layer, []):
                    if mask.area <= EPS:
                        continue
                    if not any(mask.overlaps(via_mask) and self.z_overlap(spec, via_spec) >= -EPS for via_spec in via_specs for via_mask in self.layout.get(via_spec.layer, []) if via_mask.area > EPS):
                        self.report.error(f"MD line {mask.line} has no overlapping V0 landing in X/Y/Z.")

        bmd_specs = self.live_specs("backside_sd_landing")
        if not bmd_specs:
            return
        bmd_gate_z1 = float(self.value("bmd_gate_z1"))
        gate_z0 = min(spec.z0 for spec in self.enabled("gate_mask"))
        for spec in bmd_specs:
            if bmd_gate_z1 <= spec.z0 + EPS:
                self.report.error("bmd_gate_z1 must remain above the BMD bottom Z.")
            if bmd_gate_z1 > gate_z0 + EPS:
                self.report.error(f"bmd_gate_z1={fmt(bmd_gate_z1)} enters the gate; it must not exceed gate_z0={fmt(gate_z0)}.")

    def rows(self, gates: List[Rect]) -> List[List[Rect]]:
        rows: List[List[Rect]] = []
        for gate in sorted(gates, key=lambda item: (item.cy, item.x1)):
            for row in rows:
                ref = row[0]
                if min(ref.y2, gate.y2) - max(ref.y1, gate.y1) > EPS:
                    row.append(gate)
                    break
            else:
                rows.append([gate])
        return [sorted(row, key=lambda item: item.x1) for row in rows]

    def row_boundary(self, row: List[Rect]) -> Rect:
        """Return the domain extent for this gate row, not the whole cell."""
        row_y1 = min(gate.y1 for gate in row)
        row_y2 = max(gate.y2 for gate in row)
        domain_rects = [
            rect
            for spec in self.enabled("domain_mask")
            for rect in self.layout.get(spec.layer, [])
            if rect.area > EPS and min(rect.y2, row_y2) - max(rect.y1, row_y1) > -EPS
        ]
        if not domain_rects:
            return self.boundary()
        return Rect(
            min(rect.x1 for rect in domain_rects),
            min(rect.y1 for rect in domain_rects),
            max(rect.x2 for rect in domain_rects),
            max(rect.y2 for rect in domain_rects),
            0,
            "ROW_DOMAIN",
            0,
        )

    def build_domain_dielectric(self) -> None:
        boundary = self.boundary()
        margin_xy, margin_z = DOMAIN_MARGIN_XY, DOMAIN_MARGIN_Z
        z0 = min(spec.z0 for spec in self.stack.values() if spec.enabled) - margin_z
        z1 = max(spec.z1 for spec in self.stack.values() if spec.enabled) + margin_z
        envelope = boundary.expanded(margin_xy)
        self.writer.comment("Dielectric envelope is created first; later solids replace it under ABA.")
        self.writer.cuboid("Dielectric_Envelope", envelope, z0, z1, "SiO2", "dielectric")

    def build_device_stack(self) -> None:
        """Create gate-stack solids and record, but do not yet emit, S/D EPI.

        SD-EPI is intentionally emitted after MD/BMD.  With the already-used
        ABA Boolean rule, the later octagonal SD body naturally replaces the
        MD volume that it occupies.  No XX mode or explicit Boolean CSG is
        required.
        """
        gate_specs = self.enabled("gate_mask")
        if not gate_specs:
            return
        gate_spec = gate_specs[0]
        gates = [rect for rect in self.layout.get(gate_spec.layer, []) if rect.area > EPS]
        if not gates:
            return
        high_k = float(self.value("high_k_thickness", 0.002))
        spacer = float(self.value("spacer_length", 0.005))
        width = float(self.value("sheet_width"))
        sheets = {"upper": sheet_ranges(self.value("upper_sheet_z")), "lower": sheet_ranges(self.value("lower_sheet_z"))}
        for row_id, row in enumerate(self.rows(gates)):
            boundary = self.row_boundary(row)
            segments: List[Tuple[float, float]] = []
            for index in range(len(row) + 1):
                left = boundary.x1 if index == 0 else row[index - 1].x2 + spacer
                right = boundary.x2 if index == len(row) else row[index].x1 - spacer
                if right - left <= MIN_FEATURE_SIZE:
                    self.report.error(f"Gate row {row_id}: S/D segment {index} is below min_feature_size.")
                segments.append((left, right))
            for tier in ("upper", "lower"):
                material = str(self.value(f"{tier}_sd_material"))
                sd_width = float(self.value("sd_width", width))
                z0 = min(a for a, _ in sheets[tier]) - float(self.value("sd_overgrowth_z_down", 0.006))
                z1 = max(b for _, b in sheets[tier]) + float(self.value("sd_overgrowth_z_up", 0.006))
                for index, (x0, x1) in enumerate(segments):
                    center = row[min(max(index - 1, 0), len(row) - 1)].cy
                    rect = Rect(x0, center - sd_width / 2, x1, center + sd_width / 2, -1, f"R{row_id}_SD{index}", 0)
                    if rect.area <= EPS:
                        continue
                    self.sd_plan[f"{tier}_sd"].append((f"R{row_id}_SD{index}", rect, z0, z1))
            for gate_id, gate in enumerate(row):
                token = f"R{row_id}_G{gate_id}"
                gate_region = self.writer.cuboid(f"Gate_{token}", gate, gate_spec.z0, gate_spec.z1, gate_spec.material, "gate", metal_label=gate.label)
                self.metal.append(gate_region)
                self.gates.append((gate, gate_region))
                y0, y1 = gate.cy - width / 2, gate.cy + width / 2
                wall_z0 = min(z0 for tier_sheets in sheets.values() for z0, _ in tier_sheets) - high_k
                wall_z1 = max(z1 for tier_sheets in sheets.values() for _, z1 in tier_sheets) + high_k
                wall_y0, wall_y1 = y0 - high_k, y1 + high_k
                # One continuous inner-spacer wall is created at each gate
                # side.  The channel bodies emitted below cut four through
                # holes, keeping the exterior Si3N4 sidewall connected.
                for side, wall in (
                    ("left", Rect(segments[gate_id][1], wall_y0, gate.x1, wall_y1, -1, token, 0)),
                    ("right", Rect(gate.x2, wall_y0, segments[gate_id + 1][0], wall_y1, -1, token, 0)),
                ):
                    if wall.area <= EPS:
                        self.report.error(f"Si3N4 {side} wall at {token} has no positive footprint.")
                    else:
                        self.writer.cuboid(f"SpacerWall_{token}_{side}", wall, wall_z0, wall_z1, str(self.value("spacer_material")), "inner_spacer_wall")
                for tier in ("upper", "lower"):
                    material = str(self.value(f"{tier}_channel_material"))
                    channel = Rect(segments[gate_id][1], y0, segments[gate_id + 1][0], y1, -1, token, 0)
                    if channel.area <= EPS:
                        self.report.error(f"{tier} channel at {token} has no positive footprint.")
                        continue
                    for sheet_id, (z0, z1) in enumerate(sheets[tier]):
                        # Gate -> high-k -> spacer -> channel ordering deliberately
                        # leaves a continuous GAA-like high-k shell only under
                        # gate and cuts one aperture in each Si3N4 wall.
                        highk_rect = Rect(gate.x1, y0 - high_k, gate.x2, y1 + high_k, -1, token, 0)
                        self.writer.cuboid(f"HighK_{tier}_{token}_{sheet_id}", highk_rect, z0 - high_k, z1 + high_k, str(self.value("high_k_material")), "high_k")
                        self.writer.cuboid(f"Channel_{tier}_{token}_{sheet_id}", channel, z0, z1, material, f"{tier}_channel")

    def planned_sd_overlaps(self, tier: str, mask: Rect) -> bool:
        return any(rect.overlaps(mask) for _, rect, _, _ in self.sd_plan[tier])

    def build_sd_epi(self) -> None:
        """Emit octagonal S/D last so it replaces overlapped contact metal."""
        for tier in ("upper", "lower"):
            material = str(self.value(f"{tier}_sd_material"))
            for token, rect, z0, z1 in self.sd_plan[f"{tier}_sd"]:
                region = self.writer.octagonal_prism(
                    f"SD_{tier}_{token}", rect, z0, z1,
                    float(self.value("sd_chamfer")), material, f"{tier}_sd",
                )
                self.sd[f"{tier}_sd"].append((rect, region))

    def build_frontside_md(self) -> None:
        """Emit MD before SD-EPI; later SD naturally cuts its overlap under ABA."""
        role, target = "md_contact_mask", "upper_sd"
        specs = self.enabled(role)
        if not specs:
            return
        if self.relations.get((role, target)) != "cap_shell":
            self.report.error(f"Missing required cap_shell relation: {role} -> {target}.")
            return
        spec = specs[0]
        for mask_index, mask in enumerate(self.layout.get(spec.layer, [])):
            if mask.area <= EPS:
                continue
            if self.planned_sd_overlaps(target, mask):
                name, role_name, z0 = f"{spec.name}_UpperSDCap_{mask_index}", "md_sd_contact", spec.z0
            elif any(gate.overlaps(mask) for gate, _ in self.gates):
                name, role_name, z0 = f"{spec.name}_GateContact_{mask_index}", "md_gate_contact", float(self.value("md_gate_z0"))
            else:
                name, role_name, z0 = f"{spec.name}_OtherContact_{mask_index}", "md_contact", spec.z0
            self.metal.append(self.writer.cuboid(name, mask, z0, spec.z1, spec.material, role_name, metal_label=mask.label))

    def build_backside_bmd(self) -> None:
        """Emit BMD as a lower-S/D cap or a downward gate extension."""
        role, target = "backside_sd_landing", "lower_sd"
        specs = self.enabled(role)
        if not specs:
            return
        if self.relations.get((role, target)) != "bottom_landing":
            self.report.error(f"Missing required bottom_landing relation: {role} -> {target}.")
            return
        spec = specs[0]
        for mask_index, mask in enumerate(self.layout.get(spec.layer, [])):
            if mask.area <= EPS:
                continue
            if self.planned_sd_overlaps(target, mask):
                name, role_name, z1 = f"{spec.name}_LowerSDLanding_{mask_index}", "backside_sd_contact", spec.z1
            elif any(gate.overlaps(mask) for gate, _ in self.gates):
                name, role_name, z1 = f"{spec.name}_GateLanding_{mask_index}", "backside_gate_contact", float(self.value("bmd_gate_z1"))
            else:
                name, role_name, z1 = f"{spec.name}_OtherLanding_{mask_index}", "backside_contact", spec.z1
            # BMD is emitted before SD-EPI.  The later lower-SD body removes
            # its overlap, leaving the intended half-wrap contact geometry.
            self.metal.append(self.writer.cuboid(name, mask, spec.z0, z1, spec.material, role_name, metal_label=mask.label))

    def build_interconnect(self) -> None:
        for spec in sorted(self.stack.values(), key=lambda item: (item.z0, item.layer)):
            if not spec.enabled or spec.role in SPECIAL_ROLES:
                continue
            if spec.role not in {"routing_metal", "backside_routing_metal"}:
                continue
            for index, rect in enumerate(self.layout.get(spec.layer, [])):
                if rect.area > EPS:
                    region = self.writer.cuboid(f"{spec.name}_{index}_{safe_name(rect.label)}", rect, spec.z0, spec.z1, spec.material, spec.role, metal_label=rect.label)
                    if spec.material.lower() in METALS:
                        self.metal.append(region)
        # Vertical interconnect and vias are extruded only after their landing layers.
        for role in ("vertical_interconnect", "via", "backside_via"):
            for spec in self.enabled(role):
                for index, rect in enumerate(self.layout.get(spec.layer, [])):
                    if rect.area > EPS:
                        # Match the legacy all-mask generation: a via mask is
                        # a literal metal body, including a gate-via landing.
                        region = self.writer.cuboid(f"{spec.name}_{index}_{safe_name(rect.label)}", rect, spec.z0, spec.z1, spec.material, spec.role, metal_label=rect.label)
                        self.metal.append(region)

    @staticmethod
    def metal_regions_touch(first: Region, second: Region) -> bool:
        """Return true for a face/volume contact, but reject edge-only touching."""
        overlaps = [
            min(first.bbox[axis + 3], second.bbox[axis + 3]) - max(first.bbox[axis], second.bbox[axis])
            for axis in range(3)
        ]
        return all(value >= -EPS for value in overlaps) and sum(value > EPS for value in overlaps) >= 2

    def metal_components(self, regions: List[Region]) -> List[List[Region]]:
        """Partition metal regions into 3-D face-connected components."""
        parents = list(range(len(regions)))

        def find(index: int) -> int:
            while parents[index] != index:
                parents[index] = parents[parents[index]]
                index = parents[index]
            return index

        def join(first: int, second: int) -> None:
            left, right = find(first), find(second)
            if left != right:
                parents[right] = left

        for first in range(len(regions)):
            for second in range(first + 1, len(regions)):
                if self.metal_regions_touch(regions[first], regions[second]):
                    join(first, second)
        groups: Dict[int, List[Region]] = {}
        for index, region in enumerate(regions):
            groups.setdefault(find(index), []).append(region)
        return list(groups.values())

    def propagate_c_metal_names(self) -> None:
        """Give every physically connected C metal body one readable net name.

        This intentionally does not Boolean-unite bodies.  Copper, tungsten,
        and separate physical pieces remain distinct SDE regions so their
        material data and geometry are preserved for later extraction.
        """
        if not self.writer.c_variant:
            return
        for component in self.metal_components(self.metal):
            named_nets = []
            for region in component:
                if region.net_name is not None and region.net_name not in named_nets:
                    named_nets.append(region.net_name)
            if len(named_nets) > 1:
                self.report.error(
                    "C metal component shorts distinct labeled nets: " + ", ".join(named_nets)
                )
                continue
            target_name = named_nets[0] if named_nets else component[0].name
            for region in component:
                self.writer.rename_region(region, target_name)
                region.net_name = target_name

    @staticmethod
    def regions_overlap_in_volume(first: Region, second: Region) -> bool:
        """Return whether the original solids overlap with positive 3-D volume."""
        return all(
            min(first.bbox[axis + 3], second.bbox[axis + 3])
            - max(first.bbox[axis], second.bbox[axis])
            > EPS
            for axis in range(3)
        )

    def sd_contact_target(self, metal: Region, tier: str) -> Optional[Region]:
        """Resolve one S/D body that cut a contact-metal body under ABA.

        The Python-side volume test identifies the intended body pair only.
        The actual contact face is resolved later from the final SDE topology,
        after all Boolean operations and chamfers have completed.
        """
        targets = [
            sd_region
            for _, sd_region in self.sd[tier]
            if self.regions_overlap_in_volume(metal, sd_region)
        ]
        if len(targets) != 1:
            self.report.error(
                f"{metal.name}: expected exactly one overlapping {tier} body, "
                f"found {len(targets)}."
            )
            return None
        return targets[0]

    def emit_unique_touching_face_helper(self) -> None:
        """Emit Scheme helpers for selecting one final, body-adjacent planar face."""
        self.writer.comment("Topology-based unique contact-face selection for MD/S/D")
        self.writer.lines += [
            "(define (autoldm-entity-member? entity entities)",
            "  (cond ((null? entities) #f)",
            "        ((equal? entity (car entities)) #t)",
            "        (else (autoldm-entity-member? entity (cdr entities)))))",
            "(define (autoldm-touching-pair-target touching-pair)",
            "  (let ((tail (cdr touching-pair)))",
            "    (if (pair? tail) (car tail) tail)))",
            "(define (autoldm-face-has-normal? face nx ny nz tolerance)",
            "  (and (face:planar? face)",
            "       (let ((normal (face:plane-normal face)))",
            "         (and (< (abs (- (gvector:x normal) nx)) tolerance)",
            "              (< (abs (- (gvector:y normal) ny)) tolerance)",
            "              (< (abs (- (gvector:z normal) nz)) tolerance)))))",
            "(define (autoldm-collect-touching-faces pairs target-faces nx ny nz tolerance matches)",
            "  (if (null? pairs)",
            "      matches",
            "      (let* ((touching-pair (car pairs))",
            "             (source-face (car touching-pair))",
            "             (target-face (autoldm-touching-pair-target touching-pair)))",
            "        (autoldm-collect-touching-faces",
            "          (cdr pairs) target-faces nx ny nz tolerance",
            "          (if (and (autoldm-entity-member? target-face target-faces)",
            "                   (autoldm-face-has-normal? source-face nx ny nz tolerance))",
            "              (cons source-face matches)",
            "              matches)))))",
            "(define (autoldm-unique-touching-face source-body target-body nx ny nz contact-name)",
            "  (let* ((target-faces (entity:faces target-body))",
            "         (touching-pairs (sdegeo:find-touching-faces (entity:faces source-body)))",
            "         (matches (autoldm-collect-touching-faces",
            "                    touching-pairs target-faces nx ny nz 1.0e-6 '())))",
            "    (if (= (length matches) 1)",
            "        (car matches)",
            "        (sde:error",
            '          (string-append "AutoLDM: contact " contact-name',
            '                         " expected exactly one adjacent face, found "',
            "                         (number->string (length matches)))))))",
        ]

    def add_metal_contacts(self) -> None:
        """Expose top/bottom faces of terminal R-variant metal regions.

        Via and gate-mask regions are internal conductors and must not become
        Raphael terminals.  MD gate contacts remain eligible because their
        role is ``md_gate_contact``.  For ``md_sd_contact`` only, the Bottom
        terminal is the unique final MD face adjacent to its S/D body and
        facing -Z; every other contact retains the coordinate-based path.  The
        C variant deliberately remains free of metal contacts, matching its
        semiconductor-only use case.
        """
        if self.writer.c_variant:
            return
        skipped_vias = [region for region in self.metal if is_via_role(region.role)]
        skipped_gates = [
            region
            for region in self.metal
            if region.role.strip().lower() in {"gate", "gate_mask"}
        ]
        self.report.counts["r_contact_excluded_via_regions"] = len(skipped_vias)
        self.report.counts["r_contact_excluded_gate_regions"] = len(skipped_gates)
        md_sd_regions = [
            region
            for region in self.metal
            if region.role.strip().lower() == "md_sd_contact"
        ]
        if md_sd_regions:
            self.emit_unique_touching_face_helper()
        self.writer.comment("Metal top/bottom contacts (via and gate-mask roles excluded)")
        md_sd_interface_contacts = 0
        for region in self.metal:
            if is_r_contact_excluded_role(region.role):
                continue
            x0, y0, z0, x1, y1, z1 = region.bbox
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            top, bottom = f"Contact_{region.name}_Top", f"Contact_{region.name}_Bottom"
            self.writer.lines += [
                f'(sdegeo:define-contact-set "{top}" 4 (color:rgb 1 0 0) "##")',
                f'(sdegeo:set-contact (find-face-id (position {fmt(cx)} {fmt(cy)} {fmt(z1)})) "{top}")',
                f'(sdegeo:define-contact-set "{bottom}" 4 (color:rgb 1 0 0) "##")',
            ]
            if region.role.strip().lower() == "md_sd_contact":
                sd_target = self.sd_contact_target(region, "upper_sd")
                if sd_target is not None:
                    face_variable = f"contact_face_{safe_name(region.body)}_bottom"
                    self.writer.lines += [
                        f'(define {face_variable} '
                        f'(autoldm-unique-touching-face {region.body} {sd_target.body} '
                        f'0.0 0.0 -1.0 "{bottom}"))',
                        f'(sdegeo:set-contact (list {face_variable}) "{bottom}")',
                    ]
                    md_sd_interface_contacts += 1
            else:
                self.writer.lines.append(
                    f'(sdegeo:set-contact (find-face-id '
                    f'(position {fmt(cx)} {fmt(cy)} {fmt(z0)})) "{bottom}")'
                )
        self.report.counts["r_md_sd_interface_contacts"] = md_sd_interface_contacts

    def add_doping(self) -> None:
        """Place a constant active profile in every generated S/D region."""
        groups = {
            "upper_sd": (
                "Upper_SD_Doping",
                str(self.value("upper_sd_dopant")),
                float(self.value("upper_sd_concentration")),
            ),
            "lower_sd": (
                "Lower_SD_Doping",
                str(self.value("lower_sd_dopant")),
                float(self.value("lower_sd_concentration")),
            ),
        }
        self.writer.comment("Active S/D doping profiles")
        for key, (profile, species, concentration) in groups.items():
            if concentration <= 0:
                self.report.error(f"{key} concentration must be positive.")
                continue
            regions = [region for _, region in self.sd[key]]
            if not regions:
                self.report.warn(f"No regions available for {profile}.")
                continue
            self.writer.lines.append(f'(sdedr:define-constant-profile "{profile}" "{species}" {concentration:.6g})')
            for index, region in enumerate(regions):
                self.writer.lines.append(f'(sdedr:define-constant-profile-region "Place_{profile}_{index}" "{profile}" "{region.name}")')

    def add_mesh(self) -> None:
        """Apply three stable mesh bands: global, device core, and interconnect.

        This deliberately avoids one refinement window per layout polygon.  The
        core band covers every nanosheet, high-k shell, spacer wall, gate, and
        S/D body, while the interconnect band covers all front/back metal.
        """
        boundary = self.boundary().expanded(DOMAIN_MARGIN_XY)
        z0 = min(region.bbox[2] for region in self.writer.regions)
        z1 = max(region.bbox[5] for region in self.writer.regions)
        gmax, gmin = float(self.value("mesh_global_max")), float(self.value("mesh_global_min"))
        self.writer.lines += [
            f'(sdedr:define-refeval-window "Global" "Cuboid" (position {fmt(boundary.x1)} {fmt(boundary.y1)} {fmt(z0)}) (position {fmt(boundary.x2)} {fmt(boundary.y2)} {fmt(z1)}))',
            f'(sdedr:define-refinement-size "GlobalSize" {gmax} {gmax} {gmax} {gmin} {gmin} {gmin})',
            '(sdedr:define-refinement-placement "GlobalPlace" "GlobalSize" "Global")',
        ]

        core_roles = {
            "upper_sd", "lower_sd", "gate", "high_k", "inner_spacer_wall",
            "upper_channel", "lower_channel",
        }
        core = [region for region in self.writer.regions if region.role in core_roles]
        if core:
            x0 = min(region.bbox[0] for region in core)
            y0 = min(region.bbox[1] for region in core)
            rz0 = min(region.bbox[2] for region in core)
            x1 = max(region.bbox[3] for region in core)
            y1 = max(region.bbox[4] for region in core)
            rz1 = max(region.bbox[5] for region in core)
            cmax, cmin = float(self.value("mesh_core_max")), float(self.value("mesh_core_min"))
            self.writer.lines += [
                f'(sdedr:define-refeval-window "DeviceCore" "Cuboid" (position {fmt(x0)} {fmt(y0)} {fmt(rz0)}) (position {fmt(x1)} {fmt(y1)} {fmt(rz1)}))',
                f'(sdedr:define-refinement-size "DeviceCoreSize" {cmax} {cmax} {cmax} {cmin} {cmin} {cmin})',
                '(sdedr:define-refinement-placement "DeviceCorePlace" "DeviceCoreSize" "DeviceCore")',
            ]

        if self.metal:
            x0 = min(region.bbox[0] for region in self.metal)
            y0 = min(region.bbox[1] for region in self.metal)
            rz0 = min(region.bbox[2] for region in self.metal)
            x1 = max(region.bbox[3] for region in self.metal)
            y1 = max(region.bbox[4] for region in self.metal)
            rz1 = max(region.bbox[5] for region in self.metal)
            imax, imin = float(self.value("mesh_interconnect_max")), float(self.value("mesh_interconnect_min"))
            self.writer.lines += [
                f'(sdedr:define-refeval-window "Interconnect" "Cuboid" (position {fmt(x0)} {fmt(y0)} {fmt(rz0)}) (position {fmt(x1)} {fmt(y1)} {fmt(rz1)}))',
                f'(sdedr:define-refinement-size "InterconnectSize" {imax} {imax} {imax} {imin} {imin} {imin})',
                '(sdedr:define-refinement-placement "InterconnectPlace" "InterconnectSize" "Interconnect")',
            ]

    def build(self) -> Tuple[SDEWriter, Report]:
        self.preflight()
        self.build_domain_dielectric()
        self.build_device_stack()
        self.build_frontside_md()
        self.build_backside_bmd()
        self.build_sd_epi()
        self.build_interconnect()
        self.propagate_c_metal_names()
        self.add_doping()
        self.add_mesh()
        self.add_metal_contacts()
        self.report.counts["generated_regions"] = len(self.writer.regions)
        return self.writer, self.report


def default_rules_path(layout_path: str) -> Optional[str]:
    stem = os.path.splitext(os.path.basename(layout_path))[0]
    candidate = os.path.join(os.path.dirname(layout_path), stem.replace("_gds", "_design_rules") + ".txt")
    return candidate if os.path.exists(candidate) else None


def derive_rc_paths(requested_output: str) -> Tuple[str, str, str, str]:
    """Map any requested stem to <stem>_r_sde.cmd / <stem>_c_sde.cmd and R/C mesh roots."""
    directory, filename = os.path.split(requested_output)
    stem, extension = os.path.splitext(filename)
    for suffix in ("_r_sde", "_c_sde", "_sde"):
        if stem.lower().endswith(suffix):
            stem = stem[:-len(suffix)]
            break
    extension = extension or ".cmd"
    r_cmd = os.path.join(directory, f"{stem}_r_sde{extension}")
    c_cmd = os.path.join(directory, f"{stem}_c_sde{extension}")
    return r_cmd, c_cmd, os.path.join(directory, f"{stem}_R_msh"), os.path.join(directory, f"{stem}_C_msh")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a validated AutoLDM Sentaurus SDE command file.")
    parser.add_argument("layout", help="layout txt: x1 y1 x2 y2 layer [label]")
    parser.add_argument("params", help="device and numerical parameter file")
    parser.add_argument("stack", help="layer stack / role file")
    parser.add_argument("-o", "--output", required=True, help="output .cmd path")
    parser.add_argument("--c-output", default=None, help="override the C-variant CMD output path")
    parser.add_argument("--design-rules", default=None, help="layer-relation rule file; defaults beside layout")
    parser.add_argument("--validate-only", action="store_true", help="perform input/geometry preflight without writing a cmd")
    parser.add_argument("--allow-errors", action="store_true", help="write cmd despite validation errors")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    for path in (args.layout, args.params, args.stack):
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
    params = parse_params(args.params)
    layout = parse_layout(args.layout)
    stack = parse_stack(args.stack, params)
    relations = parse_relations(args.design_rules or default_rules_path(args.layout))
    builder = Builder(layout, stack, params, relations)
    writer, report = builder.build()
    print(report.text())
    strict = True
    if report.errors and strict and not args.allow_errors:
        return 2
    if not args.validate_only:
        r_output, c_output, r_mesh, c_mesh = derive_rc_paths(args.output)
        if args.c_output:
            c_output = args.c_output
        writer.lines.append(f'(sde:build-mesh "{MESH_ENGINE}" "{MESH_OPTIONS}" "{os.path.basename(r_mesh)}")')
        writer.lines.append(f'(sde:build-mesh "{MESH_ENGINE}" "{MESH_OPTIONS}" "n@node@_R_msh")')
        writer.write(r_output)
        print(f"R SDE command file generated: {r_output}")
        c_builder = Builder(layout, stack, params, relations, c_variant=True)
        c_writer, c_report = c_builder.build()
        if c_report.errors and strict and not args.allow_errors:
            print(c_report.text())
            return 2
        c_writer.lines.append(f'(sde:build-mesh "{MESH_ENGINE}" "{MESH_OPTIONS}" "{os.path.basename(c_mesh)}")')
        c_writer.lines.append(f'(sde:build-mesh "{MESH_ENGINE}" "{MESH_OPTIONS}" "n@node@_C_msh")')
        c_writer.write(c_output)
        print(f"C SDE command file generated: {c_output}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
