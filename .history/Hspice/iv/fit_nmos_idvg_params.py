#!/usr/bin/env python3
"""Fit NMOS Verilog-A Id-Vg to WT CFET CSV without changing W or L.

The flow keeps the original VA file unchanged. Candidate parameters are
overridden on the HSPICE instance line, and each candidate keeps its own
deck, HSPICE result folder, metrics row, and final comparison plots.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
IV_DIR = ROOT / "Hspice" / "iv"
FLOW_RUNNER = ROOT / "Hspice" / "iv_flow" / "run_hspice.py"
CSV_PATH = ROOT / "Hspice" / "wt_cfet" / "CFET_N4.40_14000.csv"
WORK_DIR = IV_DIR / "fit_nmos_idvg_vmax1"
DECK_DIR = WORK_DIR / "decks"
RESULTS_DIR = WORK_DIR / "results"
PNG_DIR = IV_DIR / "png"

FLOAT_RE = re.compile(r"^[+-]?(?:(?:\d+\.\d*)|(?:\.\d+)|(?:\d+))(?:[eE][+-]?\d+)?$")

FIXED_L = 1.6e-8
FIXED_W = 2.5e-8
FIXED_NF = 1.0
FIT_VMAX = 1.0


@dataclass(frozen=True)
class Candidate:
    tag: str
    round_name: str
    u0: float
    xl: float
    dvtshift: float
    delta_wgaa: float
    delta_tgaa: float
    eot_0: float


@dataclass
class Metrics:
    tag: str
    round_name: str
    loss: float
    log_rmse_all: float
    log_rmse_low: float
    log_rmse_mid: float
    rel_rmse_high: float
    lin_rmse: float
    max_rel_err_high: float
    status: str


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
    order = np.argsort(xs)
    return np.asarray(xs)[order], np.maximum(np.asarray(ys)[order], 1e-18)


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


def deck_text(c: Candidate) -> str:
    return f"""***********************************************************************
* NMOS Id-Vg fitting candidate {c.tag}
* W and L are fixed. Other instance parameters are swept.
***********************************************************************
.OPTION POST=2 INGOLD=2 PROBE NOMOD
.TEMP 25

.HDL "../../../va/cfet_nmos_lvt.va"

.PARAM VMAX = {FIT_VMAX:.6g}
.PARAM VG_STEP = 0.002
.PARAM LCH = {FIXED_L:.6e}
.PARAM WDEV = {FIXED_W:.6e}
.PARAM NFDEV = {FIXED_NF:.6g}

Vd d 0 DC 0
Vg g 0 DC 0
Vs s 0 DC 0
Vb b 0 DC 0

Xmn d g s b cfet_nmos_lvt
+ L='LCH' W='WDEV' NF='NFDEV'
+ U0={c.u0:.8e} XL={c.xl:.8e} DVTSHIFT={c.dvtshift:.8e}
+ DeltaWGAA={c.delta_wgaa:.8e} DeltaTGAA={c.delta_tgaa:.8e}
+ EOT_0={c.eot_0:.8e}

.DC Vg 0 'VMAX' 'VG_STEP' SWEEP Vd POI 1 0.05
.PRINT DC V(g) V(d) I(Vd) PAR('-I(Vd)')

.END
"""


def run_candidate(c: Candidate, reuse: bool) -> Path:
    DECK_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    deck = DECK_DIR / f"{c.tag}.sp"
    lis_path = RESULTS_DIR / c.tag / f"{c.tag}.lis"
    if reuse and lis_path.exists():
        return lis_path

    deck.write_text(deck_text(c), encoding="utf-8")
    cmd = [
        sys.executable,
        str(FLOW_RUNNER),
        str(deck),
        "--results-dir",
        str(RESULTS_DIR),
        "--run-name",
        c.tag,
    ]
    completed = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    log_path = RESULTS_DIR / c.tag / "runner_stdout_stderr.txt"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        completed.stdout + "\n--- STDERR ---\n" + completed.stderr,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError(f"HSPICE failed for {c.tag}; see {log_path}")
    return lis_path


def compute_metrics(c: Candidate, lis_path: Path, csv_vg: np.ndarray, csv_id: np.ndarray) -> tuple[Metrics, np.ndarray, np.ndarray]:
    blocks = parse_hspice_dc_blocks(lis_path)
    if not blocks:
        raise RuntimeError(f"no DC blocks parsed from {lis_path}")
    block = blocks[0]
    va_vg = np.abs(block[:, 0])
    va_id = np.maximum(np.abs(block[:, -1]), 1e-18)
    order = np.argsort(va_vg)
    va_vg = va_vg[order]
    va_id = va_id[order]

    mask = (csv_vg >= float(np.min(va_vg))) & (csv_vg <= float(np.max(va_vg)))
    fit_vg = csv_vg[mask]
    fit_csv = csv_id[mask]
    fit_va = np.maximum(np.interp(fit_vg, va_vg, va_id), 1e-18)

    log_err = np.log10(fit_va) - np.log10(fit_csv)
    low = fit_csv < 1e-7
    mid = (fit_csv >= 1e-7) & (fit_csv < 1e-5)
    high = fit_csv >= 1e-5

    log_rmse_all = float(np.sqrt(np.mean(log_err**2)))
    log_rmse_low = float(np.sqrt(np.mean(log_err[low] ** 2))) if np.any(low) else math.nan
    log_rmse_mid = float(np.sqrt(np.mean(log_err[mid] ** 2))) if np.any(mid) else math.nan
    rel_high = (fit_va[high] - fit_csv[high]) / np.maximum(fit_csv[high], 1e-18)
    rel_rmse_high = float(np.sqrt(np.mean(rel_high**2))) if np.any(high) else math.nan
    max_rel_err_high = float(np.max(np.abs(rel_high))) if np.any(high) else math.nan
    lin_rmse = float(np.sqrt(np.mean((fit_va - fit_csv) ** 2)))

    high_term = 0.0 if math.isnan(rel_rmse_high) else rel_rmse_high
    loss = log_rmse_all + 0.25 * high_term
    metrics = Metrics(
        tag=c.tag,
        round_name=c.round_name,
        loss=loss,
        log_rmse_all=log_rmse_all,
        log_rmse_low=log_rmse_low,
        log_rmse_mid=log_rmse_mid,
        rel_rmse_high=rel_rmse_high,
        lin_rmse=lin_rmse,
        max_rel_err_high=max_rel_err_high,
        status="ok",
    )
    return metrics, va_vg, va_id


def coarse_candidates() -> list[Candidate]:
    candidates: list[Candidate] = []
    idx = 0
    for eot_nm in [0.85, 0.90, 0.95, 1.05]:
        for u0 in [0.010, 0.015, 0.020, 0.025, 0.030]:
            for dvt in [0.00, 0.04, 0.08, 0.12]:
                candidates.append(
                    Candidate(
                        tag=f"fit_c{idx:03d}",
                        round_name="coarse",
                        u0=u0,
                        xl=1.2e-8,
                        dvtshift=dvt,
                        delta_wgaa=0.0,
                        delta_tgaa=0.0,
                        eot_0=eot_nm * 1e-9,
                    )
                )
                idx += 1
    return candidates


def local_candidates(best: Candidate, start_idx: int) -> list[Candidate]:
    candidates: list[Candidate] = []
    idx = start_idx
    eot_values = sorted({best.eot_0 * x for x in [0.95, 1.0, 1.05]})
    u0_values = sorted({best.u0 * x for x in [0.8, 1.0, 1.2]})
    dvt_values = sorted({max(-0.02, best.dvtshift + x) for x in [-0.02, 0.0, 0.02]})
    xl_values = sorted({best.xl, 1.6e-8, 2.0e-8})
    delta_pairs = [(0.0, 0.0), (-2e-9, 0.0), (0.0, -1e-9), (-2e-9, -1e-9)]

    for eot in eot_values:
        for u0 in u0_values:
            for dvt in dvt_values:
                for xl in xl_values:
                    for dw, dt in delta_pairs:
                        if u0 <= 0 or eot <= 0:
                            continue
                        if FIXED_W + dw <= 1e-9 or 5.0e-9 + dt <= 1e-9:
                            continue
                        candidates.append(
                            Candidate(
                                tag=f"fit_l{idx:03d}",
                                round_name="local",
                                u0=u0,
                                xl=xl,
                                dvtshift=dvt,
                                delta_wgaa=dw,
                                delta_tgaa=dt,
                                eot_0=eot,
                            )
                        )
                        idx += 1
    return candidates


def choose_local_candidates(candidates: list[Candidate], max_local: int) -> list[Candidate]:
    if len(candidates) <= max_local:
        return candidates
    indices = np.linspace(0, len(candidates) - 1, max_local, dtype=int)
    selected: list[Candidate] = []
    seen: set[int] = set()
    for idx in indices:
        if int(idx) in seen:
            continue
        seen.add(int(idx))
        selected.append(candidates[int(idx)])
    return selected


def write_summary(rows: list[tuple[Candidate, Metrics]]) -> None:
    summary = WORK_DIR / "fit_summary.csv"
    fieldnames = list(asdict(rows[0][0]).keys()) + [
        "loss",
        "log_rmse_all",
        "log_rmse_low",
        "log_rmse_mid",
        "rel_rmse_high",
        "lin_rmse",
        "max_rel_err_high",
        "status",
    ]
    with summary.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for c, m in sorted(rows, key=lambda item: item[1].loss):
            row = asdict(c)
            row.update(asdict(m))
            writer.writerow(row)
    print(f"Wrote: {summary}")


def plot_best(
    best: Candidate,
    best_metrics: Metrics,
    best_vg: np.ndarray,
    best_id: np.ndarray,
    csv_vg: np.ndarray,
    csv_id: np.ndarray,
    file_stem: str,
) -> None:
    PNG_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    curve_csv = WORK_DIR / f"{file_stem}_curve.csv"
    with curve_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["vg", "id_va_best", "id_csv_interp"])
        mask = (csv_vg >= float(np.min(best_vg))) & (csv_vg <= float(np.max(best_vg)))
        csv_interp_vg = csv_vg[mask]
        csv_interp_id = csv_id[mask]
        va_interp_id = np.interp(csv_interp_vg, best_vg, best_id)
        for x, y_va, y_csv in zip(csv_interp_vg, va_interp_id, csv_interp_id):
            writer.writerow([f"{x:.8e}", f"{y_va:.8e}", f"{y_csv:.8e}"])

    best_json = WORK_DIR / f"{file_stem}_params.json"
    best_json.write_text(
        json.dumps(
            {
                "candidate": asdict(best),
                "metrics": asdict(best_metrics),
                "fixed": {"L": FIXED_L, "W": FIXED_W, "NF": FIXED_NF},
                "fit_vmax": FIT_VMAX,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

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
            "lines.linewidth": 2.0,
            "font.family": "DejaVu Sans",
        }
    )

    for logy in [False, True]:
        fig, ax = plt.subplots(figsize=(6.8, 4.6))
        if logy:
            ax.semilogy(best_vg, best_id, label=f"Best VA {best.tag}")
            ax.semilogy(csv_vg, csv_id, "o", markersize=4.0, markerfacecolor="none", markeredgecolor="black", label="WT CFET CSV")
            ax.set_ylabel("ID (A), log scale")
            suffix = "_logy"
        else:
            ax.plot(best_vg, best_id, label=f"Best VA {best.tag}")
            ax.plot(csv_vg, csv_id, "o", markersize=4.0, markerfacecolor="none", markeredgecolor="black", linestyle="none", label="WT CFET CSV")
            ax.set_ylabel("ID (A)")
            suffix = ""
        ax.set_xlabel("VGS (V)")
        ax.set_xlim(0, max(0.7, float(np.nanmax(csv_vg))))
        ax.set_title("Best NMOS Id-Vg Fit, W/L fixed, VDS=0.05 V")
        ax.legend(frameon=False)
        fig.tight_layout()
        out = PNG_DIR / f"compare_wt_cfet_vs_va_nmos_idvg_{file_stem}{suffix}.png"
        fig.savefig(out, bbox_inches="tight")
        print(f"Wrote: {out}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run automated NMOS Id-Vg fitting.")
    parser.add_argument("--max-local", type=int, default=80, help="Maximum local candidates after coarse sweep.")
    parser.add_argument("--reuse", action="store_true", help="Reuse existing HSPICE listings when present.")
    args = parser.parse_args()

    csv_vg, csv_id = read_csv_curve()
    rows: list[tuple[Candidate, Metrics]] = []
    curves: dict[str, tuple[np.ndarray, np.ndarray]] = {}

    candidates = coarse_candidates()
    print(f"Coarse candidates: {len(candidates)}")
    for i, c in enumerate(candidates, start=1):
        print(f"[coarse {i}/{len(candidates)}] {c.tag}")
        try:
            lis = run_candidate(c, reuse=args.reuse)
            metrics, va_vg, va_id = compute_metrics(c, lis, csv_vg, csv_id)
            curves[c.tag] = (va_vg, va_id)
        except Exception as exc:
            metrics = Metrics(c.tag, c.round_name, math.inf, math.inf, math.nan, math.nan, math.nan, math.nan, math.nan, f"failed: {exc}")
        rows.append((c, metrics))

    best_coarse, _ = min(rows, key=lambda item: item[1].loss)
    local = choose_local_candidates(
        local_candidates(best_coarse, start_idx=len(candidates)),
        args.max_local,
    )
    print(f"Local candidates: {len(local)} around {best_coarse.tag}")
    for i, c in enumerate(local, start=1):
        print(f"[local {i}/{len(local)}] {c.tag}")
        try:
            lis = run_candidate(c, reuse=args.reuse)
            metrics, va_vg, va_id = compute_metrics(c, lis, csv_vg, csv_id)
            curves[c.tag] = (va_vg, va_id)
        except Exception as exc:
            metrics = Metrics(c.tag, c.round_name, math.inf, math.inf, math.nan, math.nan, math.nan, math.nan, math.nan, f"failed: {exc}")
        rows.append((c, metrics))

    write_summary(rows)
    best, best_metrics = min(rows, key=lambda item: item[1].loss)
    best_vg, best_id = curves[best.tag]
    plot_best(best, best_metrics, best_vg, best_id, csv_vg, csv_id, "fit_best_vmax1")

    def visual_loss(item: tuple[Candidate, Metrics]) -> float:
        metric = item[1]
        high = 0.0 if math.isnan(metric.rel_rmse_high) else metric.rel_rmse_high
        return metric.log_rmse_all + 0.8 * high

    visual_best, visual_metrics = min(rows, key=visual_loss)
    visual_vg, visual_id = curves[visual_best.tag]
    plot_best(
        visual_best,
        visual_metrics,
        visual_vg,
        visual_id,
        csv_vg,
        csv_id,
        "fit_visual_vmax1",
    )
    print("Best:")
    print(json.dumps({"candidate": asdict(best), "metrics": asdict(best_metrics)}, indent=2))
    print("Visual/high-current best:")
    print(json.dumps({"candidate": asdict(visual_best), "metrics": asdict(visual_metrics)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
