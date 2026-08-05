from __future__ import annotations

import csv
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from matplotlib.patches import FancyArrowPatch, Polygon, Rectangle


BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
FIGS = BASE / "figures"
VDD = 0.7

for font_path in (Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/simhei.ttf"), Path("C:/Windows/Fonts/simsun.ttc")):
    if font_path.exists():
        font_manager.fontManager.addfont(str(font_path))
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=str(font_path)).get_name()
        break
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["svg.fonttype"] = "none"


def read_csv(path: Path) -> dict[str, np.ndarray]:
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cols = {name: [] for name in reader.fieldnames or []}
        for row in reader:
            for k in cols:
                cols[k].append(float(row[k]))
    return {k: np.asarray(v, dtype=float) for k, v in cols.items()}


def savefig_pair(stem: str) -> None:
    FIGS.mkdir(parents=True, exist_ok=True)
    plt.savefig(FIGS / f"{stem}.svg", bbox_inches="tight")
    plt.savefig(FIGS / f"{stem}.png", dpi=300, bbox_inches="tight")


def crossing_time(t: np.ndarray, y: np.ndarray, target: float, start_index: int = 0, rising: bool = True) -> float:
    for i in range(max(1, start_index), len(t)):
        y0, y1 = y[i - 1], y[i]
        ok = (y0 < target <= y1) if rising else (y0 > target >= y1)
        if ok and y1 != y0:
            return float(t[i - 1] + (target - y0) * (t[i] - t[i - 1]) / (y1 - y0))
    return float("nan")


def corrected_metric_annotation() -> None:
    read = read_csv(DATA / "ideal_read_q1.csv")
    write = read_csv(DATA / "ideal_write0.csv")
    trip = read_csv(DATA / "ideal_write_trip.csv")

    tr = read["time_s"] * 1e12
    tw = write["time_s"] * 1e12
    read_mask = (read["time_s"] >= 0.2e-9) & (read["time_s"] <= 1.2e-9)
    disturb = float(read["qb_v"][read_mask].max())
    disturb_idx = int(np.where(read_mask)[0][np.argmax(read["qb_v"][read_mask])])
    stability = 0.5 * VDD - disturb

    diff = read["bl_v"] - read["blb_v"]
    wl_cross_idx = int(np.argmax(read["wl_v"] >= 0.5 * VDD))
    sense_idx = np.where((np.arange(len(read["time_s"])) > wl_cross_idx) & (diff >= 0.05))[0]
    t_wl_read = float(read["time_s"][wl_cross_idx])
    t_diff = float(read["time_s"][sense_idx[0]]) if len(sense_idx) else float("nan")

    wl_cross_w_idx = int(np.argmax(write["wl_v"] >= 0.5 * VDD))
    cross_w_idx = np.where((np.arange(len(write["time_s"])) > wl_cross_w_idx) & (write["q_v"] <= 0.5 * VDD))[0]
    t_wl_write = float(write["time_s"][wl_cross_w_idx])
    t_q50 = float(write["time_s"][cross_w_idx[0]]) if len(cross_w_idx) else float("nan")

    x_trip = trip["bl_v"]
    ydiff = trip["q_v"] - trip["qb_v"]
    idx_trip = np.where(trip["q_v"] <= trip["qb_v"])[0]
    trip_v = float(x_trip[idx_trip[0]]) if len(idx_trip) else float("nan")
    trip_drop = VDD - trip_v

    fig, axs = plt.subplots(2, 2, figsize=(11.2, 7.6))

    ax = axs[0, 0]
    ax.plot(tr, read["qb_v"] * 1e3, label="V(QB), stored-low node")
    ax.axhline(0.5 * VDD * 1e3, color="0.35", ls="--", lw=1.0, label="VDD/2")
    ax.plot(tr[disturb_idx], disturb * 1e3, "o", ms=5)
    ax.annotate(f"read disturb = {disturb*1e3:.1f} mV",
                xy=(tr[disturb_idx], disturb * 1e3),
                xytext=(tr[disturb_idx] + 80, disturb * 1e3 + 55),
                arrowprops=dict(arrowstyle="->", lw=1.0))
    ax.annotate(f"stability proxy = {stability*1e3:.1f} mV",
                xy=(tr[disturb_idx], 0.5 * VDD * 1e3),
                xytext=(tr[disturb_idx] + 140, 0.5 * VDD * 1e3 - 95),
                arrowprops=dict(arrowstyle="<->", lw=1.0))
    ax.set_title("(a) Read disturb and read stability proxy")
    ax.set_xlabel("time (ps)")
    ax.set_ylabel("voltage (mV)")
    ax.set_xlim(0, 1250)
    ax.grid(True, alpha=0.28)
    ax.legend(fontsize=8, loc="upper left")

    ax = axs[0, 1]
    ax.plot(tr, diff * 1e3, label="BL - BLB")
    ax.axhline(50, color="0.35", ls="--", lw=1.0, label="50 mV sense target")
    ax.axvline(t_wl_read * 1e12, color="0.5", ls=":", lw=1.0, label="WL=0.5VDD")
    ax.axvline(t_diff * 1e12, color="0.2", ls="--", lw=1.0, label="BL diff=50 mV")
    ax.annotate(f"read delay = {(t_diff-t_wl_read)*1e12:.1f} ps",
                xy=(0.5 * (t_wl_read + t_diff) * 1e12, 50),
                xytext=(t_wl_read * 1e12 + 70, 115),
                arrowprops=dict(arrowstyle="<->", lw=1.0))
    ax.set_title("(b) Read delay extraction")
    ax.set_xlabel("time (ps)")
    ax.set_ylabel("BL-BLB (mV)")
    ax.set_xlim(120, 270)
    ax.grid(True, alpha=0.28)
    ax.legend(fontsize=8, loc="upper left")

    ax = axs[1, 0]
    ax.plot(tw, write["q_v"], label="V(Q)")
    ax.plot(tw, write["qb_v"], label="V(QB)")
    ax.axhline(0.5 * VDD, color="0.35", ls="--", lw=1.0, label="0.5VDD")
    ax.axvline(t_wl_write * 1e12, color="0.5", ls=":", lw=1.0, label="WL=0.5VDD")
    ax.axvline(t_q50 * 1e12, color="0.2", ls="--", lw=1.0, label="Q=0.5VDD")
    ax.annotate(f"write delay = {(t_q50-t_wl_write)*1e12:.1f} ps",
                xy=(0.5 * (t_wl_write + t_q50) * 1e12, 0.35),
                xytext=(t_wl_write * 1e12 + 95, 0.50),
                arrowprops=dict(arrowstyle="<->", lw=1.0))
    ax.set_title("(c) Write delay extraction")
    ax.set_xlabel("time (ps)")
    ax.set_ylabel("voltage (V)")
    ax.set_xlim(120, 320)
    ax.set_ylim(-0.03, 0.73)
    ax.grid(True, alpha=0.28)
    ax.legend(fontsize=8, loc="center right")

    ax = axs[1, 1]
    ax.plot(x_trip, trip["q_v"], label="V(Q)")
    ax.plot(x_trip, trip["qb_v"], label="V(QB)")
    if math.isfinite(trip_v):
        ax.axvline(trip_v, color="0.2", ls="--", lw=1.0)
        ax.annotate(f"BL trip = {trip_v:.3f} V\nBL drop = {trip_drop*1e3:.1f} mV",
                    xy=(trip_v, 0.35),
                    xytext=(trip_v + 0.08, 0.48),
                    arrowprops=dict(arrowstyle="->", lw=1.0))
    ax.set_title("(d) Write-trip BL-drop extraction")
    ax.set_xlabel("swept BL voltage (V)")
    ax.set_ylabel("internal node voltage (V)")
    ax.set_xlim(0.7, 0.0)
    ax.set_ylim(-0.03, 0.73)
    ax.grid(True, alpha=0.28)
    ax.legend(fontsize=8, loc="center right")

    fig.suptitle("Corrected metric extraction annotations from No-RC HSPICE curves", y=1.01)
    fig.tight_layout()
    savefig_pair("metric_extraction_annotation")
    plt.close(fig)


def geometric_lobe_masks(x: np.ndarray, y: np.ndarray, n: int = 1401):
    """Return dense masks for the two butterfly lobes.

    The mask is built from the HSPICE VTC y=f(x) and its mirrored curve.
    A point is inside a lobe when it is between the two curves; the diagonal
    y=x separates the upper-left and lower-right lobes.
    """
    grid = np.linspace(0.0, VDD, n)
    f = np.interp(grid, x, y)
    # Mirrored curve: y_mirror(x) = f^{-1}(x).  The VTC is monotonically
    # decreasing, so reverse both arrays before interpolation.
    g = np.interp(grid, y[::-1], x[::-1])
    lower = np.minimum(f, g)
    upper = np.maximum(f, g)
    xx, yy = np.meshgrid(grid, grid)
    between = (yy >= lower[None, :]) & (yy <= upper[None, :])
    upper_left = between & (yy >= xx)
    lower_right = between & (yy <= xx)
    return grid, upper_left, lower_right


def max_axis_aligned_square(mask: np.ndarray, grid: np.ndarray, target: tuple[float, float]):
    """Find the largest axis-aligned square fully contained in a lobe mask."""
    n = len(grid)
    dx = grid[1] - grid[0]
    integral = np.pad(mask.astype(np.int32).cumsum(axis=0).cumsum(axis=1), ((1, 0), (1, 0)))

    def valid_positions(window_points: int) -> np.ndarray:
        sums = (
            integral[window_points:, window_points:]
            - integral[:-window_points, window_points:]
            - integral[window_points:, :-window_points]
            + integral[:-window_points, :-window_points]
        )
        return sums == window_points * window_points

    lo, hi = 1, n
    best = None
    while lo <= hi:
        mid = (lo + hi) // 2
        ok = valid_positions(mid)
        if ok.any():
            best = (mid, ok)
            lo = mid + 1
        else:
            hi = mid - 1
    if best is None:
        return None

    window_points, ok = best
    ys, xs = np.where(ok)
    side = (window_points - 1) * dx
    centers_x = grid[xs] + 0.5 * side
    centers_y = grid[ys] + 0.5 * side
    tx, ty = target
    chosen = int(np.argmin((centers_x - tx) ** 2 + (centers_y - ty) ** 2))
    x0 = float(grid[xs[chosen]])
    y0 = float(grid[ys[chosen]])
    return x0, y0, float(side)


def snm_square_comparison() -> None:
    fig, axs = plt.subplots(1, 2, figsize=(11.2, 5.2), sharex=True, sharey=True)
    for ax, prefix, title in [
        (axs[0], "ideal", "No-RC hold butterfly"),
        (axs[1], "rc_candidate", "RC candidate hold butterfly"),
    ]:
        d = read_csv(DATA / f"{prefix}_hold_butterfly.csv")
        x, y = d["q_v"], d["qb_v"]
        ax.plot(x, y, lw=1.6, label="HSPICE V(QB) vs forced V(Q)")
        ax.plot(y, x, lw=1.6, label="mirrored curve")
        ax.plot([0, VDD], [0, VDD], "--", color="0.65", lw=1.0, label="V(Q)=V(QB)")
        grid, upper_left, lower_right = geometric_lobe_masks(x, y)
        squares = [
            ("upper-left", max_axis_aligned_square(upper_left, grid, (0.25 * VDD, 0.75 * VDD))),
            ("lower-right", max_axis_aligned_square(lower_right, grid, (0.75 * VDD, 0.25 * VDD))),
        ]
        valid_sides = [sq[1][2] for sq in squares if sq[1] is not None]
        geom_snm = min(valid_sides) if valid_sides else float("nan")
        for _name, sq in squares:
            if sq is None:
                continue
            x0, y0, side = sq
            ax.add_patch(Rectangle((x0, y0), side, side, fill=False, lw=2.2, edgecolor="black"))
            ax.text(x0 + 0.5 * side, y0 + 0.5 * side, f"{side*1e3:.1f} mV",
                    ha="center", va="center", fontsize=8,
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="0.7", alpha=0.9))
        if math.isfinite(geom_snm):
            ax.text(0.97, 0.95, f"geometric SNM = {geom_snm*1e3:.1f} mV",
                    transform=ax.transAxes, ha="right", va="top", fontsize=8,
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="0.7", alpha=0.9))
        ax.set_title(title)
        ax.set_xlabel("V(Q) (V)")
        ax.set_xlim(0, VDD)
        ax.set_ylim(0, VDD)
        ax.set_aspect("equal", adjustable="box")
        ax.grid(True, alpha=0.28)
    axs[0].set_ylabel("V(QB) (V)")
    axs[0].legend(fontsize=7, loc="lower left")
    fig.suptitle("Geometrically searched maximum inscribed squares on hold butterfly curves", y=1.02)
    fig.tight_layout()
    savefig_pair("hold_snm_max_square_comparison")
    plt.close(fig)


def draw_node(ax, xy, text, fc="#f7f7f7", w=0.78, h=0.32, fontsize=8):
    x, y = xy
    ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, facecolor=fc, edgecolor="0.25", lw=1.0))
    ax.text(x, y, text, ha="center", va="center", fontsize=fontsize)


def draw_line(ax, a, b, text="", ls="-", color="0.15", lw=1.4, fontsize=7):
    ax.plot([a[0], b[0]], [a[1], b[1]], ls=ls, color=color, lw=lw)
    if text:
        ax.text(0.5 * (a[0] + b[0]), 0.5 * (a[1] + b[1]), text,
                ha="center", va="center", fontsize=fontsize,
                bbox=dict(boxstyle="round,pad=0.13", fc="white", ec="none", alpha=0.9))


def circuit_norc() -> None:
    fig, ax = plt.subplots(figsize=(10.5, 6.2))
    ax.axis("off")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.set_title("No-RC 6T SRAM schematic with plain-potential labels")

    draw_node(ax, (5, 5.55), "VDD\n电源高电位", "#eef7ee", w=1.25, h=0.42)
    draw_node(ax, (5, 0.45), "VSS/GND\n地电位", "#f7eeee", w=1.25, h=0.42)
    draw_node(ax, (4.0, 3.0), "Q\n存储节点", "#eef3ff")
    draw_node(ax, (6.0, 3.0), "QB\n互补存储节点", "#eef3ff")
    draw_node(ax, (1.1, 3.0), "BL\n位线", "#fff6df")
    draw_node(ax, (8.9, 3.0), "BLB\n反位线", "#fff6df")
    draw_node(ax, (5.0, 1.25), "WL\n字线", "#f1ecff", w=1.0)

    blocks = {
        "PG1\naccess NMOS\ngate=WL": (2.55, 3.0),
        "PG2\naccess NMOS\ngate=WL": (7.45, 3.0),
        "PU1\nPMOS\ngate=QB": (4.0, 4.45),
        "PU2\nPMOS\ngate=Q": (6.0, 4.45),
        "PD1\nNMOS\ngate=QB": (4.0, 1.65),
        "PD2\nNMOS\ngate=Q": (6.0, 1.65),
    }
    for label, xy in blocks.items():
        draw_node(ax, xy, label, "#ffffff", w=1.22, h=0.62, fontsize=7)

    draw_line(ax, (1.5, 3.0), (1.95, 3.0))
    draw_line(ax, (3.15, 3.0), (3.6, 3.0))
    draw_line(ax, (6.4, 3.0), (6.85, 3.0))
    draw_line(ax, (8.05, 3.0), (8.5, 3.0))
    draw_line(ax, (4.0, 5.32), (4.0, 4.78))
    draw_line(ax, (6.0, 5.32), (6.0, 4.78))
    draw_line(ax, (4.0, 4.12), (4.0, 3.25))
    draw_line(ax, (6.0, 4.12), (6.0, 3.25))
    draw_line(ax, (4.0, 2.75), (4.0, 1.98))
    draw_line(ax, (6.0, 2.75), (6.0, 1.98))
    draw_line(ax, (4.0, 1.32), (4.0, 0.68))
    draw_line(ax, (6.0, 1.32), (6.0, 0.68))
    draw_line(ax, (3.3, 1.25), (7.05, 1.25), "WL drives PG1/PG2 gates")
    draw_line(ax, (4.35, 3.35), (5.65, 4.1), "QB controls PU1/PD1", ls="--")
    draw_line(ax, (5.65, 2.65), (4.35, 1.95), "", ls="--")
    draw_line(ax, (5.65, 3.35), (4.35, 4.1), "Q controls PU2/PD2", ls="--")
    draw_line(ax, (4.35, 2.65), (5.65, 1.95), "", ls="--")

    ax.text(5, 5.05, "Two cross-coupled inverters form the latch; PG1/PG2 connect Q/QB to BL/BLB when WL is high.",
            ha="center", fontsize=8)
    savefig_pair("sram6t_norc_schematic")
    plt.close(fig)


def circuit_rc() -> None:
    fig, ax = plt.subplots(figsize=(13.0, 8.2))
    ax.axis("off")
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 8)
    ax.set_title("RC candidate 6T SRAM netlist diagram with plain-potential labels")

    draw_node(ax, (1.0, 6.9), "BL\n位线端口", "#fff6df", w=0.9)
    draw_node(ax, (1.0, 5.95), "BLB\n反位线端口", "#fff6df", w=0.9)
    draw_node(ax, (1.0, 5.0), "WL\n字线端口", "#f1ecff", w=0.9)
    draw_node(ax, (1.0, 4.05), "Q\n存储节点端口", "#eef3ff", w=0.9)
    draw_node(ax, (1.0, 3.1), "QB\n互补节点端口", "#eef3ff", w=0.9)
    draw_node(ax, (1.0, 2.15), "VDD\n电源端口", "#eef7ee", w=0.9)
    draw_node(ax, (1.0, 1.2), "VSS\n地端口", "#f7eeee", w=0.9)

    port_nodes = {
        "BL_PORT": (2.2, 6.9),
        "BLB_PORT": (2.2, 5.95),
        "WL_PORT": (2.2, 5.0),
        "Q_NODE": (2.2, 4.05),
        "QB_NODE": (2.2, 3.1),
        "VDD_PORT": (2.2, 2.15),
        "VSS_PORT": (2.2, 1.2),
    }
    for n, xy in port_nodes.items():
        draw_node(ax, xy, n, "#ffffff", w=0.95, h=0.28, fontsize=7)
    for y, txt in [(6.9, "1mΩ"), (5.95, "1mΩ"), (5.0, "1mΩ"), (4.05, "1mΩ"),
                   (3.1, "1mΩ"), (2.15, "1mΩ"), (1.2, "1mΩ")]:
        draw_line(ax, (1.45, y), (1.72, y), txt)

    devices = {
        "PG1\naccess NMOS": (5.0, 6.3),
        "PG2\naccess NMOS": (8.0, 6.3),
        "PU1\nPMOS": (5.0, 4.75),
        "PU2\nPMOS": (8.0, 4.75),
        "PD1\nNMOS": (5.0, 2.85),
        "PD2\nNMOS": (8.0, 2.85),
    }
    for label, xy in devices.items():
        draw_node(ax, xy, label, "#ffffff", w=1.18, h=0.52, fontsize=7)

    # Series resistance paths.
    draw_line(ax, port_nodes["BL_PORT"], (4.42, 6.3), "R_BL 21.96Ω")
    draw_line(ax, port_nodes["BLB_PORT"], (7.42, 6.3), "R_BLB 25.68Ω")
    draw_line(ax, port_nodes["WL_PORT"], (5.0, 6.02), "R_WL1 7.03Ω")
    draw_line(ax, port_nodes["WL_PORT"], (8.0, 6.02), "R_WL2 7.03Ω")
    draw_line(ax, port_nodes["Q_NODE"], (5.0, 3.14), "R_Q_PD 52.48Ω")
    draw_line(ax, port_nodes["Q_NODE"], (5.0, 4.46), "R_Q_PU 134.31Ω")
    draw_line(ax, port_nodes["QB_NODE"], (8.0, 3.14), "R_QB_PD 52.48Ω")
    draw_line(ax, port_nodes["QB_NODE"], (8.0, 4.46), "R_QB_PU 134.31Ω\n悬挂支路", ls="--", color="#b23b3b")
    draw_line(ax, port_nodes["VDD_PORT"], (5.0, 5.04), "R_VDD_PU1 38.51Ω")
    draw_line(ax, port_nodes["VDD_PORT"], (8.0, 5.04), "R_VDD_PU2 38.51Ω")
    draw_line(ax, port_nodes["VSS_PORT"], (5.0, 2.56), "R_VSS_PD1 40.57Ω")
    draw_line(ax, port_nodes["VSS_PORT"], (8.0, 2.56), "R_VSS_PD2 40.57Ω")

    draw_line(ax, (5.0, 4.48), (5.0, 3.12), "Q-side pull-up/pull-down path", color="0.35")
    draw_line(ax, (8.0, 4.48), (8.0, 3.12), "QB-side path", color="0.35")
    draw_line(ax, (5.48, 4.75), (2.2, 3.1), "PU1/PD1 gate = QB", ls="--", color="0.35")
    draw_line(ax, (7.52, 4.75), (2.2, 4.05), "PU2/PD2 gate = Q", ls="--", color="0.35")

    ax.text(7.0, 7.35,
            "红色虚线：现有 candidate 网表中 R_QB_PU 接到 PU2_QB_SD，但 XPU2 漏端直接为 QB，"
            "因此该支路未真正串入 PU2 漏端路径。",
            ha="center", va="center", color="#9b2c2c", fontsize=8)

    cap_text = (
        "Complete parasitic capacitor list (aF):\n"
        "C_BL_BLB 0.028 | C_BL_WL 21.001 | C_BL_VDD 0.618 | C_BL_VSS 1.177 | C_BL_Q 1.484 | C_BL_QB 0.222\n"
        "C_BLB_WL 21.058 | C_BLB_VDD 0.607 | C_BLB_VSS 1.085 | C_BLB_Q 0.357 | C_BLB_QB 1.575\n"
        "C_WL_VDD 3.334 | C_WL_VSS 26.457 | C_WL_Q 40.638 | C_WL_QB 56.711\n"
        "C_VDD_VSS 0.0015 | C_VDD_Q 10.015 | C_VDD_QB 10.008 | C_VSS_Q 18.814 | C_VSS_QB 19.001 | C_Q_QB 93.747"
    )
    ax.text(6.85, 0.55, cap_text, ha="center", va="bottom", fontsize=7,
            bbox=dict(boxstyle="round,pad=0.35", fc="#f9f9f9", ec="0.55"))
    savefig_pair("sram6t_rc_candidate_network")
    plt.close(fig)


def main() -> None:
    corrected_metric_annotation()
    snm_square_comparison()
    circuit_norc()
    circuit_rc()


if __name__ == "__main__":
    main()
