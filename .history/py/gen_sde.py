import argparse
import ast
import os
import re
import sys
from dataclasses import dataclass


EPS = 1e-9
METAL_MATERIALS = {"Tungsten", "Copper", "Metal"}
SKIP_SIMPLE_LAYERS = {1, 7, 8, 9, 10, 111, 121, 122}

DEVICE_MAP = (
    ("PG1", "nmos", "upper", "GATE_PG1", "SDN_PG1_OUTER", "SDN_PG1_PD1_SHARED"),
    ("PD1", "nmos", "upper", "GATE_PD1_PU1", "SDN_PG1_PD1_SHARED", "SDN_PD1_OUTER"),
    ("PU1", "pmos", "lower", "GATE_PD1_PU1", "SDP_PU1_NODE", "SDP_PU1_POWER"),
    ("PD2", "nmos", "upper", "GATE_PD2_PU2", "SDN_PD2_OUTER", "SDN_PD2_PG2_SHARED"),
    ("PU2", "pmos", "lower", "GATE_PD2_PU2", "SDP_PU2_POWER", "SDP_PU2_NODE"),
    ("PG2", "nmos", "upper", "GATE_PG2", "SDN_PD2_PG2_SHARED", "SDN_PG2_OUTER"),
)


def fmt(value):
    value = float(value)
    return f"{value:.5f}"


def safe_name(text):
    text = "NONE" if text in (None, "", "None") else str(text)
    return "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in text)


def boxes_connected(a, b, tol=1e-9):
    axes = (
        (a["x1"], a["x2"], b["x1"], b["x2"]),
        (a["y1"], a["y2"], b["y1"], b["y2"]),
        (a["z1"], a["z2"], b["z1"], b["z2"]),
    )
    positive_overlaps = 0
    for a1, a2, b1, b2 in axes:
        if a2 < b1 - tol or b2 < a1 - tol:
            return False
        if min(a2, b2) - max(a1, b1) > tol:
            positive_overlaps += 1
    return positive_overlaps >= 2


def parse_literal(raw):
    raw = raw.strip()
    low = raw.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    try:
        return float(raw)
    except ValueError:
        return raw


class ExpressionResolver:
    """Resolves numeric rule expressions without using Python eval."""

    _var_ref = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")
    _placeholder = re.compile(r"@<([^<>]+)>@|@([A-Za-z_][A-Za-z0-9_]*)@")
    _number_like = re.compile(r"^[0-9eE+\-*/(). _A-Za-z$@<>]+$")

    def __init__(self, values=None):
        self.values = {}
        if values:
            for key, value in values.items():
                self.set(key, value)

    def set(self, key, value):
        if key:
            self.values[str(key)] = value
            self.values[safe_name(str(key)).lower()] = value

    def get(self, key):
        if key in self.values:
            return self.values[key]
        low = safe_name(key).lower()
        if low in self.values:
            return self.values[low]
        raise KeyError(key)

    def resolve_text(self, raw):
        raw = str(raw).strip()

        def repl_var(match):
            value = self.get(match.group(1))
            return self._value_to_text(value)

        def repl_placeholder(match):
            expr, name = match.groups()
            if expr is not None:
                return self._value_to_text(self.eval_numeric(expr))
            try:
                return self._value_to_text(self.get(name))
            except KeyError:
                # Sentaurus names such as n@node@ must survive unresolved.
                return match.group(0)

        text = self._var_ref.sub(repl_var, raw)
        text = self._placeholder.sub(repl_placeholder, text)
        return text

    def resolve_value(self, raw):
        literal = parse_literal(raw)
        if not isinstance(literal, str):
            return literal
        text = self.resolve_text(literal)
        parsed = parse_literal(text)
        if not isinstance(parsed, str):
            return parsed
        if self._looks_numeric_expression(text):
            return self.eval_numeric(text)
        return text

    def eval_numeric(self, raw):
        text = self.resolve_text(raw)
        tree = ast.parse(text, mode="eval")
        return float(self._eval_node(tree.body))

    def _looks_numeric_expression(self, text):
        if not self._number_like.match(text):
            return False
        if any(op in text for op in "+-*/()"):
            return any(ch.isdigit() for ch in text)
        try:
            float(text)
            return True
        except ValueError:
            return False

    def _eval_node(self, node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.Name):
            value = self.get(node.id)
            if isinstance(value, bool):
                raise ValueError(f"Boolean variable {node.id} cannot be used as a number.")
            return float(value)
        if isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand)
            if isinstance(node.op, ast.UAdd):
                return operand
            if isinstance(node.op, ast.USub):
                return -operand
        if isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.Pow):
                return left**right
        raise ValueError(f"Unsupported expression: {ast.dump(node)}")

    def _value_to_text(self, value):
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, float):
            return f"{value:.12g}"
        return str(value)


@dataclass
class Rect:
    x1: float
    y1: float
    x2: float
    y2: float
    layer: int
    label: str
    net: str
    line_num: int
    raw: str

    @property
    def width(self):
        return self.x2 - self.x1

    @property
    def height(self):
        return self.y2 - self.y1

    @property
    def area(self):
        return max(0.0, self.width) * max(0.0, self.height)

    @property
    def cx(self):
        return (self.x1 + self.x2) / 2.0

    @property
    def cy(self):
        return (self.y1 + self.y2) / 2.0

    def identity(self, index):
        label = safe_name(self.label)
        net = safe_name(self.net)
        if label != "NONE" and net != "NONE":
            return f"{label}_{net}_{index}"
        if label != "NONE":
            return f"{label}_{index}"
        if net != "NONE":
            return f"{net}_{index}"
        return f"L{self.layer}_{index}"


@dataclass
class LayerRule:
    layer: int
    name: str
    enable: bool
    height: float
    start_z: float
    end_z: float
    material: str
    boundary: str
    ild: str
    raw: str
    line_num: int


class SDEWriter:
    def __init__(self, noname=False):
        self.noname = noname
        self.lines = []
        self.regions = []
        self.metal_regions = []

    def add(self, line=""):
        self.lines.append(line)

    def comment(self, text):
        self.add(f"; {text}")

    def section(self, text):
        self.add("")
        self.add("; " + "-" * 72)
        self.comment(text)
        self.add("; " + "-" * 72)

    def cuboid(self, name, x1, y1, z1, x2, y2, z2, material, contact=True):
        x1, x2 = sorted((float(x1), float(x2)))
        y1, y2 = sorted((float(y1), float(y2)))
        z1, z2 = sorted((float(z1), float(z2)))
        if x2 - x1 <= EPS or y2 - y1 <= EPS or z2 - z1 <= EPS:
            return None
        internal_name = safe_name(name)
        emit_name = "" if self.omit_region_name(internal_name, material) else internal_name
        create_cmd = (
            f'(sdegeo:create-cuboid (position {fmt(x1)} {fmt(y1)} {fmt(z1)}) '
            f'(position {fmt(x2)} {fmt(y2)} {fmt(z2)}) "{material}" "{emit_name}")'
        )
        body_var = None
        if self.noname and material in METAL_MATERIALS:
            body_var = f"metal_body_{len(self.metal_regions)}"
            self.add(f"(define {body_var} {create_cmd})")
        else:
            self.add(create_cmd)
        region = {
            "name": emit_name,
            "internal_name": internal_name,
            "body_var": body_var,
            "material": material,
            "x1": x1,
            "y1": y1,
            "z1": z1,
            "x2": x2,
            "y2": y2,
            "z2": z2,
        }
        self.regions.append(region)
        if material in METAL_MATERIALS and (contact or self.noname):
            self.metal_regions.append(region)
        return region

    def omit_region_name(self, name, material):
        if not self.noname:
            return False
        return material in METAL_MATERIALS or name.startswith("ILD_")

    def write(self, filepath):
        out_dir = os.path.dirname(os.path.abspath(filepath))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(self.lines) + "\n")


def parse_layout(filepath):
    layout = {}
    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            raw = line.lstrip("\ufeff").strip()
            if not raw or raw.startswith("%"):
                continue
            parts = raw.split()
            if len(parts) < 5:
                raise ValueError(f"Invalid layout line {line_num}: {raw}")
            x1, y1, x2, y2 = map(float, parts[:4])
            layer = int(float(parts[4]))
            label = parts[5] if len(parts) >= 6 else "None"
            net = parts[6] if len(parts) >= 7 else ""
            rect = Rect(
                min(x1, x2),
                min(y1, y2),
                max(x1, x2),
                max(y1, y2),
                layer,
                label,
                net,
                line_num,
                raw,
            )
            layout.setdefault(layer, []).append(rect)
    return layout


def parse_arch(filepath):
    raw = {}
    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            clean = line.lstrip("\ufeff").split("%", 1)[0].strip()
            if not clean or "=" not in clean:
                continue
            key, value = clean.split("=", 1)
            raw[key.strip()] = value.strip()

    resolved = {}
    resolver = ExpressionResolver()
    pending = dict(raw)
    while pending:
        progressed = False
        for key in list(pending):
            try:
                value = resolver.resolve_value(pending[key])
            except KeyError:
                continue
            except Exception as exc:
                raise ValueError(f"Invalid arch expression for {key}: {pending[key]} ({exc})") from exc
            resolved[key] = value
            resolver.set(key, value)
            pending.pop(key)
            progressed = True
        if not progressed:
            unresolved = ", ".join(sorted(pending))
            raise ValueError(f"Unresolved arch variables: {unresolved}")
    return resolved


def parse_layer_rules(filepath, arch):
    raw_rules = []
    variables = {}
    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            raw = line.lstrip("\ufeff").strip()
            clean = raw.split("%", 1)[0].strip()
            if not clean:
                continue
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*\s*=", clean):
                key, value = clean.split("=", 1)
                variables[key.strip()] = value.strip()
                continue
            if clean.startswith("%"):
                continue
            parts = clean.split()
            if len(parts) < 9:
                raise ValueError(f"Invalid layer rule line {line_num}: {raw}")
            raw_rules.append((line_num, raw, parts))

    resolver = ExpressionResolver(arch)
    for key, value in variables.items():
        resolver.set(key, resolver.resolve_value(value))

    rules = {}
    pending = list(raw_rules)
    while pending:
        progressed = False
        next_pending = []
        for line_num, raw, parts in pending:
            layer = int(float(parts[0]))
            name = parts[1]
            enable = str(resolver.resolve_value(parts[2])).lower() == "true"
            try:
                height = float(resolver.resolve_value(parts[3]))
                start_z = float(resolver.resolve_value(parts[4]))
                end_z = float(resolver.resolve_value(parts[5]))
            except KeyError:
                next_pending.append((line_num, raw, parts))
                continue
            except Exception as exc:
                raise ValueError(f"Invalid z expression at layer-rule line {line_num}: {raw} ({exc})") from exc
            material = str(resolver.resolve_value(parts[6]))
            boundary = str(resolver.resolve_value(parts[7]))
            ild = str(resolver.resolve_value(parts[8]))
            if enable and abs((end_z - start_z) - height) > 1e-5:
                raise ValueError(
                    f"Layer {layer} z rule mismatch at line {line_num}: "
                    f"end_z2 - start_z1 = {end_z - start_z:.8g}, height = {height:.8g}; raw: {raw}"
                )
            rule = LayerRule(layer, name, enable, height, start_z, end_z, material, boundary, ild, raw, line_num)
            rules[layer] = rule
            for prefix in (f"layer_{layer}", safe_name(name), safe_name(name).lower()):
                resolver.set(f"{prefix}_height", height)
                resolver.set(f"{prefix}_start_z", start_z)
                resolver.set(f"{prefix}_end_z", end_z)
            progressed = True
        if not progressed:
            unresolved = ", ".join(str(item[0]) for item in next_pending)
            raise ValueError(f"Unresolved layer-rule expressions at lines: {unresolved}")
        pending = next_pending
    return rules


class SDEBuilder:
    def __init__(self, layout, rules, arch, output_name, noname=False):
        self.layout = layout
        self.rules = rules
        self.arch = arch
        self.output_name = output_name
        self.noname = noname
        self.sde = SDEWriter(noname=noname)
        self.boundary = self.compute_boundary()
        self.sheet_z = self.compute_sheet_z()
        self.sd_regions = []
        self.channel_regions = []
        self.used_gate_layers = set()
        self.built_gates = set()
        self.built_sd = {}

    def a(self, key, default=None):
        if key in self.arch:
            return self.arch[key]
        if default is not None:
            return default
        raise KeyError(f"Missing required arch parameter: {key}")

    def rule(self, layer):
        rule = self.rules.get(layer)
        return rule if rule and rule.enable else None

    def first_enabled_rule_by_name(self, *names):
        lowers = {name.lower() for name in names}
        for rule in self.rules.values():
            if rule.enable and rule.name.lower() in lowers:
                return rule
        return None

    def compute_boundary(self):
        rects = [r for layer_rects in self.layout.values() for r in layer_rects if r.area > EPS]
        if not rects:
            raise ValueError("Layout has no non-zero rectangles to derive the x/y boundary.")
        return {
            "x1": min(r.x1 for r in rects),
            "y1": min(r.y1 for r in rects),
            "x2": max(r.x2 for r in rects),
            "y2": max(r.y2 for r in rects),
        }

    def compute_sheet_z(self):
        thickness = float(self.a("channel_thickness"))
        gap = float(self.a("channel_vertical_gap", self.a("channel_mdi_thickness", 0.012)))
        mdi = float(self.a("mdi_thickness"))
        n_lower = int(float(self.a("num_channel_lower", self.a("num_channel", 2))))
        n_upper = int(float(self.a("num_channel_upper", self.a("num_channel_upeer", self.a("num_channel", 2)))))

        lower = []
        z = 0.0
        for _ in range(n_lower):
            z += gap
            lower.append((z, z + thickness))
            z += thickness
        z += gap + mdi

        upper = []
        for _ in range(n_upper):
            z += gap
            upper.append((z, z + thickness))
            z += thickness
        return {"lower": lower, "upper": upper}

    def build(self):
        self.sde.comment("Generated by AutoLDM/gen_sde.py")
        self.sde.comment("layout supplies x/y geometry and names; layer rules supply z/material; arch supplies process hard parameters.")
        if self.noname:
            self.sde.comment("Noname variant: metal and ILD cuboids use empty region names; contacts are omitted.")
        self.sde.add("(sde:clear)")
        self.sde.add('(sdegeo:set-default-boolean "ABA")')
        self.build_dielectrics()
        self.build_substrate_if_needed()
        self.build_layout_driven_devices()
        self.build_generic_layout_layers()
        if self.noname:
            self.unite_connected_metals()
        if not self.noname:
            self.add_contacts()
        self.add_doping()
        self.add_meshing()
        return self.sde

    def build_dielectrics(self):
        if not bool(self.a("dielectric_enable", True)):
            return
        self.sde.section("Dielectric envelope")
        intervals = []
        for rule in self.rules.values():
            if not rule.enable or rule.layer in {1, 111, 121, 122}:
                continue
            if rule.ild.lower() in {"none", "null", "-"}:
                continue
            intervals.append((rule.start_z, rule.end_z, rule.ild))
        if not intervals:
            return
        cuts = sorted({z for z1, z2, _ in intervals for z in (z1, z2)})
        b = self.boundary
        for index, (z1, z2) in enumerate(zip(cuts, cuts[1:])):
            if z2 - z1 <= EPS:
                continue
            material = next((ild for a, bnd, ild in intervals if a <= z1 + EPS and bnd >= z2 - EPS), None)
            if material:
                self.sde.cuboid(f"ILD_{index}", b["x1"], b["y1"], z1, b["x2"], b["y2"], z2, material, False)

    def has_backside_interconnect(self):
        for layer, rects in self.layout.items():
            rule = self.rule(layer)
            if not rule or not rects:
                continue
            name = rule.name.lower()
            if layer >= 51 or name.startswith(("bm", "bv", "bmd", "bvmd")):
                return True
        return False

    def build_substrate_if_needed(self):
        rule = self.rule(1)
        if not rule or self.has_backside_interconnect():
            return
        b = self.boundary
        self.sde.section("Substrate")
        self.sde.cuboid("Substrate_1", b["x1"], b["y1"], rule.start_z, b["x2"], b["y2"], rule.end_z, rule.material, False)

    def build_layout_driven_devices(self):
        marker_gates = [r for r in self.layout.get(111, []) if r.area > EPS]
        marker_n = [r for r in self.layout.get(121, []) if r.area > EPS]
        marker_p = [r for r in self.layout.get(122, []) if r.area > EPS]
        if marker_gates and marker_n and marker_p:
            self.build_marker_devices(marker_gates, marker_n, marker_p)
            return

        gate_layer = 7 if self.layout.get(7) and self.rule(7) else None
        if gate_layer is None and marker_gates:
            gate_layer = 111
        if gate_layer is None:
            return

        gates = [r for r in self.layout.get(gate_layer, []) if r.area > EPS]
        if not gates:
            return

        self.sde.section("Derived CFET device geometry from gate rows")
        gate_rule = self.device_gate_rule(gate_layer)
        rows = self.group_gate_rows(gates)
        for row_index, row_gates in enumerate(rows):
            for gate_index, gate in enumerate(row_gates):
                self.build_gate_stack(gate_layer, gate_rule, gate, gate_index)
            for tier in ("upper", "lower"):
                self.build_derived_row_tier(tier, row_index, row_gates, gate_rule)
        self.used_gate_layers.add(gate_layer)

    def device_gate_rule(self, gate_layer):
        if gate_layer == 111 and self.rule(7):
            return self.rule(7)
        rule = self.rule(gate_layer)
        if rule:
            return rule
        return self.rule(7) or self.rule(111)

    def build_marker_devices(self, marker_gates, marker_n, marker_p):
        self.sde.section("Marker-driven CFET device geometry")
        gates = {rect.label: rect for rect in marker_gates}
        sd_n = {rect.label: rect for rect in marker_n}
        sd_p = {rect.label: rect for rect in marker_p}
        gate_rule = self.device_gate_rule(111)
        for device_name, device_type, tier, gate_label, left_label, right_label in DEVICE_MAP:
            gate = gates.get(gate_label)
            sd_map = sd_p if device_type == "pmos" else sd_n
            left_sd = sd_map.get(left_label)
            right_sd = sd_map.get(right_label)
            if not gate or not left_sd or not right_sd:
                continue
            self.build_gate_stack(111, gate_rule, gate, 0)
            left_region = self.build_marker_sd(tier, device_type, left_sd)
            right_region = self.build_marker_sd(tier, device_type, right_sd)
            self.build_marker_channel_and_spacer(device_name, tier, gate, left_sd, right_sd, gate_rule)
            if left_region:
                self.sd_regions.append((left_region["internal_name"], device_type))
            if right_region:
                self.sd_regions.append((right_region["internal_name"], device_type))
        self.used_gate_layers.add(111)

    def build_marker_sd(self, tier, device_type, rect):
        z1, z2 = self.sd_z_range(tier)
        material = self.sd_material(tier)
        key = (
            tier,
            device_type,
            round(rect.x1, 9),
            round(rect.y1, 9),
            round(rect.x2, 9),
            round(rect.y2, 9),
            safe_name(rect.label),
            safe_name(rect.net),
        )
        if key in self.built_sd:
            return None
        name = f"SD_{safe_name(rect.label)}_{safe_name(rect.net)}_{tier}"
        region = self.sde.cuboid(name, rect.x1, rect.y1, z1, rect.x2, rect.y2, z2, material, False)
        self.built_sd[key] = region
        return region

    def build_marker_channel_and_spacer(self, device_name, tier, gate, left_sd, right_sd, gate_rule):
        hk = float(self.a("high_k_thickness", 0.002))
        x_segments = (
            ("Left", left_sd.x2, gate.x1 - hk),
            ("Right", gate.x2 + hk, right_sd.x1),
        )
        y1 = max(left_sd.y1, right_sd.y1)
        y2 = min(left_sd.y2, right_sd.y2)
        if y2 - y1 <= EPS:
            return
        material = self.channel_material(tier)
        windows = []
        for side, x1, x2 in x_segments:
            if x2 - x1 <= EPS:
                continue
            for sheet_index, (z1, z2) in enumerate(self.sheet_z[tier]):
                name = f"CH_{device_name}_{side}_{sheet_index}"
                if self.sde.cuboid(name, x1, y1, z1, x2, y2, z2, material, False):
                    self.channel_regions.append(name)
                    windows.append((z1, z2))
        self.build_inner_spacers(tier, device_name, gate_rule, gate, x_segments, y1, y2, sorted(set(windows)))

    def group_gate_rows(self, gates):
        rows = []
        for gate in sorted(gates, key=lambda r: (r.cy, r.x1)):
            for row in rows:
                reference = row[0]
                if min(reference.y2, gate.y2) - max(reference.y1, gate.y1) > EPS:
                    row.append(gate)
                    break
            else:
                rows.append([gate])
        return [sorted(row, key=lambda r: r.x1) for row in rows]

    def row_boundary(self, gates):
        y1 = min(gate.y1 for gate in gates)
        y2 = max(gate.y2 for gate in gates)
        boundary_rects = [
            rect for rect in self.layout.get(1, [])
            if rect.area > EPS and min(rect.y2, y2) - max(rect.y1, y1) > -EPS
        ]
        if not boundary_rects:
            return self.boundary["x1"], self.boundary["x2"]
        return min(rect.x1 for rect in boundary_rects), max(rect.x2 for rect in boundary_rects)

    def build_derived_row_tier(self, tier, row_index, gates, gate_rule):
        if not gates:
            return
        spacing = float(self.a("gate_to_sd_sidewall_spacing", 0.005))
        channel_width = float(self.a(f"{tier}_channel_width", self.a("channel_width", 0.021)))
        sd_width = float(self.a(f"{tier}_sd_width", self.a("sd_width", channel_width)))
        row_x1, row_x2 = self.row_boundary(gates)

        segments = []
        for index in range(len(gates) + 1):
            if index == 0:
                x1 = row_x1
                x2 = gates[0].x1 - spacing
                center_y = gates[0].cy
            elif index == len(gates):
                x1 = gates[-1].x2 + spacing
                x2 = row_x2
                center_y = gates[-1].cy
            else:
                x1 = gates[index - 1].x2 + spacing
                x2 = gates[index].x1 - spacing
                center_y = (gates[index - 1].cy + gates[index].cy) / 2.0
            y1 = center_y - sd_width / 2.0
            y2 = center_y + sd_width / 2.0
            region = self.build_derived_sd(tier, row_index, index, x1, y1, x2, y2)
            segments.append({"x1": x1, "x2": x2, "y1": y1, "y2": y2, "region": region})

        hk = float(self.a("high_k_thickness", 0.002))
        material = self.channel_material(tier)
        for gate_index, gate in enumerate(gates):
            ch_y1 = gate.cy - channel_width / 2.0
            ch_y2 = gate.cy + channel_width / 2.0
            x_segments = (
                ("Left", segments[gate_index]["x2"], gate.x1 - hk),
                ("Right", gate.x2 + hk, segments[gate_index + 1]["x1"]),
            )
            gate_token = f"R{row_index}_{gate.identity(gate_index)}"
            windows = []
            for side, x1, x2 in x_segments:
                if x2 - x1 <= EPS:
                    continue
                for sheet_index, (z1, z2) in enumerate(self.sheet_z[tier]):
                    name = f"CH_{tier}_{gate_token}_{side}_{sheet_index}"
                    if self.sde.cuboid(name, x1, ch_y1, z1, x2, ch_y2, z2, material, False):
                        self.channel_regions.append(name)
                        windows.append((z1, z2))
            self.build_inner_spacers(tier, gate_token, gate_rule, gate, x_segments, ch_y1, ch_y2, sorted(set(windows)))

    def build_derived_sd(self, tier, row_index, segment_index, x1, y1, x2, y2):
        if x2 - x1 <= EPS or y2 - y1 <= EPS:
            return None
        z1, z2 = self.sd_z_range(tier)
        material = self.sd_material(tier)
        name = f"SD_{tier}_R{row_index}_S{segment_index}"
        region = self.sde.cuboid(name, x1, y1, z1, x2, y2, z2, material, False)
        if region:
            self.sd_regions.append((region["internal_name"], "nmos" if tier == "upper" else "pmos"))
        return region

    def channel_material(self, tier):
        return str(self.a(f"{tier}_channel_material", self.a("channel_material", "Silicon")))

    def sd_material(self, tier):
        return str(self.a(f"{tier}_sd_material", "Silicon" if tier == "upper" else "SiGe"))

    def sd_z_range(self, tier):
        sheets = self.sheet_z[tier]
        z_down = float(self.a(f"{tier}_sd_overgrowth_z_down", self.a("sd_overgrowth_z_down", 0.006)))
        z_up = float(self.a(f"{tier}_sd_overgrowth_z_up", self.a("sd_overgrowth_z_up", 0.006)))
        return min(z for z, _ in sheets) - z_down, max(z for _, z in sheets) + z_up

    def build_gate_stack(self, layer, rule, gate, index):
        gate_key = (
            round(gate.x1, 9),
            round(gate.y1, 9),
            round(gate.x2, 9),
            round(gate.y2, 9),
            safe_name(gate.label),
            safe_name(gate.net),
        )
        if gate_key in self.built_gates:
            return
        base = f"Gate_{gate.identity(index)}"
        self.sde.cuboid(base, gate.x1, gate.y1, rule.start_z, gate.x2, gate.y2, rule.end_z, rule.material)
        hk = float(self.a("high_k_thickness", 0.002))
        hk_material = str(self.a("high_k_material", "HfO2"))
        self.sde.cuboid(f"HighK_{base}_XMin", gate.x1 - hk, gate.y1, rule.start_z, gate.x1, gate.y2, rule.end_z, hk_material, False)
        self.sde.cuboid(f"HighK_{base}_XMax", gate.x2, gate.y1, rule.start_z, gate.x2 + hk, gate.y2, rule.end_z, hk_material, False)
        self.sde.cuboid(f"HighK_{base}_YMin", gate.x1, gate.y1 - hk, rule.start_z, gate.x2, gate.y1, rule.end_z, hk_material, False)
        self.sde.cuboid(f"HighK_{base}_YMax", gate.x1, gate.y2, rule.start_z, gate.x2, gate.y2 + hk, rule.end_z, hk_material, False)
        self.built_gates.add(gate_key)

    def build_inner_spacers(self, tier, gate_token, gate_rule, gate, x_segments, y1, y2, windows):
        if not gate_rule or not windows:
            return
        material = str(self.a("inner_spacer_material", "Si3N4"))
        for side, x1, x2 in x_segments:
            if x2 - x1 <= EPS:
                continue
            prefix = f"InnerSpacer_{tier}_{gate_token}_{side}"
            self.sde.cuboid(prefix + "_YMin", x1, gate.y1, gate_rule.start_z, x2, y1, gate_rule.end_z, material, False)
            self.sde.cuboid(prefix + "_YMax", x1, y2, gate_rule.start_z, x2, gate.y2, gate_rule.end_z, material, False)
            current = gate_rule.start_z
            for index, (z1, z2) in enumerate(windows):
                self.sde.cuboid(prefix + f"_ZGap_{index}", x1, y1, current, x2, y2, z1, material, False)
                current = max(current, z2)
            self.sde.cuboid(prefix + f"_ZGap_{len(windows)}", x1, y1, current, x2, y2, gate_rule.end_z, material, False)

    def build_generic_layout_layers(self):
        self.sde.section("Layout layers from rules")
        for layer in sorted(self.layout):
            rule = self.rule(layer)
            if not rule or layer in SKIP_SIMPLE_LAYERS:
                continue
            for index, rect in enumerate(self.layout[layer]):
                if rect.area <= EPS:
                    continue
                token = rect.identity(index)
                name = f"{safe_name(rule.name)}_{token}"
                self.sde.cuboid(name, rect.x1, rect.y1, rule.start_z, rect.x2, rect.y2, rule.end_z, rule.material)

    def unite_connected_metals(self):
        metals = [region for region in self.sde.metal_regions if region.get("body_var")]
        if len(metals) < 2:
            return

        parent = list(range(len(metals)))

        def find(index):
            while parent[index] != index:
                parent[index] = parent[parent[index]]
                index = parent[index]
            return index

        def union(left, right):
            root_left = find(left)
            root_right = find(right)
            if root_left != root_right:
                parent[root_right] = root_left

        for left in range(len(metals)):
            for right in range(left + 1, len(metals)):
                if boxes_connected(metals[left], metals[right]):
                    union(left, right)

        components = {}
        for index in range(len(metals)):
            components.setdefault(find(index), []).append(index)

        merged = [items for items in components.values() if len(items) > 1]
        if not merged:
            return

        self.sde.section("Boolean-unite connected metal components")
        for component_index, items in enumerate(merged):
            body_list = " ".join(metals[index]["body_var"] for index in items)
            self.sde.add(f'(sdegeo:bool-unite (list {body_list}))')

    def add_contacts(self):
        self.sde.section("Metal top/bottom contacts")
        for region in self.sde.metal_regions:
            cx = (region["x1"] + region["x2"]) / 2.0
            cy = (region["y1"] + region["y2"]) / 2.0
            top = f"Contact_{region['name']}_Top"
            bottom = f"Contact_{region['name']}_Bottom"
            self.sde.add(f'(sdegeo:define-contact-set "{top}" 4 (color:rgb 1 0 0) "##")')
            self.sde.add(f'(sdegeo:set-contact (find-face-id (position {fmt(cx)} {fmt(cy)} {fmt(region["z2"])})) "{top}")')
            self.sde.add(f'(sdegeo:define-contact-set "{bottom}" 4 (color:rgb 1 0 0) "##")')
            self.sde.add(f'(sdegeo:set-contact (find-face-id (position {fmt(cx)} {fmt(cy)} {fmt(region["z1"])})) "{bottom}")')

    def add_doping(self):
        if not bool(self.a("doping_enable", True)):
            return
        self.sde.section("Source/drain doping")
        groups = {
            "nmos": (
                "NMOS_SD_Doping",
                str(self.a("nmos_doping_species", "ArsenicActiveConcentration")),
                float(self.a("nmos_doping_concentration", 8e19)),
            ),
            "pmos": (
                "PMOS_SD_Doping",
                str(self.a("pmos_doping_species", "BoronActiveConcentration")),
                float(self.a("pmos_doping_concentration", 8e19)),
            ),
        }
        for kind, (profile, species, concentration) in groups.items():
            regions = [name for name, region_kind in self.sd_regions if region_kind == kind]
            if not regions:
                continue
            self.sde.add(f'(sdedr:define-constant-profile "{profile}" "{species}" {concentration:.6g})')
            for index, region_name in enumerate(regions):
                self.sde.add(
                    f'(sdedr:define-constant-profile-region "Place_{profile}_{index}" "{profile}" "{region_name}")'
                )

    def add_meshing(self):
        if not bool(self.a("meshing_enable", True)) or not self.sde.regions:
            return
        self.sde.section("Meshing")
        b = self.boundary
        z_min = min(region["z1"] for region in self.sde.regions)
        z_max = max(region["z2"] for region in self.sde.regions)
        margin = max(
            float(self.a("global_mesh_max_x", 0.02)),
            float(self.a("global_mesh_max_y", 0.02)),
            float(self.a("global_mesh_max_z", 0.02)),
        )
        self.sde.add(
            f'(sdedr:define-refeval-window "Global_Win" "Cuboid" '
            f'(position {fmt(b["x1"] - margin)} {fmt(b["y1"] - margin)} {fmt(z_min - margin)}) '
            f'(position {fmt(b["x2"] + margin)} {fmt(b["y2"] + margin)} {fmt(z_max + margin)}))'
        )
        self.sde.add(
            f'(sdedr:define-refinement-size "Global_Mesh_Size" '
            f'{float(self.a("global_mesh_max_x", 0.02)):.6g} {float(self.a("global_mesh_max_y", 0.02)):.6g} {float(self.a("global_mesh_max_z", 0.02)):.6g} '
            f'{float(self.a("global_mesh_min_x", 0.01)):.6g} {float(self.a("global_mesh_min_y", 0.01)):.6g} {float(self.a("global_mesh_min_z", 0.01)):.6g})'
        )
        self.sde.add('(sdedr:define-refinement-placement "Global_Mesh_Place" "Global_Mesh_Size" "Global_Win")')
        self.sde.add(
            f'(sdedr:define-refeval-window "Core_Win" "Cuboid" '
            f'(position {fmt(b["x1"])} {fmt(b["y1"])} {fmt(float(self.a("core_mesh_window_z_min", z_min)))}) '
            f'(position {fmt(b["x2"])} {fmt(b["y2"])} {fmt(float(self.a("core_mesh_window_z_max", z_max))) }))'
        )
        self.sde.add(
            f'(sdedr:define-refinement-size "Core_Mesh_Size" '
            f'{float(self.a("core_mesh_max_x", 0.002)):.6g} {float(self.a("core_mesh_max_y", 0.002)):.6g} {float(self.a("core_mesh_max_z", 0.002)):.6g} '
            f'{float(self.a("core_mesh_min_x", 0.001)):.6g} {float(self.a("core_mesh_min_y", 0.001)):.6g} {float(self.a("core_mesh_min_z", 0.001)):.6g})'
        )
        self.sde.add('(sdedr:define-refinement-placement "Core_Mesh_Place" "Core_Mesh_Size" "Core_Win")')
        mesh_output_name = str(self.a("mesh_output_name", self.output_name))
        self.sde.add(
            f'(sde:build-mesh "{self.a("mesh_engine", "snmesh")}" '
            f'"{self.a("mesh_options", "-a -c boxmethod")}" "{mesh_output_name}")'
        )


def derive_output_name(layout_path):
    stem = os.path.splitext(os.path.basename(layout_path))[0]
    return f"n@node@_{stem}_sde"


def derive_noname_path(output_path):
    root, ext = os.path.splitext(output_path)
    return f"{root}_noname{ext or '.cmd'}"


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Generate a Sentaurus SDE command file directly from layout/rules.")
    parser.add_argument("layout", help="layout txt: x1 y1 x2 y2 layer_num [label] [net]")
    parser.add_argument("arch", help="architecture/process parameter file")
    parser.add_argument("layers", help="layer rule file")
    parser.add_argument("-o", "--output", default=None, help="output .cmd path")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])
    for key in ("layout", "arch", "layers"):
        path = getattr(args, key)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Missing {key} file: {path}")
    output = args.output or os.path.join("output_SDE", os.path.splitext(os.path.basename(args.layout))[0] + "_sde.cmd")
    arch = parse_arch(args.arch)
    layout = parse_layout(args.layout)
    rules = parse_layer_rules(args.layers, arch)
    writer = SDEBuilder(layout, rules, arch, derive_output_name(args.layout)).build()
    writer.write(output)
    noname_output = derive_noname_path(output)
    noname_writer = SDEBuilder(layout, rules, arch, derive_output_name(args.layout), noname=True).build()
    noname_writer.write(noname_output)
    print(f"SDE command file generated: {output}")
    print(f"Noname SDE command file generated: {noname_output}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
