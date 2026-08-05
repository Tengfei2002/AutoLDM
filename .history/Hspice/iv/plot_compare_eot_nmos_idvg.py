#!/usr/bin/env python3
"""Plot WT CFET CSV against NMOS Id-Vg EOT_0 sweep HSPICE results."""

from __future__ import annotations

import csv
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
IV_DIR = ROOT / "Hspice" / "iv"
CSV_PATH = ROOT / "Hspice" / "wt_cfet" / "CFET_N4.40_14000.csv"
RESULTS_DIR = IV_DIR / "results_eot"
PNG_DIR = IV_DIR / "png"

EOT_VALUES_NM = [0.90, 0.95, 1.00, 1.05, 1.10, 1.15, 1.20]
VDS_BLOCK_INDEX = 0  # L16_W25, VDS=0.05 V; this is the blue curve in the existing plot.

FLOAT_RE = re.compile(r"^[+-]?(?:(?:\d+\.\d*)|(?:\.\d+)|(?:\d+))(?:[eE][+-]?\d+)?$")


def eot_tag(eot_nm: float) -> str:
    return f"EOT{eot_nm:.2f}".replace(".", "_")


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
    return np.asarray(xs), np.maximum(np.asarray(ys), 1e-18)


def parse_hspice_dc_blocks(lis_path: Path) -> list[np.ndarray]:
    blocks: list[np.ndarray] = []
    rows: list[list[float]] = []
    in_table = False
    for raw in lis_path.read_text(errors="ignore").splitlines():
        line = raw.strip()
        if line == "x":
            in_table = True
            rows = []
            continue
        if not in_table:
            continue
        if line == "y":
            if rows:
                blocks.append(np.asarray(rows, dtype=float))
            in_table = False
            continue
        parts = line.split()
        vals = [parse_float(part) for part in parts]
        if parts and all(v is not None for v in vals):
            rows.append([float(v) for v in vals if v is not None])
    return blocks


def read_eot_curves() -> list[tuple[float, np.ndarray, np.ndarray]]:
    curves: list[tuple[float, np.ndarray, np.ndarray]] = []
    for eot_nm in EOT_VALUES_NM:
        stem = f"single_va_nmos_idvg_{eot_tag(eot_nm)}"
        lis_path = RESULTS_DIR / stem / f"{stem}.lis"
        if not lis_path.exists():
            raise SystemExit(f"missing HSPICE listing: {lis_path}")
        blocks = parse_hspice_dc_blocks(lis_path)
        if len(blocks) <= VDS_BLOCK_INDEX:
            raise SystemExit(f"expected block {VDS_BLOCK_INDEX} in {lis_path}, got {len(blocks)}")
        block = blocks[VDS_BLOCK_INDEX]
        vg = np.abs(block[:, 0])
        current = np.maximum(np.abs(block[:, -1]), 1e-18)
        order = np.argsort(vg)
        curves.append((eot_nm, vg[order], current[order]))
    return curves


def setup_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 130,
            "savefig.dpi": 320,
            "font.size": 10,
            "axes.labelsize": 11,
            "axes.titlesize": 12,
            "legend.fontsize": 8.5,
            "axes.grid": True,
            "grid.alpha": 0.28,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "lines.linewidth": 1.8,
            "font.family": "DejaVu Sans",
        }
    )


def plot_curves(logy: bool) -> Path:
    csv_vg, csv_id = read_csv_curve()
    curves = read_eot_curves()
    setup_style()

    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    colors = plt.cm.viridis(np.linspace(0.08, 0.92, len(curves)))
    for (eot_nm, vg, current), color in zip(curves, colors):
        label = f"VA EOT_0={eot_nm:.2f} nm"
        if logy:
            ax.semilogy(vg, current, color=color, label=label)
        else:
            ax.plot(vg, current, color=color, label=label)

    if logy:
        ax.semilogy(
            csv_vg,
            csv_id,
            "o",
            markersize=4.0,
            markerfacecolor="none",
            markeredgecolor="black",
            markeredgewidth=1.1,
            label="WT CFET CSV",
        )
        suffix = "_logy"
        ax.set_ylabel("ID (A), log scale")
    else:
        ax.plot(
            csv_vg,
            csv_id,
            "o",
            markersize=4.0,
            markerfacecolor="none",
            markeredgecolor="black",
            markeredgewidth=1.1,
            linestyle="none",
            label="WT CFET CSV",
        )
        suffix = ""
        ax.set_ylabel("ID (A)")

    ax.set_xlabel("VGS (V)")
    ax.set_title("NMOS Id-Vg EOT_0 Sweep vs WT CFET CSV (L16_W25, VDS=0.05 V)")
    ax.set_xlim(0, max(0.7, float(np.nanmax(csv_vg))))
    ax.legend(frameon=False, ncols=2)
    fig.tight_layout()

    PNG_DIR.mkdir(parents=True, exist_ok=True)
    out = PNG_DIR / f"compare_wt_cfet_vs_va_nmos_idvg_EOT_sweep{suffix}.png"
    fig.savefig(out, bbox_inches="tight")
    print(f"Wrote: {out}")
    return out


def main() -> int:
    plot_curves(logy=False)
    plot_curves(logy=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
