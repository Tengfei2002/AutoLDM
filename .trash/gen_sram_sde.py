import os
import sys


EPS = 1e-9

GATE_MARKER_LAYER = 111
SD_N_LAYER = 121
SD_P_LAYER = 122
LAYOUT_FEOL_LAYERS = {1, GATE_MARKER_LAYER, SD_N_LAYER, SD_P_LAYER}


def parse_value(raw):
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


def fmt(value):
    if isinstance(value, int):
        value = float(value)
    if isinstance(value, float):
        return f"{value:.5f}"
    return str(value)


def parse_layout(filepath):
    layout = {}
    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            raw = line.strip()
            if not raw or raw.startswith("%"):
                continue
            parts = raw.split()
            if len(parts) < 5:
                raise ValueError(f"Invalid layout line {line_num}: {raw}")
            x1, y1, x2, y2 = map(float, parts[:4])
            layer_num = int(float(parts[4]))
            label = parts[5] if len(parts) >= 6 else f"L{layer_num}_{len(layout.get(layer_num, []))}"
            net = parts[6] if len(parts) >= 7 else ""
            rect = {
                "x1": min(x1, x2),
                "y1": min(y1, y2),
                "x2": max(x1, x2),
                "y2": max(y1, y2),
                "layer_num": layer_num,
                "label": label,
                "net": net,
                "line_num": line_num,
                "raw": raw,
            }
            layout.setdefault(layer_num, []).append(rect)
    return layout


def parse_layer_rules(filepath):
    rules = {}
    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            raw = line.strip()
            if not raw or raw.startswith("%"):
                continue
            parts = raw.split()
            if len(parts) < 9:
                raise ValueError(f"Invalid layer rule line {line_num}: {raw}")
            layer_num = int(parts[0])
            enable = parts[2].lower() == "true"
            height = float(parts[3])
            start_z = float(parts[4])
            end_z = float(parts[5])
            if enable and abs((end_z - start_z) - height) > 1e-5:
                raise ValueError(
                    f"Layer {layer_num} z rule mismatch at line {line_num}: "
                    f"end_z2 - start_z1 = {end_z - start_z}, height = {height}; raw: {raw}"
                )
            rules[layer_num] = {
                "layer_name": parts[1],
                "enable": enable,
                "height": height,
                "start_z": start_z,
                "end_z": end_z,
                "material": parts[6],
                "boundary": parts[7],
                "ild": parts[8],
                "line_num": line_num,
                "raw": raw,
            }
    return rules


def parse_arch(filepath):
    arch = {}
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            clean = line.split("%", 1)[0].strip()
            if not clean or "=" not in clean:
                continue
            key, value = clean.split("=", 1)
            arch[key.strip()] = parse_value(value)
    return arch


def derive_active_rect(arch, gate, sd_rects, dev_type):
    polarity = "p" if dev_type == "pmos" else "n"
    width = float(arch[f"{polarity}_active_width"])
    gate_center_x = (gate["x1"] + gate["x2"]) / 2.0
    side = "left" if gate_center_x < float(arch["ch"]) / 2.0 else "right"
    center_x = float(arch[f"{polarity}_active_{side}_center_x"])
    y1 = min([gate["y1"]] + [rect["y1"] for rect in sd_rects])
    y2 = max([gate["y2"]] + [rect["y2"] for rect in sd_rects])
    return {
        "x1": center_x - width / 2.0,
        "y1": y1,
        "x2": center_x + width / 2.0,
        "y2": y2,
        "label": gate["label"],
        "net": polarity,
    }


class SDEWriter:
    def __init__(self):
        self.lines = []
        self.regions = []
        self.metal_regions = []

    def add(self, line=""):
        self.lines.append(line)

    def comment(self, text):
        self.add(f"; {text}")

    def section(self, text):
        self.add("")
        self.add("; " + "-" * 70)
        self.comment(text)
        self.add("; " + "-" * 70)

    def cuboid(self, name, x1, y1, z1, x2, y2, z2, material, metal_contact=True):
        if x2 - x1 <= EPS or y2 - y1 <= EPS or z2 - z1 <= EPS:
            return False
        self.add(
            f'(sdegeo:create-cuboid (position {fmt(x1)} {fmt(y1)} {fmt(z1)}) '
            f'(position {fmt(x2)} {fmt(y2)} {fmt(z2)}) "{material}" "{name}")'
        )
        region = {
            "name": name,
            "material": material,
            "x1": x1,
            "y1": y1,
            "z1": z1,
            "x2": x2,
            "y2": y2,
            "z2": z2,
        }
        self.regions.append(region)
        if metal_contact and material in {"Tungsten", "Copper", "Metal"}:
            self.metal_regions.append(region)
        return True

    def write(self, filepath):
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(self.lines) + "\n")


class SRAMBuilder:
    def __init__(self, layout, rules, arch):
        self.layout = layout
        self.rules = rules
        self.arch = arch
        self.sde = SDEWriter()
        self.channel_regions = []
        self.sd_regions = []
        self.sd_contacts = []
        self.gate_contacts = []
        self.built_gate_keys = set()
        self.built_sd_keys = set()
        self.has_backside = self.detect_backside()
        self.boundary = self.get_boundary()
        self.tier_z = self.compute_tier_z()

    def a(self, key, default=None):
        if default is None and key not in self.arch:
            raise KeyError(f"Missing required arch parameter: {key}")
        return self.arch.get(key, default)

    def enabled_rule(self, layer_num):
        rule = self.rules.get(layer_num)
        if not rule or not rule["enable"]:
            return None
        return rule

    def detect_backside(self):
        if str(self.arch.get("bm0_mode", "none")).lower() != "none":
            return True
        for layer_num, rule in self.rules.items():
            name = rule["layer_name"].lower()
            is_backside_name = (
                name.startswith("bm")
                or name.startswith("bv")
                or name.startswith("bmd")
                or name.startswith("bvmd")
            )
            if rule["enable"] and (layer_num >= 52 or is_backside_name):
                return True
        return False

    def get_boundary(self):
        rects = self.layout.get(1, [])
        if rects:
            x1 = min(r["x1"] for r in rects)
            y1 = min(r["y1"] for r in rects)
            x2 = max(r["x2"] for r in rects)
            y2 = max(r["y2"] for r in rects)
            return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
        width = self.a("ch")
        height = self.a("cpp") * self.a("cpp_count_y", self.a("sram_num_cpp", 4.0))
        return {"x1": 0.0, "y1": 0.0, "x2": width, "y2": height}

    def compute_tier_z(self):
        ch_t = self.a("channel_thickness")
        ch_gap = self.a("channel_mdi_thickness")
        mdi = self.a("mdi_thickness")
        n_lower = int(self.a("num_channel_lower", self.a("num_channel", 2)))
        n_upper = int(self.a("num_channel_upeer", self.a("num_channel", 2)))
        lower = []
        z = 0.0
        for _ in range(n_lower):
            z += ch_gap
            lower.append((z, z + ch_t))
            z += ch_t
        z += ch_gap + mdi
        upper = []
        for _ in range(n_upper):
            z += ch_gap
            upper.append((z, z + ch_t))
            z += ch_t
        return {"lower": lower, "upper": upper}

    def build(self):
        self.sde.comment("Generated by AutoLDM/LD/gen_sram_sde.py")
        self.sde.comment("DTCO-oriented abstract CFET SRAM model, not an industrial mask-accurate model.")
        self.sde.comment("x: cell-height/metal-track direction, y: CPP/channel-transport direction, z: CFET vertical stack.")
        self.sde.add("(sde:clear)")
        self.sde.add('(sdegeo:set-default-boolean "ABA")')
        self.build_geometry()
        self.add_contacts()
        self.add_doping()
        self.add_meshing()
        return self.sde

    def build_geometry(self):
        self.sde.section("Geometry")
        self.build_substrate()
        self.build_dielectrics()
        self.build_transistors_from_layout()
        self.build_layout_routing()
        self.build_layout_generic_layers()

    def build_substrate(self):
        rule = self.enabled_rule(1)
        if not rule:
            return
        if self.has_backside:
            self.sde.comment("Substrate skipped because backside interconnect is enabled.")
            return
        b = self.boundary
        self.sde.cuboid("Substrate_1", b["x1"], b["y1"], rule["start_z"], b["x2"], b["y2"], rule["end_z"], "Silicon")

    def build_dielectrics(self):
        if not self.a("dielectric_enable", True):
            return
        b = self.boundary
        spans = [
            ("ILD_FEOL_Lower", 0.000, 0.070),
            ("ILD_MDI", 0.070, 0.100),
            ("ILD_FEOL_Upper", 0.100, 0.170),
            ("ILD_MOL", 0.170, 0.240),
            ("ILD_BEOL", 0.240, 0.285),
        ]
        if self.has_backside:
            spans.insert(0, ("ILD_Backside", -0.095, 0.000))
        for name, z1, z2 in spans:
            self.sde.cuboid(name, b["x1"], b["y1"], z1, b["x2"], b["y2"], z2, "SiO2", False)

    def safe(self, text):
        return "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in str(text))

    def rect_center(self, rect):
        return (rect["x1"] + rect["x2"]) / 2.0, (rect["y1"] + rect["y2"]) / 2.0

    def build_transistors_from_layout(self):
        gates = self.layout.get(GATE_MARKER_LAYER, [])
        self.build_layout_device_set(SD_N_LAYER, "nmos", str(self.a("nmos_tier", "upper")).lower(), gates, ("PG_", "PD_"))
        self.build_layout_device_set(SD_P_LAYER, "pmos", str(self.a("pmos_tier", "lower")).lower(), gates, ("PU_",))

    def build_layout_device_set(self, sd_layer, dev_type, tier, gates, prefixes):
        sd_rects = self.layout.get(sd_layer, [])
        channel_material = str(self.a("p_channel_material" if dev_type == "pmos" else "n_channel_material"))
        for gate in gates:
            inst_name = gate["label"]
            if not inst_name.startswith(prefixes):
                continue
            sds = [
                r for r in sd_rects
                if inst_name in r["label"].replace("+", " ").split()
                or r["label"].startswith(inst_name + "_")
                or r["label"].startswith("SD_" + inst_name + "_")
            ]
            if len(sds) < 2:
                raise ValueError(f"Device {inst_name} requires at least two S/D rectangles on layer {sd_layer}.")
            active = derive_active_rect(self.arch, gate, sds, dev_type)
            self.build_layout_device(active, gate, sds, dev_type, tier, channel_material)

    def build_layout_device(self, active, gate, sd_rects, dev_type, tier, channel_material):
        name = active["label"]
        gate_net = gate["net"]
        gx1, gy1, gx2, gy2 = gate["x1"], gate["y1"], gate["x2"], gate["y2"]
        gz1, gz2, gmat, gprefix = self.gate_z_for(tier)
        cx, cy = self.rect_center(gate)
        hk = self.a("high_k_thickness")
        gate_mode = str(self.a("gate_mode", "common")).lower()
        gate_key = (gx1, gy1, gx2, gy2, gate_net, tier if gate_mode == "split" else "common")
        if gate_key not in self.built_gate_keys:
            gate_name = f"{gprefix}_{self.safe(name)}_{self.safe(gate_net)}"
            self.sde.cuboid(gate_name, gx1, gy1, gz1, gx2, gy2, gz2, gmat)
            self.gate_contacts.append({"name": gate_name, "net": gate_net, "x": cx, "y": cy, "z1": gz1, "z2": gz2})
            self.sde.cuboid(f"HighK_{self.safe(name)}_XMin", gx1 - hk, gy1, gz1, gx1, gy2, gz2, "HfO2", False)
            self.sde.cuboid(f"HighK_{self.safe(name)}_XMax", gx2, gy1, gz1, gx2 + hk, gy2, gz2, "HfO2", False)
            self.sde.cuboid(f"HighK_{self.safe(name)}_YMin", gx1, gy1 - hk, gz1, gx2, gy1, gz2, "HfO2", False)
            self.sde.cuboid(f"HighK_{self.safe(name)}_YMax", gx1, gy2, gz1, gx2, gy2 + hk, gz2, "HfO2", False)
            self.built_gate_keys.add(gate_key)

        ordered_sd = sorted(sd_rects, key=lambda r: (r["y1"] + r["y2"]) / 2.0)
        lower_sd = max((r for r in ordered_sd if r["y2"] <= gy1 + EPS), key=lambda r: r["y2"], default=None)
        upper_sd = min((r for r in ordered_sd if r["y1"] >= gy2 - EPS), key=lambda r: r["y1"], default=None)
        if not lower_sd or not upper_sd:
            raise ValueError(f"Device {name} needs one S/D rectangle on each side of its gate.")
        lower_y1 = lower_sd["y2"]
        lower_y2 = gy1 - hk
        upper_y1 = gy2 + hk
        upper_y2 = upper_sd["y1"]
        cx1, cx2 = active["x1"], active["x2"]
        sheet_ranges = self.tier_z[tier]
        for idx, (z1, z2) in enumerate(sheet_ranges):
            for side, y1, y2 in (("YMin", lower_y1, lower_y2), ("YMax", upper_y1, upper_y2)):
                cname = f"CH_{self.safe(name)}_{side}_{idx}"
                if self.sde.cuboid(cname, cx1, y1, z1, cx2, y2, z2, channel_material, False):
                    self.channel_regions.append(cname)

        self.build_layout_spacer(name, active, gate, gz1, gz2, sheet_ranges, lower_y1, lower_y2, upper_y1, upper_y2)
        self.build_layout_sd(name, sd_rects, dev_type, tier, sheet_ranges)

    def build_layout_spacer(self, name, active, gate, gz1, gz2, sheets, ly1, ly2, uy1, uy2):
        for side, y1, y2 in (("YMin", ly1, ly2), ("YMax", uy1, uy2)):
            prefix = f"IS_{self.safe(name)}_{side}"
            self.sde.cuboid(f"{prefix}_XMin", gate["x1"], y1, gz1, active["x1"], y2, gz2, "Si3N4", False)
            self.sde.cuboid(f"{prefix}_XMax", active["x2"], y1, gz1, gate["x2"], y2, gz2, "Si3N4", False)
            curr = gz1
            for idx, (hz1, hz2) in enumerate(sheets):
                self.sde.cuboid(f"{prefix}_ZGap_{idx}", active["x1"], y1, curr, active["x2"], y2, hz1, "Si3N4", False)
                curr = max(curr, hz2)
            self.sde.cuboid(f"{prefix}_ZGap_{len(sheets)}", active["x1"], y1, curr, active["x2"], y2, gz2, "Si3N4", False)

    def gate_z_for(self, tier):
        gate_mode = str(self.a("gate_mode", "common")).lower()
        if gate_mode == "split":
            layer = 9 if tier == "lower" else 8
            rule = self.enabled_rule(layer)
            if not rule:
                raise ValueError(f"Split gate requires enabled layer {layer}.")
            return rule["start_z"], rule["end_z"], rule["material"], f"Gate_{tier.capitalize()}"
        rule = self.enabled_rule(7)
        if not rule:
            raise ValueError("Common gate requires enabled layer 7.")
        return rule["start_z"], rule["end_z"], rule["material"], "Gate_Common"

    def build_layout_sd(self, inst_name, sd_rects, dev_type, tier, sheets):
        growth_up = self.a("sd_overgrowth_z_up", 0.006)
        growth_down = self.a("sd_overgrowth_z_down", 0.006)
        z1 = min(z[0] for z in sheets) - growth_down
        z2 = max(z[1] for z in sheets) + growth_up
        mat = "Silicon" if dev_type == "nmos" else "SiGe"
        for rect in sd_rects:
            net = rect["net"]
            key = (
                tier, dev_type, net,
                round(rect["x1"], 9), round(rect["y1"], 9),
                round(rect["x2"], 9), round(rect["y2"], 9),
            )
            if key in self.built_sd_keys:
                continue
            name = f"SD_{self.safe(inst_name)}_{self.safe(rect['label'])}_{self.safe(net)}"
            self.sde.cuboid(name, rect["x1"], rect["y1"], z1, rect["x2"], rect["y2"], z2, mat, False)
            self.sd_regions.append((name, dev_type))
            self.sd_contacts.append({
                "name": name,
                "net": net,
                "x1": rect["x1"],
                "y1": rect["y1"],
                "z1": z1,
                "x2": rect["x2"],
                "y2": rect["y2"],
                "z2": z2,
            })
            self.built_sd_keys.add(key)

    def layer_box(self, layer_num, name, x1, y1, x2, y2):
        rule = self.enabled_rule(layer_num)
        if not rule:
            return
        self.sde.cuboid(name, x1, y1, rule["start_z"], x2, y2, rule["end_z"], rule["material"])

    def via(self, name, x, y, z1, z2, size=None):
        if abs(z2 - z1) <= EPS:
            return
        if size is None:
            size = self.a("via_cd", 0.008)
        lo = min(z1, z2)
        hi = max(z1, z2)
        self.sde.cuboid(name, x - size / 2, y - size / 2, lo, x + size / 2, y + size / 2, hi, "Tungsten")

    def metal_pad(self, layer_num, name, x, y, size=None):
        if size is None:
            size = self.a("local_pad_cd", 0.012)
        b = self.boundary
        x1 = max(b["x1"], x - size / 2)
        y1 = max(b["y1"], y - size / 2)
        x2 = min(b["x2"], x + size / 2)
        y2 = min(b["y2"], y + size / 2)
        self.layer_box(layer_num, name, x1, y1, x2, y2)

    def build_layout_routing(self):
        for layer_num, rects in sorted(self.layout.items()):
            if layer_num in LAYOUT_FEOL_LAYERS:
                continue
            rule = self.enabled_rule(layer_num)
            if not rule:
                continue
            for idx, r in enumerate(rects):
                if layer_num == 1:
                    continue
                net = self.safe(r["net"]) if r["net"] else "NONET"
                name = f"{self.safe(rule['layer_name'])}_{self.safe(r['label'])}_{net}_{idx}"
                self.sde.cuboid(name, r["x1"], r["y1"], rule["start_z"], r["x2"], r["y2"], rule["end_z"], rule["material"])

    def build_interconnect_vias(self):
        r_m0 = self.enabled_rule(19)
        r_vm0 = self.enabled_rule(20)
        r_m1 = self.enabled_rule(21)
        r_bvmd = self.enabled_rule(52)
        r_bm0 = self.enabled_rule(53)
        r_vmd = self.enabled_rule(18)
        r_vmm = self.enabled_rule(17)

        q_layer = 18 if self.enabled_rule(18) else 19
        q_rule = self.enabled_rule(q_layer)

        for gate in self.gate_contacts:
            x = gate["x"]
            y = gate["y"]
            net = gate["net"]
            target_layer = q_layer if net in {"Q", "QB"} else 19
            self.metal_pad(target_layer, f"Pad_Gate_{gate['name']}", x, y)
            if net in {"Q", "QB"} and q_rule:
                self.via(f"VIA_Gate_{gate['name']}_to_QMetal", x, y, gate["z2"], q_rule["start_z"])
            elif r_m0:
                self.via(f"VIA_Gate_{gate['name']}_to_M0", x, y, gate["z2"], r_m0["start_z"])
            if net in {"Q", "QB"} and r_vmm and r_vmd:
                self.via(f"VIA_Gate_{gate['name']}_to_VMM", x, y, gate["z2"], r_vmm["start_z"])
                self.via(f"VIA_VMM_{gate['name']}_to_VMD", x, y, r_vmm["end_z"], r_vmd["end_z"])

        for sd in self.sd_contacts:
            x = (sd["x1"] + sd["x2"]) / 2.0
            y = (sd["y1"] + sd["y2"]) / 2.0
            net = sd["net"]
            if net in {"VDD", "VSS"} and self.has_backside and r_bvmd and r_bm0:
                self.metal_pad(52, f"BVMDPad_{sd['name']}", x, y)
                self.metal_pad(53, f"BM0Pad_{sd['name']}", x, y)
                self.via(f"BVI_{sd['name']}_to_BVMD", x, y, sd["z1"], r_bvmd["end_z"])
                self.via(f"VIA_BVMD_{sd['name']}_to_BM0", x, y, r_bvmd["start_z"], r_bm0["end_z"])
            else:
                target_layer = q_layer if net in {"Q", "QB"} else 19
                target_rule = q_rule if net in {"Q", "QB"} else r_m0
                self.metal_pad(target_layer, f"Pad_{sd['name']}", x, y)
                if target_rule:
                    self.via(f"VIA_{sd['name']}_to_Metal", x, y, sd["z2"], target_rule["start_z"])
                elif r_m0:
                    self.via(f"VIA_{sd['name']}_to_M0", x, y, sd["z2"], r_m0["start_z"])
            if net in {"BL", "BLB"} and r_m0 and r_vm0 and r_m1:
                self.metal_pad(21, f"M1Pad_{sd['name']}", x, y)
                self.via(f"VM0_{sd['name']}_to_M1", x, y, r_m0["end_z"], r_m1["start_z"])

    def build_layout_generic_layers(self):
        if not self.a("include_layout_generic_layers", False):
            return
        generated = {1, 7, 8, 9, 10, 17, 18, 19, 21, 52, 53, 54, GATE_MARKER_LAYER, SD_N_LAYER, SD_P_LAYER}
        for layer_num, rects in sorted(self.layout.items()):
            if layer_num in generated:
                continue
            rule = self.enabled_rule(layer_num)
            if not rule:
                continue
            for idx, r in enumerate(rects):
                name = f"Layout_{layer_num}_{rule['layer_name']}_{r['label']}_{idx}"
                self.sde.cuboid(name, r["x1"], r["y1"], rule["start_z"], r["x2"], r["y2"], rule["end_z"], rule["material"])

    def add_contacts(self):
        self.sde.section("Contacts")
        for idx, region in enumerate(self.sde.metal_regions):
            name = region["name"]
            cx = (region["x1"] + region["x2"]) / 2.0
            cy = (region["y1"] + region["y2"]) / 2.0
            top = f"Contact_{name}_Top_{idx}"
            bot = f"Contact_{name}_Bot_{idx}"
            self.sde.add(f'(sdegeo:define-contact-set "{top}" 4 (color:rgb 1 0 0) "##")')
            self.sde.add(f'(sdegeo:define-contact-set "{bot}" 4 (color:rgb 1 0 0) "##")')
            self.sde.add(f'(sdegeo:set-contact (find-face-id (position {fmt(cx)} {fmt(cy)} {fmt(region["z2"])})) "{top}")')
            self.sde.add(f'(sdegeo:set-contact (find-face-id (position {fmt(cx)} {fmt(cy)} {fmt(region["z1"])})) "{bot}")')
        for idx, region in enumerate(self.sd_contacts):
            cx = (region["x1"] + region["x2"]) / 2.0
            cy = (region["y1"] + region["y2"]) / 2.0
            contact = f"Contact_{region['net']}_{region['name']}_{idx}"
            self.sde.add(f'(sdegeo:define-contact-set "{contact}" 4 (color:rgb 0 0 1) "##")')
            self.sde.add(f'(sdegeo:set-contact (find-face-id (position {fmt(cx)} {fmt(cy)} {fmt(region["z2"])})) "{contact}")')

    def add_doping(self):
        if not self.a("doping_enable", True):
            return
        self.sde.section("Doping")
        n_regions = [name for name, typ in self.sd_regions if typ == "nmos"]
        p_regions = [name for name, typ in self.sd_regions if typ == "pmos"]
        self.constant_profile("NMOS_SD_Doping", self.a("nmos_doping_species", "ArsenicActiveConcentration"), self.a("nmos_doping_concentration", 8e19), n_regions)
        self.constant_profile("PMOS_SD_Doping", self.a("pmos_doping_species", "BoronActiveConcentration"), self.a("pmos_doping_concentration", 8e19), p_regions)

    def constant_profile(self, profile_name, species, concentration, regions):
        if not regions:
            return
        self.sde.add(f'(sdedr:define-constant-profile "{profile_name}" "{species}" {concentration:.6g})')
        for idx, region_name in enumerate(regions):
            self.sde.add(f'(sdedr:define-constant-profile-region "Place_{profile_name}_{idx}" "{profile_name}" "{region_name}")')

    def add_meshing(self):
        if not self.a("meshing_enable", True):
            return
        self.sde.section("Meshing")
        b = self.boundary
        z_min = min(region["z1"] for region in self.sde.regions)
        z_max = max(region["z2"] for region in self.sde.regions)
        margin = max(self.a("global_mesh_max_x", 0.02), self.a("global_mesh_max_y", 0.02), self.a("global_mesh_max_z", 0.02))
        self.sde.add(
            f'(sdedr:define-refeval-window "Global_Win" "Cuboid" '
            f'(position {fmt(b["x1"] - margin)} {fmt(b["y1"] - margin)} {fmt(z_min - margin)}) '
            f'(position {fmt(b["x2"] + margin)} {fmt(b["y2"] + margin)} {fmt(z_max + margin)}))'
        )
        self.sde.add(
            f'(sdedr:define-refinement-size "Global_Mesh_Size" '
            f'{self.a("global_mesh_max_x", 0.02):.6g} {self.a("global_mesh_max_y", 0.02):.6g} {self.a("global_mesh_max_z", 0.02):.6g} '
            f'{self.a("global_mesh_min_x", 0.01):.6g} {self.a("global_mesh_min_y", 0.01):.6g} {self.a("global_mesh_min_z", 0.01):.6g})'
        )
        self.sde.add('(sdedr:define-refinement-placement "Global_Mesh_Place" "Global_Mesh_Size" "Global_Win")')
        self.sde.add(
            f'(sdedr:define-refeval-window "Core_Win" "Cuboid" '
            f'(position {fmt(b["x1"])} {fmt(b["y1"])} {fmt(self.a("core_mesh_window_z_min", z_min))}) '
            f'(position {fmt(b["x2"])} {fmt(b["y2"])} {fmt(self.a("core_mesh_window_z_max", z_max))}))'
        )
        self.sde.add(
            f'(sdedr:define-refinement-size "Core_Mesh_Size" '
            f'{self.a("core_mesh_max_x", 0.002):.6g} {self.a("core_mesh_max_y", 0.002):.6g} {self.a("core_mesh_max_z", 0.002):.6g} '
            f'{self.a("core_mesh_min_x", 0.001):.6g} {self.a("core_mesh_min_y", 0.001):.6g} {self.a("core_mesh_min_z", 0.001):.6g})'
        )
        self.sde.add('(sdedr:define-refinement-placement "Core_Mesh_Place" "Core_Mesh_Size" "Core_Win")')
        self.sde.add(
            f'(sde:build-mesh "{self.a("mesh_engine", "snmesh")}" '
            f'"{self.a("mesh_options", "-a -c boxmethod")}" "{self.a("mesh_output_name", "n@node@_sram_6t")}")'
        )


def default_paths(base_dir):
    return {
        "layout": os.path.join(base_dir, "gds", "sram_6t_scfet_gds.txt"),
        "arch": os.path.join(base_dir, "rules", "sram_scfet_arch.txt"),
        "rules": os.path.join(base_dir, "rules", "sram_scfet_layer_rule.txt"),
        "output": os.path.join(base_dir, "SDE", "sram_6t_scfet_sde.cmd"),
    }


def main(argv):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    paths = default_paths(base_dir)
    if len(argv) > 1:
        paths["layout"] = argv[1]
    if len(argv) > 2:
        paths["arch"] = argv[2]
    if len(argv) > 3:
        paths["rules"] = argv[3]
    if len(argv) > 4:
        paths["output"] = argv[4]
    for key in ("layout", "arch", "rules"):
        if not os.path.exists(paths[key]):
            raise FileNotFoundError(f"Missing {key} file: {paths[key]}")

    layout = parse_layout(paths["layout"])
    rules = parse_layer_rules(paths["rules"])
    arch = parse_arch(paths["arch"])
    sde = SRAMBuilder(layout, rules, arch).build()
    sde.write(paths["output"])
    print(f"SRAM SDE command file generated: {paths['output']}")


if __name__ == "__main__":
    try:
        main(sys.argv)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
