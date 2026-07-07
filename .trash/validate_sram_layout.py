import os
import sys

from gen_sram_sde import derive_active_rect, parse_arch, parse_layout


EPS = 1e-6
METAL_LAYERS = {17, 18, 19, 20, 21, 22, 23, 52, 53, 54}
CONDUCTIVE_LAYERS = {17, 18, 19, 20, 21, 22, 23, 52, 53, 54, 111, 121, 122}
REQUIRED_NETS = {"WL", "BL", "BLB", "Q", "QB", "VDD", "VSS"}
ALLOWED_LAYER_CONNECTIONS = {
    frozenset((111, 18)),
    frozenset((121, 18)),
    frozenset((122, 18)),
    frozenset((121, 17)),
    frozenset((122, 17)),
    frozenset((121, 52)),
    frozenset((122, 52)),
    frozenset((17, 18)),
    frozenset((17, 52)),
    frozenset((18, 19)),
    frozenset((19, 20)),
    frozenset((20, 21)),
    frozenset((21, 22)),
    frozenset((22, 23)),
    frozenset((52, 53)),
    frozenset((53, 54)),
}


def overlaps(a, b):
    return min(a["x2"], b["x2"]) > max(a["x1"], b["x1"]) + EPS and min(a["y2"], b["y2"]) > max(a["y1"], b["y1"]) + EPS


def touches(a, b):
    return (
        min(a["x2"], b["x2"]) >= max(a["x1"], b["x1"]) - EPS
        and min(a["y2"], b["y2"]) >= max(a["y1"], b["y1"]) - EPS
    )


def check_net_connectivity(layout, name):
    errors = []
    for net in REQUIRED_NETS:
        objects = [
            rect
            for layer_num, rects in layout.items()
            if layer_num in CONDUCTIVE_LAYERS
            for rect in rects
            if rect["net"] == net
        ]
        if not objects:
            errors.append(f"{name}: net {net} has no conductive layout objects.")
            continue
        adjacency = [set() for _ in objects]
        for first_idx, first in enumerate(objects):
            for second_idx in range(first_idx + 1, len(objects)):
                second = objects[second_idx]
                same_layer = first["layer_num"] == second["layer_num"]
                allowed_pair = frozenset((first["layer_num"], second["layer_num"])) in ALLOWED_LAYER_CONNECTIONS
                if (same_layer or allowed_pair) and touches(first, second):
                    adjacency[first_idx].add(second_idx)
                    adjacency[second_idx].add(first_idx)
        seen = {0}
        stack = [0]
        while stack:
            current = stack.pop()
            for neighbor in adjacency[current]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        if len(seen) != len(objects):
            disconnected = [
                f"L{objects[idx]['layer_num']}:{objects[idx]['label']}"
                for idx in range(len(objects))
                if idx not in seen
            ]
            errors.append(f"{name}: net {net} has disconnected objects: {', '.join(disconnected)}.")
    return errors


def near(value, target, tolerance=1e-5):
    return abs(value - target) <= tolerance


def boundary(layout):
    rects = layout.get(1, [])
    if not rects:
        raise ValueError("Missing layer 1 cell boundary.")
    return {
        "x1": min(r["x1"] for r in rects),
        "y1": min(r["y1"] for r in rects),
        "x2": max(r["x2"] for r in rects),
        "y2": max(r["y2"] for r in rects),
    }


def check_track_rect(rect, axis, origin, pitch, width, lower, upper, description):
    center = (rect[f"{axis}1"] + rect[f"{axis}2"]) / 2
    approx_index = round((center - origin) / pitch)
    track_center = origin + approx_index * pitch
    expected_low = max(lower, track_center - width / 2)
    expected_high = min(upper, track_center + width / 2)
    if not near(rect[f"{axis}1"], expected_low) or not near(rect[f"{axis}2"], expected_high):
        return (
            f"{description} {rect['label']} is off-grid: "
            f"{axis}=[{rect[f'{axis}1']:.5f},{rect[f'{axis}2']:.5f}], "
            f"nearest track center={track_center:.5f}, CD={width:.5f}"
        )
    return None


def validate_case(layout_file, arch_file):
    layout = parse_layout(layout_file)
    arch = parse_arch(arch_file)
    b = boundary(layout)
    errors = []
    name = os.path.basename(layout_file)

    expected_gate_nets = {
        "PG_L": "WL",
        "PD_L": "QB",
        "PU_L": "QB",
        "PD_R": "Q",
        "PU_R": "Q",
        "PG_R": "WL",
    }
    expected_sd_nets = {
        "PG_L": {"BL", "Q"},
        "PD_L": {"VSS", "Q"},
        "PD_R": {"VSS", "QB"},
        "PG_R": {"QB", "BLB"},
        "PU_L": {"VDD", "Q"},
        "PU_R": {"VDD", "QB"},
    }

    expected_x = float(arch["ch"])
    expected_y = float(arch["cpp"]) * int(float(arch.get("cpp_count_y", arch.get("sram_num_cpp", 4))))
    if not near(b["x2"] - b["x1"], expected_x):
        errors.append(f"{name}: boundary x size does not match decisive CH {expected_x:.5f}.")
    if not near(b["y2"] - b["y1"], expected_y):
        errors.append(f"{name}: boundary y size does not match CPP count {expected_y:.5f}.")
    if "cell_width" in arch and not near(float(arch["cell_width"]), expected_x):
        errors.append(f"{name}: compatibility cell_width must equal CH.")
    if "cell_height" in arch and not near(float(arch["cell_height"]), expected_y):
        errors.append(f"{name}: compatibility cell_height must equal CPP * cpp_count_y.")
    if "mmp" in arch and "sram_mmp_count_x" in arch:
        mmp_width = float(arch["mmp"]) * int(float(arch["sram_mmp_count_x"]))
        if not near(mmp_width, expected_x):
            errors.append(f"{name}: CH must equal MMP * sram_mmp_count_x ({mmp_width:.5f}).")

    for layer_num, rects in layout.items():
        for rect in rects:
            if rect["x1"] < b["x1"] - EPS or rect["y1"] < b["y1"] - EPS or rect["x2"] > b["x2"] + EPS or rect["y2"] > b["y2"] + EPS:
                errors.append(f"{name}: L{layer_num} {rect['label']} exceeds cell boundary.")
        if layer_num in METAL_LAYERS:
            for idx, first in enumerate(rects):
                for second in rects[idx + 1:]:
                    if first["net"] and second["net"] and first["net"] != second["net"] and overlaps(first, second):
                        errors.append(
                            f"{name}: L{layer_num} different-net overlap "
                            f"{first['label']}({first['net']}) / {second['label']}({second['net']})."
                        )

    cpp = float(arch["cpp"])
    gate_y = float(arch.get("gate_length_y", arch.get("gate_length", 0.014)))
    gate_extension = float(arch["gate_extension_x_each_side"])
    for gate in layout.get(111, []):
        dev_type = "pmos" if gate["label"].startswith("PU") else "nmos"
        sd_layer = 122 if dev_type == "pmos" else 121
        sds = [
            rect for rect in layout.get(sd_layer, [])
            if gate["label"] in rect["label"].replace("+", " ").split()
            or rect["label"].startswith(gate["label"] + "_")
        ]
        if len(sds) < 2:
            errors.append(f"{name}: gate {gate['label']} has fewer than two S/D objects.")
            continue
        active = derive_active_rect(arch, gate, sds, dev_type)
        gate_x = active["x2"] - active["x1"] + 2 * gate_extension
        if not near(gate["y2"] - gate["y1"], gate_y):
            errors.append(f"{name}: gate {gate['label']} y length must be {gate_y:.5f}.")
        if gate["x2"] - gate["x1"] + EPS < gate_x:
            errors.append(f"{name}: gate {gate['label']} x extension is shorter than {gate_x:.5f}.")
        center_y = (gate["y1"] + gate["y2"]) / 2
        index = round((center_y - cpp / 2) / cpp)
        expected_center = cpp / 2 + index * cpp
        if not near(center_y, expected_center):
            errors.append(f"{name}: gate {gate['label']} center y={center_y:.5f} is not on a CPP track.")
        expected_net = expected_gate_nets.get(gate["label"])
        if expected_net and gate["net"] != expected_net:
            errors.append(f"{name}: gate {gate['label']} must connect to {expected_net}, not {gate['net']}.")

    if layout.get(101) or layout.get(102):
        errors.append(f"{name}: layers 101/102 are forbidden; active geometry must come from arch hyperparameters.")

    for device, expected in expected_sd_nets.items():
        layer_num = 122 if device.startswith("PU") else 121
        nets = {
            rect["net"] for rect in layout.get(layer_num, [])
            if device in rect["label"].replace("+", " ").split()
            or rect["label"].startswith(device + "_")
            or rect["label"] == device
        }
        if nets != expected:
            errors.append(f"{name}: {device} S/D nets must be {sorted(expected)}, not {sorted(nets)}.")

    epi_extension = float(arch["epi_extension_x_each_side"])
    for layer_num, polarity in ((121, "n"), (122, "p")):
        expected_span = float(arch[f"{polarity}_active_width"]) + 2 * epi_extension
        for rect in layout.get(layer_num, []):
            if not near(rect["x2"] - rect["x1"], expected_span):
                errors.append(
                    f"{name}: {rect['label']} EPI x span must be active width + "
                    f"2*epi_extension = {expected_span:.5f}."
                )
        expected_length = float(arch.get("sd_epi_length_y", 0.009))
        for rect in layout.get(layer_num, []):
            length = rect["y2"] - rect["y1"]
            if not near(length, expected_length) and not near(length, 2 * expected_length):
                errors.append(
                    f"{name}: {rect['label']} EPI y length must be outer {expected_length:.5f} "
                    f"or shared {2 * expected_length:.5f}."
                )

    shared_q = [r for r in layout.get(121, []) if r["net"] == "Q" and "+" in r["label"]]
    shared_qb = [r for r in layout.get(121, []) if r["net"] == "QB" and "+" in r["label"]]
    if len(shared_q) != 1 or len(shared_qb) != 1:
        errors.append(f"{name}: top chains require exactly one shared Q SD and one shared QB SD.")
    vmm = layout.get(17, [])
    if bool(arch.get("vmm_enable", False)):
        if len(vmm) > 1:
            errors.append(f"{name}: minimal sCFET topology permits at most one VMM bypass.")
    elif vmm:
        errors.append(f"{name}: VMM geometry exists while vmm_enable=false.")

    m0_origin = float(arch.get("m0_track_origin_x", 0.0))
    m0_pitch = float(arch.get("m0_pitch", 0.018))
    m0_cd = float(arch.get("m0_cd", 0.010))
    for rect in layout.get(19, []):
        if rect["y2"] - rect["y1"] > 0.02:
            error = check_track_rect(rect, "x", m0_origin, m0_pitch, m0_cd, b["x1"], b["x2"], "M0")
            if error:
                errors.append(f"{name}: {error}")

    m1_origin = float(arch.get("m1_track_origin_y", cpp / 2))
    m1_pitch = float(arch.get("m1_pitch", cpp))
    m1_cd = float(arch.get("m1_cd", 0.010))
    for rect in layout.get(21, []):
        if rect["label"].startswith("M1_T"):
            error = check_track_rect(rect, "y", m1_origin, m1_pitch, m1_cd, b["y1"], b["y2"], "M1")
            if error:
                errors.append(f"{name}: {error}")

    m2_origin = float(arch.get("m2_track_origin_x", m0_origin))
    m2_pitch = float(arch.get("m2_pitch", m0_pitch))
    m2_cd = float(arch.get("m2_cd", m0_cd))
    for rect in layout.get(23, []):
        if rect["y2"] - rect["y1"] > 0.02:
            error = check_track_rect(rect, "x", m2_origin, m2_pitch, m2_cd, b["x1"], b["x2"], "M2")
            if error:
                errors.append(f"{name}: {error}")

    bm0_origin = float(arch.get("bm0_track_origin_x", 0.0))
    bm0_pitch = float(arch.get("bm0_pitch", 0.031))
    bm0_cd = float(arch.get("bm0_cd", 0.010))
    for rect in layout.get(53, []):
        if rect["y2"] - rect["y1"] > 0.02:
            error = check_track_rect(rect, "x", bm0_origin, bm0_pitch, bm0_cd, b["x1"], b["x2"], "BM0")
            if error:
                errors.append(f"{name}: {error}")

    errors.extend(check_net_connectivity(layout, name))

    return errors


def main(argv):
    base = os.path.dirname(os.path.abspath(__file__))
    if len(argv) == 3:
        cases = [(argv[1], argv[2])]
    elif len(argv) == 1:
        cases = [
            (os.path.join(base, "gds", "sram_6t_mcfet_cg_gds.txt"), os.path.join(base, "rules", "sram_mcfet_cg_arch.txt")),
            (os.path.join(base, "gds", "sram_6t_hdr_denseBM0_gds.txt"), os.path.join(base, "rules", "sram_hdr_denseBM0_arch.txt")),
            (os.path.join(base, "gds", "sram_6t_hdr_split_gate_gds.txt"), os.path.join(base, "rules", "sram_hdr_split_gate_arch.txt")),
            (os.path.join(base, "gds", "sram_6t_scfet_gds.txt"), os.path.join(base, "rules", "sram_scfet_arch.txt")),
        ]
    else:
        print("Usage: python validate_sram_layout.py [layout_gds.txt arch.txt]")
        return 2

    errors = []
    for layout_file, arch_file in cases:
        errors.extend(validate_case(layout_file, arch_file))
    if errors:
        for error in errors:
            print(error)
        return 1
    print("SRAM geometry/topology/connectivity precheck passed; this is not an extracted LVS result.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
