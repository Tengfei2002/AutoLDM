from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
FIGS = BASE / "figures"
VDD = 0.7


def main() -> None:
    read = np.genfromtxt(DATA / "ideal_read_q1.csv", delimiter=",", names=True)
    write = np.genfromtxt(DATA / "ideal_write0.csv", delimiter=",", names=True)
    trip = np.genfromtxt(DATA / "ideal_write_trip.csv", delimiter=",", names=True)

    tr = read["time_s"] * 1e9
    tw = write["time_s"] * 1e9
    read_diff = read["bl_v"] - read["blb_v"]
    read_disturb = read["qb_v"].max()
    idx_disturb = int(np.argmax(read["qb_v"]))
    idx_wl_read = int(np.argmax(read["wl_v"] >= 0.5 * VDD))
    idx_read_delay = np.where((np.arange(len(read)) > idx_wl_read) & (read_diff >= 0.05))[0][0]

    idx_wl_write = int(np.argmax(write["wl_v"] >= 0.5 * VDD))
    idx_write_delay = np.where((np.arange(len(write)) > idx_wl_write) & (write["q_v"] <= 0.5 * VDD))[0][0]
    idx_trip = np.where(trip["q_v"] <= trip["qb_v"])[0][0]

    fig, axes = plt.subplots(2, 2, figsize=(10.5, 7.5))
    ax = axes[0, 0]
    ax.plot(tr, read["qb_v"], label="QB stored-low")
    ax.plot(tr, read["q_v"], label="Q stored-high")
    ax.scatter(tr[idx_disturb], read_disturb, color="crimson", zorder=5)
    ax.annotate(
        f"read disturb = {read_disturb*1e3:.1f} mV",
        xy=(tr[idx_disturb], read_disturb),
        xytext=(tr[idx_disturb] + 0.08, read_disturb + 0.08),
        arrowprops={"arrowstyle": "->", "color": "crimson"},
        color="crimson",
    )
    ax.set_title("Read-disturb extraction")
    ax.set_xlabel("Time / ns")
    ax.set_ylabel("Voltage / V")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)

    ax = axes[0, 1]
    ax.plot(tr, read_diff, label="BL - BLB")
    ax.axhline(0.05, ls="--", color="0.45", label="50 mV threshold")
    ax.axvline(tr[idx_wl_read], ls=":", color="0.45")
    ax.axvline(tr[idx_read_delay], ls=":", color="crimson")
    ax.annotate(
        f"read delay = {tr[idx_read_delay]-tr[idx_wl_read]:.1f} ps",
        xy=(tr[idx_read_delay], 0.05),
        xytext=(tr[idx_read_delay] + 0.12, 0.16),
        arrowprops={"arrowstyle": "->", "color": "crimson"},
        color="crimson",
    )
    ax.set_title("Read-delay extraction")
    ax.set_xlabel("Time / ns")
    ax.set_ylabel("BL differential / V")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)

    ax = axes[1, 0]
    ax.plot(tw, write["q_v"], label="Q target low")
    ax.plot(tw, write["qb_v"], label="QB target high")
    ax.axhline(0.5 * VDD, ls="--", color="0.45", label="0.5VDD")
    ax.axvline(tw[idx_wl_write], ls=":", color="0.45")
    ax.axvline(tw[idx_write_delay], ls=":", color="crimson")
    ax.annotate(
        f"write delay = {tw[idx_write_delay]-tw[idx_wl_write]:.1f} ps",
        xy=(tw[idx_write_delay], 0.5 * VDD),
        xytext=(tw[idx_write_delay] + 0.12, 0.50),
        arrowprops={"arrowstyle": "->", "color": "crimson"},
        color="crimson",
    )
    ax.set_title("Write-delay extraction")
    ax.set_xlabel("Time / ns")
    ax.set_ylabel("Voltage / V")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)

    ax = axes[1, 1]
    ax.plot(trip["bl_v"], trip["q_v"], label="Q")
    ax.plot(trip["bl_v"], trip["qb_v"], label="QB")
    ax.scatter(trip["bl_v"][idx_trip], trip["q_v"][idx_trip], color="crimson", zorder=5)
    ax.invert_xaxis()
    ax.annotate(
        f"BL drop = {(VDD-trip['bl_v'][idx_trip])*1e3:.0f} mV",
        xy=(trip["bl_v"][idx_trip], trip["q_v"][idx_trip]),
        xytext=(trip["bl_v"][idx_trip] + 0.15, trip["q_v"][idx_trip] + 0.18),
        arrowprops={"arrowstyle": "->", "color": "crimson"},
        color="crimson",
    )
    ax.set_title("Write-trip extraction")
    ax.set_xlabel("Forced BL voltage / V")
    ax.set_ylabel("Storage-node voltage / V")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)

    fig.suptitle("How SRAM metrics are extracted from HSPICE curves", fontsize=14)
    fig.tight_layout()
    out = FIGS / "metric_extraction_annotation.png"
    fig.savefig(out, dpi=220)
    fig.savefig(out.with_suffix(".svg"))


if __name__ == "__main__":
    main()
