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
WL_TARGET = 0.5 * VDD
BLDIFF_TARGET = 0.05


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


def crossing_time(
    t: np.ndarray,
    y: np.ndarray,
    target: float,
    start_index: int = 1,
    rising: bool = True,
) -> tuple[float, int]:
    for i in range(max(1, start_index), len(t)):
        y0 = y[i - 1]
        y1 = y[i]
        crossed = (y0 < target <= y1) if rising else (y0 > target >= y1)
        if crossed:
            if y1 == y0:
                return float(t[i]), i
            frac = (target - y0) / (y1 - y0)
            return float(t[i - 1] + frac * (t[i] - t[i - 1])), i
    return float("nan"), -1


def make_one(csv_name: str, stem: str, title: str) -> dict[str, float]:
    d = read_csv(DATA / csv_name)
    time_s = d["time_s"]
    time_ps = time_s * 1e12
    wl_v = d["wl_v"]
    bl_v = d["bl_v"]
    blb_v = d["blb_v"]
    bl_diff_v = bl_v - blb_v

    t_wl, idx_wl = crossing_time(time_s, wl_v, WL_TARGET, rising=True)
    t_diff, idx_diff = crossing_time(time_s, bl_diff_v, BLDIFF_TARGET, start_index=idx_wl, rising=True)
    if not np.isfinite(t_wl) or not np.isfinite(t_diff):
        raise RuntimeError(f"Cannot extract read delay from {csv_name}: t_wl={t_wl}, t_diff={t_diff}")

    delay_ps = (t_diff - t_wl) * 1e12
    t_wl_ps = t_wl * 1e12
    t_diff_ps = t_diff * 1e12

    # Keep enough context around the two readout events.
    x0 = max(0.0, t_wl_ps - 45.0)
    x1 = t_diff_ps + 75.0

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    ax.plot(time_ps, bl_diff_v * 1e3, color="#1f77b4", lw=2.2, label="BL - BLB")
    ax.axhline(BLDIFF_TARGET * 1e3, color="0.25", ls="--", lw=1.2, label="sense criterion = 50 mV")
    ax.axvline(t_wl_ps, color="#2ca02c", ls=":", lw=1.6, label="WL = 0.5VDD")
    ax.axvline(t_diff_ps, color="#d62728", ls=":", lw=1.6, label="BL-BLB = 50 mV")
    ax.plot([t_diff_ps], [BLDIFF_TARGET * 1e3], "o", color="#d62728", ms=5)

    ax.annotate(
        f"read delay = {delay_ps:.1f} ps",
        xy=((t_wl_ps + t_diff_ps) / 2.0, BLDIFF_TARGET * 1e3),
        xytext=(t_wl_ps + 8.0, BLDIFF_TARGET * 1e3 + 30.0),
        arrowprops=dict(arrowstyle="<->", lw=1.1, color="0.2"),
        fontsize=10,
    )
    ax.annotate(
        "start",
        xy=(t_wl_ps, 0.0),
        xytext=(t_wl_ps - 18.0, 22.0),
        arrowprops=dict(arrowstyle="->", lw=0.9, color="#2ca02c"),
        color="#2ca02c",
        fontsize=9,
    )
    ax.annotate(
        "readout point",
        xy=(t_diff_ps, BLDIFF_TARGET * 1e3),
        xytext=(t_diff_ps + 8.0, BLDIFF_TARGET * 1e3 + 12.0),
        arrowprops=dict(arrowstyle="->", lw=0.9, color="#d62728"),
        color="#d62728",
        fontsize=9,
    )

    ax2 = ax.twinx()
    ax2.plot(time_ps, wl_v / VDD, color="#2ca02c", lw=1.3, alpha=0.75, label="WL / VDD")
    ax2.set_ylabel("WL / VDD")
    ax2.set_ylim(-0.05, 1.08)
    ax2.axhline(0.5, color="#2ca02c", ls="--", lw=0.8, alpha=0.45)

    ax.set_title(title)
    ax.set_xlabel("time (ps)")
    ax.set_ylabel("BL - BLB (mV)")
    ax.set_xlim(x0, x1)
    y_max = max(80.0, float(np.nanmax(bl_diff_v[(time_ps >= x0) & (time_ps <= x1)] * 1e3)) * 1.15)
    ax.set_ylim(-5.0, y_max)
    ax.grid(True, alpha=0.28)

    lines, labels = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines + lines2, labels + labels2, loc="upper left", fontsize=8, frameon=True)

    fig.tight_layout()
    FIGS.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGS / f"{stem}.svg", bbox_inches="tight")
    fig.savefig(FIGS / f"{stem}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    return {
        "t_wl_ps": t_wl_ps,
        "t_bldiff50_ps": t_diff_ps,
        "read_delay_ps": delay_ps,
    }


def main() -> None:
    results = {
        "No-RC": make_one(
            "ideal_read_q1.csv",
            "ideal_read_bldiff",
            "No-RC read delay extraction from HSPICE waveform",
        ),
        "RC": make_one(
            "rc_candidate_read_q1.csv",
            "rc_candidate_read_bldiff",
            "RC read delay extraction from HSPICE waveform",
        ),
    }
    for name, r in results.items():
        print(
            f"{name}: WL@0.5VDD={r['t_wl_ps']:.3f} ps, "
            f"BL-BLB@50mV={r['t_bldiff50_ps']:.3f} ps, "
            f"read_delay={r['read_delay_ps']:.3f} ps"
        )


if __name__ == "__main__":
    main()
