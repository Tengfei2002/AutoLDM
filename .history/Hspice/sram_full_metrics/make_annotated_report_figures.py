from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager


BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
FIGS = BASE / "figures"
VDD = 0.7


for font_path in (
    Path("C:/Windows/Fonts/msyh.ttc"),
    Path("C:/Windows/Fonts/simhei.ttf"),
    Path("C:/Windows/Fonts/simsun.ttc"),
):
    if font_path.exists():
        font_manager.fontManager.addfont(str(font_path))
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=str(font_path)).get_name()
        break

plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["svg.fonttype"] = "none"


def read_csv(path: Path) -> dict[str, np.ndarray]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        columns = {name: [] for name in reader.fieldnames or []}
        for row in reader:
            for name in columns:
                columns[name].append(float(row[name]))
    return {name: np.asarray(values, dtype=float) for name, values in columns.items()}


def savefig(stem: str) -> None:
    FIGS.mkdir(parents=True, exist_ok=True)
    plt.savefig(FIGS / f"{stem}.svg", bbox_inches="tight")
    plt.savefig(FIGS / f"{stem}.png", dpi=300, bbox_inches="tight")


def crossing_time(t: np.ndarray, y: np.ndarray, target: float, start_index: int = 1, rising: bool = True) -> tuple[float, int]:
    for i in range(max(1, start_index), len(t)):
        y0, y1 = y[i - 1], y[i]
        crossed = (y0 < target <= y1) if rising else (y0 > target >= y1)
        if crossed:
            if y1 == y0:
                return float(t[i]), i
            frac = (target - y0) / (y1 - y0)
            return float(t[i - 1] + frac * (t[i] - t[i - 1])), i
    return float("nan"), -1


def cumulative_energy_j(time_s: np.ndarray, ivdd_a: np.ndarray) -> np.ndarray:
    iv = np.abs(ivdd_a)
    return np.cumsum(np.r_[0.0, 0.5 * (iv[1:] + iv[:-1]) * np.diff(time_s)]) * VDD


def energy_window(time_s: np.ndarray, ivdd_a: np.ndarray, start_s: float = 0.2e-9, stop_s: float = 1.2e-9) -> float:
    en = cumulative_energy_j(time_s, ivdd_a)
    mask = (time_s >= start_s) & (time_s <= stop_s)
    if not mask.any():
        return float("nan")
    idx = np.where(mask)[0]
    return float(en[idx[-1]] - en[idx[0]])


def plot_rsnm(prefix: str, title: str) -> None:
    q1 = read_csv(DATA / f"{prefix}_rsnm_noise_q1.csv")
    q0 = read_csv(DATA / f"{prefix}_rsnm_noise_q0.csv")

    def crit(d: dict[str, np.ndarray], state: str) -> float:
        if state == "q1":
            idx = np.where(d["q_v"] <= d["qb_v"])[0]
        else:
            idx = np.where(d["qb_v"] <= d["q_v"])[0]
        return float(d["noise_v"][idx[0]]) if len(idx) else float("nan")

    c1 = crit(q1, "q1")
    c0 = crit(q0, "q0")
    rsnm = np.nanmin([c1, c0])
    rsnm_mv = rsnm * 1e3

    fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(10.6, 4.1), gridspec_kw={"width_ratios": [1.0, 1.15]})
    for ax in (ax0, ax1):
        ax.plot(q1["noise_v"] * 1e3, q1["q_v"], color="#1f77b4", lw=1.9, label="Q=1 init: V(Q)")
        ax.plot(q1["noise_v"] * 1e3, q1["qb_v"], color="#1f77b4", lw=1.5, ls="--", label="Q=1 init: V(QB)")
        ax.plot(q0["noise_v"] * 1e3, q0["q_v"], color="#d62728", lw=1.9, label="Q=0 init: V(Q)")
        ax.plot(q0["noise_v"] * 1e3, q0["qb_v"], color="#d62728", lw=1.5, ls="--", label="Q=0 init: V(QB)")
        ax.axvline(rsnm_mv, color="0.15", lw=1.2, ls="-.")
        ax.grid(True, alpha=0.28)
        ax.set_xlabel("Injected read noise VN (mV)")
        ax.set_ylabel("Storage-node voltage (V)")

    ax0.set_title("Full sweep")
    ax0.set_xlim(0, 500)
    ax0.set_ylim(-0.03, VDD + 0.03)
    ax0.legend(fontsize=6.5, loc="lower right")

    ax1.set_title("Critical region: 100–110 mV")
    ax1.set_xlim(100, 110)
    ax1.set_ylim(0.08, 0.72)
    ax1.text(
        100.25,
        0.675,
        f"RSNM = {rsnm_mv:.1f} mV\nQ=1 crit: {c1*1e3:.1f} mV\nQ=0 crit: {c0*1e3:.1f} mV",
        fontsize=8.5,
        va="top",
        bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="0.65", alpha=0.95),
    )
    ax1.legend(fontsize=6.5, loc="lower left")

    fig.suptitle(title, y=0.99)
    fig.tight_layout(rect=[0.0, 0.0, 1.0, 0.93])
    savefig(f"{prefix}_rsnm_noise")
    plt.close(fig)


def plot_read_waveform(prefix: str, title: str) -> None:
    d = read_csv(DATA / f"{prefix}_read_q1.csv")
    t = d["time_s"]
    t_ns = t * 1e9
    q, qb, bl, blb, wl = d["q_v"], d["qb_v"], d["bl_v"], d["blb_v"], d["wl_v"]
    diff = bl - blb

    read_mask = (t >= 0.2e-9) & (t <= 1.2e-9)
    mask_idx = np.where(read_mask)[0]
    disturb_local = int(mask_idx[np.argmax(qb[read_mask])])
    disturb_v = float(qb[disturb_local])
    proxy_v = 0.5 * VDD - disturb_v
    t_wl, idx_wl = crossing_time(t, wl, 0.5 * VDD, rising=True)
    t_diff, _ = crossing_time(t, diff, 0.05, start_index=idx_wl, rising=True)
    delay_ps = (t_diff - t_wl) * 1e12

    fig, ax = plt.subplots(figsize=(7.0, 4.35))
    ax.plot(t_ns, q, label="Q", lw=1.9)
    ax.plot(t_ns, qb, label="QB (stored-low)", lw=1.9)
    ax.plot(t_ns, bl, label="BL", lw=1.5)
    ax.plot(t_ns, blb, label="BLB", lw=1.5)
    ax.plot(t_ns, wl, "--", label="WL", lw=1.4)
    ax.axvline(t_wl * 1e9, color="0.45", ls=":", lw=1.0)
    ax.axvline(t_diff * 1e9, color="0.45", ls=":", lw=1.0)
    ax.axhline(0.5 * VDD, color="0.35", ls="--", lw=0.9)
    ax.plot(t_ns[disturb_local], disturb_v, "o", color="#d62728", ms=5)
    ax.annotate(
        f"read disturb = {disturb_v*1e3:.1f} mV",
        xy=(t_ns[disturb_local], disturb_v),
        xytext=(t_ns[disturb_local] + 0.055, disturb_v + 0.045),
        arrowprops=dict(arrowstyle="->", lw=0.9, color="#d62728"),
        color="#d62728",
        fontsize=9,
        bbox=dict(boxstyle="round,pad=0.20", fc="white", ec="0.75", alpha=0.95),
    )
    ax.text(
        0.56,
        0.10,
        f"read delay = {delay_ps:.1f} ps\nmargin proxy = {proxy_v*1e3:.1f} mV",
        transform=ax.transAxes,
        fontsize=9,
        bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="0.7", alpha=0.95),
    )
    ax.set_title(title)
    ax.set_xlabel("Time (ns)")
    ax.set_ylabel("Voltage (V)")
    ax.set_xlim(0.0, 1.25)
    ax.set_ylim(-0.03, 0.74)
    ax.grid(True, alpha=0.28)
    ax.legend(fontsize=8, loc="center right")
    fig.tight_layout()
    savefig(f"{prefix}_read_waveform")
    plt.close(fig)


def plot_write_waveform(prefix: str, title: str) -> None:
    d = read_csv(DATA / f"{prefix}_write0.csv")
    t = d["time_s"]
    t_ns = t * 1e9
    q, qb, bl, blb, wl = d["q_v"], d["qb_v"], d["bl_v"], d["blb_v"], d["wl_v"]
    t_wl, idx_wl = crossing_time(t, wl, 0.5 * VDD, rising=True)
    t_q50, _ = crossing_time(t, q, 0.5 * VDD, start_index=idx_wl, rising=False)
    delay_ps = (t_q50 - t_wl) * 1e12

    fig, ax = plt.subplots(figsize=(7.0, 4.35))
    ax.plot(t_ns, q, label="Q target low", lw=1.9)
    ax.plot(t_ns, qb, label="QB target high", lw=1.9)
    ax.plot(t_ns, bl, label="BL=0 write", lw=1.5)
    ax.plot(t_ns, blb, label="BLB=VDD write", lw=1.5)
    ax.plot(t_ns, wl, "--", label="WL", lw=1.4)
    ax.axhline(0.5 * VDD, color="0.35", ls="--", lw=0.9)
    ax.axvline(t_wl * 1e9, color="0.45", ls=":", lw=1.0)
    ax.axvline(t_q50 * 1e9, color="0.45", ls=":", lw=1.0)
    ax.plot(t_q50 * 1e9, 0.5 * VDD, "o", color="#d62728", ms=5)
    ax.annotate(
        f"write delay = {delay_ps:.1f} ps",
        xy=(t_q50 * 1e9, 0.5 * VDD),
        xytext=(t_q50 * 1e9 + 0.055, 0.47),
        arrowprops=dict(arrowstyle="->", lw=0.9, color="0.25"),
        fontsize=9.5,
        bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="0.7", alpha=0.95),
    )
    ax.text(
        0.50,
        0.16,
        "write-0 condition:\nBL=0, BLB=VDD, WL rises to VDD",
        transform=ax.transAxes,
        fontsize=8.5,
        bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="0.7", alpha=0.95),
    )
    ax.set_title(title)
    ax.set_xlabel("Time (ns)")
    ax.set_ylabel("Voltage (V)")
    ax.set_xlim(0.0, 1.20)
    ax.set_ylim(-0.03, 0.74)
    ax.grid(True, alpha=0.28)
    ax.legend(fontsize=8, loc="center right")
    fig.tight_layout()
    savefig(f"{prefix}_write_waveform")
    plt.close(fig)


def interpolate_crossing_x(x: np.ndarray, y: np.ndarray, target: float = 0.0) -> float:
    for i in range(1, len(x)):
        y0, y1 = y[i - 1], y[i]
        if (y0 >= target >= y1) or (y0 <= target <= y1):
            if y1 == y0:
                return float(x[i])
            frac = (target - y0) / (y1 - y0)
            return float(x[i - 1] + frac * (x[i] - x[i - 1]))
    return float("nan")


def plot_write_trip(prefix: str, title: str) -> None:
    d = read_csv(DATA / f"{prefix}_write_trip.csv")
    bl, q, qb = d["bl_v"], d["q_v"], d["qb_v"]
    trip_bl = interpolate_crossing_x(bl, q - qb, 0.0)
    drop_mv = (VDD - trip_bl) * 1e3

    fig, ax = plt.subplots(figsize=(6.3, 4.25))
    ax.plot(bl, q, label="Q", lw=2.0)
    ax.plot(bl, qb, label="QB", lw=2.0)
    ax.axhline(0.5 * VDD, color="0.35", ls="--", lw=0.9)
    if np.isfinite(trip_bl):
        ax.axvline(trip_bl, color="#d62728", ls=":", lw=1.4)
        ax.plot(trip_bl, 0.5 * (np.interp(trip_bl, bl[::-1], q[::-1]) + np.interp(trip_bl, bl[::-1], qb[::-1])), "o", color="#d62728", ms=5)
        ax.annotate(
            f"Q=QB crossing\nBL={trip_bl:.3f} V\nBL drop={drop_mv:.1f} mV",
            xy=(trip_bl, 0.35),
            xytext=(0.58, 0.60),
            textcoords="axes fraction",
            arrowprops=dict(arrowstyle="->", lw=0.9, color="#d62728"),
            fontsize=9,
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="0.7", alpha=0.95),
        )
    ax.invert_xaxis()
    ax.set_title(title)
    ax.set_xlabel("Forced BL voltage during write-0 DC sweep (V)")
    ax.set_ylabel("Storage-node voltage (V)")
    ax.set_ylim(-0.03, 0.74)
    ax.grid(True, alpha=0.28)
    ax.legend(fontsize=8, loc="center right")
    fig.tight_layout()
    savefig(f"{prefix}_write_trip")
    plt.close(fig)


def plot_energy(prefix: str, title: str) -> None:
    read = read_csv(DATA / f"{prefix}_read_q1.csv")
    write = read_csv(DATA / f"{prefix}_write0.csv")

    read_en = cumulative_energy_j(read["time_s"], read["ivdd_a"])
    write_en = cumulative_energy_j(write["time_s"], write["ivdd_a"])
    read_win = energy_window(read["time_s"], read["ivdd_a"])
    write_win = energy_window(write["time_s"], write["ivdd_a"])

    fig, ax = plt.subplots(figsize=(6.8, 4.25))
    ax.plot(read["time_s"] * 1e9, read_en * 1e15, label="read cumulative energy", lw=2.0)
    ax.plot(write["time_s"] * 1e9, write_en * 1e15, label="write cumulative energy", lw=2.0)
    ax.axvspan(0.2, 1.2, color="0.85", alpha=0.30, label="integration window")
    ax.text(
        0.53,
        0.16,
        f"Eread(0.2–1.2 ns) = {read_win*1e15:.3f} fJ\nEwrite(0.2–1.2 ns) = {write_win*1e15:.3f} fJ",
        transform=ax.transAxes,
        fontsize=9,
        bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="0.7", alpha=0.95),
    )
    ax.set_title(title)
    ax.set_xlabel("Time (ns)")
    ax.set_ylabel("Cumulative energy from VDD·|I(VDD)| (fJ)")
    ax.set_xlim(0.0, 1.25)
    ax.grid(True, alpha=0.28)
    ax.legend(fontsize=8, loc="upper left")
    fig.tight_layout()
    savefig(f"{prefix}_energy")
    plt.close(fig)


def main() -> None:
    plot_rsnm("ideal", "No-RC read-SNM noise-source sweep")
    plot_rsnm("rc_candidate", "RC read-SNM noise-source sweep")
    plot_read_waveform("ideal", "No-RC read transient")
    plot_read_waveform("rc_candidate", "RC read transient")
    plot_write_waveform("ideal", "No-RC write-0 transient")
    plot_write_waveform("rc_candidate", "RC write-0 transient")
    # Keep both write-trip figures annotated so the report remains visually consistent.
    plot_write_trip("ideal", "No-RC write-trip DC curve")
    plot_write_trip("rc_candidate", "RC write-trip DC curve")
    plot_energy("ideal", "No-RC energy integration")
    plot_energy("rc_candidate", "RC energy integration")


if __name__ == "__main__":
    main()
