from __future__ import annotations

import importlib.util
import json
import math
import os
import re
import shutil
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import differential_evolution, minimize


ROOT = Path(__file__).resolve().parents[2]
HSPICE_DIR = ROOT / "Hspice"
WORK_DIR = Path(__file__).resolve().parent
REF_DIR = HSPICE_DIR / ".ref_iv"
VA_TEMPLATE = HSPICE_DIR / "va" / "cfet_pmos_lvt.va"

DECK_DIR = WORK_DIR / "decks"
RESULT_DIR = WORK_DIR / "results"
DATA_DIR = WORK_DIR / "data"
FIG_DIR = WORK_DIR / "figures"

FIXED = {
    "L": 1.6e-8,
    "W": 2.5e-8,
    "NF": 1.0,
    # PMOS template value. Keep EOT fixed and only optimize the requested five compact-model knobs.
    "EOT_0": 7.6e-10,
}

DEFAULT_TUNABLE = {
    "U0": 3.0e-2,
    "XL": 1.2e-8,
    "DVTSHIFT": 0.0,
    "DeltaWGAA": 0.0,
    "DeltaTGAA": 0.0,
}

FLOAT_RE = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eEdD][-+]?\d+)?")


def load_base():
    base_path = HSPICE_DIR / "nfet_48nm_dualvd_fit" / "fit_nfet_48nm_dualvd.py"
    spec = importlib.util.spec_from_file_location("nfet_fit_base", base_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import base fitter: {base_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


base = load_base()


def ensure_dirs(clean: bool = False) -> None:
    if clean:
        for path in [DECK_DIR, RESULT_DIR, DATA_DIR, FIG_DIR]:
            if path.exists():
                shutil.rmtree(path)
    for path in [DECK_DIR, RESULT_DIR, DATA_DIR, FIG_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def read_ref() -> dict[float, pd.DataFrame]:
    refs = {
        0.05: REF_DIR / "pfet_idvg_0_05V_48nm.csv",
        0.70: REF_DIR / "pfet_idvg_0_70V_48nm.csv",
    }
    out: dict[float, pd.DataFrame] = {}
    for vd, path in refs.items():
        df = pd.read_csv(path)
        if list(df.columns)[:2] != ["Vg", "Id"]:
            raise ValueError(f"{path} must have columns Vg,Id")
        df = df[["Vg", "Id"]].astype(float).sort_values("Vg").reset_index(drop=True)
        if (df["Id"] <= 0).any():
            raise ValueError(f"{path} contains non-positive Id")
        out[vd] = df
    return out


def write_deck(tag: str, params: dict[str, float], vg_points: list[float]) -> Path:
    deck = DECK_DIR / f"{tag}.sp"
    rel_va = os.path.relpath(VA_TEMPLATE, DECK_DIR).replace("\\", "/")
    deck.write_text(
        f"""***********************************************************************
* 48 nm PFET dual-Vd Id-Vg fitting deck: {tag}
* CSV Vg is treated as negative gate voltage; CSV VD is treated as positive |VSD|.
***********************************************************************
.OPTION POST=2 INGOLD=2 PROBE NOMOD
.TEMP 25

.HDL "{rel_va}"

.PARAM LCH = {FIXED['L']:.12e}
.PARAM WDEV = {FIXED['W']:.12e}
.PARAM NFDEV = {FIXED['NF']:.12e}
.PARAM EOTFIX = {FIXED['EOT_0']:.12e}

Vd d 0 DC 0
Vg g 0 DC 0
Vs s 0 DC 0
Vb b 0 DC 0

Xmp d g s b cfet_pmos_lvt
+ L='LCH' W='WDEV' NF='NFDEV'
+ U0={params['U0']:.12e} XL={params['XL']:.12e} DVTSHIFT={params['DVTSHIFT']:.12e}
+ DeltaWGAA={params['DeltaWGAA']:.12e} DeltaTGAA={params['DeltaTGAA']:.12e}
+ EOT_0='EOTFIX'

.DC Vg POI {len(vg_points)} {" ".join(f"{v:.9g}" for v in vg_points)} SWEEP Vd POI 2 -0.05 -0.70
.PRINT DC V(g) V(d) I(Vd) PAR('ABS(I(Vd))')

.END
""",
        encoding="utf-8",
    )
    return deck


def parse_lis_table(lis: Path) -> pd.DataFrame:
    rows: list[tuple[float, float, float]] = []
    in_table = False
    for raw in lis.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if line == "x":
            in_table = True
            continue
        if in_table and line == "y":
            in_table = False
            continue
        if not in_table:
            continue
        nums = FLOAT_RE.findall(line.replace("D", "E").replace("d", "e"))
        if len(nums) < 5:
            continue
        vals = [float(s.replace("D", "E").replace("d", "e")) for s in nums[:5]]
        vg = vals[1]
        vd_abs = abs(vals[2])
        ids = abs(vals[4])
        if math.isfinite(vg) and math.isfinite(vd_abs) and math.isfinite(ids):
            rows.append((vg, vd_abs, ids))
    if not rows:
        raise RuntimeError(f"No .PRINT DC table parsed from {lis}")
    df = pd.DataFrame(rows, columns=["Vg", "Vd", "Id_model"])
    df["Vd_key"] = np.where(np.abs(df["Vd"] - 0.05) < np.abs(df["Vd"] - 0.70), 0.05, 0.70)
    return df


def simulate(tag: str, params: dict[str, float], vg_points: list[float]) -> pd.DataFrame:
    deck = write_deck(tag, params, vg_points)
    lis = base.run_hspice(deck, tag)
    return parse_lis_table(lis)


def replace_parameter_line(text: str, name: str, value: float) -> str:
    pattern = re.compile(rf"(^\s*parameter\s+real\s+{re.escape(name)}\s*=\s*)([^;]+)(;.*$)", re.MULTILINE)
    text_new, count = pattern.subn(rf"\g<1>{value:.12e}\g<3>", text, count=1)
    if count != 1:
        raise RuntimeError(f"Could not replace parameter {name}")
    return text_new


def write_fitted_va(params: dict[str, float]) -> Path:
    text = VA_TEMPLATE.read_text(encoding="utf-8", errors="ignore")
    for name, value in {**FIXED, **params}.items():
        text = replace_parameter_line(text, name, value)
    out = WORK_DIR / "cfet_pmos_lvt_48nm_dualvd_fit.va"
    out.write_text(text, encoding="utf-8")
    return out


def plot_results(comp: pd.DataFrame) -> None:
    colors = {0.05: "#1f77b4", 0.70: "#d62728"}
    labels = {0.05: "|VSD|=0.05 V", 0.70: "|VSD|=0.70 V"}
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.2), constrained_layout=True)
    for vd in [0.05, 0.70]:
        sub = comp[comp["Vd"] == vd].sort_values("Vg")
        axes[0].plot(sub["Vg"], sub["Id"], "o", color=colors[vd], ms=4.5, label=f"Reference {labels[vd]}")
        axes[0].plot(sub["Vg"], sub["Id_model"], "-", color=colors[vd], lw=2.0, label=f"Fitted VA {labels[vd]}")
        axes[1].plot(sub["Vg"], sub["log_error_dec"], "o-", color=colors[vd], ms=4.0, lw=1.6, label=labels[vd])
    axes[0].set_yscale("log")
    axes[0].set_xlabel("Gate voltage Vg (V)")
    axes[0].set_ylabel("Drain current |Id| (A, log scale)")
    axes[0].set_title("PFET simultaneous dual-|VSD| Id-Vg fit")
    axes[0].grid(True, which="both", ls=":", alpha=0.55)
    axes[0].legend(fontsize=8)
    axes[1].axhline(0, color="black", lw=1.0)
    axes[1].axhline(0.3, color="gray", lw=0.9, ls="--")
    axes[1].axhline(-0.3, color="gray", lw=0.9, ls="--")
    axes[1].set_xlabel("Gate voltage Vg (V)")
    axes[1].set_ylabel("log10(Id_model) - log10(Id_ref) (decade)")
    axes[1].set_title("Point-wise log-domain residual")
    axes[1].grid(True, ls=":", alpha=0.55)
    axes[1].legend(fontsize=8)
    for ext in ["png", "svg"]:
        fig.savefig(FIG_DIR / f"pfet_48nm_dualvd_fit.{ext}", dpi=300)
    plt.close(fig)


def write_report(best, va_path: Path, comp: pd.DataFrame) -> Path:
    scale = 3.9e-5 / (0.44893 * 0.156)
    txt = f"""# 48 nm PFET 双 Vd 同参 Verilog-A 拟合报告

## 数据与电压方向

参考文件：

- `Hspice/.ref_iv/pfet_idvg_0_05V_48nm.csv`
- `Hspice/.ref_iv/pfet_idvg_0_70V_48nm.csv`

参考 Id 已按 `.ref_iv/id_scale_summary.md` 中记录的公式缩放：

```text
Id_scaled = Id_original / 0.44893 * 3.9E-5 / 0.156
scale = {scale:.12e}
```

PFET 仿真中将 CSV 的负 `Vg` 直接作为 gate 电压；将 CSV 中的 `VD=0.05/0.70 V` 解释为 `|VSD|`，HSPICE 中分别使用 `Vd=-0.05/-0.70 V`，并用 `abs(I(Vd))` 与参考 Id 对比。

## 固定参数

| 参数 | 数值 |
|---|---:|
| L | {FIXED['L']:.12e} |
| W | {FIXED['W']:.12e} |
| NF | {FIXED['NF']:.6g} |
| EOT_0 | {FIXED['EOT_0']:.12e} |

## 最佳可调参数

| 参数 | 拟合值 |
|---|---:|
| U0 | {best.params['U0']:.12e} |
| XL | {best.params['XL']:.12e} |
| DVTSHIFT | {best.params['DVTSHIFT']:.12e} |
| DeltaWGAA | {best.params['DeltaWGAA']:.12e} |
| DeltaTGAA | {best.params['DeltaTGAA']:.12e} |

## 拟合质量

| 指标 | 数值 |
|---|---:|
| loss | {best.loss:.6g} |
| log RMSE, all | {best.log_rmse_all:.6g} decade |
| log RMSE, VD=0.05 V | {best.log_rmse_vd005:.6g} decade |
| log RMSE, VD=0.70 V | {best.log_rmse_vd070:.6g} decade |
| high-current relative RMSE, VD=0.05 V | {best.rel_rmse_high_vd005:.6g} |
| high-current relative RMSE, VD=0.70 V | {best.rel_rmse_high_vd070:.6g} |
| max absolute log error | {best.max_abs_log_err:.6g} decade |

![[figures/pfet_48nm_dualvd_fit.png]]

拟合后的 VA 文件副本：`{va_path.name}`。
"""
    path = WORK_DIR / "pfet_48nm_dualvd_fit_report.md"
    path.write_text(txt, encoding="utf-8")
    return path


def patch_base_globals() -> None:
    base.WORK_DIR = WORK_DIR
    base.DECK_DIR = DECK_DIR
    base.RESULT_DIR = RESULT_DIR
    base.DATA_DIR = DATA_DIR
    base.FIG_DIR = FIG_DIR
    base.VA_TEMPLATE = VA_TEMPLATE
    base.FIXED = FIXED
    base.DEFAULT_TUNABLE = DEFAULT_TUNABLE
    base.simulate = simulate


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--max-evals", type=int, default=160)
    parser.add_argument("--seed", type=int, default=31)
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()

    ensure_dirs(clean=args.clean)
    patch_base_globals()
    refs = read_ref()
    runner = base.FitRunner(refs, max_evals=args.max_evals)
    runner.objective(base.params_to_vec(DEFAULT_TUNABLE))

    remaining = max(0, args.max_evals - runner.counter)
    if remaining > 0:
        popsize = 4
        maxiter = max(1, min(4, remaining // (popsize * len(base.BOUNDS))))
        differential_evolution(
            runner.objective,
            bounds=base.BOUNDS,
            seed=args.seed,
            popsize=popsize,
            maxiter=maxiter,
            polish=False,
            tol=0.03,
            updating="immediate",
            workers=1,
        )
        if runner.best_result is not None and runner.counter < args.max_evals:
            minimize(
                runner.objective,
                base.params_to_vec(runner.best_result.params),
                method="Nelder-Mead",
                options={"maxfev": args.max_evals - runner.counter, "xatol": 0.02, "fatol": 0.01},
            )

    if runner.best_result is None or runner.best_comp is None:
        raise RuntimeError("No successful PFET HSPICE candidate")

    best = runner.best_result
    comp = runner.best_comp.sort_values(["Vd", "Vg"]).reset_index(drop=True)
    comp.to_csv(DATA_DIR / "best_fit_points.csv", index=False)
    va_path = write_fitted_va(best.params)
    plot_results(comp)
    payload = {
        "best_tag": best.tag,
        "fixed": FIXED,
        "params": best.params,
        "metrics": {
            "loss": best.loss,
            "log_rmse_all": best.log_rmse_all,
            "log_rmse_vd005": best.log_rmse_vd005,
            "log_rmse_vd070": best.log_rmse_vd070,
            "rel_rmse_high_vd005": best.rel_rmse_high_vd005,
            "rel_rmse_high_vd070": best.rel_rmse_high_vd070,
            "max_abs_log_err": best.max_abs_log_err,
        },
    }
    (WORK_DIR / "best_params.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    report = write_report(best, va_path, comp)
    print(f"[done] best={best.tag} loss={best.loss:.6g}")
    print(f"[done] report={report}")
    print(f"[done] fitted_va={va_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
