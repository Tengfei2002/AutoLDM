import os
import sys

from gen_sram_sde import parse_arch, parse_layout


EPS = 1e-6
POTENTIALS = {"P1", "P2", "P3", "P4", "P5", "P6", "P7"}
METAL_LAYERS = {16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 51, 52, 53}
CONDUCTIVE_LAYERS = METAL_LAYERS | {111, 121, 122}
ALLOWED_CONNECTIONS = {
    frozenset((111, 18)),
    frozenset((121, 16)),
    frozenset((122, 51)),
    frozenset((16, 17)),
    frozenset((51, 17)),
    frozenset((16, 18)),
    frozenset((17, 18)),
    frozenset((18, 19)),
    frozenset((19, 20)),
    frozenset((20, 21)),
    frozenset((21, 22)),
    frozenset((22, 23)),
    frozenset((23, 24)),
    frozenset((24, 25)),
    frozenset((51, 52)),
    frozenset((52, 53)),
}


def overlaps(a, b):
    return (
        min(a["x2"], b["x2"]) > max(a["x1"], b["x1"]) + EPS
        and min(a["y2"], b["y2"]) > max(a["y1"], b["y1"]) + EPS
    )


def touches(a, b):
    return (
        min(a["x2"], b["x2"]) >= max(a["x1"], b["x1"]) - EPS
        and min(a["y2"], b["y2"]) >= max(a["y1"], b["y1"]) - EPS
    )


def near(a, b):
    return abs(a - b) <= 1e-5


def boundary(layout):
    rects = layout.get(1, [])
    if len(rects) != 1:
        raise ValueError("Standard layout requires exactly one layer-1 boundary.")
    return rects[0]


def check_bounds(layout, arch, name):
    errors = []
    b = boundary(layout)
    width = float(arch["cpp"]) * int(float(arch["sram_cpp_count"]))
    height = float(arch["double_row_height"])
    if not near(b["x1"], 0.0) or not near(b["y1"], 0.0):
        errors.append(f"{name}: boundary origin must be (0, 0).")
    if not near(b["x2"], width) or not near(b["y2"], height):
        errors.append(f"{name}: boundary must be {width:.5f} x {height:.5f}.")

    m0_boundary = {
        (float(arch["m0_track_0_y1"]), float(arch["m0_track_0_y2"])),
        (float(arch["m0_track_6_y1"]), float(arch["m0_track_6_y2"])),
    }
    bm0_boundary = {
        (float(arch["bm0_track_0_y1"]), float(arch["bm0_track_0_y2"])),
        (float(arch["bm0_track_4_y1"]), float(arch["bm0_track_4_y2"])),
    }
    for layer, rects in layout.items():
        for rect in rects:
            if rect["x1"] < -EPS or rect["x2"] > width + EPS:
                errors.append(f"{name}: L{layer} {rect['label']} exceeds CPP width.")
            y_out = rect["y1"] < -EPS or rect["y2"] > height + EPS
            allowed = (
                layer == 19 and (rect["y1"], rect["y2"]) in m0_boundary
            ) or (
                layer == 53 and (rect["y1"], rect["y2"]) in bm0_boundary
            )
            if y_out and not allowed:
                errors.append(f"{name}: L{layer} {rect['label']} illegally exceeds Cell Height.")
    return errors


def check_same_layer_shorts(layout, name):
    errors = []
    for layer in METAL_LAYERS:
        rects = layout.get(layer, [])
        for index, first in enumerate(rects):
            for second in rects[index + 1:]:
                if first["net"] != second["net"] and overlaps(first, second):
                    errors.append(
                        f"{name}: L{layer} short risk: "
                        f"{first['label']}({first['net']}) overlaps "
                        f"{second['label']}({second['net']})."
                    )
    return errors


def check_m1_plus(layout, arch, name):
    errors = []
    cd = float(arch["m1_plus_cd"])
    pitch = float(arch["m1_plus_min_pitch"])
    directions = {21: "y", 23: "x", 25: "y"}
    for layer, direction in directions.items():
        wires = []
        for rect in layout.get(layer, []):
            width = rect["x2"] - rect["x1"] if direction == "y" else rect["y2"] - rect["y1"]
            if not near(width, cd):
                errors.append(f"{name}: L{layer} {rect['label']} width must be {cd:.5f}.")
            long_axis = rect["y2"] - rect["y1"] if direction == "y" else rect["x2"] - rect["x1"]
            if long_axis > cd + EPS:
                wires.append(rect)
        for index, first in enumerate(wires):
            for second in wires[index + 1:]:
                parallel_overlap = (
                    min(first["y2"], second["y2"]) > max(first["y1"], second["y1"]) + EPS
                    if direction == "y"
                    else min(first["x2"], second["x2"]) > max(first["x1"], second["x1"]) + EPS
                )
                if not parallel_overlap or first["net"] == second["net"]:
                    continue
                axis = "x" if direction == "y" else "y"
                c1 = (first[f"{axis}1"] + first[f"{axis}2"]) / 2
                c2 = (second[f"{axis}1"] + second[f"{axis}2"]) / 2
                if abs(c1 - c2) < pitch - EPS:
                    errors.append(
                        f"{name}: L{layer} {first['label']}/{second['label']} "
                        f"parallel pitch {abs(c1-c2):.5f} < {pitch:.5f}."
                    )
    for layer in (20, 22, 24):
        for rect in layout.get(layer, []):
            if not near(rect["x2"] - rect["x1"], 0.008) or not near(rect["y2"] - rect["y1"], 0.008):
                errors.append(f"{name}: L{layer} {rect['label']} must be an 8 nm square via.")
    return errors


def check_fixed_layers(layout, arch, name):
    errors = []
    cpp = float(arch["cpp"])
    gate_length = float(arch["gate_length_cpp"])
    gate_slots = [
        (
            cpp * index + (cpp - gate_length) / 2,
            cpp * index + (cpp + gate_length) / 2,
        )
        for index in range(int(float(arch["sram_cpp_count"])))
    ]
    row_windows = {
        (0.0165, 0.0455),
        (0.0785, 0.1075),
    }
    for rect in layout.get(111, []):
        legal_x = any(near(rect["x1"], x1) and near(rect["x2"], x2) for x1, x2 in gate_slots)
        legal_y = any(near(rect["y1"], y1) and near(rect["y2"], y2) for y1, y2 in row_windows)
        if not legal_x or not legal_y:
            errors.append(f"{name}: gate {rect['label']} is outside a legal CPP/half-row slot.")

    m0_windows = {
        (float(arch[f"m0_track_{index}_y1"]), float(arch[f"m0_track_{index}_y2"]))
        for index in range(7)
    }
    bm0_windows = {
        (float(arch[f"bm0_track_{index}_y1"]), float(arch[f"bm0_track_{index}_y2"]))
        for index in range(5)
    }
    for rect in layout.get(19, []):
        if (rect["y1"], rect["y2"]) not in m0_windows:
            errors.append(f"{name}: M0 {rect['label']} is outside a fixed M0 track window.")
    for rect in layout.get(53, []):
        if (rect["y1"], rect["y2"]) not in bm0_windows:
            errors.append(f"{name}: BM0 {rect['label']} is outside a fixed BM0 track window.")

    for layer, description in ((16, "MD"), (51, "BMD")):
        for rect in layout.get(layer, []):
            if not near(rect["x2"] - rect["x1"], 0.008):
                errors.append(f"{name}: {description} {rect['label']} CPP width must be 8 nm.")
    for layer, description in ((18, "V0"), (52, "BV0")):
        for rect in layout.get(layer, []):
            if not near(rect["x2"] - rect["x1"], 0.008) or not near(rect["y2"] - rect["y1"], 0.008):
                errors.append(f"{name}: {description} {rect['label']} must be an 8 nm square.")
    return errors


def check_via_landings(layout, name):
    errors = []
    upper_layers = {18: 19, 20: 21, 22: 23, 24: 25, 52: 53}
    for via_layer, metal_layer in upper_layers.items():
        for via in layout.get(via_layer, []):
            candidates = [
                metal for metal in layout.get(metal_layer, [])
                if metal["net"] == via["net"]
                and metal["x1"] <= via["x1"] + EPS
                and metal["y1"] <= via["y1"] + EPS
                and metal["x2"] >= via["x2"] - EPS
                and metal["y2"] >= via["y2"] - EPS
            ]
            if not candidates:
                errors.append(
                    f"{name}: L{via_layer} {via['label']} is not fully covered "
                    f"by same-net L{metal_layer}."
                )
                continue
            if via_layer in {20, 22, 24}:
                metal = min(candidates, key=lambda rect: (rect["x2"] - rect["x1"]) * (rect["y2"] - rect["y1"]))
                enclosure = [
                    via["x1"] - metal["x1"],
                    metal["x2"] - via["x2"],
                    via["y1"] - metal["y1"],
                    metal["y2"] - via["y2"],
                ]
                if sum(near(value, 0.003) for value in enclosure) < 3:
                    errors.append(
                        f"{name}: {via['label']} must have 3 nm enclosure on "
                        f"at least three M1+ landing edges; got {enclosure}."
                    )
    return errors


def check_topology(layout, name):
    errors = []
    expected = {
        "GATE_PG1": "P7",
        "GATE_PD1_PU1": "P5",
        "GATE_PD2_PU2": "P2",
        "GATE_PG2": "P7",
    }
    gates = {rect["label"]: rect["net"] for rect in layout.get(111, [])}
    if gates != expected:
        errors.append(f"{name}: gate mapping is {gates}, expected {expected}.")
    shared = {
        ("SDN_PG1_PD1_SHARED", "P2"),
        ("SDN_PD2_PG2_SHARED", "P5"),
    }
    actual = {(rect["label"], rect["net"]) for rect in layout.get(121, [])}
    if not shared.issubset(actual):
        errors.append(f"{name}: missing P2/P5 shared NFET S/D.")
    mrw = {(rect["label"], rect["net"]) for rect in layout.get(17, [])}
    if mrw != {("MRW_Q", "P2"), ("MRW_QB", "P5")}:
        errors.append(f"{name}: MRW must contain one continuous P2 site and one continuous P5 site.")
    for rect in layout.get(17, []):
        if not near(rect["x2"] - rect["x1"], 0.008) or not near(rect["y1"], 0.056) or not near(rect["y2"], 0.068):
            errors.append(f"{name}: {rect['label']} must be 8 nm wide and span y=56..68 nm.")
        center_x = (rect["x1"] + rect["x2"]) / 2
        legal_centers = {0.021, 0.042, 0.063, 0.084, 0.105}
        if not any(near(center_x, center) for center in legal_centers):
            errors.append(
                f"{name}: {rect['label']} center x={center_x:.5f} must align "
                f"with a gate or the midpoint of adjacent gates."
            )
    return errors


def check_connectivity(layout, name):
    errors = []
    for net in POTENTIALS:
        objects = [
            rect for layer, rects in layout.items()
            if layer in CONDUCTIVE_LAYERS
            for rect in rects if rect["net"] == net
        ]
        if not objects:
            errors.append(f"{name}: {net} has no geometry.")
            continue
        adjacency = [set() for _ in objects]
        for i, first in enumerate(objects):
            for j in range(i + 1, len(objects)):
                second = objects[j]
                same = first["layer_num"] == second["layer_num"]
                allowed = frozenset((first["layer_num"], second["layer_num"])) in ALLOWED_CONNECTIONS
                if (same or allowed) and touches(first, second):
                    adjacency[i].add(j)
                    adjacency[j].add(i)
        components = []
        unseen = set(range(len(objects)))
        while unseen:
            root = unseen.pop()
            component = {root}
            stack = [root]
            while stack:
                current = stack.pop()
                for neighbor in adjacency[current]:
                    if neighbor in unseen:
                        unseen.remove(neighbor)
                        component.add(neighbor)
                        stack.append(neighbor)
            components.append(component)
        allowed_components = 2 if net == "P3" else 1
        if len(components) > allowed_components:
            descriptions = [
                "/".join(f"L{objects[i]['layer_num']}:{objects[i]['label']}" for i in sorted(component))
                for component in components
            ]
            errors.append(f"{name}: {net} has {len(components)} components: {' | '.join(descriptions)}.")
    return errors


def validate(layout_file, arch_file):
    layout = parse_layout(layout_file)
    arch = parse_arch(arch_file)
    name = os.path.basename(layout_file)
    errors = []
    errors.extend(check_bounds(layout, arch, name))
    errors.extend(check_same_layer_shorts(layout, name))
    errors.extend(check_fixed_layers(layout, arch, name))
    errors.extend(check_via_landings(layout, name))
    errors.extend(check_m1_plus(layout, arch, name))
    errors.extend(check_topology(layout, name))
    errors.extend(check_connectivity(layout, name))
    return errors


def main(argv):
    base = os.path.dirname(os.path.abspath(__file__))
    layout_file = argv[1] if len(argv) > 1 else os.path.join(base, "gds", "sram_standard_6t_gds.txt")
    arch_file = argv[2] if len(argv) > 2 else os.path.join(base, "rules", "sram_standard_arch.txt")
    errors = validate(layout_file, arch_file)
    if errors:
        print("\n".join(errors))
        return 1
    print("sram_standard geometry, topology, pitch, short and abstract-connectivity checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
