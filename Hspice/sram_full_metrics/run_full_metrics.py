from __future__ import annotations

import csv
import math
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


BASE = Path(__file__).resolve().parent
HSPICE = Path(r"C:\synopsys\Hspice_P-2019.06-SP1-1\WIN64\hspice.com")
LICENSE = "27000@LAPTOP-K9QP6UAM"
VDD = 0.7

DECKS = BASE / "decks"
RESULTS = BASE / "results"
FIGS = BASE / "figures"
DATA = BASE / "data"
SOURCE_DECKS = BASE.parent / "sram_clean" / "decks"


def savefig_pair(path: Path) -> None:
    plt.savefig(path)
    plt.savefig(path.with_suffix(".png"), dpi=220)


def ensure_dirs() -> None:
    for folder in (DECKS, RESULTS, FIGS, DATA):
        folder.mkdir(parents=True, exist_ok=True)
    for name in ("sram6t_ideal.inc", "sram6t_rc.inc", "sram6t_rc_gate_direct.inc"):
        shutil.copy2(SOURCE_DECKS / name, DECKS / name)


def write_text(path: Path, text: str) -> None:
    path.write_text(text.strip() + "\n", encoding="utf-8")


def common_options(title: str, include_name: str) -> str:
    return f"""
* {title}
.OPTION POST=2 PROBE INGOLD=2 MEASDGT=6 METHOD=GEAR GSHUNT=1e-12
.TEMP 25
.INCLUDE "{include_name}"
.PARAM VDD={VDD}
VDD_SRC vdd 0 DC 'VDD'
VSS_SRC vss 0 DC 0
"""


def instance(subckt: str) -> str:
    return f"XSRAM bl blb wl q qb vdd vss {subckt}"


def deck_snm(name: str, include_name: str, subckt: str, mode: str) -> Path:
    wl = "0" if mode == "hold" else "'VDD'"
    title = f"{name} {mode} butterfly dc"
    text = common_options(title, include_name) + f"""
VBL bl 0 DC 'VDD'
VBLB blb 0 DC 'VDD'
VWL wl 0 DC {wl}
VQ q 0 DC 0
CQB qb 0 1f
CBL bl 0 10f
CBLB blb 0 10f
{instance(subckt)}
.DC VQ 0 'VDD' 0.001
.PRINT DC V(q) V(qb)
.END
"""
    path = DECKS / f"{name}_{mode}_snm.sp"
    write_text(path, text)
    return path


def deck_rsnm_noise(name: str, include_name: str, state: str) -> Path:
    """Read-SNM noise-source deck.

    The SRAM is biased in read mode (WL=VDD, BL=BLB=VDD).  Instead of forcing a
    storage node, the feedback gates are separated into GQ/GQB and driven by
    voltage sources whose values are +/-VN relative to the corresponding storage
    nodes.  VN is swept until the stored state flips.
    """
    if state not in {"q1", "q0"}:
        raise ValueError(state)
    q_ic, qb_ic = ("'VDD'", "0") if state == "q1" else ("0", "'VDD'")
    # For Q=1,QB=0, the destructive noise raises the QB-controlled feedback
    # gate and lowers the Q-controlled feedback gate.  For Q=0,QB=1 the signs
    # are reversed.
    gqb_expr, gq_expr = ("V(qb)+V(vn)", "V(q)-V(vn)") if state == "q1" else ("V(qb)-V(vn)", "V(q)+V(vn)")
    title = f"{name} read noise-source RSNM {state}"

    if name == "ideal":
        core = """
XPG1 bl wl q vss nmos_lvt L='LCH' W='WPG' NF='NF'
XPG2 blb wl qb vss nmos_lvt L='LCH' W='WPG' NF='NF'
XPD1 q gqb vss vss nmos_lvt L='LCH' W='WPD' NF='NF'
XPD2 qb gq vss vss nmos_lvt L='LCH' W='WPD' NF='NF'
XPU1 q gqb vdd vdd pmos_lvt L='LCH' W='WPU' NF='NF'
XPU2 qb gq vdd vdd pmos_lvt L='LCH' W='WPU' NF='NF'
"""
    else:
        core = """
XPG1 PG1_BL_SD PG1_WL_GATE PG1_PD1_Q_SD vss nmos_lvt L='LCH' W='WPG' NF='NF'
XPG2 PG2_BLB_SD PG2_WL_GATE PD2_PG2_QB_SD vss nmos_lvt L='LCH' W='WPG' NF='NF'
XPD1 PG1_PD1_Q_SD gqb PD1_VSS_SD vss nmos_lvt L='LCH' W='WPD' NF='NF'
XPD2 PD2_PG2_QB_SD gq PD2_VSS_SD vss nmos_lvt L='LCH' W='WPD' NF='NF'
XPU1 PU1_Q_SD gqb PU1_VDD_SD vdd pmos_lvt L='LCH' W='WPU' NF='NF'
XPU2 qb gq PU2_VDD_SD vdd pmos_lvt L='LCH' W='WPU' NF='NF'
RPORT_BL bl BL_PORT 1m
RPORT_BLB blb BLB_PORT 1m
RPORT_WL wl WL_PORT 1m
RPORT_Q q Q_NODE 1m
RPORT_QB qb QB_NODE 1m
RPORT_VDD vdd VDD_PORT 1m
RPORT_VSS vss VSS_PORT 1m
R_BL BL_PORT PG1_BL_SD 2.195710e1
R_BLB BLB_PORT PG2_BLB_SD 2.568020e1
R_WL1 WL_PORT PG1_WL_GATE 7.031990e0
R_WL2 WL_PORT PG2_WL_GATE 7.031990e0
R_Q_PD Q_NODE PG1_PD1_Q_SD 5.248000e1
R_Q_PU Q_NODE PU1_Q_SD 1.343127e2
R_QB_PD QB_NODE PD2_PG2_QB_SD 5.248000e1
R_QB_PU QB_NODE PU2_QB_SD 1.343127e2
R_VDD_PU1 VDD_PORT PU1_VDD_SD 3.850940e1
R_VDD_PU2 VDD_PORT PU2_VDD_SD 3.850940e1
R_VSS_PD1 VSS_PORT PD1_VSS_SD 4.056860e1
R_VSS_PD2 VSS_PORT PD2_VSS_SD 4.056860e1
C_BL_BLB BL_PORT BLB_PORT 2.813200e-20
C_BL_WL BL_PORT WL_PORT 2.100100e-17
C_BL_VDD BL_PORT VDD_PORT 6.178700e-22
C_BL_VSS BL_PORT VSS_PORT 1.177000e-18
C_BL_Q BL_PORT Q_NODE 1.484100e-18
C_BL_QB BL_PORT QB_NODE 2.222800e-19
C_BLB_WL BLB_PORT WL_PORT 2.105800e-17
C_BLB_VDD BLB_PORT VDD_PORT 6.067700e-22
C_BLB_VSS BLB_PORT VSS_PORT 1.085400e-18
C_BLB_Q BLB_PORT Q_NODE 3.574200e-19
C_BLB_QB BLB_PORT QB_NODE 1.574900e-18
C_WL_VDD WL_PORT VDD_PORT 3.334300e-18
C_WL_VSS WL_PORT VSS_PORT 2.645700e-17
C_WL_Q WL_PORT Q_NODE 4.063800e-17
C_WL_QB WL_PORT QB_NODE 5.671100e-17
C_VDD_VSS VDD_PORT VSS_PORT 1.529300e-21
C_VDD_Q VDD_PORT Q_NODE 1.001500e-17
C_VDD_QB VDD_PORT QB_NODE 1.000800e-17
C_VSS_Q VSS_PORT Q_NODE 1.881400e-17
C_VSS_QB VSS_PORT QB_NODE 1.900100e-17
C_Q_QB Q_NODE QB_NODE 9.374700e-17
"""

    text = common_options(title, include_name) + f"""
VNOISE vn 0 DC 0
VBL bl 0 DC 'VDD'
VBLB blb 0 DC 'VDD'
VWL wl 0 DC 'VDD'
EGQB gqb 0 VOL='{gqb_expr}'
EGQ gq 0 VOL='{gq_expr}'
CQ q 0 1f
CQB qb 0 1f
CBL bl 0 10f
CBLB blb 0 10f
{core}
.NODESET V(q)={q_ic} V(qb)={qb_ic} V(bl)='VDD' V(blb)='VDD'
.DC VNOISE 0 0.5 0.001
.PRINT DC V(q) V(qb) V(gq) V(gqb) V(vn)
.END
"""
    path = DECKS / f"{name}_rsnm_noise_{state}.sp"
    write_text(path, text)
    return path


def deck_read(name: str, include_name: str, subckt: str) -> Path:
    text = common_options(f"{name} read transient q=1", include_name) + f"""
VBLDRV bl_drv 0 DC 'VDD'
VBLBDRV blb_drv 0 DC 'VDD'
RBL bl bl_drv 1G
RBLB blb blb_drv 1G
VWL wl 0 PWL(0 0 0.10n 0 0.20n 'VDD' 1.20n 'VDD')
CQ q 0 1f
CQB qb 0 1f
CBL bl 0 10f
CBLB blb 0 10f
{instance(subckt)}
.IC V(q)='VDD' V(qb)=0 V(bl)='VDD' V(blb)='VDD'
.TRAN 0.2p 1.2n
.PRINT TRAN V(q) V(qb) V(bl) V(blb)
.PRINT TRAN V(wl) I(VDD_SRC)
.MEAS TRAN Q_LOW_MAX MAX V(qb) FROM=0.20n TO=1.20n
.MEAS TRAN Q_HIGH_MIN MIN V(q) FROM=0.20n TO=1.20n
.END
"""
    path = DECKS / f"{name}_read_q1.sp"
    write_text(path, text)
    return path


def deck_write(name: str, include_name: str, subckt: str) -> Path:
    text = common_options(f"{name} write zero transient", include_name) + f"""
VBLDRV bl_drv 0 DC 0
VBLBDRV blb_drv 0 DC 'VDD'
RBL bl bl_drv 10
RBLB blb blb_drv 10
VWL wl 0 PWL(0 0 0.10n 0 0.20n 'VDD' 1.20n 'VDD')
CQ q 0 1f
CQB qb 0 1f
CBL bl 0 10f
CBLB blb 0 10f
{instance(subckt)}
.IC V(q)='VDD' V(qb)=0 V(bl)='VDD' V(blb)='VDD'
.TRAN 0.2p 1.2n
.PRINT TRAN V(q) V(qb) V(bl) V(blb)
.PRINT TRAN V(wl) I(VDD_SRC)
.MEAS TRAN Q_FINAL FIND V(q) AT=1.20n
.MEAS TRAN QB_FINAL FIND V(qb) AT=1.20n
.END
"""
    path = DECKS / f"{name}_write0.sp"
    write_text(path, text)
    return path


def deck_write_trip(name: str, include_name: str, subckt: str) -> Path:
    text = common_options(f"{name} write trip dc", include_name) + f"""
VBLDRV bl 0 DC 'VDD'
VBLBDRV blb 0 DC 'VDD'
VWL wl 0 DC 'VDD'
CQ q 0 1f
CQB qb 0 1f
CBL bl 0 10f
CBLB blb 0 10f
{instance(subckt)}
.NODESET V(q)='VDD' V(qb)=0
.DC VBLDRV 'VDD' 0 -0.001
.PRINT DC V(bl) V(q) V(qb)
.END
"""
    path = DECKS / f"{name}_write_trip.sp"
    write_text(path, text)
    return path


def deck_hold_current(name: str, include_name: str, subckt: str) -> Path:
    text = common_options(f"{name} hold leakage q=1", include_name) + f"""
VBL bl 0 DC 'VDD'
VBLB blb 0 DC 'VDD'
VWL wl 0 DC 0
CQ q 0 1f
CQB qb 0 1f
CBL bl 0 10f
CBLB blb 0 10f
{instance(subckt)}
.IC V(q)='VDD' V(qb)=0 V(bl)='VDD' V(blb)='VDD'
.TRAN 0.2p 1.2n
.PRINT TRAN V(q) V(qb)
.PRINT TRAN I(VDD_SRC)
.MEAS TRAN I_HOLD AVG I(VDD_SRC) FROM=0.60n TO=1.20n
.END
"""
    path = DECKS / f"{name}_hold_leakage.sp"
    write_text(path, text)
    return path


def deck_original_rc_check() -> Path:
    text = common_options("original rc connectivity check", "sram6t_rc.inc") + f"""
VBL bl 0 DC 'VDD'
VBLB blb 0 DC 'VDD'
VWL wl 0 DC 0
CQ q 0 1f
CQB qb 0 1f
CBL bl 0 10f
CBLB blb 0 10f
XSRAM bl blb wl q qb vdd vss SRAM6T_RC
.IC V(q)='VDD' V(qb)=0 V(bl)='VDD' V(blb)='VDD'
.TRAN 0.2p 0.5n
.PRINT TRAN V(q) V(qb)
.END
"""
    path = DECKS / "original_rc_connectivity_check.sp"
    write_text(path, text)
    return path


def run_hspice(deck: Path) -> int:
    run_dir = RESULTS / deck.stem
    run_dir.mkdir(parents=True, exist_ok=True)
    out = run_dir / deck.stem
    env = os.environ.copy()
    env["SNPSLMD_LICENSE_FILE"] = LICENSE
    env["LM_LICENSE_FILE"] = LICENSE
    env["installdir_P-2019.06-SP1-1"] = str(HSPICE.parent.parent)
    cmd = [str(HSPICE), "-i", deck.name, "-o", str(out)]
    proc = subprocess.run(cmd, cwd=deck.parent, env=env, text=True, capture_output=True)
    (run_dir / "runner_stdout_stderr.txt").write_text(
        proc.stdout + "\n" + proc.stderr, encoding="utf-8", errors="ignore"
    )
    return proc.returncode


def parse_measurements(lis: Path) -> dict[str, float]:
    values: dict[str, float] = {}
    pat = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([-+0-9.eE]+)")
    for line in lis.read_text(errors="ignore").splitlines():
        match = pat.match(line)
        if match:
            values[match.group(1).lower()] = float(match.group(2))
    return values


def parse_print_blocks(lis: Path) -> dict[tuple[str, ...], np.ndarray]:
    lines = lis.read_text(errors="ignore").splitlines()
    blocks: dict[tuple[str, ...], list[list[float]]] = {}
    i = 0
    num = re.compile(r"^\s*[-+]?\d")
    while i < len(lines) - 2:
        first_token = lines[i].strip().split()[0].lower() if lines[i].strip().split() else ""
        if first_token in {"time", "v-sweep", "volt"}:
            first = lines[i].split()
            second = lines[i + 1].split()
            if first[0].lower() in {"time", "v-sweep", "volt"}:
                xname = first[0]
                names = [xname] + second
                rows: list[list[float]] = []
                i += 2
                while i < len(lines) and num.match(lines[i]):
                    parts = lines[i].split()
                    try:
                        vals = [float(p) for p in parts[: len(names)]]
                    except ValueError:
                        break
                    if len(vals) == len(names):
                        rows.append(vals)
                    i += 1
                if rows:
                    blocks[tuple(names)] = rows
                continue
        i += 1
    return {k: np.asarray(v, dtype=float) for k, v in blocks.items()}


def find_block(blocks: dict[tuple[str, ...], np.ndarray], *names: str) -> tuple[tuple[str, ...], np.ndarray]:
    lowered = [n.lower() for n in names]
    for header, arr in blocks.items():
        h = [x.lower() for x in header]
        if all(n in h for n in lowered):
            return header, arr
    raise KeyError(f"missing block containing {names}")


def save_csv(path: Path, header: list[str], arr: np.ndarray) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(arr.tolist())


def snm_from_curve(x: np.ndarray, y: np.ndarray) -> float:
    # Geometric SNM from the largest axis-aligned square fully contained in
    # each butterfly lobe.  This is stricter than the earlier 45-degree opening
    # approximation and matches the report visualization.
    n = 1401
    grid = np.linspace(0.0, VDD, n)
    f = np.interp(grid, x, y)
    g = np.interp(grid, y[::-1], x[::-1])
    lower = np.minimum(f, g)
    upper = np.maximum(f, g)
    xx, yy = np.meshgrid(grid, grid)
    between = (yy >= lower[None, :]) & (yy <= upper[None, :])
    masks = [between & (yy >= xx), between & (yy <= xx)]
    dx = grid[1] - grid[0]

    def max_square_side(mask: np.ndarray) -> float:
        integral = np.pad(mask.astype(np.int32).cumsum(axis=0).cumsum(axis=1), ((1, 0), (1, 0)))

        def has_square(window_points: int) -> bool:
            sums = (
                integral[window_points:, window_points:]
                - integral[:-window_points, window_points:]
                - integral[window_points:, :-window_points]
                + integral[:-window_points, :-window_points]
            )
            return bool(np.any(sums == window_points * window_points))

        lo, hi = 1, n
        best = 0
        while lo <= hi:
            mid = (lo + hi) // 2
            if has_square(mid):
                best = mid
                lo = mid + 1
            else:
                hi = mid - 1
        return (best - 1) * dx if best > 1 else float("nan")

    sides = [max_square_side(mask) for mask in masks]
    valid = [s for s in sides if math.isfinite(s)]
    return min(valid) if len(valid) == 2 else float("nan")


@dataclass
class CaseResult:
    config: str
    status: str
    metrics: dict[str, float]


def analyze_config(config: str, prefix: str) -> CaseResult:
    metrics: dict[str, float] = {}
    # SNM curves
    for mode in ("hold", "read"):
        lis = RESULTS / f"{prefix}_{mode}_snm" / f"{prefix}_{mode}_snm.lis"
        blocks = parse_print_blocks(lis)
        header, arr = find_block(blocks, "q", "qb")
        cols = {n.lower(): i for i, n in enumerate(header)}
        data = arr[:, [cols[header[0].lower()], cols["q"], cols["qb"]]]
        save_csv(DATA / f"{prefix}_{mode}_butterfly.csv", ["sweep_v", "q_v", "qb_v"], data)
        x, y = data[:, 1], data[:, 2]
        metrics[f"{mode}_snm_v"] = snm_from_curve(x, y)
        plt.figure(figsize=(5.2, 4.8))
        plt.plot(x, y, label="HSPICE V(QB) vs forced V(Q)")
        plt.plot(y, x, label="mirrored curve")
        plt.plot([0, VDD], [0, VDD], "--", color="0.65", lw=1)
        plt.xlabel("V(Q) / V")
        plt.ylabel("V(QB) / V")
        plt.title(f"{config} {mode.upper()} butterfly")
        plt.xlim(0, VDD)
        plt.ylim(0, VDD)
        plt.grid(True, alpha=0.3)
        plt.legend(fontsize=8)
        plt.tight_layout()
        savefig_pair(FIGS / f"{prefix}_{mode}_butterfly.svg")
        plt.close()

    # Read SNM from dedicated noise-source sweeps.
    rsnm_values: list[float] = []
    rsnm_plot_data: list[tuple[str, np.ndarray, np.ndarray, np.ndarray]] = []
    for state in ("q1", "q0"):
        lis = RESULTS / f"{prefix}_rsnm_noise_{state}" / f"{prefix}_rsnm_noise_{state}.lis"
        blocks = parse_print_blocks(lis)
        header, arr = find_block(blocks, "q", "qb", "gq", "gqb")
        cols = {n.lower(): i for i, n in enumerate(header)}
        vn = arr[:, cols[header[0].lower()]]
        qv, qbv = arr[:, cols["q"]], arr[:, cols["qb"]]
        gqv, gqbv = arr[:, cols["gq"]], arr[:, cols["gqb"]]
        data = np.column_stack([vn, qv, qbv, gqv, gqbv])
        save_csv(DATA / f"{prefix}_rsnm_noise_{state}.csv", ["noise_v", "q_v", "qb_v", "gq_v", "gqb_v"], data)
        if state == "q1":
            idx = np.where(qv <= qbv)[0]
            label_prefix = "Q=1 initial"
        else:
            idx = np.where(qbv <= qv)[0]
            label_prefix = "Q=0 initial"
        rsnm = float(vn[idx[0]]) if len(idx) else float("nan")
        metrics[f"read_snm_noise_{state}_v"] = rsnm
        if math.isfinite(rsnm):
            rsnm_values.append(rsnm)
        rsnm_plot_data.append((label_prefix, vn, qv, qbv))
    metrics["read_snm_noise_v"] = min(rsnm_values) if rsnm_values else float("nan")

    fig, (ax_full, ax_zoom) = plt.subplots(1, 2, figsize=(10.8, 4.2), gridspec_kw={"width_ratios": [1.0, 1.25]})
    for label_prefix, vn, qv, qbv in rsnm_plot_data:
        vn_mv = vn * 1e3
        ax_full.plot(vn_mv, qv, label=f"{label_prefix}: V(Q)")
        ax_full.plot(vn_mv, qbv, "--", label=f"{label_prefix}: V(QB)")
        ax_zoom.plot(vn_mv, qv, label=f"{label_prefix}: V(Q)")
        ax_zoom.plot(vn_mv, qbv, "--", label=f"{label_prefix}: V(QB)")

    if math.isfinite(metrics["read_snm_noise_v"]):
        rsnm_mv = metrics["read_snm_noise_v"] * 1e3
        for ax in (ax_full, ax_zoom):
            ax.axvline(rsnm_mv, color="0.1", lw=1.2, ls="-.")
        ax_zoom.text(
            rsnm_mv + 0.8,
            0.50,
            f"RSNM = {rsnm_mv:.1f} mV",
            fontsize=8,
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="0.7", alpha=0.9),
        )
    ax_full.set_title("Full sweep")
    ax_full.set_xlabel("Injected read noise VN / mV")
    ax_full.set_ylabel("Storage-node voltage / V")
    ax_full.set_xlim(0, 500)
    ax_full.set_ylim(-0.03, VDD + 0.03)
    ax_full.grid(True, alpha=0.3)
    ax_full.legend(fontsize=6.8, ncol=1, loc="lower right")

    center_mv = metrics["read_snm_noise_v"] * 1e3 if math.isfinite(metrics["read_snm_noise_v"]) else 110.0
    ax_zoom.set_title("Critical region")
    ax_zoom.set_xlabel("Injected read noise VN / mV")
    ax_zoom.set_xlim(max(0, center_mv - 18), center_mv + 18)
    ax_zoom.set_ylim(0.10, 0.72)
    ax_zoom.grid(True, alpha=0.3)
    ax_zoom.legend(fontsize=6.8, ncol=1, loc="best")

    fig.suptitle(f"{config} read-SNM noise-source sweep", y=0.98)
    fig.tight_layout(rect=[0.0, 0.0, 1.0, 0.93])
    savefig_pair(FIGS / f"{prefix}_rsnm_noise.svg")
    plt.close(fig)

    # Read transient
    lis = RESULTS / f"{prefix}_read_q1" / f"{prefix}_read_q1.lis"
    blocks = parse_print_blocks(lis)
    h1, a1 = find_block(blocks, "q", "qb", "bl", "blb")
    h2, a2 = find_block(blocks, "wl")
    c1 = {n.lower(): i for i, n in enumerate(h1)}
    c2 = {n.lower(): i for i, n in enumerate(h2)}
    read = np.column_stack([a1[:, c1["time"]], a1[:, c1["q"]], a1[:, c1["qb"]], a1[:, c1["bl"]], a1[:, c1["blb"]]])
    # Interpolate WL/current block onto first time grid.
    wl = np.interp(read[:, 0], a2[:, c2["time"]], a2[:, c2["wl"]])
    current_name = next((n for n in h2 if "vdd_src" in n.lower()), None)
    ivdd = np.interp(read[:, 0], a2[:, c2["time"]], a2[:, c2[current_name.lower()]]) if current_name else np.zeros_like(wl)
    read = np.column_stack([read, wl, ivdd])
    save_csv(DATA / f"{prefix}_read_q1.csv", ["time_s", "q_v", "qb_v", "bl_v", "blb_v", "wl_v", "ivdd_a"], read)
    t = read[:, 0]
    q, qb, bl, blb, wl, ivdd = read[:, 1], read[:, 2], read[:, 3], read[:, 4], read[:, 5], read[:, 6]
    metrics["read_disturb_v"] = float(qb[(t >= 0.2e-9) & (t <= 1.2e-9)].max())
    metrics["read_high_loss_v"] = VDD - float(q[(t >= 0.2e-9) & (t <= 1.2e-9)].min())
    diff = bl - blb
    trig_idx = np.argmax(wl >= 0.5 * VDD)
    sense_idx = np.where((np.arange(len(t)) > trig_idx) & (diff >= 0.05))[0]
    metrics["read_delay_s_50mv"] = float(t[sense_idx[0]] - t[trig_idx]) if len(sense_idx) else float("nan")
    mask = (t >= 0.2e-9) & (t <= 1.2e-9)
    energy = np.cumsum(np.r_[0, 0.5 * (np.abs(ivdd[1:]) + np.abs(ivdd[:-1])) * np.diff(t)]) * VDD
    metrics["read_energy_j"] = float(energy[mask][-1] - energy[mask][0]) if mask.any() else float("nan")
    plt.figure(figsize=(6.2, 4.2))
    plt.plot(t * 1e9, q, label="Q")
    plt.plot(t * 1e9, qb, label="QB (stored-low disturb)")
    plt.plot(t * 1e9, bl, label="BL")
    plt.plot(t * 1e9, blb, label="BLB")
    plt.plot(t * 1e9, wl, "--", label="WL")
    plt.xlabel("Time / ns")
    plt.ylabel("Voltage / V")
    plt.title(f"{config} read transient")
    plt.grid(True, alpha=0.3)
    plt.legend(fontsize=8)
    plt.tight_layout()
    savefig_pair(FIGS / f"{prefix}_read_waveform.svg")
    plt.close()
    plt.figure(figsize=(6.2, 4.0))
    plt.plot(t * 1e9, diff, label="BL - BLB")
    plt.axhline(0.05, ls="--", color="0.5", label="50 mV sense threshold")
    plt.xlabel("Time / ns")
    plt.ylabel("Differential voltage / V")
    plt.title(f"{config} read bit-line differential")
    plt.grid(True, alpha=0.3)
    plt.legend(fontsize=8)
    plt.tight_layout()
    savefig_pair(FIGS / f"{prefix}_read_bldiff.svg")
    plt.close()

    # Write transient
    lis = RESULTS / f"{prefix}_write0" / f"{prefix}_write0.lis"
    blocks = parse_print_blocks(lis)
    h1, a1 = find_block(blocks, "q", "qb", "bl", "blb")
    h2, a2 = find_block(blocks, "wl")
    c1 = {n.lower(): i for i, n in enumerate(h1)}
    c2 = {n.lower(): i for i, n in enumerate(h2)}
    t = a1[:, c1["time"]]
    q, qb, bl, blb = a1[:, c1["q"]], a1[:, c1["qb"]], a1[:, c1["bl"]], a1[:, c1["blb"]]
    wl = np.interp(t, a2[:, c2["time"]], a2[:, c2["wl"]])
    current_name = next((n for n in h2 if "vdd_src" in n.lower()), None)
    ivdd = np.interp(t, a2[:, c2["time"]], a2[:, c2[current_name.lower()]]) if current_name else np.zeros_like(wl)
    write = np.column_stack([t, q, qb, bl, blb, wl, ivdd])
    save_csv(DATA / f"{prefix}_write0.csv", ["time_s", "q_v", "qb_v", "bl_v", "blb_v", "wl_v", "ivdd_a"], write)
    trig_idx = np.argmax(wl >= 0.5 * VDD)
    cross_idx = np.where((np.arange(len(t)) > trig_idx) & (q <= 0.5 * VDD))[0]
    metrics["write_delay_s_q50"] = float(t[cross_idx[0]] - t[trig_idx]) if len(cross_idx) else float("nan")
    metrics["write_final_q_v"] = float(q[-1])
    metrics["write_final_qb_v"] = float(qb[-1])
    energy = np.cumsum(np.r_[0, 0.5 * (np.abs(ivdd[1:]) + np.abs(ivdd[:-1])) * np.diff(t)]) * VDD
    mask = (t >= 0.2e-9) & (t <= 1.2e-9)
    metrics["write_energy_j"] = float(energy[mask][-1] - energy[mask][0]) if mask.any() else float("nan")
    plt.figure(figsize=(6.2, 4.2))
    plt.plot(t * 1e9, q, label="Q target low")
    plt.plot(t * 1e9, qb, label="QB target high")
    plt.plot(t * 1e9, bl, label="BL=0 write")
    plt.plot(t * 1e9, blb, label="BLB=VDD write")
    plt.plot(t * 1e9, wl, "--", label="WL")
    plt.xlabel("Time / ns")
    plt.ylabel("Voltage / V")
    plt.title(f"{config} write-0 transient")
    plt.grid(True, alpha=0.3)
    plt.legend(fontsize=8)
    plt.tight_layout()
    savefig_pair(FIGS / f"{prefix}_write_waveform.svg")
    plt.close()

    # Write-trip DC curve, reported as a write-margin proxy.
    lis = RESULTS / f"{prefix}_write_trip" / f"{prefix}_write_trip.lis"
    blocks = parse_print_blocks(lis)
    h, a = find_block(blocks, "bl", "q", "qb")
    c = {n.lower(): i for i, n in enumerate(h)}
    trip = np.column_stack([a[:, c[h[0].lower()]], a[:, c["bl"]], a[:, c["q"]], a[:, c["qb"]]])
    save_csv(DATA / f"{prefix}_write_trip.csv", ["sweep_v", "bl_v", "q_v", "qb_v"], trip)
    blv, qv, qbv = trip[:, 1], trip[:, 2], trip[:, 3]
    idx = np.where(qv <= qbv)[0]
    if len(idx):
        trip_bl = float(blv[idx[0]])
        metrics["write_trip_bl_v"] = trip_bl
        metrics["write_required_bl_drop_v"] = VDD - trip_bl
    else:
        metrics["write_trip_bl_v"] = float("nan")
        metrics["write_required_bl_drop_v"] = float("nan")
    plt.figure(figsize=(5.8, 4.2))
    plt.plot(blv, qv, label="Q")
    plt.plot(blv, qbv, label="QB")
    plt.gca().invert_xaxis()
    plt.xlabel("Forced BL voltage during write-0 DC sweep / V")
    plt.ylabel("Storage-node voltage / V")
    plt.title(f"{config} write-trip DC curve")
    plt.grid(True, alpha=0.3)
    plt.legend(fontsize=8)
    plt.tight_layout()
    savefig_pair(FIGS / f"{prefix}_write_trip.svg")
    plt.close()

    # Hold leakage current
    lis = RESULTS / f"{prefix}_hold_leakage" / f"{prefix}_hold_leakage.lis"
    meas = parse_measurements(lis)
    metrics["hold_leakage_w"] = VDD * abs(meas.get("i_hold", float("nan")))

    # Current and energy plot from read/write.
    plt.figure(figsize=(6.2, 4.2))
    for csv_name, label in [(f"{prefix}_read_q1.csv", "read"), (f"{prefix}_write0.csv", "write")]:
        data = np.genfromtxt(DATA / csv_name, delimiter=",", names=True)
        t = data["time_s"]
        iv = np.abs(data["ivdd_a"])
        en = np.cumsum(np.r_[0, 0.5 * (iv[1:] + iv[:-1]) * np.diff(t)]) * VDD
        plt.plot(t * 1e9, en * 1e15, label=f"{label} cumulative energy")
    plt.xlabel("Time / ns")
    plt.ylabel("Energy / fJ")
    plt.title(f"{config} energy integration from I(VDD)")
    plt.grid(True, alpha=0.3)
    plt.legend(fontsize=8)
    plt.tight_layout()
    savefig_pair(FIGS / f"{prefix}_energy.svg")
    plt.close()

    return CaseResult(config, "pass", metrics)


def write_summary(results: list[CaseResult], original_rc_log: str) -> None:
    def fmt(value: float, digits: int = 2) -> str:
        return "invalid" if not math.isfinite(value) else f"{value:.{digits}f}"

    rows = []
    for r in results:
        m = r.metrics
        rows.append({
            "configuration": r.config,
            "hold_snm_mv": m.get("hold_snm_v", float("nan")) * 1e3,
            "read_snm_mv": m.get("read_snm_noise_v", float("nan")) * 1e3,
            "read_disturb_mv": m.get("read_disturb_v", float("nan")) * 1e3,
            "read_stability_margin_mv": (0.35 - m.get("read_disturb_v", float("nan"))) * 1e3,
            "read_delay_ps_50mv": m.get("read_delay_s_50mv", float("nan")) * 1e12,
            "write_delay_ps_q50": m.get("write_delay_s_q50", float("nan")) * 1e12,
            "write_required_bl_drop_mv": m.get("write_required_bl_drop_v", float("nan")) * 1e3,
            "read_energy_fj": m.get("read_energy_j", float("nan")) * 1e15,
            "write_energy_fj": m.get("write_energy_j", float("nan")) * 1e15,
            "hold_leakage_pw": m.get("hold_leakage_w", float("nan")) * 1e12,
        })
    with (DATA / "summary_metrics.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# SRAM full HSPICE metric extraction",
        "",
        "This report is generated from the new `Hspice/sram_full_metrics` flow. All curves are from HSPICE `.PRINT` output in `.lis` files. The original extracted-RC netlist is checked first and remains blocked if HSPICE reports empty matrix rows/columns.",
        "",
        "## Metric summary",
        "",
        "| configuration | HSNM (mV) | RSNM noise-source (mV) | read disturb (mV) | read stability margin (mV) | read delay to 50 mV BL diff (ps) | write delay to Q=0.5VDD (ps) | write-trip BL drop (mV) | read energy (fJ) | write energy (fJ) | hold leakage (pW) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['configuration']} | {fmt(row['hold_snm_mv'])} | {fmt(row['read_snm_mv'])} | "
            f"{fmt(row['read_disturb_mv'])} | {fmt(row['read_stability_margin_mv'])} | {fmt(row['read_delay_ps_50mv'])} | "
            f"{fmt(row['write_delay_ps_q50'])} | {fmt(row['write_required_bl_drop_mv'])} | {fmt(row['read_energy_fj'], 3)} | "
            f"{fmt(row['write_energy_fj'], 3)} | {fmt(row['hold_leakage_pw'], 3)} |"
        )
    lines += [
        "",
        "## Original extracted-RC status",
        "",
        "The unmodified extracted-RC netlist is not used for metric extraction because the connectivity check reports:",
        "",
        "```text",
        original_rc_log.strip() or "No empty-row message captured.",
        "```",
        "",
        "Therefore the `RC candidate` curves below are diagnostic only. They use `sram6t_rc_gate_direct.inc`, where PMOS gates are directly tied according to the 6T topology. This does not replace a correct distributed RC extraction.",
        "",
        "## No-RC curves",
        "",
        "![[sram_full_metrics/figures/ideal_hold_butterfly.png]]",
        "",
        "![[sram_full_metrics/figures/ideal_read_butterfly.png]]",
        "",
        "![[sram_full_metrics/figures/ideal_rsnm_noise.png]]",
        "",
        "![[sram_full_metrics/figures/ideal_read_waveform.png]]",
        "",
        "![[sram_full_metrics/figures/ideal_read_bldiff.png]]",
        "",
        "![[sram_full_metrics/figures/ideal_write_waveform.png]]",
        "",
        "![[sram_full_metrics/figures/ideal_write_trip.png]]",
        "",
        "![[sram_full_metrics/figures/ideal_energy.png]]",
        "",
        "## RC diagnostic candidate curves",
        "",
        "![[sram_full_metrics/figures/rc_candidate_hold_butterfly.png]]",
        "",
        "![[sram_full_metrics/figures/rc_candidate_read_butterfly.png]]",
        "",
        "![[sram_full_metrics/figures/rc_candidate_rsnm_noise.png]]",
        "",
        "![[sram_full_metrics/figures/rc_candidate_read_waveform.png]]",
        "",
        "![[sram_full_metrics/figures/rc_candidate_read_bldiff.png]]",
        "",
        "![[sram_full_metrics/figures/rc_candidate_write_waveform.png]]",
        "",
        "![[sram_full_metrics/figures/rc_candidate_write_trip.png]]",
        "",
        "![[sram_full_metrics/figures/rc_candidate_energy.png]]",
        "",
        "## Extraction definitions",
        "",
        "- HSNM: extracted from HSPICE hold butterfly curves by geometrically searching the largest axis-aligned square fully contained in each lobe; the reported value is the smaller lobe square side.",
        "- RSNM: extracted with a dedicated read-mode noise-source sweep. WL=VDD and BL=BLB=VDD; opposite feedback-gate noise is swept until the stored state flips. The reported value is the smaller critical noise of Q=1 and Q=0 initial states.",
        "- Read stability margin remains an auxiliary dynamic proxy: `VDD/2 - max(V(QB))` during the read transient.",
        "- Read disturb: maximum voltage of the stored-low node `QB` during the read window.",
        "- Read delay: time from `WL=0.5*VDD` to `BL-BLB=50 mV`.",
        "- Write delay: time from `WL=0.5*VDD` to the target node `Q` crossing `0.5*VDD` during write-0.",
        "- Write-trip BL drop: DC write-0 sweep with `WL=VDD`, `BLB=VDD`, and `BL` swept from `VDD` to 0. It is a write-margin proxy, not a strict WSNM butterfly extraction.",
        "- Dynamic energy: numerical integral of `VDD*abs(I(VDD_SRC))` over the operation window.",
        "- Hold leakage: `VDD*abs(avg(I(VDD_SRC)))` over the settled hold window.",
    ]
    (BASE.parent / "sram_comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ensure_dirs()
    decks = [
        deck_snm("ideal", "sram6t_ideal.inc", "SRAM6T", "hold"),
        deck_snm("ideal", "sram6t_ideal.inc", "SRAM6T", "read"),
        deck_rsnm_noise("ideal", "sram6t_ideal.inc", "q1"),
        deck_rsnm_noise("ideal", "sram6t_ideal.inc", "q0"),
        deck_read("ideal", "sram6t_ideal.inc", "SRAM6T"),
        deck_write("ideal", "sram6t_ideal.inc", "SRAM6T"),
        deck_write_trip("ideal", "sram6t_ideal.inc", "SRAM6T"),
        deck_hold_current("ideal", "sram6t_ideal.inc", "SRAM6T"),
        deck_original_rc_check(),
        deck_snm("rc_candidate", "sram6t_rc_gate_direct.inc", "SRAM6T_RC_GATE_DIRECT", "hold"),
        deck_snm("rc_candidate", "sram6t_rc_gate_direct.inc", "SRAM6T_RC_GATE_DIRECT", "read"),
        deck_rsnm_noise("rc_candidate", "sram6t_rc_gate_direct.inc", "q1"),
        deck_rsnm_noise("rc_candidate", "sram6t_rc_gate_direct.inc", "q0"),
        deck_read("rc_candidate", "sram6t_rc_gate_direct.inc", "SRAM6T_RC_GATE_DIRECT"),
        deck_write("rc_candidate", "sram6t_rc_gate_direct.inc", "SRAM6T_RC_GATE_DIRECT"),
        deck_write_trip("rc_candidate", "sram6t_rc_gate_direct.inc", "SRAM6T_RC_GATE_DIRECT"),
        deck_hold_current("rc_candidate", "sram6t_rc_gate_direct.inc", "SRAM6T_RC_GATE_DIRECT"),
    ]
    for deck in decks:
        lis = RESULTS / deck.stem / f"{deck.stem}.lis"
        if lis.exists() and lis.stat().st_mtime >= deck.stat().st_mtime:
            print(f"reuse {deck.name}")
        else:
            print(f"running {deck.name}")
            run_hspice(deck)

    rc_lis = RESULTS / "original_rc_connectivity_check" / "original_rc_connectivity_check.lis"
    rc_log_lines = []
    if rc_lis.exists():
        for line in rc_lis.read_text(errors="ignore").splitlines():
            if "Empty row/column" in line:
                rc_log_lines.append(line.strip())
    results = [
        analyze_config("No-RC", "ideal"),
        analyze_config("RC candidate (diagnostic)", "rc_candidate"),
    ]
    write_summary(results, "\n".join(rc_log_lines))


if __name__ == "__main__":
    main()
