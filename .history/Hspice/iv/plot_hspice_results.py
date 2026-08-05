#!/usr/bin/env python3
"""Plot generated HSPICE SRAM and single-device results.

The script reads HSPICE .lis files produced by .PRINT statements and
generates publication-style PNG figures under Hspice/iv/png by default.
It does not synthesize device data from equations; plotted curves come
from HSPICE output tables.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np

try:
    import matplotlib.pyplot as plt
except Exception as exc:  # pragma: no cover - user environment issue
    raise SystemExit(
        "matplotlib is required for plotting. Install it in the active Python environment."
    ) from exc


FLOAT_RE = re.compile(
    r"^[+-]?(?:(?:\d+\.\d*)|(?:\.\d+)|(?:\d+))(?:[eE][+-]?\d+)?$"
)


def as_float(token: str) -> float | None:
    token = token.strip()
    if FLOAT_RE.match(token):
        try:
            return float(token)
        except ValueError:
            return None
    return None


def parse_lis_tables(lis_path: Path) -> list[dict[str, object]]:
    """Parse HSPICE x/y .PRINT tables from a .lis file."""
    blocks: list[dict[str, object]] = []
    in_table = False
    header: list[str] = []
    rows: list[list[float]] = []

    for raw in lis_path.read_text(errors="ignore").splitlines():
        line = raw.strip()
        if line == "x":
            in_table = True
            header = []
            rows = []
            continue

        if not in_table:
            continue

        if line == "y":
            if rows:
                lower_header = " ".join(header).lower()
                if "time" in lower_header:
                    kind = "tran"
                elif "volt" in lower_header:
                    kind = "dc"
                else:
                    kind = "unknown"
                blocks.append(
                    {
                        "kind": kind,
                        "header": header,
                        "rows": np.array(rows, dtype=float),
                    }
                )
            in_table = False
            continue

        parts = line.split()
        nums = [as_float(part) for part in parts]
        if parts and all(num is not None for num in nums):
            rows.append([float(num) for num in nums if num is not None])
        elif line:
            header.append(line)

    return blocks


def read_plot_metadata(deck_path: Path) -> dict[str, list[str] | str]:
    meta: dict[str, list[str] | str] = {}
    if not deck_path.exists():
        return meta
    for raw in deck_path.read_text(errors="ignore").splitlines():
        line = raw.strip()
        if not line.startswith("* PLOT_"):
            continue
        payload = line[2:].strip()
        if " " not in payload:
            continue
        key, value = payload.split(None, 1)
        key = key.replace("PLOT_", "").lower()
        values = value.split()
        meta[key] = values if key in {"variants", "curves"} else value.strip()
    return meta


def configure_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 130,
            "savefig.dpi": 320,
            "font.size": 9,
            "axes.labelsize": 9,
            "axes.titlesize": 10,
            "legend.fontsize": 8,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "axes.grid": True,
            "grid.alpha": 0.28,
            "grid.linestyle": "-",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "lines.linewidth": 1.65,
            "font.family": "DejaVu Sans",
        }
    )


def savefig(fig: "plt.Figure", out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out_path}")


def plot_single_va(deck_path: Path, lis_path: Path, png_dir: Path) -> bool:
    meta = read_plot_metadata(deck_path)
    if meta.get("family") != "single_va":
        return False

    device = str(meta.get("device", "device"))
    kind = str(meta.get("kind", "iv"))
    variants = list(meta.get("variants", []))  # type: ignore[arg-type]
    curves = list(meta.get("curves", []))  # type: ignore[arg-type]
    blocks = [b for b in parse_lis_tables(lis_path) if b["kind"] == "dc"]

    if not variants or not curves or not blocks:
        print(f"skip {lis_path}: missing metadata or DC tables")
        return True

    curves_per_variant = len(curves)
    usable_variants = min(len(variants), len(blocks) // curves_per_variant)
    if usable_variants == 0:
        print(f"skip {lis_path}: not enough DC tables")
        return True

    rows = int(np.ceil(usable_variants / 2))
    fig, axes = plt.subplots(rows, 2, figsize=(7.2, 3.0 * rows), squeeze=False)
    axes_flat = axes.ravel()

    is_pmos = device.lower() == "pmos"
    gate_label = "VSG" if is_pmos else "VGS"
    drain_label = "VSD" if is_pmos else "VDS"
    x_label = f"{gate_label} (V)" if kind == "idvg" else f"{drain_label} (V)"
    y_label = "|ID| (A)" if is_pmos else "ID (A)"

    for vidx in range(usable_variants):
        ax = axes_flat[vidx]
        ax.set_title(variants[vidx])
        for cidx, curve in enumerate(curves):
            block = blocks[vidx * curves_per_variant + cidx]
            data = block["rows"]  # type: ignore[assignment]
            if not isinstance(data, np.ndarray) or data.ndim != 2 or data.shape[1] < 2:
                continue
            x = np.abs(data[:, 0])
            y = np.maximum(np.abs(data[:, -1]), 1e-18)
            label = curve.replace("=", " = ")
            if kind == "idvg":
                ax.semilogy(x, y, label=label)
            else:
                ax.plot(x, y, label=label)
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        ax.legend(frameon=False)

    for ax in axes_flat[usable_variants:]:
        ax.axis("off")

    title = f"{device.upper()} {kind.upper()} from HSPICE .lis"
    fig.suptitle(title, y=1.01, fontsize=11)
    savefig(fig, png_dir / f"{deck_path.stem}.png")
    return True


def block_rows(block: dict[str, object]) -> np.ndarray:
    rows = block.get("rows")
    if isinstance(rows, np.ndarray):
        return rows
    return np.empty((0, 0))


def plot_tran_group(
    tran_map: dict[str, np.ndarray],
    names: list[str],
    title: str,
    out_path: Path,
) -> None:
    available = [name for name in names if name in tran_map]
    if not available:
        return
    fig, axes = plt.subplots(len(available), 1, figsize=(7.2, 2.6 * len(available)), sharex=True)
    if len(available) == 1:
        axes = [axes]
    for ax, name in zip(axes, available):
        data = tran_map[name]
        if data.shape[1] < 6:
            continue
        t_ns = data[:, 0] * 1e9
        ax.plot(t_ns, data[:, 1], label="BL")
        ax.plot(t_ns, data[:, 2], label="BLB")
        ax.plot(t_ns, data[:, 3], label="WL", linestyle="--")
        ax.plot(t_ns, data[:, 4], label="Q")
        ax.plot(t_ns, data[:, 5], label="QB")
        ax.set_ylabel("Voltage (V)")
        ax.set_title(name)
        ax.legend(ncol=5, frameon=False, loc="best")
    axes[-1].set_xlabel("Time (ns)")
    fig.suptitle(title, y=1.01, fontsize=11)
    savefig(fig, out_path)


def plot_sram(lis_path: Path, png_dir: Path) -> bool:
    if lis_path.stem not in {"standard_sram", "standard_sram_tran", "standard_sram_snm"}:
        return False

    blocks = parse_lis_tables(lis_path)
    raw_tran_blocks = [block_rows(b) for b in blocks if b["kind"] == "tran"]
    raw_dc_blocks = [block_rows(b) for b in blocks if b["kind"] == "dc"]

    tran_blocks: list[np.ndarray] = []
    for idx in range(0, len(raw_tran_blocks) - 1, 2):
        first = raw_tran_blocks[idx]
        second = raw_tran_blocks[idx + 1]
        if first.size and second.size and first.shape[0] == second.shape[0]:
            tran_blocks.append(np.column_stack([first, second[:, 1:]]))

    dc_blocks: list[np.ndarray] = []
    for idx in range(0, len(raw_dc_blocks) - 2, 3):
        first = raw_dc_blocks[idx]
        second = raw_dc_blocks[idx + 1]
        third = raw_dc_blocks[idx + 2]
        if (
            first.size
            and second.size
            and third.size
            and first.shape[0] == second.shape[0] == third.shape[0]
        ):
            dc_blocks.append(np.column_stack([first, second[:, 1:], third[:, 1:]]))

    tran_names = ["READ_Q1", "READ_Q0", "WRITE_0", "WRITE_1", "HOLD_Q1", "HOLD_Q0"]
    dc_names = [
        "HOLD_SNM_Q_SWEEP",
        "HOLD_SNM_QB_SWEEP",
        "READ_SNM_Q_SWEEP",
        "READ_SNM_QB_SWEEP",
    ]
    tran_map = {
        name: data
        for name, data in zip(tran_names, tran_blocks)
        if isinstance(data, np.ndarray) and data.size
    }
    dc_map = {
        name: data
        for name, data in zip(dc_names, dc_blocks)
        if isinstance(data, np.ndarray) and data.size
    }

    plot_tran_group(
        tran_map,
        ["READ_Q1", "READ_Q0"],
        "SRAM Read Transients",
        png_dir / "sram_read_transient.png",
    )
    plot_tran_group(
        tran_map,
        ["WRITE_0", "WRITE_1"],
        "SRAM Write Transients",
        png_dir / "sram_write_transient.png",
    )
    plot_tran_group(
        tran_map,
        ["HOLD_Q1", "HOLD_Q0"],
        "SRAM Hold Retention",
        png_dir / "sram_hold_retention.png",
    )

    current_available = [name for name in tran_names if name in tran_map and tran_map[name].shape[1] >= 7]
    if current_available:
        fig, ax = plt.subplots(figsize=(7.2, 4.2))
        for name in current_available:
            data = tran_map[name]
            ax.plot(data[:, 0] * 1e9, -data[:, 6] * 1e6, label=name)
        ax.set_xlabel("Time (ns)")
        ax.set_ylabel("-I(VDD_SRC) (uA)")
        ax.set_title("SRAM Supply Current")
        ax.legend(frameon=False, ncol=2)
        savefig(fig, png_dir / "sram_supply_current.png")

    if all(name in dc_map for name in dc_names):
        fig, axes = plt.subplots(1, 2, figsize=(8.0, 3.6), sharex=True, sharey=True)
        for ax, prefix, title in zip(axes, ["HOLD", "READ"], ["Hold SNM", "Read SNM"]):
            q_data = dc_map[f"{prefix}_SNM_Q_SWEEP"]
            qb_data = dc_map[f"{prefix}_SNM_QB_SWEEP"]
            if q_data.shape[1] >= 3 and qb_data.shape[1] >= 3:
                ax.plot(q_data[:, 1], q_data[:, 2], label="Q forced")
                ax.plot(qb_data[:, 2], qb_data[:, 1], label="QB forced")
                v_max = max(np.nanmax(q_data[:, 1:3]), np.nanmax(qb_data[:, 1:3]))
                ax.plot([0, v_max], [0, v_max], color="0.35", linestyle=":", linewidth=1.0)
            ax.set_title(title)
            ax.set_xlabel("Forced/input node (V)")
            ax.set_ylabel("Complement/output node (V)")
            ax.legend(frameon=False)
        fig.suptitle("SRAM Butterfly Curves from HSPICE", y=1.02, fontsize=11)
        savefig(fig, png_dir / "sram_snm_butterfly.png")

        fig, ax = plt.subplots(figsize=(7.2, 4.2))
        for name, label in [
            ("HOLD_SNM_Q_SWEEP", "hold"),
            ("READ_SNM_Q_SWEEP", "read"),
        ]:
            data = dc_map[name]
            if data.shape[1] >= 7:
                ax.plot(data[:, 1], data[:, 6] * 1e6, label=label)
        ax.axhline(0, color="0.35", linewidth=1.0, linestyle=":")
        ax.set_xlabel("V(Q) forced (V)")
        ax.set_ylabel("I(VQF) (uA)")
        ax.set_title("SRAM N-Curve Style Forced-Node Current")
        handles, labels = ax.get_legend_handles_labels()
        if labels:
            ax.legend(handles, labels, frameon=False)
        savefig(fig, png_dir / "sram_ncurve.png")

    return True


def find_deck_for_lis(repo_root: Path, lis_path: Path) -> Path:
    stem = lis_path.stem
    single_deck = repo_root / "Hspice" / "iv" / f"{stem}.sp"
    if single_deck.exists():
        return single_deck
    if stem == "standard_sram":
        return repo_root / "output_SDE" / "rc_sp" / "standard_sram.sp"
    return Path()


def main(argv: list[str]) -> int:
    script_path = Path(__file__).resolve()
    repo_root = script_path.parents[2]

    parser = argparse.ArgumentParser(description="Plot generated HSPICE .lis results.")
    parser.add_argument(
        "--results",
        default=str(repo_root / "Hspice" / "iv" / "results"),
        help="Directory containing HSPICE result folders.",
    )
    parser.add_argument(
        "--png",
        default=str(repo_root / "Hspice" / "iv" / "png"),
        help="Output directory for PNG figures.",
    )
    args = parser.parse_args(argv)

    configure_style()
    results_dir = Path(args.results).resolve()
    png_dir = Path(args.png).resolve()
    if not results_dir.exists():
        print(f"results directory does not exist yet: {results_dir}")
        return 1

    lis_files = sorted(
        path
        for path in results_dir.rglob("*.lis")
        if not any(part.lower().endswith(".pvadir") for part in path.parts)
    )
    if not lis_files:
        print(f"no .lis files found under {results_dir}")
        return 1

    handled = 0
    for lis_path in lis_files:
        deck_path = find_deck_for_lis(repo_root, lis_path)
        try:
            if plot_sram(lis_path, png_dir):
                handled += 1
                continue
            if deck_path and plot_single_va(deck_path, lis_path, png_dir):
                handled += 1
                continue
        except Exception as exc:
            print(f"failed to plot {lis_path}: {exc}", file=sys.stderr)

    if handled == 0:
        print(f"found {len(lis_files)} .lis files, but none matched generated decks")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
