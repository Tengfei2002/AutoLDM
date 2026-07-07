import os
import sys


EPS = 1e-9


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
            line = line.strip()
            if not line or line.startswith("%"):
                continue
            parts = line.split()
            if len(parts) < 5:
                raise ValueError(f"Invalid layout line {line_num}: {line}")
            x1, y1, x2, y2 = map(float, parts[:4])
            layer_num = int(float(parts[4]))
            layout[layer_num] = {
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "line_num": line_num,
                "raw": line,
            }
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

    def cuboid(self, name, x1, y1, z1, x2, y2, z2, material):
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
        if material in {"Tungsten", "Copper", "Metal"}:
            self.metal_regions.append(region)
        return True

    def write(self, filepath):
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(self.lines) + "\n")


class StructureBuilder:
    def __init__(self, layout, rules, arch):
        self.layout = layout
        self.rules = rules
        self.arch = arch
        self.sde = SDEWriter()
        self.channels = []
        self.channel_regions = []
        self.has_backside_interconnect = self.detect_backside_interconnect()

    def a(self, key, default=None):
        if default is None and key not in self.arch:
            raise KeyError(f"Missing required arch parameter: {key}")
        return self.arch.get(key, default)

    def enabled_rule(self, layer_num):
        rule = self.rules.get(layer_num)
        if not rule or not rule["enable"]:
            return None
        return rule

    def detect_backside_interconnect(self):
        bm0_mode = str(self.arch.get("bm0_mode", "none")).lower()
        if bm0_mode != "none":
            return True
        for layer_num, rule in self.rules.items():
            if not rule["enable"]:
                continue
            name = rule["layer_name"].lower()
            is_backside_name = (
                name.startswith("bm")
                or name.startswith("bv")
                or name.startswith("bmd")
                or name.startswith("bvmd")
            )
            if layer_num >= 52 or is_backside_name:
                return True
        return False

    def require_layout_rule(self, layer_num, purpose):
        layout = self.layout.get(layer_num)
        rule = self.enabled_rule(layer_num)
        if not layout or not rule:
            raise ValueError(f"Missing enabled layer {layer_num} for {purpose}.")
        return layout, rule

    def build(self):
        self.sde.comment("Generated by AutoLDM/LD/gen_sde.py from guide1/guide2 and rules.")
        self.sde.comment("x: Source-Gate-Drain, y: gate width/channel width, z: vertical stacking.")
        self.sde.add("(sde:clear)")
        self.build_geometry()
        self.add_contacts()
        self.add_doping()
        self.add_meshing()
        return self.sde

    def build_geometry(self):
        self.sde.section("Geometry")
        self.build_substrate()
        self.build_gate()
        self.build_channels()
        self.build_gate_highk()
        self.build_inner_spacers()
        self.build_sd_epi()
        self.build_generic_layout_layers()

    def build_substrate(self):
        layout, rule = self.require_layout_rule(1, "substrate/boundary")
        if self.has_backside_interconnect:
            self.sde.comment("Substrate skipped because backside interconnect is enabled.")
            return
        material = "Silicon"
        self.sde.cuboid(
            "Substrate_1",
            layout["x1"],
            layout["y1"],
            rule["start_z"],
            layout["x2"],
            layout["y2"],
            rule["end_z"],
            material,
        )

    def build_gate(self):
        rule7 = self.enabled_rule(7)
        if 7 in self.layout and rule7:
            l = self.layout[7]
            self.gate_bounds = {
                "x1": l["x1"],
                "y1": l["y1"],
                "x2": l["x2"],
                "y2": l["y2"],
                "z1": rule7["start_z"],
                "z2": rule7["end_z"],
            }
            self.sde.cuboid(
                "Gate_Common",
                l["x1"],
                l["y1"],
                rule7["start_z"],
                l["x2"],
                l["y2"],
                rule7["end_z"],
                rule7["material"],
            )
            return

        split_layers = (8, 9, 10)
        if all(layer in self.layout and self.enabled_rule(layer) for layer in split_layers):
            names = {8: "Gate_Upper", 9: "Gate_Lower", 10: "Gate_Merge"}
            bounds = []
            for layer in split_layers:
                l = self.layout[layer]
                r = self.enabled_rule(layer)
                bounds.append((l, r))
                self.sde.cuboid(
                    names[layer],
                    l["x1"],
                    l["y1"],
                    r["start_z"],
                    l["x2"],
                    l["y2"],
                    r["end_z"],
                    r["material"],
                )
            self.gate_bounds = {
                "x1": min(l["x1"] for l, _ in bounds),
                "y1": min(l["y1"] for l, _ in bounds),
                "x2": max(l["x2"] for l, _ in bounds),
                "y2": max(l["y2"] for l, _ in bounds),
                "z1": min(r["start_z"] for _, r in bounds),
                "z2": max(r["end_z"] for _, r in bounds),
            }
            return

        raise ValueError("Missing gate definition: enable layer 7 or enable layers 8/9/10.")

    def select_count(self):
        num_channel = self.a("num_channel", -1)
        if num_channel == -1:
            return int(self.a("num_channel_lower", 2)), int(self.a("num_channel_upeer", 2))
        return int(num_channel), int(num_channel)

    def select_channel_size(self):
        ch_len = self.a("channel_length", -1)
        ch_wid = self.a("channel_width", -1)
        lower_len = self.a("channel_lower_length", ch_len) if ch_len == -1 else ch_len
        upper_len = self.a("channel_upper_length", ch_len) if ch_len == -1 else ch_len
        lower_wid = self.a("channel_lower_width", ch_wid) if ch_wid == -1 else ch_wid
        upper_wid = self.a("channel_upper_width", ch_wid) if ch_wid == -1 else ch_wid
        return lower_len, upper_len, lower_wid, upper_wid

    def build_channels(self):
        num_lower, num_upper = self.select_count()
        lower_len, upper_len, lower_wid, upper_wid = self.select_channel_size()
        ch_t = self.a("channel_thickness")
        ch_mdi_t = self.a("channel_mdi_thickness")
        mdi_t = self.a("mdi_thickness")
        cx = self.a("channel_center_x")
        cy = self.a("channel_center_y")
        hk_t = self.a("high_k_thickness")

        current_z = 0.0

        def stack(prefix, count, length, width):
            nonlocal current_z
            total_x1 = cx - length / 2.0
            total_x2 = cx + length / 2.0
            left_x1 = total_x1
            left_x2 = self.gate_bounds["x1"] - hk_t
            right_x1 = self.gate_bounds["x2"] + hk_t
            right_x2 = total_x2
            y1 = cy - width / 2.0
            y2 = cy + width / 2.0
            group = []
            for i in range(count):
                current_z += ch_mdi_t
                z1 = current_z
                z2 = z1 + ch_t
                current_z = z2
                for side, x1, x2 in (("L", left_x1, left_x2), ("R", right_x1, right_x2)):
                    name = f"{prefix}_{i}_{side}"
                    self.sde.cuboid(name, x1, y1, z1, x2, y2, z2, "Silicon")
                    channel = {
                        "name": name,
                        "group": prefix,
                        "side": side,
                        "x1": x1,
                        "y1": y1,
                        "z1": z1,
                        "x2": x2,
                        "y2": y2,
                        "z2": z2,
                        "length": length,
                        "width": width,
                    }
                    self.channels.append(channel)
                    self.channel_regions.append(name)
                    group.append(channel)
            return group

        self.lower_channels = stack("ChannelLower", num_lower, lower_len, lower_wid)
        current_z += ch_mdi_t + mdi_t
        self.upper_channels = stack("ChannelUpper", num_upper, upper_len, upper_wid)

    def build_gate_highk(self):
        t = self.a("high_k_thickness")
        g = self.gate_bounds
        self.sde.cuboid("HighK_Gate_Left", g["x1"] - t, g["y1"], g["z1"], g["x1"], g["y2"], g["z2"], "HfO2")
        self.sde.cuboid("HighK_Gate_Right", g["x2"], g["y1"], g["z1"], g["x2"] + t, g["y2"], g["z2"], "HfO2")
        self.sde.cuboid("HighK_Gate_Front", g["x1"], g["y1"] - t, g["z1"], g["x2"], g["y1"], g["z2"], "HfO2")
        self.sde.cuboid("HighK_Gate_Back", g["x1"], g["y2"], g["z1"], g["x2"], g["y2"] + t, g["z2"], "HfO2")

    def add_wall_with_holes(self, prefix, x1, x2):
        y1 = self.gate_bounds["y1"]
        y2 = self.gate_bounds["y2"]
        z1 = self.gate_bounds["z1"]
        z2 = self.gate_bounds["z2"]
        hole_y1 = min(ch["y1"] for ch in self.channels)
        hole_y2 = max(ch["y2"] for ch in self.channels)
        holes = sorted(set((ch["z1"], ch["z2"]) for ch in self.channels))

        self.sde.cuboid(f"{prefix}_YMin", x1, y1, z1, x2, hole_y1, z2, "Si3N4")
        self.sde.cuboid(f"{prefix}_YMax", x1, hole_y2, z1, x2, y2, z2, "Si3N4")

        curr = z1
        for i, (hz1, hz2) in enumerate(holes):
            self.sde.cuboid(f"{prefix}_ZGap_{i}", x1, hole_y1, curr, x2, hole_y2, hz1, "Si3N4")
            curr = max(curr, hz2)
        self.sde.cuboid(f"{prefix}_ZGap_{len(holes)}", x1, hole_y1, curr, x2, hole_y2, z2, "Si3N4")

    def build_inner_spacers(self):
        left_channels = [ch for ch in self.channels if ch["side"] == "L"]
        right_channels = [ch for ch in self.channels if ch["side"] == "R"]
        self.spacer_left_x1 = min(ch["x1"] for ch in left_channels)
        self.spacer_left_x2 = max(ch["x2"] for ch in left_channels)
        self.spacer_right_x1 = min(ch["x1"] for ch in right_channels)
        self.spacer_right_x2 = max(ch["x2"] for ch in right_channels)

        self.add_wall_with_holes("InnerSpacer_L", self.spacer_left_x1, self.spacer_left_x2)
        self.add_wall_with_holes("InnerSpacer_R", self.spacer_right_x1, self.spacer_right_x2)

        self.sd_left_inner_x = self.spacer_left_x1
        self.sd_right_inner_x = self.spacer_right_x2

    def select_sd_overgrowth(self):
        oy = self.a("sd_overgrowth_y", -1)
        oz_up = self.a("sd_overgrowth_z_up", -1)
        oz_down = self.a("sd_overgrowth_z_down", -1)
        lower = {
            "oy": self.a("sd_lower_overgrowth_y") if oy == -1 else oy,
            "oz_up": self.a("sd_lower_overgrowth_z_up") if oz_up == -1 else oz_up,
            "oz_down": self.a("sd_lower_overgrowth_z_down") if oz_down == -1 else oz_down,
        }
        upper = {
            "oy": self.a("sd_upper_overgrowth_y") if oy == -1 else oy,
            "oz_up": self.a("sd_upper_overgrowth_z_up") if oz_up == -1 else oz_up,
            "oz_down": self.a("sd_upper_overgrowth_z_down") if oz_down == -1 else oz_down,
        }
        return lower, upper

    def build_sd_group(self, prefix, channels, growth, material):
        boundary = self.layout[1]
        ch_x1 = min(ch["x1"] for ch in channels)
        ch_x2 = max(ch["x2"] for ch in channels)
        ch_y1 = min(ch["y1"] for ch in channels)
        ch_y2 = max(ch["y2"] for ch in channels)
        z1 = min(ch["z1"] for ch in channels) - growth["oz_down"]
        z2 = max(ch["z2"] for ch in channels) + growth["oz_up"]
        y1 = ch_y1 - growth["oy"]
        y2 = ch_y2 + growth["oy"]
        left_x2 = ch_x1
        right_x1 = ch_x2
        self.sde.cuboid(f"{prefix}_Left", boundary["x1"], y1, z1, left_x2, y2, z2, material)
        self.sde.cuboid(f"{prefix}_Right", right_x1, y1, z1, boundary["x2"], y2, z2, material)

    def build_sd_epi(self):
        lower_growth, upper_growth = self.select_sd_overgrowth()
        self.build_sd_group("SD_Lower", self.lower_channels, lower_growth, "SiGe")
        self.build_sd_group("SD_Upper", self.upper_channels, upper_growth, "Silicon")

    def build_generic_layout_layers(self):
        if not self.a("generic_layers_enable", True):
            return
        core_layers = {1, 7, 8, 9, 10}
        for layer_num in sorted(self.layout):
            if layer_num in core_layers:
                continue
            rule = self.enabled_rule(layer_num)
            if not rule:
                continue
            l = self.layout[layer_num]
            name = f"Layer_{layer_num}_{rule['layer_name']}"
            self.sde.cuboid(
                name,
                l["x1"],
                l["y1"],
                rule["start_z"],
                l["x2"],
                l["y2"],
                rule["end_z"],
                rule["material"],
            )

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
            self.sde.add(
                f'(sdegeo:set-contact '
                f'(find-face-id (position {fmt(cx)} {fmt(cy)} {fmt(region["z2"])})) "{top}")'
            )
            self.sde.add(
                f'(sdegeo:set-contact '
                f'(find-face-id (position {fmt(cx)} {fmt(cy)} {fmt(region["z1"])})) "{bot}")'
            )

    def add_doping(self):
        if not self.a("doping_enable", True):
            return
        self.sde.section("Doping")

        self.constant_profile(
            "SD_Upper_Doping",
            self.a("sd_upper_doping_species", "ArsenicActiveConcentration"),
            self.a("sd_upper_doping_concentration", 8e19),
            [("Place_SD_U_L", "SD_Upper_Left"), ("Place_SD_U_R", "SD_Upper_Right")],
        )
        self.constant_profile(
            "SD_Lower_Doping",
            self.a("sd_lower_doping_species", "BoronActiveConcentration"),
            self.a("sd_lower_doping_concentration", 8e19),
            [("Place_SD_L_L", "SD_Lower_Left"), ("Place_SD_L_R", "SD_Lower_Right")],
        )

        if self.a("channel_doping_enable", False):
            placements = [(f"Place_{name}_Doping", name) for name in self.channel_regions]
            self.constant_profile(
                "Channel_Doping",
                self.a("channel_doping_species", "BoronActiveConcentration"),
                self.a("channel_doping_concentration", 1e15),
                placements,
            )

    def constant_profile(self, profile_name, species, concentration, placements):
        self.sde.add(
            f'(sdedr:define-constant-profile "{profile_name}" "{species}" {concentration:.6g})'
        )
        for placement_name, region_name in placements:
            self.sde.add(
                f'(sdedr:define-constant-profile-region "{placement_name}" "{profile_name}" "{region_name}")'
            )

    def add_meshing(self):
        if not self.a("meshing_enable", True):
            return
        self.sde.section("Meshing")
        b = self.layout[1]
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
        self.sde.add(
            '(sdedr:define-refinement-placement "Global_Mesh_Place" "Global_Mesh_Size" "Global_Win")'
        )
        self.sde.add(
            f'(sdedr:define-refeval-window "Core_Win" "Cuboid" '
            f'(position {fmt(b["x1"])} {fmt(b["y1"])} {fmt(self.a("core_mesh_window_z_min", 0.0))}) '
            f'(position {fmt(b["x2"])} {fmt(b["y2"])} {fmt(self.a("core_mesh_window_z_max", 0.2))}))'
        )
        self.sde.add(
            f'(sdedr:define-refinement-size "Core_Mesh_Size" '
            f'{self.a("core_mesh_max_x", 0.002):.6g} {self.a("core_mesh_max_y", 0.002):.6g} {self.a("core_mesh_max_z", 0.002):.6g} '
            f'{self.a("core_mesh_min_x", 0.001):.6g} {self.a("core_mesh_min_y", 0.001):.6g} {self.a("core_mesh_min_z", 0.001):.6g})'
        )
        self.sde.add(
            '(sdedr:define-refinement-placement "Core_Mesh_Place" "Core_Mesh_Size" "Core_Win")'
        )
        self.sde.add(
            f'(sde:build-mesh "{self.a("mesh_engine", "snmesh")}" '
            f'"{self.a("mesh_options", "-a -c boxmethod")}" "{self.a("mesh_output_name", "n@node@_cfet_structure")}")'
        )


def default_paths(base_dir):
    return {
        "layout": os.path.join(base_dir, "gds", "test1_gds.txt"),
        "rules": os.path.join(base_dir, "rules", "layer_rule_1.txt"),
        "arch": os.path.join(base_dir, "rules", "cfet_arch.txt"),
        "output": os.path.join(base_dir, "gen_sde.cmd"),
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

    for key in ("layout", "rules", "arch"):
        if not os.path.exists(paths[key]):
            raise FileNotFoundError(f"Missing {key} file: {paths[key]}")

    layout = parse_layout(paths["layout"])
    rules = parse_layer_rules(paths["rules"])
    arch = parse_arch(paths["arch"])

    builder = StructureBuilder(layout, rules, arch)
    sde = builder.build()
    sde.write(paths["output"])
    print(f"SDE command file generated: {paths['output']}")


if __name__ == "__main__":
    try:
        main(sys.argv)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
