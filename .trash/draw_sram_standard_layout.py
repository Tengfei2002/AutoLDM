import os
import sys

from PIL import Image, ImageDraw, ImageFont

from gen_sram_sde import parse_arch, parse_layout


LAYER_INFO = {
    111: ("Gate", "#ef3340"),
    16: ("MD", "#21a6b8"),
    17: ("MRW", "#8e44ad"),
    18: ("V0", "#303030"),
    19: ("M0", "#d7a51b"),
    20: ("V1", "#222222"),
    21: ("M1", "#3478e5"),
    22: ("V2", "#222222"),
    23: ("M2", "#35a853"),
    24: ("V3", "#222222"),
    25: ("M3", "#b56b1c"),
    51: ("BMD", "#a02191"),
    52: ("BV0", "#333333"),
    53: ("BM0", "#777777"),
}
FRONT = [111, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25]
BACK = [51, 52, 53]
MIXED = [111, 51, 52, 53, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25]


def font(size, bold=False):
    path = "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"
    return ImageFont.truetype(path, size) if os.path.exists(path) else ImageFont.load_default()


def render(layout_file, arch_file, kind, output_file):
    layout = parse_layout(layout_file)
    arch = parse_arch(arch_file)
    width = float(arch["sram_width"])
    height = float(arch["sram_height"])
    image = Image.new("RGBA", (1800, 1100), "white")
    draw = ImageDraw.Draw(image, "RGBA")
    left, top, right, bottom = 140, 170, 1290, 900
    scale = min((right - left) / width, (bottom - top) / height)
    origin_x = left
    origin_y = top + height * scale

    def xy(x, y):
        return origin_x + x * scale, origin_y - y * scale

    def box(rect):
        x1, y2 = xy(rect["x1"], rect["y1"])
        x2, y1 = xy(rect["x2"], rect["y2"])
        return x1, y1, x2, y2

    title = f"sram_standard_6t - {kind}"
    draw.text((70, 35), title, fill="#111111", font=font(31, True))
    draw.text((70, 82), "3 CPP x 124 nm  common-gate double-row", fill="#444444", font=font(21))

    for index in range(int(float(arch["sram_cpp_count"])) + 1):
        x = index * float(arch["cpp"])
        p1 = xy(x, 0)
        p2 = xy(x, height)
        draw.line((p1[0], p1[1], p2[0], p2[1]), fill=(80, 80, 80, 90), width=2)
        draw.text((p1[0], origin_y + 28), f"{index} CPP", fill="#555555", font=font(16), anchor="mm")
    center_a = xy(0, 0.062)
    center_b = xy(width, 0.062)
    draw.line((*center_a, *center_b), fill=(80, 80, 80, 100), width=2)

    layers = {"frontside": FRONT, "backside": BACK, "mixed": MIXED}[kind]
    if kind == "mixed":
        order = BACK + FRONT
    else:
        order = layers
    for layer in order:
        color = LAYER_INFO[layer][1]
        rgb = tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))
        alpha = 65 if kind == "mixed" and layer in BACK else (120 if layer in {19, 21, 23, 53} else 185)
        for rect in layout.get(layer, []):
            draw.rectangle(box(rect), fill=(*rgb, alpha), outline=(20, 20, 20, 220), width=2)
            if layer in {17, 19, 21, 23, 53}:
                b = box(rect)
                if b[2] - b[0] > 48 and b[3] - b[1] > 24:
                    draw.text(((b[0] + b[2]) / 2, (b[1] + b[3]) / 2), rect["net"], fill="#111111", font=font(15), anchor="mm")

    border = (origin_x, origin_y - height * scale, origin_x + width * scale, origin_y)
    draw.rectangle(border, outline="#111111", width=4)
    draw.text((left, top - 34), "upper mirrored half-row", fill="#333333", font=font(18))
    draw.text((left, origin_y + 62), "CPP direction", fill="#222222", font=font(20))
    draw.text((left - 110, top + 300), "Cell Height", fill="#222222", font=font(20))

    legend_x, legend_y = 1360, 170
    draw.text((legend_x, legend_y - 40), "Layers", fill="#111111", font=font(22, True))
    for layer in layers:
        if not layout.get(layer):
            continue
        label, color = LAYER_INFO[layer]
        draw.rectangle((legend_x, legend_y, legend_x + 34, legend_y + 22), fill=color, outline="#222222")
        draw.text((legend_x + 48, legend_y + 11), f"L{layer} {label}", fill="#222222", font=font(17), anchor="lm")
        legend_y += 36

    pin_y = 730
    draw.text((1360, pin_y - 42), "Potentials", fill="#111111", font=font(22, True))
    mapping = [("P1", "BL"), ("P2", "Q"), ("P3", "VSS"), ("P4", "VDD"), ("P5", "QB"), ("P6", "BLB"), ("P7", "WL")]
    for alias, net in mapping:
        draw.text((1360, pin_y), f"{alias} = {net}", fill="#222222", font=font(19, True))
        pin_y += 38

    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
    image.convert("RGB").save(output_file, quality=95)


def main(argv):
    base = os.path.dirname(os.path.abspath(__file__))
    layout_file = argv[1] if len(argv) > 1 else os.path.join(base, "gds", "sram_standard_6t_gds.txt")
    arch_file = argv[2] if len(argv) > 2 else os.path.join(base, "rules", "sram_standard_arch.txt")
    output_dir = argv[3] if len(argv) > 3 else os.path.join(base, "layout_views")
    for kind in ("frontside", "backside", "mixed"):
        output = os.path.join(output_dir, f"sram_standard_6t_{kind}.png")
        render(layout_file, arch_file, kind, output)
        print(f"Generated {output}")


if __name__ == "__main__":
    main(sys.argv)
