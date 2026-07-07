import datetime
import os
import struct
import sys

from gen_sram_sde import parse_layout


DB_UNITS_PER_UM = 1000


def record(record_type, data_type, data=b""):
    return struct.pack(">HBB", len(data) + 4, record_type, data_type) + data


def int2(values):
    return struct.pack(">" + "h" * len(values), *values)


def int4(values):
    return struct.pack(">" + "i" * len(values), *values)


def ascii_data(text):
    data = text.encode("ascii", "replace")
    return data if len(data) % 2 == 0 else data + b"\0"


def real8(value):
    if value == 0:
        return b"\0" * 8
    sign = 0x80 if value < 0 else 0
    value = abs(value)
    exponent = 64
    while value >= 1.0:
        value /= 16.0
        exponent += 1
    while value < 1.0 / 16.0:
        value *= 16.0
        exponent -= 1
    mantissa = int(value * (1 << 56))
    if mantissa >= 1 << 56:
        mantissa >>= 4
        exponent += 1
    return bytes([sign | exponent]) + mantissa.to_bytes(7, "big")


def timestamp():
    now = datetime.datetime.now()
    values = [now.year, now.month, now.day, now.hour, now.minute, now.second]
    return int2(values + values)


def db(value_um):
    return int(round(value_um * DB_UNITS_PER_UM))


def boundary_element(rect):
    points = [
        db(rect["x1"]), db(rect["y1"]),
        db(rect["x2"]), db(rect["y1"]),
        db(rect["x2"]), db(rect["y2"]),
        db(rect["x1"]), db(rect["y2"]),
        db(rect["x1"]), db(rect["y1"]),
    ]
    return b"".join([
        record(0x08, 0x00),
        record(0x0D, 0x02, int2([rect["layer_num"]])),
        record(0x0E, 0x02, int2([0])),
        record(0x10, 0x03, int4(points)),
        record(0x11, 0x00),
    ])


def text_element(rect):
    if rect["layer_num"] == 1:
        return b""
    x = db((rect["x1"] + rect["x2"]) / 2)
    y = db((rect["y1"] + rect["y2"]) / 2)
    text = rect["label"]
    if rect["net"] and rect["net"] not in {"n", "p", "CELL"}:
        text += f":{rect['net']}"
    return b"".join([
        record(0x0C, 0x00),
        record(0x0D, 0x02, int2([rect["layer_num"]])),
        record(0x16, 0x02, int2([0])),
        record(0x10, 0x03, int4([x, y])),
        record(0x19, 0x06, ascii_data(text)),
        record(0x11, 0x00),
    ])


def write_gds(layout_file, output_file):
    layout = parse_layout(layout_file)
    cell_name = os.path.basename(layout_file).replace("_gds.txt", "").upper()[:32]
    lib_name = (cell_name + "_LIB")[:32]
    stream = [
        record(0x00, 0x02, int2([600])),
        record(0x01, 0x02, timestamp()),
        record(0x02, 0x06, ascii_data(lib_name)),
        record(0x03, 0x05, real8(0.001) + real8(1e-9)),
        record(0x05, 0x02, timestamp()),
        record(0x06, 0x06, ascii_data(cell_name)),
    ]
    for layer_num in sorted(layout):
        for rect in layout[layer_num]:
            stream.append(boundary_element(rect))
            stream.append(text_element(rect))
    stream.extend([record(0x07, 0x00), record(0x04, 0x00)])
    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
    with open(output_file, "wb") as handle:
        handle.write(b"".join(stream))


def inspect_gds(filepath):
    counts = {"boundary": 0, "text": 0}
    with open(filepath, "rb") as handle:
        data = handle.read()
    offset = 0
    while offset < len(data):
        if offset + 4 > len(data):
            raise ValueError("Truncated GDS record header.")
        length, record_type, _ = struct.unpack(">HBB", data[offset:offset + 4])
        if length < 4 or offset + length > len(data):
            raise ValueError(f"Invalid GDS record length at byte {offset}.")
        if record_type == 0x08:
            counts["boundary"] += 1
        elif record_type == 0x0C:
            counts["text"] += 1
        offset += length
    if offset != len(data) or not data.endswith(record(0x04, 0x00)):
        raise ValueError("GDS stream does not terminate cleanly.")
    return counts


def main(argv):
    if len(argv) not in {2, 3}:
        print("Usage: python txt_to_gds.py layout_gds.txt [output.gds]")
        return 2
    layout_file = argv[1]
    output_file = argv[2] if len(argv) == 3 else layout_file.replace("_gds.txt", ".gds")
    write_gds(layout_file, output_file)
    counts = inspect_gds(output_file)
    print(
        f"Generated {output_file}: "
        f"{counts['boundary']} rectangles, {counts['text']} labels."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
