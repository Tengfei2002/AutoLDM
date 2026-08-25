#!/usr/bin/env python3
"""Run generated SRAM1 HSPICE decks and collect reproducible research results.

The script accepts one .sp file or a directory of .sp files.  It keeps raw
HSPICE results, converts .PRINT tables in .lis files into CSV data, extracts
basic SRAM metrics, and creates publication-ready PNG/SVG figures.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

try:
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib import font_manager
except ImportError as exc:  # pragma: no cover - environment dependent
    raise SystemExit("run_sram1_sp.py requires numpy and matplotlib.") from exc


DEFAULT_LICENSE = "27000@LAPTOP-K9QP6UAM"
HSPICE_INSTALL_CANDIDATES = (
    Path(r"C:\synopsys\Hspice_P-2019.06-SP1-1"),
    Path(r"C:\synopsys\Hspice_O-2018.09"),
)
TEST_NAMES = ("smoke", "hold", "read0", "read1", "write0", "write1", "wtrip0", "wtrip1", "hsnm_qb", "hsnm", "rsnm_qb", "rsnm")
NUMBER_RE = re.compile(r"^[+-]?(?:(?:\d+\.\d*)|(?:\.\d+)|(?:\d+))(?:[eEdD][+-]?\d+)?$")
MODEL_NAN_RE = re.compile(r"(?:numerical\s+NaN|FPE:)", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run SRAM1 HSPICE decks and create raw/data/figures research outputs."
    )
    parser.add_argument("input", type=Path, help="One .sp deck or a directory containing generated decks")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Result root directory")
    parser.add_argument("--hspice-cmd", default="", help="Explicit hspice.com or hspice.exe path")
    parser.add_argument("--install-dir", default="", help="HSPICE installation directory")
    parser.add_argument(
        "--license-server",
        default=os.environ.get("SNPSLMD_LICENSE_FILE", DEFAULT_LICENSE),
        help="FLEXlm license server; defaults to SNPSLMD_LICENSE_FILE or the project default",
    )
    parser.add_argument("--rerun", action="store_true", help="Rerun decks even when a newer .lis already exists")
    parser.add_argument("--dry-run", action="store_true", help="Create the manifest and print commands without HSPICE execution")
    parser.add_argument("--no-plot", action="store_true", help="Collect raw files and CSV data but skip PNG/SVG figures")
    return parser.parse_args()


def find_hspice(explicit_cmd: str, explicit_install_dir: str) -> Path:
    if explicit_cmd:
        candidate = Path(explicit_cmd).resolve()
        if candidate.is_file():
            return candidate
        raise FileNotFoundError(f"HSPICE executable not found: {candidate}")
    install_dirs: list[Path] = []
    if explicit_install_dir:
        install_dirs.append(Path(explicit_install_dir).resolve())
    install_dirs.extend(HSPICE_INSTALL_CANDIDATES)
    for install_dir in install_dirs:
        for relative in (r"WIN64\hspice.com", r"WIN64\hspice.exe"):
            candidate = install_dir / relative
            if candidate.is_file():
                return candidate
    found = shutil.which("hspice")
    if found:
        return Path(found).resolve()
    raise FileNotFoundError("Cannot find HSPICE. Pass --hspice-cmd or --install-dir.")


def collect_decks(source: Path) -> list[Path]:
    source = source.resolve()
    if source.is_file():
        if source.suffix.lower() != ".sp":
            raise ValueError(f"Expected a .sp deck, got: {source}")
        return [source]
    if not source.is_dir():
        raise FileNotFoundError(source)
    decks = sorted(path.resolve() for path in source.glob("*.sp"))
    if not decks:
        raise FileNotFoundError(f"No .sp files found in: {source}")
    return decks


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_hspice_env(hspice: Path, license_server: str) -> dict[str, str]:
    env = os.environ.copy()
    env["SNPSLMD_LICENSE_FILE"] = license_server
    env["LM_LICENSE_FILE"] = license_server
    install_dir = str(hspice.parent.parent)
    env["installdir_P-2019.06-SP1-1"] = install_dir
    env["installdir_O-2018.09"] = install_dir
    return env


def listing_has_model_nan(listing: Path) -> bool:
    if not listing.is_file():
        return False
    return bool(MODEL_NAN_RE.search(listing.read_text(encoding="utf-8", errors="ignore")))


def run_one(deck: Path, raw_dir: Path, hspice: Path, license_server: str, rerun: bool, dry_run: bool) -> dict[str, object]:
    run_dir = raw_dir / deck.stem
    run_dir.mkdir(parents=True, exist_ok=True)
    prefix = run_dir / deck.stem
    listing = prefix.with_suffix(".lis")
    command = [str(hspice), "-i", deck.name, "-o", str(prefix)]
    status: dict[str, object] = {
        "deck": str(deck),
        "deck_name": deck.name,
        "deck_sha256": sha256(deck),
        "run_dir": str(run_dir),
        "listing": str(listing),
        "command": command,
        "reused": False,
        "return_code": None,
    }
    if not rerun and listing.is_file() and listing.stat().st_mtime >= deck.stat().st_mtime:
        status["reused"] = True
        status["return_code"] = 0
        status["model_numerical_error"] = listing_has_model_nan(listing)
        return status
    if dry_run:
        status["return_code"] = 0
        status["dry_run"] = True
        return status
    completed = subprocess.run(
        command,
        cwd=deck.parent,
        env=make_hspice_env(hspice, license_server),
        text=True,
        capture_output=True,
        check=False,
    )
    (run_dir / "runner_stdout_stderr.txt").write_text(
        completed.stdout + "\n" + completed.stderr,
        encoding="utf-8",
        errors="ignore",
    )
    status["return_code"] = completed.returncode
    status["outputs"] = sorted(path.name for path in run_dir.glob(f"{deck.stem}.*"))
    status["model_numerical_error"] = listing_has_model_nan(listing)
    return status


def to_float(token: str) -> float | None:
    value = token.strip().replace("D", "E").replace("d", "e")
    if not NUMBER_RE.fullmatch(value):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_print_blocks(listing: Path) -> dict[tuple[str, ...], np.ndarray]:
    """Parse HSPICE `.PRINT` tables from a listing file."""
    lines = listing.read_text(encoding="utf-8", errors="ignore").splitlines()
    blocks: dict[tuple[str, ...], np.ndarray] = {}
    index = 0
    while index < len(lines) - 2:
        first = lines[index].split()
        if not first or first[0].lower() not in {"time", "v-sweep", "volt"}:
            index += 1
            continue
        second = lines[index + 1].split()
        names = tuple([first[0], *second])
        rows: list[list[float]] = []
        index += 2
        while index < len(lines):
            values = [to_float(token) for token in lines[index].split()]
            if len(values) < len(names) or any(value is None for value in values[: len(names)]):
                break
            rows.append([float(value) for value in values[: len(names)] if value is not None])
            index += 1
        if rows:
            blocks[names] = np.asarray(rows, dtype=float)
    return blocks


def canonical_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def column_index(header: tuple[str, ...], target: str) -> int | None:
    target = canonical_name(target)
    candidates = {target, f"v{target}", f"i{target}"}
    for index, name in enumerate(header):
        if canonical_name(name) in candidates:
            return index
    return None


def merged_transient_data(blocks: dict[tuple[str, ...], np.ndarray]) -> dict[str, np.ndarray] | None:
    """Merge HSPICE transient print blocks that split variables across pages."""
    time_blocks: list[tuple[tuple[str, ...], np.ndarray, int]] = []
    for header, values in blocks.items():
        time_index = column_index(header, "time")
        if time_index is not None:
            time_blocks.append((header, values, time_index))
    if not time_blocks:
        return None
    base_header, base_values, base_time_index = max(time_blocks, key=lambda item: len(item[1]))
    del base_header
    time = base_values[:, base_time_index]
    merged: dict[str, np.ndarray] = {"time": time}
    for target in ("bl", "blb", "blf", "blbf", "wl", "q", "qb", "vvdd", "vbldrv", "vblbdrv", "vwl_drv"):
        for header, values, time_index in time_blocks:
            value_index = column_index(header, target)
            if value_index is None:
                continue
            source_time = values[:, time_index]
            merged[target] = np.interp(time, source_time, values[:, value_index])
            break
    required = {"time", "bl", "blb", "wl", "q", "qb"}
    return merged if required.issubset(merged) else None


def dc_block(blocks: dict[tuple[str, ...], np.ndarray]) -> tuple[tuple[str, ...], np.ndarray] | None:
    for header, values in blocks.items():
        if column_index(header, "q") is not None and column_index(header, "qb") is not None:
            return header, values
    return None


def parse_supply(deck: Path) -> tuple[float, float]:
    text = deck.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"\.param\s+VDD_VAL\s*=\s*([^\s]+)\s+VSS_VAL\s*=\s*([^\s]+)", text, re.IGNORECASE)
    if not match:
        return float("nan"), float("nan")
    vdd, vss = to_float(match.group(1)), to_float(match.group(2))
    return (float("nan") if vdd is None else vdd, float("nan") if vss is None else vss)


def parse_param(deck: Path, name: str, default: float) -> float:
    match = re.search(rf"\b{name}\s*=\s*([^\s]+)", deck.read_text(encoding="utf-8", errors="ignore"), re.IGNORECASE)
    value = to_float(match.group(1)) if match else None
    return default if value is None else value


def test_name(deck: Path) -> str:
    lowered = deck.stem.lower()
    for name in TEST_NAMES:
        if lowered.endswith(f"_{name}"):
            return name
    return "unknown"


def save_csv(path: Path, header: list[str], columns: list[np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.column_stack(columns)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(data.tolist())


def crossing_time(time: np.ndarray, signal: np.ndarray, level: float, rising: bool, start: int = 0) -> float:
    """Return a linearly interpolated first threshold crossing."""
    if len(time) < 2:
        return float("nan")
    start = max(1, min(start, len(time) - 1))
    crossed = signal >= level if rising else signal <= level
    candidates = np.where(crossed[start:] & ~crossed[start - 1 : -1])[0]
    if not len(candidates):
        return float("nan")
    index = int(candidates[0] + start)
    previous = index - 1
    delta = signal[index] - signal[previous]
    if delta == 0:
        return float(time[index])
    fraction = float(np.clip((level - signal[previous]) / delta, 0.0, 1.0))
    return float(time[previous] + fraction * (time[index] - time[previous]))


def operation_window(time: np.ndarray, wl: np.ndarray, midpoint: float) -> tuple[int, int]:
    high = np.where(wl >= midpoint)[0]
    if not len(high):
        return 0, len(time) - 1
    start = int(high[0])
    low_after = np.where(wl[start + 1 :] <= midpoint)[0]
    stop = int(low_after[0] + start + 1) if len(low_after) else len(time) - 1
    return start, stop


def cumulative_energy(time: np.ndarray, power: np.ndarray) -> np.ndarray:
    if len(time) < 2:
        return np.zeros_like(time)
    increments = 0.5 * (power[1:] + power[:-1]) * np.diff(time)
    return np.concatenate(([0.0], np.cumsum(increments)))


def snm_from_curves(
    q_force_q: np.ndarray,
    qb_measured: np.ndarray,
    q_measured: np.ndarray,
    qb_force_qb: np.ndarray,
    vss: float,
    vdd: float,
) -> float:
    """Largest axis-aligned square between independently measured inverter VTCs."""
    if min(len(q_force_q), len(qb_measured), len(q_measured), len(qb_force_qb)) < 3:
        return float("nan")
    if not (math.isfinite(vss) and math.isfinite(vdd) and vdd > vss):
        return float("nan")

    def interpolate_curve(x: np.ndarray, y: np.ndarray, grid: np.ndarray) -> np.ndarray:
        order = np.argsort(x)
        x, y = x[order], y[order]
        unique_x, unique_index = np.unique(x, return_index=True)
        return np.interp(grid, unique_x, y[unique_index])

    grid = np.linspace(vss, vdd, 1001)
    first = interpolate_curve(q_force_q, qb_measured, grid)
    second = interpolate_curve(q_measured, qb_force_qb, grid)
    lower, upper = np.minimum(first, second), np.maximum(first, second)
    xx, yy = np.meshgrid(grid, grid)
    between = (yy >= lower[None, :]) & (yy <= upper[None, :])
    diagonal_masks = (between & (yy >= xx), between & (yy <= xx))
    step = grid[1] - grid[0]

    def largest_square(mask: np.ndarray) -> float:
        integral = np.pad(mask.astype(np.int32).cumsum(0).cumsum(1), ((1, 0), (1, 0)))
        low, high, best = 1, len(grid), 0
        while low <= high:
            width = (low + high) // 2
            sums = integral[width:, width:] - integral[:-width, width:] - integral[width:, :-width] + integral[:-width, :-width]
            if np.any(sums == width * width):
                best, low = width, width + 1
            else:
                high = width - 1
        return (best - 1) * step if best > 1 else float("nan")

    values = [largest_square(mask) for mask in diagonal_masks]
    valid = [value for value in values if math.isfinite(value)]
    return min(valid) if len(valid) == 2 else float("nan")


def configure_plot_style() -> None:
    chinese_fonts = ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC")
    for font_name in chinese_fonts:
        try:
            font_manager.findfont(
                font_manager.FontProperties(family=font_name),
                fallback_to_default=False,
            )
        except ValueError:
            continue
        plt.rcParams["font.sans-serif"] = [font_name, "DejaVu Sans"]
        break
    plt.rcParams.update({
        "font.size": 9,
        "axes.labelsize": 10,
        "axes.titlesize": 11,
        "legend.fontsize": 8,
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "axes.grid": True,
        "grid.alpha": 0.28,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.unicode_minus": False,
    })


def save_figure(figure: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.tight_layout()
    figure.savefig(path.with_suffix(".png"), dpi=300, bbox_inches="tight")
    figure.savefig(path.with_suffix(".svg"), bbox_inches="tight")
    plt.close(figure)


def extract_transient(deck: Path, listing: Path, data_dir: Path, figure_dir: Path, make_plots: bool) -> dict[str, float | str]:
    blocks = parse_print_blocks(listing)
    transient = merged_transient_data(blocks)
    if transient is None:
        return {"analysis_status": "missing_transient_print_table"}
    time = transient["time"]
    bl, blb, wl = (transient[name] for name in ("bl", "blb", "wl"))
    blf, blbf = transient.get("blf", bl), transient.get("blbf", blb)
    q, qb = (transient[name] for name in ("q", "qb"))
    ivdd = transient.get("vvdd", np.full_like(time, np.nan))
    vdd, vss = parse_supply(deck)
    vcore = vdd - vss
    source_currents = [ivdd]
    for name in ("vbldrv", "vblbdrv", "vwldrv"):
        if name in transient:
            source_currents.append(transient[name])
    power = -vcore * np.sum(source_currents, axis=0)
    energy = cumulative_energy(time, power)
    save_csv(
        data_dir / f"{deck.stem}.csv",
        ["time_s", "bl_v", "blb_v", "bl_far_v", "blb_far_v", "wl_v", "q_v", "qb_v", "ivdd_a", "total_source_power_w", "total_source_energy_j"],
        [time, bl, blb, blf, blbf, wl, q, qb, ivdd, power, energy],
    )
    test = test_name(deck)
    metrics: dict[str, float | str] = {
        "analysis_status": "ok",
        "vdd_v": vdd,
        "vss_v": vss,
        "final_q_v": float(q[-1]),
        "final_qb_v": float(qb[-1]),
        "peak_abs_supply_current_a": float(np.nanmax(np.abs(ivdd))),
    }
    midpoint = vss + 0.5 * vcore
    wl_crossing = crossing_time(time, wl, midpoint, rising=True)
    write_start = int(np.searchsorted(time, wl_crossing)) if math.isfinite(wl_crossing) else 1
    start, stop = operation_window(time, wl, midpoint)
    metrics["active_energy_j"] = float(energy[stop] - energy[start])
    metrics["active_average_power_w"] = float(np.nanmean(power[start : stop + 1]))
    sense_threshold = parse_param(deck, "SENSE_V", 0.05)
    if test in {"read0", "read1"}:
        bldiff = blbf - blf
        crossing = crossing_time(time, bldiff, sense_threshold, rising=True, start=write_start)
        metrics["read_delay_s"] = crossing - wl_crossing if math.isfinite(crossing) and math.isfinite(wl_crossing) else float("nan")
        metrics["read_bldiff_peak_v"] = float(np.max(bldiff[start : stop + 1]))
        metrics["read_sense_threshold_v"] = sense_threshold
        if test == "read0":
            metrics["read_disturb_peak_v"] = float(np.max(q[start : stop + 1]))
            metrics["read_pass"] = "pass" if q[-1] < midpoint and qb[-1] > midpoint else "fail"
        else:
            metrics["read_disturb_peak_v"] = float(np.max(qb[start : stop + 1]))
            metrics["read_pass"] = "pass" if q[-1] > midpoint and qb[-1] < midpoint else "fail"
    elif test == "write0":
        crossing = crossing_time(time, q, midpoint, rising=False, start=write_start)
        metrics["write_cell_delay_s"] = crossing - wl_crossing if math.isfinite(crossing) and math.isfinite(wl_crossing) else float("nan")
        metrics["write_pass"] = "pass" if q[-1] <= midpoint and qb[-1] >= midpoint else "fail"
    elif test == "write1":
        crossing = crossing_time(time, q, midpoint, rising=True, start=write_start)
        metrics["write_cell_delay_s"] = crossing - wl_crossing if math.isfinite(crossing) and math.isfinite(wl_crossing) else float("nan")
        metrics["write_pass"] = "pass" if q[-1] >= midpoint and qb[-1] <= midpoint else "fail"
    elif test == "hold":
        quiet_start = int(0.8 * len(time))
        metrics["hold_total_static_power_w"] = float(np.nanmean(power[quiet_start:]))
        metrics["hold_pass"] = "pass" if q[-1] < midpoint and qb[-1] > midpoint else "fail"

    if make_plots:
        fig, axis = plt.subplots(figsize=(6.5, 4.1))
        axis.plot(time * 1e9, q, label="Q", lw=1.5)
        axis.plot(time * 1e9, qb, label="QB", lw=1.5)
        axis.plot(time * 1e9, bl, label="BL", lw=1.2)
        axis.plot(time * 1e9, blb, label="BLB", lw=1.2)
        axis.plot(time * 1e9, wl, "--", label="WL", lw=1.2)
        axis.set(xlabel="时间 / ns", ylabel="电压 / V", title=f"{deck.stem}: 瞬态波形")
        axis.legend(ncol=3)
        save_figure(fig, figure_dir / f"{deck.stem}_waveform")
        if test in {"read0", "read1"}:
            fig, axis = plt.subplots(figsize=(6.2, 3.8))
            axis.plot(time * 1e9, blb - bl, label="BLB − BL", lw=1.6)
            axis.axhline(sense_threshold, color="0.35", ls="--", label=f"感放阈值 {sense_threshold * 1e3:.0f} mV")
            axis.set(xlabel="时间 / ns", ylabel="位线差分 / V", title=f"{deck.stem}: 读位线差分")
            axis.legend()
            save_figure(fig, figure_dir / f"{deck.stem}_bldiff")
        if False:  # Array-level energy is undefined without a bitline/periphery model.
            fig, axis = plt.subplots(figsize=(6.2, 3.8))
            axis.plot(time * 1e9, energy * 1e15, label="累计供电能量", lw=1.6)
            axis.set(xlabel="时间 / ns", ylabel="能量 / fJ", title=f"{deck.stem}: 供电能量积分")
            axis.legend()
            save_figure(fig, figure_dir / f"{deck.stem}_energy")
    return metrics


def extract_snm(deck: Path, listing: Path, data_dir: Path, figure_dir: Path, make_plots: bool) -> dict[str, float | str]:
    selected = dc_block(parse_print_blocks(listing))
    if selected is None:
        return {"analysis_status": "missing_dc_print_table"}
    header, values = selected
    q_index, qb_index = column_index(header, "q"), column_index(header, "qb")
    assert q_index is not None and qb_index is not None
    sweep = values[:, 0]
    q, qb = values[:, q_index], values[:, qb_index]
    save_csv(data_dir / f"{deck.stem}.csv", ["sweep_v", "q_v", "qb_v"], [sweep, q, qb])
    vdd, vss = parse_supply(deck)
    snm = snm_from_curve(q, qb, vss, vdd)
    metrics: dict[str, float | str] = {"analysis_status": "ok", "vdd_v": vdd, "vss_v": vss, "snm_v": snm}
    if make_plots:
        fig, axis = plt.subplots(figsize=(5.2, 4.6))
        axis.plot(q, qb, label="HSPICE: V(QB) 对 V(Q)", lw=1.6)
        axis.plot(qb, q, label="镜像传输曲线", lw=1.3)
        axis.plot([vss, vdd], [vss, vdd], "--", color="0.45", lw=1.0, label="V(Q)=V(QB)")
        if math.isfinite(snm):
            axis.text(0.03, 0.95, f"SNM = {snm * 1e3:.1f} mV", transform=axis.transAxes, va="top")
        axis.set(xlabel="V(Q) / V", ylabel="V(QB) / V", title=f"{deck.stem}: Butterfly 曲线", xlim=(vss, vdd), ylim=(vss, vdd))
        axis.legend()
        save_figure(fig, figure_dir / f"{deck.stem}_butterfly")
    return metrics


def extract_snm_curve(deck: Path, listing: Path, data_dir: Path) -> dict[str, np.ndarray | float | str]:
    """Save one independently forced SRAM inverter VTC."""
    selected = dc_block(parse_print_blocks(listing))
    if selected is None:
        return {"analysis_status": "missing_dc_print_table"}
    header, values = selected
    q_index, qb_index = column_index(header, "q"), column_index(header, "qb")
    assert q_index is not None and qb_index is not None
    sweep, q, qb = values[:, 0], values[:, q_index], values[:, qb_index]
    save_csv(data_dir / f"{deck.stem}.csv", ["sweep_v", "q_v", "qb_v"], [sweep, q, qb])
    vdd, vss = parse_supply(deck)
    return {"analysis_status": "curve_captured", "vdd_v": vdd, "vss_v": vss, "q": q, "qb": qb}


def extract_write_trip(deck: Path, listing: Path, data_dir: Path) -> dict[str, float | str]:
    selected = dc_block(parse_print_blocks(listing))
    if selected is None:
        return {"analysis_status": "missing_dc_print_table"}
    header, values = selected
    q_index, qb_index = column_index(header, "q"), column_index(header, "qb")
    assert q_index is not None and qb_index is not None
    sweep, q, qb = values[:, 0], values[:, q_index], values[:, qb_index]
    save_csv(data_dir / f"{deck.stem}.csv", ["bitline_drive_v", "q_v", "qb_v"], [sweep, q, qb])
    vdd, vss = parse_supply(deck)
    midpoint = vss + 0.5 * (vdd - vss)
    signal = qb if test_name(deck) == "wtrip1" else q
    cross = crossing_time(sweep, signal, midpoint, rising=False)
    return {"analysis_status": "ok", "vdd_v": vdd, "vss_v": vss, "write_trip_bl_v": cross, "write_trip_margin_v": vdd - cross if math.isfinite(cross) else float("nan")}


def summarize_snm_pair(
    test: str,
    first: dict[str, np.ndarray | float | str],
    second: dict[str, np.ndarray | float | str],
    data_dir: Path,
    figure_dir: Path,
    make_plots: bool,
) -> dict[str, float | str]:
    if first.get("analysis_status") != "curve_captured" or second.get("analysis_status") != "curve_captured":
        return {"test": test, "deck": test, "analysis_status": "missing_snm_curve"}
    q1, qb1 = first["q"], first["qb"]
    q2, qb2 = second["q"], second["qb"]
    assert isinstance(q1, np.ndarray) and isinstance(qb1, np.ndarray)
    assert isinstance(q2, np.ndarray) and isinstance(qb2, np.ndarray)
    vdd, vss = float(first["vdd_v"]), float(first["vss_v"])
    snm = snm_from_curves(q1, qb1, q2, qb2, vss, vdd)
    save_csv(
        data_dir / f"{test}_butterfly.csv",
        ["q_force_q_v", "qb_measured_v", "q_measured_v", "qb_force_qb_v"],
        [q1, qb1, q2, qb2],
    )
    if make_plots:
        fig, axis = plt.subplots(figsize=(5.2, 4.6))
        axis.plot(q1, qb1, label="force Q, measure QB", lw=1.6)
        axis.plot(q2, qb2, label="force QB, measure Q", lw=1.3)
        axis.plot([vss, vdd], [vss, vdd], "--", color="0.45", lw=1.0, label="Q = QB")
        if math.isfinite(snm):
            axis.text(0.03, 0.95, f"SNM = {snm * 1e3:.1f} mV", transform=axis.transAxes, va="top")
        axis.set(xlabel="V(Q) / V", ylabel="V(QB) / V", title=f"{test.upper()} butterfly", xlim=(vss, vdd), ylim=(vss, vdd))
        axis.legend()
        save_figure(fig, figure_dir / f"{test}_butterfly")
    return {"deck": test, "test": test, "analysis_status": "ok", "vdd_v": vdd, "vss_v": vss, "snm_v": snm}


def write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def plot_summary(rows: list[dict[str, object]], figure_dir: Path) -> None:
    candidates = [("write0", "write_cell_delay_s", "写 0 单元延迟 / ps"), ("write1", "write_cell_delay_s", "写 1 单元延迟 / ps")]
    labels, values = [], []
    for test, key, label in candidates:
        row = next((item for item in rows if item.get("test") == test and item.get("analysis_status") == "ok"), None)
        if row is not None and isinstance(row.get(key), (int, float)) and math.isfinite(float(row[key])):
            labels.append(label)
            values.append(float(row[key]) * 1e12)
    if not values:
        return
    fig, axis = plt.subplots(figsize=(6.2, 3.8))
    bars = axis.bar(labels, values, color=["#4477AA", "#CC6677", "#AA4499"][: len(values)])
    axis.set_ylabel("时延 / ps")
    axis.set_title("SRAM 单元读写时延汇总")
    for bar, value in zip(bars, values):
        axis.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{value:.2f}", ha="center", va="bottom", fontsize=8)
    save_figure(fig, figure_dir / "delay_summary")


def main() -> int:
    args = parse_args()
    decks = collect_decks(args.input)
    output = args.output.resolve()
    raw_dir, data_dir, figure_dir = output / "raw", output / "data", output / "figures"
    for directory in (raw_dir, data_dir, figure_dir):
        directory.mkdir(parents=True, exist_ok=True)
    hspice = find_hspice(args.hspice_cmd, args.install_dir)
    configure_plot_style()

    status_rows: list[dict[str, object]] = []
    metric_rows: list[dict[str, object]] = []
    snm_curves: dict[str, dict[str, np.ndarray | float | str]] = {}
    for deck in decks:
        run = run_one(deck, raw_dir, hspice, args.license_server, args.rerun, args.dry_run)
        test = test_name(deck)
        return_code = int(run["return_code"] or 0)
        status_rows.append({
            "deck": deck.name,
            "test": test,
            "return_code": return_code,
            "reused": run.get("reused", False),
            "model_numerical_error": run.get("model_numerical_error", False),
            "listing": run["listing"],
            "run_dir": run["run_dir"],
        })
        print(f"{deck.name}: {'reused' if run.get('reused') else 'ran'} (return={return_code})")
        if args.dry_run or return_code != 0 or run.get("model_numerical_error", False):
            if args.dry_run:
                analysis_status = "not_analyzed"
            elif run.get("model_numerical_error", False):
                analysis_status = "model_numerical_error"
            else:
                analysis_status = "hspice_failed"
            metric_rows.append({"deck": deck.name, "test": test, "analysis_status": analysis_status})
            continue
        listing = Path(str(run["listing"]))
        if not listing.is_file():
            metric_rows.append({"deck": deck.name, "test": test, "analysis_status": "missing_listing"})
            continue
        if test in {"hold", "read0", "read1", "write0", "write1"}:
            metrics = extract_transient(deck, listing, data_dir, figure_dir, not args.no_plot)
        elif test in {"wtrip0", "wtrip1"}:
            metrics = extract_write_trip(deck, listing, data_dir)
        elif test in {"hsnm", "hsnm_qb", "rsnm", "rsnm_qb"}:
            curve = extract_snm_curve(deck, listing, data_dir)
            snm_curves[test] = curve
            metrics = {key: value for key, value in curve.items() if not isinstance(value, np.ndarray)}
        else:
            metrics = {"analysis_status": "hspice_ok"}
        metric_rows.append({"deck": deck.name, "test": test, **metrics})

    for test in ("hsnm", "rsnm"):
        first, second = snm_curves.get(test), snm_curves.get(f"{test}_qb")
        if first is not None or second is not None:
            metric_rows.append(
                summarize_snm_pair(
                    test,
                    first if first is not None else {"analysis_status": "missing"},
                    second if second is not None else {"analysis_status": "missing"},
                    data_dir,
                    figure_dir,
                    not args.no_plot,
                )
            )

    write_rows(output / "run_status.csv", status_rows)
    write_rows(data_dir / "summary_metrics.csv", metric_rows)
    if not args.no_plot:
        plot_summary(metric_rows, figure_dir)
    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "input": str(Path(args.input).resolve()),
        "output": str(output),
        "hspice": str(hspice),
        "license_server": args.license_server,
        "decks": [run for run in status_rows],
    }
    (output / "run_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    failures = sum(1 for row in status_rows if int(row["return_code"]) != 0)
    print(f"Raw HSPICE results: {raw_dir}")
    print(f"CSV data: {data_dir}")
    print(f"Figures: {figure_dir}")
    print(f"Metric summary: {data_dir / 'summary_metrics.csv'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
