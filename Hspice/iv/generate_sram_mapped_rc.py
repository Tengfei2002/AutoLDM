#!/usr/bin/env python3
"""Generate SRAM HSPICE deck with RC values mapped through sram_schematic.txt."""

from __future__ import annotations

import itertools
import heapq
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCHEMATIC = ROOT / "output_SDE" / "rc_raphreal" / "sram_schematic.txt"
R_MATRIX = ROOT / "output_SDE" / "rc_raphreal" / "n19_cMatrix.spi"
C_MATRIX = ROOT / "output_SDE" / "rc_raphreal" / "n18_cMatrix.spi"
OUT_IV = ROOT / "Hspice" / "iv" / "standard_sram.sp"
OUT_RCSP = ROOT / "output_SDE" / "rc_sp" / "standard_sram.sp"

R_OPEN_THRESHOLD = 1e12
FIXED_ALIASES = [
    ("Q", "PU2_Q_GATE", "PD2_Q_GATE", "same Q gate top/bottom in schematic map"),
    ("QB", "PU1_QB_GATE", "PD1_QB_GATE", "same QB gate top/bottom in schematic map"),
]

NET_GROUPS = {
    "BL": ["BL_PORT", "PG1_BL_SD"],
    "BLB": ["BLB_PORT", "PG2_BLB_SD"],
    "WL": ["WL_PORT", "PG1_WL_GATE", "PG2_WL_GATE"],
    "Q": ["Q_NODE", "PG1_PD1_Q_SD", "PU1_Q_SD", "PD2_Q_GATE", "PU2_Q_GATE"],
    "QB": ["QB_NODE", "PD2_PG2_QB_SD", "PU2_QB_SD", "PD1_QB_GATE", "PU1_QB_GATE"],
    "VDD": ["VDD_PORT", "PU1_VDD_SD", "PU2_VDD_SD"],
    "VSS": ["VSS_PORT", "PD1_VSS_SD", "PD2_VSS_SD"],
}


def parse_schematic() -> tuple[dict[str, str], dict[str, str]]:
    text = SCHEMATIC.read_text(errors="ignore")
    r_map: dict[str, str] = {}
    c_map: dict[str, str] = {}
    for kind, name, target in re.findall(r"#define\s+([RC])\s+(\S+)\s+(\S+)", text):
        if kind == "R":
            r_map[name] = target
        else:
            c_map[name] = target
    return r_map, c_map


def parse_r_matrix() -> dict[frozenset[str], tuple[str, float | None]]:
    data: dict[frozenset[str], tuple[str, float | None]] = {}
    for raw in R_MATRIX.read_text(errors="ignore").splitlines():
        parts = raw.split()
        if len(parts) != 4 or not parts[0].startswith("R_"):
            continue
        name, node_a, node_b, value_text = parts
        value = None if value_text.lower() == "inf" else float(value_text)
        data[frozenset((node_a, node_b))] = (name, value)
    return data


def build_r_graph(
    r_matrix: dict[frozenset[str], tuple[str, float | None]]
) -> dict[str, list[tuple[str, float, str]]]:
    graph: dict[str, list[tuple[str, float, str]]] = {}
    for pair, (name, value) in r_matrix.items():
        if value is None or value >= R_OPEN_THRESHOLD:
            continue
        node_a, node_b = tuple(pair)
        graph.setdefault(node_a, []).append((node_b, value, name))
        graph.setdefault(node_b, []).append((node_a, value, name))
    return graph


def shortest_path(
    graph: dict[str, list[tuple[str, float, str]]], start: str, goal: str
) -> tuple[float, list[str]] | None:
    queue: list[tuple[float, str, list[str]]] = [(0.0, start, [])]
    best: dict[str, float] = {start: 0.0}
    while queue:
        cost, node, path = heapq.heappop(queue)
        if node == goal:
            return cost, path
        if cost > best.get(node, float("inf")):
            continue
        for nxt, edge_cost, edge_name in graph.get(node, []):
            new_cost = cost + edge_cost
            if new_cost < best.get(nxt, float("inf")):
                best[nxt] = new_cost
                heapq.heappush(queue, (new_cost, nxt, path + [edge_name]))
    return None


def parse_c_matrix() -> dict[frozenset[str], tuple[str, float]]:
    data: dict[frozenset[str], tuple[str, float]] = {}
    for raw in C_MATRIX.read_text(errors="ignore").splitlines():
        parts = raw.split()
        if len(parts) != 4 or not parts[0].startswith("C_"):
            continue
        name, node_a, node_b, value_text = parts
        data[frozenset((node_a, node_b))] = (name, float(value_text))
    return data


def spice_value(value: float) -> str:
    return f"{value:.6e}"


def build_mapped_rc(r_map: dict[str, str], c_map: dict[str, str]) -> tuple[list[str], list[str], list[str]]:
    r_matrix = parse_r_matrix()
    r_graph = build_r_graph(r_matrix)
    c_matrix = parse_c_matrix()
    r_lines: list[str] = []
    c_lines: list[str] = []
    report: list[str] = []

    for net_name, left, right, reason in FIXED_ALIASES:
        if left in r_map and right in r_map:
            r_lines.append(f"RMAP_ALIAS_{left}_{right} {left} {right} 1u $ {reason}")
            report.append(f"R alias {net_name} {left} {right} {reason}")

    seen_pairs: set[frozenset[str]] = set()
    for net_name, labels in NET_GROUPS.items():
        for left, right in itertools.combinations(labels, 2):
            if left not in r_map or right not in r_map:
                report.append(f"R missing-label {net_name} {left} {right}")
                continue
            label_pair = frozenset((left, right))
            if label_pair in seen_pairs:
                continue
            seen_pairs.add(label_pair)

            contact_left = r_map[left]
            contact_right = r_map[right]
            if contact_left == contact_right:
                r_lines.append(
                    f"RMAP_{net_name}_{left}_{right} {left} {right} 1u "
                    f"$ same contact {contact_left}"
                )
                report.append(f"R same {net_name} {left} {right} {contact_left}")
                continue

            found = r_matrix.get(frozenset((contact_left, contact_right)))
            if found is not None:
                matrix_name, value = found
                if value is not None and value < R_OPEN_THRESHOLD:
                    r_lines.append(
                        f"RMAP_{net_name}_{left}_{right} {left} {right} {spice_value(value)} "
                        f"$ direct {matrix_name}: {contact_left} <-> {contact_right}"
                    )
                    report.append(f"R keep-direct {net_name} {left} {right} {matrix_name} {value:.6e}")
                    continue

            path = shortest_path(r_graph, contact_left, contact_right)
            if path is None:
                matrix_name = found[0] if found else "not-in-matrix"
                report.append(
                    f"R open {net_name} {left} {right} {matrix_name} "
                    f"{contact_left} {contact_right}"
                )
                continue
            value, edges = path
            if value >= R_OPEN_THRESHOLD:
                report.append(f"R open-path {net_name} {left} {right} {value:.6e}")
                continue
            r_lines.append(
                f"RMAP_{net_name}_{left}_{right} {left} {right} {spice_value(value)} "
                f"$ path {'+'.join(edges)}: {contact_left} <-> {contact_right}"
            )
            report.append(
                f"R keep-path {net_name} {left} {right} {value:.6e} {'+'.join(edges)}"
            )
            continue

    for left, right in itertools.combinations(c_map, 2):
        region_left = c_map[left]
        region_right = c_map[right]
        found = c_matrix.get(frozenset((region_left, region_right)))
        if found is None:
            report.append(f"C missing {left} {right} {region_left} {region_right}")
            continue
        matrix_name, value = found
        c_lines.append(
            f"CMAP_{left}_{right} {left} {right} {spice_value(value)} "
            f"$ {matrix_name}: {region_left} <-> {region_right}"
        )
        report.append(f"C keep {left} {right} {matrix_name} {value:.6e}")

    return r_lines, c_lines, report


def deck_text(r_lines: list[str], c_lines: list[str]) -> str:
    r_body = "\n".join(r_lines) if r_lines else "* no finite mapped R entries"
    c_body = "\n".join(c_lines) if c_lines else "* no mapped C entries"
    return f"""***********************************************************************
* Standard 6T SRAM test deck with RC values mapped from schematic names.
* Generated by Hspice/iv/generate_sram_mapped_rc.py.
*
* R source: output_SDE/rc_raphreal/n19_cMatrix.spi
* C source: output_SDE/rc_raphreal/n18_cMatrix.spi
* Map:      output_SDE/rc_raphreal/sram_schematic.txt
***********************************************************************
.OPTION POST=2 INGOLD=2 PROBE NOMOD METHOD=GEAR RUNLVL=5 MEASDGT=6
.TEMP 25

.HDL "../va/cfet_nmos_lvt.va"
.HDL "../va/cfet_pmos_lvt.va"

.PARAM VDD_VAL = 0.7
.PARAM TSTEP   = 1p
.PARAM DC_STEP = 1m
.PARAM LCH  = 16n
.PARAM WPG  = 25n
.PARAM WPD  = 25n
.PARAM WPU  = 25n
.PARAM NFPG = 1
.PARAM NFPD = 1
.PARAM NFPU = 1
.PARAM RBL_DRV   = 1e12
.PARAM RBLB_DRV  = 1e12
.PARAM RQ_FORCE  = 1e15
.PARAM RQB_FORCE = 1e15
.PARAM CBL_EXT   = 10f
.PARAM CBLB_EXT  = 10f
.PARAM CQ_EXT    = 1f
.PARAM CQB_EXT   = 1f

.SUBCKT SRAM_6T_STANDARD BL BLB WL Q QB VDD VSS
+ LCH=16n WPG=25n WPD=25n WPU=25n NFPG=1 NFPD=1 NFPU=1

* External ports to schematic-mapped RC nodes.
RPORT_BL   BL   BL_PORT   1m
RPORT_BLB  BLB  BLB_PORT  1m
RPORT_WL   WL   WL_PORT   1m
RPORT_Q    Q    Q_NODE    1m
RPORT_QB   QB   QB_NODE   1m
RPORT_VDD  VDD  VDD_PORT  1m
RPORT_VSS  VSS  VSS_PORT  1m

* SRAM devices. Terminals use names from sram_schematic.txt.
XPG1 PG1_BL_SD PG1_WL_GATE PG1_PD1_Q_SD VSS cfet_nmos_lvt
+ L='LCH' W='WPG' NF='NFPG'
XPG2 PG2_BLB_SD PG2_WL_GATE PD2_PG2_QB_SD VSS cfet_nmos_lvt
+ L='LCH' W='WPG' NF='NFPG'
XPD1 PG1_PD1_Q_SD PD1_QB_GATE PD1_VSS_SD VSS cfet_nmos_lvt
+ L='LCH' W='WPD' NF='NFPD'
XPD2 PD2_PG2_QB_SD PD2_Q_GATE PD2_VSS_SD VSS cfet_nmos_lvt
+ L='LCH' W='WPD' NF='NFPD'
XPU1 PU1_Q_SD PU1_QB_GATE PU1_VDD_SD VDD cfet_pmos_lvt
+ L='LCH' W='WPU' NF='NFPU'
XPU2 PU2_QB_SD PU2_Q_GATE PU2_VDD_SD VDD cfet_pmos_lvt
+ L='LCH' W='WPU' NF='NFPU'

* Resistance entries looked up through #define R names.
{r_body}

* Capacitance entries looked up through #define C names.
{c_body}

.ENDS SRAM_6T_STANDARD

VDD_SRC  vdd 0 DC 'VDD_VAL'
VSS_SRC  vss 0 DC 0
VBL_DRV   bl_drv  0 DC 'VDD_VAL'
VBLB_DRV  blb_drv 0 DC 'VDD_VAL'
RBL_DRV   bl      bl_drv  'RBL_DRV'
RBLB_DRV  blb     blb_drv 'RBLB_DRV'
VWL_DRV wl 0 DC 0
VQF  q_force  0 DC 0
VQBF qb_force 0 DC 0
RQ_FORCE  q  q_force  'RQ_FORCE'
RQB_FORCE qb qb_force 'RQB_FORCE'
CBL_LOAD   bl  0 'CBL_EXT'
CBLB_LOAD  blb 0 'CBLB_EXT'
CQ_LOAD    q   0 'CQ_EXT'
CQB_LOAD   qb  0 'CQB_EXT'

XSRAM bl blb wl q qb vdd vss SRAM_6T_STANDARD
+ LCH='LCH' WPG='WPG' WPD='WPD' WPU='WPU'
+ NFPG='NFPG' NFPD='NFPD' NFPU='NFPU'

.PRINT TRAN V(bl) V(blb) V(wl) V(q) V(qb) I(VDD_SRC) I(VBL_DRV) I(VBLB_DRV)
.PRINT DC   V(q) V(qb) V(bl) V(blb) V(wl) I(VQF) I(VQBF) I(VDD_SRC) I(VBL_DRV) I(VBLB_DRV)

.NODESET V(q)='VDD_VAL' V(qb)=0 V(bl)='VDD_VAL' V(blb)='VDD_VAL'
.OP

.ALTER READ_Q1
.PARAM RBL_DRV=1e12 RBLB_DRV=1e12 RQ_FORCE=1e15 RQB_FORCE=1e15
VBL_DRV  bl_drv  0 DC 'VDD_VAL'
VBLB_DRV blb_drv 0 DC 'VDD_VAL'
VWL_DRV  wl 0 PWL(0 0 0.20n 0 0.22n 'VDD_VAL' 1.20n 'VDD_VAL' 1.22n 0 2.00n 0)
.IC V(q)='VDD_VAL' V(qb)=0 V(bl)='VDD_VAL' V(blb)='VDD_VAL'
.TRAN 'TSTEP' 2n UIC
.MEAS TRAN READ_Q1_DELAY TRIG V(wl) VAL='0.5*VDD_VAL' RISE=1 TARG V(blb) VAL='VDD_VAL-0.05' FALL=1
.MEAS TRAN READ_Q1_Q_MIN MIN V(q) FROM=0.22n TO=1.20n

.ALTER READ_Q0
.PARAM RBL_DRV=1e12 RBLB_DRV=1e12 RQ_FORCE=1e15 RQB_FORCE=1e15
VBL_DRV  bl_drv  0 DC 'VDD_VAL'
VBLB_DRV blb_drv 0 DC 'VDD_VAL'
VWL_DRV  wl 0 PWL(0 0 0.20n 0 0.22n 'VDD_VAL' 1.20n 'VDD_VAL' 1.22n 0 2.00n 0)
.IC V(q)=0 V(qb)='VDD_VAL' V(bl)='VDD_VAL' V(blb)='VDD_VAL'
.TRAN 'TSTEP' 2n UIC
.MEAS TRAN READ_Q0_DELAY TRIG V(wl) VAL='0.5*VDD_VAL' RISE=1 TARG V(bl) VAL='VDD_VAL-0.05' FALL=1
.MEAS TRAN READ_Q0_QB_MIN MIN V(qb) FROM=0.22n TO=1.20n

.ALTER WRITE_0
.PARAM RBL_DRV=10 RBLB_DRV=10 RQ_FORCE=1e15 RQB_FORCE=1e15
VBL_DRV  bl_drv  0 PWL(0 'VDD_VAL' 0.20n 'VDD_VAL' 0.22n 0 1.50n 0 1.52n 'VDD_VAL' 2.00n 'VDD_VAL')
VBLB_DRV blb_drv 0 DC 'VDD_VAL'
VWL_DRV  wl 0 PWL(0 0 0.20n 0 0.22n 'VDD_VAL' 1.50n 'VDD_VAL' 1.52n 0 2.00n 0)
.IC V(q)='VDD_VAL' V(qb)=0 V(bl)='VDD_VAL' V(blb)='VDD_VAL'
.TRAN 'TSTEP' 2n UIC
.MEAS TRAN WRITE0_DELAY TRIG V(wl) VAL='0.5*VDD_VAL' RISE=1 TARG V(q) VAL='0.5*VDD_VAL' FALL=1
.MEAS TRAN WRITE0_Q_FINAL FIND V(q) AT=1.80n
.MEAS TRAN WRITE0_QB_FINAL FIND V(qb) AT=1.80n

.ALTER WRITE_1
.PARAM RBL_DRV=10 RBLB_DRV=10 RQ_FORCE=1e15 RQB_FORCE=1e15
VBL_DRV  bl_drv  0 DC 'VDD_VAL'
VBLB_DRV blb_drv 0 PWL(0 'VDD_VAL' 0.20n 'VDD_VAL' 0.22n 0 1.50n 0 1.52n 'VDD_VAL' 2.00n 'VDD_VAL')
VWL_DRV  wl 0 PWL(0 0 0.20n 0 0.22n 'VDD_VAL' 1.50n 'VDD_VAL' 1.52n 0 2.00n 0)
.IC V(q)=0 V(qb)='VDD_VAL' V(bl)='VDD_VAL' V(blb)='VDD_VAL'
.TRAN 'TSTEP' 2n UIC
.MEAS TRAN WRITE1_DELAY TRIG V(wl) VAL='0.5*VDD_VAL' RISE=1 TARG V(q) VAL='0.5*VDD_VAL' RISE=1
.MEAS TRAN WRITE1_Q_FINAL FIND V(q) AT=1.80n
.MEAS TRAN WRITE1_QB_FINAL FIND V(qb) AT=1.80n

.ALTER HOLD_Q1
.PARAM RBL_DRV=1e15 RBLB_DRV=1e15 RQ_FORCE=1e15 RQB_FORCE=1e15
VBL_DRV  bl_drv  0 DC 'VDD_VAL'
VBLB_DRV blb_drv 0 DC 'VDD_VAL'
VWL_DRV  wl 0 DC 0
.IC V(q)='VDD_VAL' V(qb)=0 V(bl)='VDD_VAL' V(blb)='VDD_VAL'
.TRAN 'TSTEP' 2n UIC
.MEAS TRAN HOLD_Q1_Q_MIN MIN V(q) FROM=0.10n TO=2.00n
.MEAS TRAN HOLD_Q1_QB_MAX MAX V(qb) FROM=0.10n TO=2.00n
.MEAS TRAN HOLD_Q1_IVDD_AVG AVG I(VDD_SRC) FROM=0.50n TO=2.00n

.ALTER HOLD_Q0
.PARAM RBL_DRV=1e15 RBLB_DRV=1e15 RQ_FORCE=1e15 RQB_FORCE=1e15
VBL_DRV  bl_drv  0 DC 'VDD_VAL'
VBLB_DRV blb_drv 0 DC 'VDD_VAL'
VWL_DRV  wl 0 DC 0
.IC V(q)=0 V(qb)='VDD_VAL' V(bl)='VDD_VAL' V(blb)='VDD_VAL'
.TRAN 'TSTEP' 2n UIC
.MEAS TRAN HOLD_Q0_Q_MAX MAX V(q) FROM=0.10n TO=2.00n
.MEAS TRAN HOLD_Q0_QB_MIN MIN V(qb) FROM=0.10n TO=2.00n
.MEAS TRAN HOLD_Q0_IVDD_AVG AVG I(VDD_SRC) FROM=0.50n TO=2.00n

.ALTER HOLD_SNM_Q_SWEEP
.PARAM RBL_DRV=1e15 RBLB_DRV=1e15 RQ_FORCE=1m RQB_FORCE=1e15
VBL_DRV  bl_drv  0 DC 'VDD_VAL'
VBLB_DRV blb_drv 0 DC 'VDD_VAL'
VWL_DRV  wl 0 DC 0
VQF      q_force 0 DC 0
VQBF     qb_force 0 DC 0
.NODESET V(qb)='VDD_VAL'
.DC VQF 0 'VDD_VAL' 'DC_STEP'

.ALTER HOLD_SNM_QB_SWEEP
.PARAM RBL_DRV=1e15 RBLB_DRV=1e15 RQ_FORCE=1e15 RQB_FORCE=1m
VBL_DRV  bl_drv  0 DC 'VDD_VAL'
VBLB_DRV blb_drv 0 DC 'VDD_VAL'
VWL_DRV  wl 0 DC 0
VQF      q_force 0 DC 0
VQBF     qb_force 0 DC 0
.NODESET V(q)='VDD_VAL'
.DC VQBF 0 'VDD_VAL' 'DC_STEP'

.ALTER READ_SNM_Q_SWEEP
.PARAM RBL_DRV=1m RBLB_DRV=1m RQ_FORCE=1m RQB_FORCE=1e15
VBL_DRV  bl_drv  0 DC 'VDD_VAL'
VBLB_DRV blb_drv 0 DC 'VDD_VAL'
VWL_DRV  wl 0 DC 'VDD_VAL'
VQF      q_force 0 DC 0
VQBF     qb_force 0 DC 0
.NODESET V(qb)='VDD_VAL'
.DC VQF 0 'VDD_VAL' 'DC_STEP'

.ALTER READ_SNM_QB_SWEEP
.PARAM RBL_DRV=1m RBLB_DRV=1m RQ_FORCE=1e15 RQB_FORCE=1m
VBL_DRV  bl_drv  0 DC 'VDD_VAL'
VBLB_DRV blb_drv 0 DC 'VDD_VAL'
VWL_DRV  wl 0 DC 'VDD_VAL'
VQF      q_force 0 DC 0
VQBF     qb_force 0 DC 0
.NODESET V(q)='VDD_VAL'
.DC VQBF 0 'VDD_VAL' 'DC_STEP'

.END
"""


def main() -> int:
    r_map, c_map = parse_schematic()
    r_lines, c_lines, report = build_mapped_rc(r_map, c_map)
    text = deck_text(r_lines, c_lines)
    OUT_IV.write_text(text, encoding="utf-8")
    OUT_RCSP.write_text(text.replace('.HDL "../va/', '.HDL "../../Hspice/va/'), encoding="utf-8")
    report_path = ROOT / "Hspice" / "iv" / "standard_sram_mapped_rc_report.txt"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"R entries kept: {len(r_lines)}")
    print(f"C entries kept: {len(c_lines)}")
    print(f"Wrote: {OUT_IV}")
    print(f"Wrote: {OUT_RCSP}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
