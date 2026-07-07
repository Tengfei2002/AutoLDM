import csv
import os
import sys

from PIL import Image, ImageDraw, ImageFont

from gen_sram_sde import parse_arch, parse_layout


LAYER_INFO = {
    1: ("Boundary", "#ffffff"),
    111: ("Gate marker", "#ef3340"),
    121: ("NFET S/D", "#f08a5d"),
    122: ("PFET S/D", "#a86ee6"),
    17: ("VMM", "#8e44ad"),
    18: ("VMD", "#21a6b8"),
    19: ("M0", "#d7a51b"),
    20: ("VM0", "#333333"),
    21: ("M1", "#3478e5"),
    22: ("V1", "#222222"),
    23: ("M2", "#32a852"),
    52: ("BVMD", "#b2188b"),
    53: ("BM0", "#777777"),
    54: ("BV0", "#191919"),
}

FRONT_LAYERS = [121, 122, 111, 17, 18, 19, 20, 21, 22, 23]
BACK_LAYERS = [52, 53, 54]
MIXED_LAYERS = [121, 122, 111, 17, 18, 19, 20, 21, 22, 23, 52, 53, 54]
PIN_NETS = ("WL", "BL", "BLB", "Q", "QB", "VDD", "VSS")


def load_font(size, bold=False):
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def boundary_from_layout(layout, arch):
    rects = layout.get(1, [])
    if rects:
        return {
            "x1": min(r["x1"] for r in rects),
            "y1": min(r["y1"] for r in rects),
            "x2": max(r["x2"] for r in rects),
            "y2": max(r["y2"] for r in rects),
        }
    return {
        "x1": 0.0,
        "y1": 0.0,
        "x2": float(arch["ch"]),
        "y2": float(arch["cpp"]) * int(float(arch.get("cpp_count_y", 2))),
    }


class LayoutCanvas:
    def __init__(self, boundary, arch, title, width=1800, height=1100):
        self.b = boundary
        self.arch = arch
        self.width = width
        self.height = height
        self.img = Image.new("RGBA", (width, height), "white")
        self.draw = ImageDraw.Draw(self.img, "RGBA")
        self.font = load_font(20)
        self.small = load_font(17)
        self.title_font = load_font(31, True)
        self.subtitle_font = load_font(21)
        self.rotate = bool(arch.get("layout_view_rotate_90", True))
        self.plot_left = 150
        self.plot_top = 180
        self.plot_right = 1260
        self.plot_bottom = 850
        display_w = (self.b["y2"] - self.b["y1"]) if self.rotate else (self.b["x2"] - self.b["x1"])
        display_h = (self.b["x2"] - self.b["x1"]) if self.rotate else (self.b["y2"] - self.b["y1"])
        sx = (self.plot_right - self.plot_left) / display_w
        sy = (self.plot_bottom - self.plot_top) / display_h
        self.scale = min(sx, sy)
        plot_w = display_w * self.scale
        plot_h = display_h * self.scale
        self.origin_x = self.plot_left + ((self.plot_right - self.plot_left) - plot_w) / 2
        self.origin_y = self.plot_top + plot_h
        self.draw.text((70, 35), title, fill="#151515", font=self.title_font)
        if "sram_mmp_count_x" in arch:
            size_text = f"{int(float(arch['sram_mmp_count_x']))}MMP x {int(float(arch.get('cpp_count_y', 2)))}CPP"
        else:
            size_text = f"{arch.get('cell_height_tracks', '?')}T"
        details = (
            f"{size_text}  size={1000 * (self.b['x2'] - self.b['x1']):.0f}x"
            f"{1000 * (self.b['y2'] - self.b['y1']):.0f} nm  "
            f"gate={arch.get('gate_mode', '?')}  BM0={arch.get('bm0_mode', '?')}"
        )
        self.draw.text((72, 82), details, fill="#444444", font=self.subtitle_font)

    def xy(self, x, y):
        if self.rotate:
            px = self.origin_x + (y - self.b["y1"]) * self.scale
            py = self.origin_y - (x - self.b["x1"]) * self.scale
        else:
            px = self.origin_x + (x - self.b["x1"]) * self.scale
            py = self.origin_y - (y - self.b["y1"]) * self.scale
        return px, py

    def box(self, rect):
        corners = [
            self.xy(rect["x1"], rect["y1"]),
            self.xy(rect["x1"], rect["y2"]),
            self.xy(rect["x2"], rect["y1"]),
            self.xy(rect["x2"], rect["y2"]),
        ]
        xs = [p[0] for p in corners]
        ys = [p[1] for p in corners]
        return (min(xs), min(ys), max(xs), max(ys))

    def draw_track_grid(self, kind):
        cpp = float(self.arch.get("cpp", 0.042))
        count = int(float(self.arch.get("cpp_count_y", self.arch.get("sram_num_cpp", 4))))
        for idx in range(count):
            y = self.b["y1"] + cpp * (idx + 0.5)
            p1 = self.xy(self.b["x1"], y)
            p2 = self.xy(self.b["x2"], y)
            self.draw.line((p1[0], p1[1], p2[0], p2[1]), fill=(100, 100, 100, 95), width=2)
            if self.rotate:
                self.draw.text((p1[0], self.origin_y + 30), f"CPP {idx}", fill="#555555", font=self.small, anchor="mm")
            else:
                self.draw.text((self.origin_x - 64, p1[1]), f"CPP {idx}", fill="#555555", font=self.small, anchor="lm")

        prefix = "bm0" if kind == "backside" else "m0"
        pitch = float(self.arch.get(f"{prefix}_pitch", 0.018))
        origin = float(self.arch.get(f"{prefix}_track_origin_x", 0.0))
        idx = 0
        x = origin
        while x <= self.b["x2"] + 1e-9:
            if x >= self.b["x1"] - 1e-9:
                p1 = self.xy(x, self.b["y1"])
                p2 = self.xy(x, self.b["y2"])
                color = (180, 120, 0, 90) if prefix == "m0" else (90, 90, 90, 90)
                self.draw.line((p1[0], p1[1], p2[0], p2[1]), fill=color, width=2)
                if self.rotate:
                    self.draw.text((self.origin_x - 55, p1[1]), f"{prefix.upper()}{idx}", fill="#555555", font=self.small, anchor="lm")
                else:
                    self.draw.text((p1[0], self.origin_y + 28), f"{prefix.upper()}{idx}", fill="#555555", font=self.small, anchor="mm")
            idx += 1
            x = origin + idx * pitch

        border = self.box(self.b)
        self.draw.rectangle(border, outline="#111111", width=4)
        self.draw.text(
            ((border[0] + border[2]) / 2, border[3] + 70),
            "Layout X: MMP / cell-height direction" if not self.rotate else "Layout X: CPP / transistor-column direction",
            fill="#222222",
            font=self.font,
            anchor="mm",
        )
        self.draw.text(
            (border[0], border[1] - 40),
            "Layout Y: CPP rows" if not self.rotate else "Layout Y: Cell Height / metal tracks",
            fill="#222222",
            font=self.font,
            anchor="lm",
        )

    def draw_rect(self, rect, layer_num, alpha=185):
        _, color = LAYER_INFO[layer_num]
        rgb = tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))
        box = self.box(rect)
        self.draw.rectangle(box, fill=(*rgb, alpha), outline=(25, 25, 25, 225), width=2)
        w = box[2] - box[0]
        h = box[3] - box[1]
        text = rect["net"] if rect["net"] and rect["net"] not in {"n", "p", "CELL"} else ""
        if layer_num in {17, 19, 21, 23, 53} and w >= 52 and h >= 28:
            self.draw.text(((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), text, fill="#111111", font=self.small, anchor="mm")

    def legend(self, layers):
        x = 1330
        y = 180
        self.draw.text((x, y - 45), "Layer legend", fill="#151515", font=self.subtitle_font)
        for layer in layers:
            if layer not in LAYER_INFO:
                continue
            name, color = LAYER_INFO[layer]
            self.draw.rectangle((x, y, x + 34, y + 22), fill=color, outline="#222222", width=2)
            self.draw.text((x + 48, y + 11), f"L{layer}  {name}", fill="#222222", font=self.small, anchor="lm")
            y += 38

    def pin_callouts(self, layout, layers):
        candidates = {}
        preferred = [21, 19, 18, 53, 52, 17, 111, 121, 122]
        for layer in preferred:
            if layer not in layers:
                continue
            for rect in layout.get(layer, []):
                if rect["net"] in PIN_NETS and rect["net"] not in candidates:
                    candidates[rect["net"]] = rect
        x_text = 1360
        self.draw.text((x_text, 700), "SRAM pins / nets", fill="#151515", font=self.subtitle_font)
        missing = []
        y = 745
        for net in PIN_NETS:
            rect = candidates.get(net)
            color = "#222222" if rect else "#999999"
            marker = "#111111" if rect else "#cccccc"
            self.draw.ellipse((x_text, y - 7, x_text + 14, y + 7), fill=marker)
            self.draw.text((x_text + 28, y), net, fill=color, font=load_font(22, True), anchor="lm")
            if rect:
                layer = rect["layer_num"]
                self.draw.text((x_text + 105, y), f"L{layer}", fill="#777777", font=self.small, anchor="lm")
            else:
                missing.append(net)
            y += 44
        if missing:
            self.draw.text((x_text, y + 10), "Gray: not present in this view", fill="#888888", font=self.small)

    def topology_labels(self, layout):
        if self.rotate:
            columns = [("PG1", 0.5), ("PU1 / PD1", 1.5), ("PU2 / PD2", 2.5), ("PG2", 3.5)]
            cpp = float(self.arch.get("cpp", 0.042))
            for text, index in columns:
                px, _ = self.xy(self.b["x2"], self.b["y1"] + index * cpp)
                self.draw.text((px, self.plot_top - 28), text, fill="#111111", font=load_font(20, True), anchor="mm")
            return
        labels = {"PG_L": "PG1", "PD_L": "PD1", "PU_L": "PU1", "PD_R": "PD2", "PU_R": "PU2", "PG_R": "PG2"}
        offsets = {"PG_L": (-16, 0), "PD_L": (0, 18), "PU_L": (0, -18), "PD_R": (0, 18), "PU_R": (0, -18), "PG_R": (16, 0)}
        gates = {rect["label"]: rect for rect in layout.get(111, [])}
        for key, text in labels.items():
            rect = gates.get(key)
            if not rect:
                continue
            px, py = self.xy((rect["x1"] + rect["x2"]) / 2, (rect["y1"] + rect["y2"]) / 2)
            dx, dy = offsets[key]
            self.draw.text((px + dx, py + dy), text, fill="#111111", font=load_font(18, True), anchor="mm")

    def save(self, path):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.img.convert("RGB").save(path, quality=95)


def save_view(kind, layout_file, arch_file, output_file):
    layout = parse_layout(layout_file)
    arch = parse_arch(arch_file)
    boundary = boundary_from_layout(layout, arch)
    layers = {"frontside": FRONT_LAYERS, "backside": BACK_LAYERS, "mixed": MIXED_LAYERS}[kind]
    stem = os.path.basename(layout_file).replace("_gds.txt", "")
    canvas = LayoutCanvas(boundary, arch, f"{stem} - {kind} layout")
    canvas.draw_track_grid("backside" if kind == "backside" else "frontside")
    if kind == "mixed":
        for layer in [52, 53, 54]:
            for rect in layout.get(layer, []):
                canvas.draw_rect(rect, layer, 55)
        for layer in [121, 122, 111]:
            for rect in layout.get(layer, []):
                canvas.draw_rect(rect, layer, 205)
        for layer in [17, 18, 19, 20, 21, 22, 23]:
            for rect in layout.get(layer, []):
                alpha = 145 if layer in {17, 20, 22} else 105
                canvas.draw_rect(rect, layer, alpha)
    else:
        for layer in layers:
            for rect in layout.get(layer, []):
                if layer in {121, 122, 111}:
                    alpha = 210
                elif layer in {17, 20, 22, 52, 54}:
                    alpha = 155
                else:
                    alpha = 120
                canvas.draw_rect(rect, layer, alpha)
    if kind != "backside":
        canvas.topology_labels(layout)
    canvas.legend([layer for layer in layers if layout.get(layer)])
    canvas.pin_callouts(layout, layers)
    canvas.save(output_file)


def write_coordinates(layout_file, arch_file, output_file):
    layout = parse_layout(layout_file)
    rows = []
    for layer_num, rects in sorted(layout.items()):
        layer_name = LAYER_INFO.get(layer_num, (f"Layer {layer_num}", ""))[0]
        view = "backside" if layer_num >= 52 else "frontside"
        if layer_num == 1:
            view = "boundary"
        for rect in rects:
            rows.append({
                "layer_num": layer_num,
                "layer_name": layer_name,
                "label": rect["label"],
                "net": rect["net"],
                "x1": f"{rect['x1']:.5f}",
                "y1": f"{rect['y1']:.5f}",
                "x2": f"{rect['x2']:.5f}",
                "y2": f"{rect['y2']:.5f}",
                "view": view,
            })
    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["layer_num", "layer_name", "label", "net", "x1", "y1", "x2", "y2", "view"])
        writer.writeheader()
        writer.writerows(rows)


def main(argv):
    base = os.path.dirname(os.path.abspath(__file__))
    out_dir = argv[3] if len(argv) > 3 else os.path.join(base, "layout_views")
    if len(argv) > 2:
        cases = [(argv[1], argv[2])]
    else:
        cases = [
            (os.path.join(base, "gds", "sram_6t_mcfet_cg_gds.txt"), os.path.join(base, "rules", "sram_mcfet_cg_arch.txt")),
            (os.path.join(base, "gds", "sram_6t_hdr_denseBM0_gds.txt"), os.path.join(base, "rules", "sram_hdr_denseBM0_arch.txt")),
            (os.path.join(base, "gds", "sram_6t_hdr_split_gate_gds.txt"), os.path.join(base, "rules", "sram_hdr_split_gate_arch.txt")),
            (os.path.join(base, "gds", "sram_6t_scfet_gds.txt"), os.path.join(base, "rules", "sram_scfet_arch.txt")),
        ]
    for layout_file, arch_file in cases:
        stem = os.path.basename(layout_file).replace("_gds.txt", "")
        for kind in ("frontside", "backside", "mixed"):
            output = os.path.join(out_dir, f"{stem}_{kind}.png")
            save_view(kind, layout_file, arch_file, output)
            print(f"Generated {output}")
        coordinates = os.path.join(out_dir, f"{stem}_coordinates.csv")
        write_coordinates(layout_file, arch_file, coordinates)
        print(f"Generated {coordinates}")


if __name__ == "__main__":
    main(sys.argv)
