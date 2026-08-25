#!/usr/bin/env python3
"""Generate standard 6T-SRAM HSPICE test decks from an extracted .inc file."""

from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path


SUBCKT_RE = re.compile(r"^\s*\.subckt\s+(\S+)(?:\s+(.*?))?\s*$", re.IGNORECASE)
REQUIRED_PORTS = ("BL", "BLB", "WL", "VDD", "VSS", "Q", "QB")
DEFAULT_BENCH = {
    "cbl": "30f", "rbl": "100", "rwl": "100", "rbl_drv": "100",
    "cwl": "5f", "rvdd": "10", "rvss": "10", "cvdd": "10f",
    "sense_v": "0.05", "tr": "20p", "tstep": "1p", "tstop": "5n",
}


@dataclass(frozen=True)
class SramCell:
    name: str
    ports: tuple[str, ...]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate smoke/hold/read/write/SNM HSPICE decks for a 6T SRAM PEX include."
    )
    parser.add_argument("inc", type=Path, help="Extracted SRAM .inc file")
    parser.add_argument("bench", type=Path, help="Benchmark settings text file (vdd/vss)")
    parser.add_argument("n_va", type=Path, help="NMOS Verilog-A model")
    parser.add_argument("p_va", type=Path, help="PMOS Verilog-A model")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output deck directory")
    return parser.parse_args()


def require_file(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    return resolved


def parse_subckt(inc: Path) -> SramCell:
    lines = inc.read_text(encoding="utf-8", errors="replace").splitlines()
    for index, raw_line in enumerate(lines):
        match = SUBCKT_RE.match(raw_line)
        if not match:
            continue
        name, raw_ports = match.groups()
        ports = (raw_ports or "").split()
        next_index = index + 1
        while next_index < len(lines) and lines[next_index].lstrip().startswith("+"):
            ports.extend(lines[next_index].lstrip()[1:].split())
            next_index += 1
        if not ports:
            raise ValueError(f"{inc}: .subckt {name} has no ports")
        port_names = {port.upper() for port in ports}
        missing = sorted(set(REQUIRED_PORTS) - port_names)
        extra = sorted(port_names - set(REQUIRED_PORTS))
        if missing or extra:
            raise ValueError(
                f"{inc}: expected exactly {', '.join(REQUIRED_PORTS)}; "
                f"missing={missing}, extra={extra}"
            )
        return SramCell(name=name, ports=tuple(ports))
    raise ValueError(f"{inc}: no .subckt declaration found")


def parse_bench(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    section: str | None = None
    for number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith(("*", "#", ";")):
            continue
        if line.startswith("(") and line.endswith(")"):
            section = line[1:-1].strip().upper()
            continue
        if section not in {"SUPPLY", "ARRAY", "TIMING", "MEASURE"} or "=" not in line:
            raise ValueError(f"{path}:{number}: expected key=value in (SUPPLY)/(ARRAY)/(TIMING)/(MEASURE)")
        key, value = (item.strip() for item in line.split("=", 1))
        key = key.lower()
        allowed = {"SUPPLY": {"vdd", "vss"}, "ARRAY": {"cbl", "rbl", "rwl", "rbl_drv", "cwl", "rvdd", "rvss", "cvdd"}, "TIMING": {"tr", "tstep", "tstop"}, "MEASURE": {"sense_v"}}
        if key not in allowed[section] or key in values or not value:
            raise ValueError(f"{path}:{number}: invalid or duplicate {key}")
        values[key] = value
    if not {"vdd", "vss"}.issubset(values):
        raise ValueError(f"{path}: both vdd and vss are required")
    if Decimal(values["vdd"]) <= Decimal(values["vss"]):
        raise ValueError(f"{path}: vdd must be greater than vss")
    return {**DEFAULT_BENCH, **values}


def relative_path(target: Path, deck_path: Path) -> str:
    return os.path.relpath(target, deck_path.parent).replace("\\", "/")


def header(deck_name: str, deck_path: Path, cell: SramCell, inc: Path, n_va: Path, p_va: Path, bench: dict[str, str]) -> list[str]:
    return [
        f"* Auto-generated SRAM1 PEX test: {deck_name}",
        ".option INGOLD=2 POST=2",
        f'.hdl "{relative_path(n_va, deck_path)}"',
        f'.hdl "{relative_path(p_va, deck_path)}"',
        f'.include "{relative_path(inc, deck_path)}"',
        f".param VDD_VAL={bench['vdd']} VSS_VAL={bench['vss']}",
        ".param VCORE='VDD_VAL-VSS_VAL'",
        ".param " + " ".join(f"{key.upper()}={value}" for key, value in bench.items() if key not in {"vdd", "vss"}),
        "",
        "VVSS VSS_SRC 0 'VSS_VAL'",
        "VVDD VDD_SRC VSS_SRC 'VCORE'",
        "RVDD VDD_SRC VDD 'RVDD'",
        "RVSS VSS VSS_SRC 'RVSS'",
        "CVDD VDD VSS 'CVDD'",
        "",
    ]


def dut_line(cell: SramCell) -> str:
    nodes = {port.upper(): port for port in REQUIRED_PORTS}
    return f"XDUT {' '.join(nodes[port.upper()] for port in cell.ports)} {cell.name}"


def tran_footer() -> list[str]:
    return [
        "* 1 ps output interval prevents timing metrics from being quantized at 10 ps.",
        "* Do not use UIC: establish a DC operating point before the transient run.",
        ".tran 'TSTEP' 'TSTOP'",
        ".probe tran v(BL) v(BLB) v(WL) v(Q) v(QB) v(BLF) v(BLBF) i(VVDD) i(VBLDRV) i(VBLBDRV) i(VWLDRV)",
        ".print tran v(BL) v(BLB) v(WL) v(Q) v(QB) v(BLF) v(BLBF) i(VVDD) i(VBLDRV) i(VBLBDRV) i(VWLDRV)",
        ".end",
        "",
    ]


def smoke_deck(cell: SramCell, common: list[str]) -> str:
    lines = [*common, "VQINIT Q VSS 0", "VQBINIT QB VSS 'VCORE'", dut_line(cell), ".op", ".end", ""]
    return "\n".join(lines)


def hold_deck(cell: SramCell, common: list[str]) -> str:
    lines = [
        *common,
        "VBLDRV BLF VSS_SRC 'VCORE'", "VBLBDRV BLBF VSS_SRC 'VCORE'",
        "RBL0 BLF BL 'RBL'", "RBLB0 BLBF BLB 'RBL'", "CBL0 BLF VSS 'CBL'", "CBLB0 BLBF VSS 'CBL'",
        "VWLDRV WLDRV VSS_SRC 0", "RWL0 WLDRV WL 'RWL'", "CWL0 WL VSS 'CWL'",
        dut_line(cell),
        ".ic V(Q)=0 V(QB)='VCORE'",
        *tran_footer(),
    ]
    return "\n".join(lines)


def read_deck(cell: SramCell, common: list[str], read_one: bool) -> str:
    initial_q, initial_qb = ("'VCORE'", "0") if read_one else ("0", "'VCORE'")
    lines = [
        *common,
        "VBLDRV BLPRE VSS_SRC 'VCORE'", "VBLBDRV BLBPRE VSS_SRC 'VCORE'",
        "* 1G keeps the DC precharge point but is electrically open during the read pulse.",
        "RPREBL BLPRE BLF 1G", "RPREBLB BLBPRE BLBF 1G",
        "RBL0 BLF BL 'RBL'", "RBLB0 BLBF BLB 'RBL'", "CBL0 BLF VSS 'CBL'", "CBLB0 BLBF VSS 'CBL'",
        "VWLDRV WLDRV VSS_SRC PULSE(0 'VCORE' 1n 'TR' 'TR' 2n 'TSTOP')", "RWL0 WLDRV WL 'RWL'", "CWL0 WL VSS 'CWL'",
        dut_line(cell), f".ic V(Q)={initial_q} V(QB)={initial_qb}", *tran_footer(),
    ]
    return "\n".join(lines)


def write_deck(cell: SramCell, common: list[str], write_one: bool) -> str:
    bl, blb = ("'VCORE'", "0") if write_one else ("0", "'VCORE'")
    initial_q, initial_qb = ("0", "'VCORE'") if write_one else ("'VCORE'", "0")
    lines = [
        *common,
        f"VBLDRV BLDRV_SRC VSS_SRC {bl}", f"VBLBDRV BLBDRV_SRC VSS_SRC {blb}",
        "RBLDRV0 BLDRV_SRC BLF 'RBL_DRV'", "RBLBDRV0 BLBDRV_SRC BLBF 'RBL_DRV'",
        "RBL0 BLF BL 'RBL'", "RBLB0 BLBF BLB 'RBL'", "CBL0 BLF VSS 'CBL'", "CBLB0 BLBF VSS 'CBL'",
        "VWLDRV WLDRV VSS_SRC PULSE(0 'VCORE' 1n 'TR' 'TR' 2n 'TSTOP')", "RWL0 WLDRV WL 'RWL'", "CWL0 WL VSS 'CWL'",
        dut_line(cell),
        f".ic V(Q)={initial_q} V(QB)={initial_qb}",
        *tran_footer(),
    ]
    return "\n".join(lines)


def write_trip_deck(cell: SramCell, common: list[str], write_one: bool) -> str:
    source = "VBLBTRIP" if write_one else "VBLTRIP"
    fixed = "VBLTRIP BL VSS 'VCORE'" if write_one else "VBLBTRIP BLB VSS 'VCORE'"
    swept_node = "BLB" if write_one else "BL"
    lines = [
        *common, fixed, f"{source} {swept_node} VSS 'VCORE'", "VWL WL VSS 'VCORE'",
        dut_line(cell), ".dc " + source + " 'VCORE' 0 1m", ".print dc v(BL) v(BLB) v(Q) v(QB)", ".end", "",
    ]
    return "\n".join(lines)


def snm_deck(cell: SramCell, common: list[str], read_mode: bool, force_qb: bool) -> str:
    wl = "'VCORE'" if read_mode else "0"
    force_name = "VQBFORCE QB VSS 0" if force_qb else "VQFORCE Q VSS 0"
    sweep_name = "VQBFORCE" if force_qb else "VQFORCE"
    lines = [
        *common,
        "VBL BL VSS 'VCORE'",
        "VBLB BLB VSS 'VCORE'",
        f"VWL WL VSS {wl}",
        force_name,
        dut_line(cell),
        f".dc {sweep_name} 0 'VCORE' 1m",
        ".print dc v(Q) v(QB)",
        ".end",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    inc = require_file(args.inc)
    bench = require_file(args.bench)
    n_va = require_file(args.n_va)
    p_va = require_file(args.p_va)
    cell = parse_subckt(inc)
    supply = parse_bench(bench)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    stem = inc.stem
    builders = {
        "smoke": lambda common: smoke_deck(cell, common),
        "hold": lambda common: hold_deck(cell, common),
        "read0": lambda common: read_deck(cell, common, read_one=False),
        "read1": lambda common: read_deck(cell, common, read_one=True),
        "write0": lambda common: write_deck(cell, common, write_one=False),
        "write1": lambda common: write_deck(cell, common, write_one=True),
        "wtrip0": lambda common: write_trip_deck(cell, common, write_one=False),
        "wtrip1": lambda common: write_trip_deck(cell, common, write_one=True),
        "hsnm": lambda common: snm_deck(cell, common, read_mode=False, force_qb=False),
        "hsnm_qb": lambda common: snm_deck(cell, common, read_mode=False, force_qb=True),
        "rsnm": lambda common: snm_deck(cell, common, read_mode=True, force_qb=False),
        "rsnm_qb": lambda common: snm_deck(cell, common, read_mode=True, force_qb=True),
    }
    for test_name, build in builders.items():
        deck_path = output / f"{stem}_{test_name}.sp"
        deck_path.write_text(
            build(header(test_name, deck_path, cell, inc, n_va, p_va, supply)),
            encoding="utf-8",
        )
        print(f"Wrote: {deck_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
