#!/usr/bin/env python3
"""Compare WT CFET CSV IdVg with HSPICE single_va_nmos_idvg result."""

from __future__ import annotations

import csv
import re
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = ROOT / "Hspice" / "wt_cfet" / "CFET_N4.40_14000.csv"
LIS_PATH = ROOT / "Hspice" / "iv" / "single_va_nmos_idvg" / "single_va_nmos_idvg.lis"
PNG_PATH = ROOT / "Hspice" / "iv" / "png" / "compare_wt_cfet_vs_va_nmos_idvg.png"

CURVE_LABELS = ["HSPICE L16_W25, VDS=0.05 V", "HSPICE L16_W25, VDS=0.35 V", "HSPICE L16_W25, VDS=0.70 V"]


FLOAT_RE = re.compile(r"^[+-]?(?:(?:\d+\.\d*)|(?:\.\d+)|(?:\d+))(?:[eE][+-]?\d+)?$")


def parse_float(token: str) -> float | None:
    token = token.strip()
    if FLOAT_RE.match(token):
        return float(token)
    return None


def read_csv_curve() -> tuple[np.ndarray, np.ndarray]:
    xs: list[float] = []
    ys: list[float] = []
    with CSV_PATH.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if len(row) < 2:
                continue
            x = parse_float(row[0])
            y = parse_float(row[1])
            if x is None or y is None:
                continue
            xs.append(x)
            ys.append(abs(y))
    return np.array(xs), np.maximum(np.array(ys), 1e-18)


def parse_hspice_dc_blocks() -> list[np.ndarray]:
    blocks: list[np.ndarray] = []
    rows: list[list[float]] = []
    in_table = False
    for raw in LIS_PATH.read_text(errors="ignore").splitlines():
        line = raw.strip()
        if line == "x":
            in_table = True
            rows = []
            continue
        if not in_table:
            continue
        if line == "y":
            if rows:
                blocks.append(np.array(rows, dtype=float))
            in_table = False
            continue
        parts = line.split()
        vals = [parse_float(part) for part in parts]
        if parts and all(v is not None for v in vals):
            rows.append([float(v) for v in vals if v is not None])
    return blocks


def main() -> int:
    csv_vg, csv_id = read_csv_curve()
    hspice_blocks = parse_hspice_dc_blocks()
    if len(hspice_blocks) < 3:
        raise SystemExit(f"Expected at least 3 HSPICE curves, got {len(hspice_blocks)}")

    plt.rcParams.update(
        {
            "figure.dpi": 130,
            "savefig.dpi": 320,
            "font.size": 10,
            "axes.labelsize": 11,
            "axes.titlesize": 12,
            "legend.fontsize": 9,
            "axes.grid": True,
            "grid.alpha": 0.28,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "lines.linewidth": 1.9,
            "font.family": "DejaVu Sans",
        }
    )

    fig, ax = plt.subplots(figsize=(6.8, 4.6))
    for block, label in zip(hspice_blocks[:3], CURVE_LABELS):
        vg = np.abs(block[:, 0])
        current = np.maximum(np.abs(block[:, -1]), 1e-18)
        ax.semilogy(vg, current, label=label)

    ax.semilogy(
        csv_vg,
        csv_id,
        "o",
        markersize=4.2,
        markerfacecolor="none",
        markeredgewidth=1.2,
        label="WT CFET CSV: CFET_N4.40_14000",
    )
    ax.set_xlabel("VGS (V)")
    ax.set_ylabel("ID (A), log scale")
    ax.set_title("NMOS Id-Vg: WT CFET CSV vs Verilog-A HSPICE")
    ax.set_xlim(0, max(0.7, float(np.nanmax(csv_vg))))
    ax.legend(frameon=False)
    fig.tight_layout()
    PNG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(PNG_PATH, bbox_inches="tight")
    print(f"Wrote: {PNG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
