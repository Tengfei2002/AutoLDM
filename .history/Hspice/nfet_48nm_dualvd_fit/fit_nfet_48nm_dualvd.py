from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import differential_evolution, minimize


ROOT = Path(__file__).resolve().parents[2]
HSPICE_DIR = ROOT / "Hspice"
WORK_DIR = Path(__file__).resolve().parent
REF_DIR = HSPICE_DIR / ".ref_iv"
VA_TEMPLATE = HSPICE_DIR / "va" / "cfet_nmos_lvt.va"
HSPICE_EXE = Path(r"C:\synopsys\Hspice_P-2019.06-SP1-1\WIN64\hspice.com")

DECK_DIR = WORK_DIR / "decks"
RESULT_DIR = WORK_DIR / "results"
DATA_DIR = WORK_DIR / "data"
FIG_DIR = WORK_DIR / "figures"

FIXED = {
    "L": 1.6e-8,
    "W": 2.5e-8,
    "NF": 1.0,
    "EOT_0": 7.9e-10,
}

DEFAULT_TUNABLE = {
    "U0": 3.0e-2,
    "XL": 1.2e-8,
    "DVTSHIFT": 0.0,
    "DeltaWGAA": 0.0,
    "DeltaTGAA": 0.0,
}

# Search variables are [log10(U0), XL_nm, DVTSHIFT, DeltaWGAA_nm, DeltaTGAA_nm].
# Bounds are intentionally broad enough to fit the supplied data, but constrained
# to keep the effective GAA geometry in a physically interpretable neighborhood.
BOUNDS = [
    (-4.0, 0.0),     # U0: 1e-4 ... 1.0 m^2/V/s
    (-5.0, 40.0),    # XL in nm
    (-0.8, 0.8),     # threshold shift in V-equivalent model parameter
    (-14.0, 15.0),   # DeltaWGAA in nm; W=25 nm, model nominal range 10-40 nm
    (-2.0, 2.0),     # DeltaTGAA in nm
]

FLOAT_RE = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eEdD][-+]?\d+)?")


@dataclass(frozen=True)
class EvalResult:
    tag: str
    params: dict[str, float]
    loss: float
    log_rmse_vd005: float
    log_rmse_vd070: float
    log_rmse_all: float
    rel_rmse_high_vd005: float
    rel_rmse_high_vd070: float
    max_abs_log_err: float
    status: str


def ensure_dirs(clean: bool = False) -> None:
    if clean:
        for path in [DECK_DIR, RESULT_DIR, DATA_DIR, FIG_DIR]:
            if path.exists():
                shutil.rmtree(path)
    for path in [DECK_DIR, RESULT_DIR, DATA_DIR, FIG_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def read_ref() -> dict[float, pd.DataFrame]:
    refs = {
        0.05: REF_DIR / "nfet_idvg_0_05V_48nm.csv",
        0.70: REF_DIR / "nfet_idvg_0_70V_48nm.csv",
    }
    out: dict[float, pd.DataFrame] = {}
    for vd, path in refs.items():
        df = pd.read_csv(path)
        if list(df.columns)[:2] != ["Vg", "Id"]:
            raise ValueError(f"{path} must have columns Vg,Id")
        df = df[["Vg", "Id"]].astype(float).sort_values("Vg").reset_index(drop=True)
        if (df["Id"] <= 0).any():
            raise ValueError(f"{path} contains non-positive Id; log-domain fitting requires Id>0")
        out[vd] = df
    return out


def union_vg_points(refs: dict[float, pd.DataFrame]) -> list[float]:
    vals = sorted({round(float(v), 9) for df in refs.values() for v in df["Vg"].values})
    return vals


def vec_to_params(x: np.ndarray | list[float]) -> dict[str, float]:
    x = np.asarray(x, dtype=float)
    return {
        "U0": float(10 ** x[0]),
        "XL": float(x[1] * 1e-9),
        "DVTSHIFT": float(x[2]),
        "DeltaWGAA": float(x[3] * 1e-9),
        "DeltaTGAA": float(x[4] * 1e-9),
    }


def params_to_vec(params: dict[str, float]) -> np.ndarray:
    return np.array(
        [
            math.log10(params["U0"]),
            params["XL"] / 1e-9,
            params["DVTSHIFT"],
            params["DeltaWGAA"] / 1e-9,
            params["DeltaTGAA"] / 1e-9,
        ],
        dtype=float,
    )


def fmt_spice_list(vals: list[float]) -> str:
    return " ".join(f"{v:.9g}" for v in vals)


def write_deck(tag: str, params: dict[str, float], vg_points: list[float]) -> Path:
    deck = DECK_DIR / f"{tag}.sp"
    rel_va = os.path.relpath(VA_TEMPLATE, DECK_DIR).replace("\\", "/")
    deck.write_text(
        f"""***********************************************************************
* 48 nm NFET dual-Vd Id-Vg fitting deck: {tag}
* Fixed: L={FIXED['L']:.8e}, W={FIXED['W']:.8e}, NF={FIXED['NF']:.1f}, EOT_0={FIXED['EOT_0']:.8e}
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

Xmn d g s b cfet_nmos_lvt
+ L='LCH' W='WDEV' NF='NFDEV'
+ U0={params['U0']:.12e} XL={params['XL']:.12e} DVTSHIFT={params['DVTSHIFT']:.12e}
+ DeltaWGAA={params['DeltaWGAA']:.12e} DeltaTGAA={params['DeltaTGAA']:.12e}
+ EOT_0='EOTFIX'

.DC Vg POI {len(vg_points)} {fmt_spice_list(vg_points)} SWEEP Vd POI 2 0.05 0.70
.PRINT DC V(g) V(d) I(Vd) PAR('-I(Vd)')

.END
""",
        encoding="utf-8",
    )
    return deck


def run_hspice(deck: Path, tag: str) -> Path:
    out_dir = RESULT_DIR / tag
    out_dir.mkdir(parents=True, exist_ok=True)
    out_prefix = out_dir / tag
    env = os.environ.copy()
    env.setdefault("SNPSLMD_LICENSE_FILE", "27000@LAPTOP-K9QP6UAM")
    env.setdefault("LM_LICENSE_FILE", "27000@LAPTOP-K9QP6UAM")
    cmd = [str(HSPICE_EXE), "-i", str(deck.name), "-o", str(out_prefix)]
    proc = subprocess.run(
        cmd,
        cwd=str(DECK_DIR),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=90,
    )
    log_path = out_dir / f"{tag}.stdout.txt"
    log_path.write_text(proc.stdout, encoding="utf-8", errors="ignore")
    lis = out_dir / f"{tag}.lis"
    if proc.returncode != 0 or not lis.exists():
        raise RuntimeError(f"HSPICE failed for {tag}; return={proc.returncode}; see {log_path}")
    return lis


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
        try:
            vals = [float(s.replace("D", "E").replace("d", "e")) for s in nums[:5]]
        except ValueError:
            continue
        vg = vals[1]
        vd = vals[2]
        ids = vals[4]
        if math.isfinite(vg) and math.isfinite(vd) and math.isfinite(ids):
            rows.append((vg, vd, abs(ids)))
    if not rows:
        raise RuntimeError(f"No .PRINT DC table parsed from {lis}")
    df = pd.DataFrame(rows, columns=["Vg", "Vd", "Id_model"])
    df["Vd_key"] = np.where(np.abs(df["Vd"] - 0.05) < np.abs(df["Vd"] - 0.70), 0.05, 0.70)
    return df


def simulate(tag: str, params: dict[str, float], vg_points: list[float]) -> pd.DataFrame:
    deck = write_deck(tag, params, vg_points)
    lis = run_hspice(deck, tag)
    return parse_lis_table(lis)


def compare_model_to_ref(model: pd.DataFrame, refs: dict[float, pd.DataFrame]) -> tuple[pd.DataFrame, dict[str, float]]:
    frames = []
    log_errs = []
    metrics: dict[str, float] = {}
    for vd, ref in refs.items():
        sub = model[model["Vd_key"] == vd].sort_values("Vg")
        if len(sub) < 2:
            raise RuntimeError(f"Model data missing Vd={vd}")
        id_interp = np.interp(ref["Vg"].values, sub["Vg"].values, sub["Id_model"].values)
        comp = ref.copy()
        comp["Vd"] = vd
        comp["Id_model"] = np.maximum(id_interp, 1e-300)
        comp["log10_Id_ref"] = np.log10(np.maximum(comp["Id"].values, 1e-300))
        comp["log10_Id_model"] = np.log10(comp["Id_model"].values)
        comp["log_error_dec"] = comp["log10_Id_model"] - comp["log10_Id_ref"]
        comp["rel_error"] = (comp["Id_model"] - comp["Id"]) / comp["Id"]
        frames.append(comp)

        err = comp["log_error_dec"].values
        log_errs.extend(err.tolist())
        metrics[f"log_rmse_vd{int(round(vd * 1000)):03d}"] = float(np.sqrt(np.mean(err * err)))
        high_mask = comp["Id"].values >= np.quantile(comp["Id"].values, 0.65)
        rel = comp.loc[high_mask, "rel_error"].values
        metrics[f"rel_rmse_high_vd{int(round(vd * 1000)):03d}"] = float(np.sqrt(np.mean(rel * rel)))
    all_comp = pd.concat(frames, ignore_index=True)
    all_err = np.asarray(log_errs, dtype=float)
    metrics["log_rmse_all"] = float(np.sqrt(np.mean(all_err * all_err)))
    metrics["max_abs_log_err"] = float(np.max(np.abs(all_err)))
    # Dominant objective: log-domain simultaneous fit. Add a small high-current
    # relative-error term so Ion magnitude is not ignored.
    metrics["loss"] = float(
        metrics["log_rmse_all"]
        + 0.15 * metrics["rel_rmse_high_vd050"]
        + 0.15 * metrics["rel_rmse_high_vd700"]
    )
    return all_comp, metrics


def replace_parameter_line(text: str, name: str, value: float) -> str:
    pattern = re.compile(rf"(^\s*parameter\s+real\s+{re.escape(name)}\s*=\s*)([^;]+)(;.*$)", re.MULTILINE)
    repl = rf"\g<1>{value:.12e}\g<3>"
    text_new, count = pattern.subn(repl, text, count=1)
    if count != 1:
        raise RuntimeError(f"Could not replace parameter {name} in VA template")
    return text_new


def write_fitted_va(params: dict[str, float]) -> Path:
    text = VA_TEMPLATE.read_text(encoding="utf-8", errors="ignore")
    for name, value in {**FIXED, **params}.items():
        text = replace_parameter_line(text, name, value)
    out = WORK_DIR / "cfet_nmos_lvt_48nm_dualvd_fit.va"
    out.write_text(text, encoding="utf-8")
    return out


class FitRunner:
    def __init__(self, refs: dict[float, pd.DataFrame], max_evals: int):
        self.refs = refs
        self.vg_points = union_vg_points(refs)
        self.max_evals = max_evals
        self.counter = 0
        self.cache: dict[tuple[float, ...], EvalResult] = {}
        self.summary_rows: list[dict[str, float | str]] = []
        self.best_comp: pd.DataFrame | None = None
        self.best_result: EvalResult | None = None
        self.best_model: pd.DataFrame | None = None

    def objective(self, x: np.ndarray) -> float:
        key = tuple(np.round(x.astype(float), 10))
        if key in self.cache:
            return self.cache[key].loss
        if self.counter >= self.max_evals:
            return 1e9
        tag = f"eval_{self.counter:04d}"
        self.counter += 1
        params = vec_to_params(x)
        try:
            model = simulate(tag, params, self.vg_points)
            comp, metrics = compare_model_to_ref(model, self.refs)
            result = EvalResult(
                tag=tag,
                params=params,
                loss=metrics["loss"],
                log_rmse_vd005=metrics["log_rmse_vd050"],
                log_rmse_vd070=metrics["log_rmse_vd700"],
                log_rmse_all=metrics["log_rmse_all"],
                rel_rmse_high_vd005=metrics["rel_rmse_high_vd050"],
                rel_rmse_high_vd070=metrics["rel_rmse_high_vd700"],
                max_abs_log_err=metrics["max_abs_log_err"],
                status="ok",
            )
        except Exception as exc:
            result = EvalResult(
                tag=tag,
                params=params,
                loss=1e8,
                log_rmse_vd005=float("nan"),
                log_rmse_vd070=float("nan"),
                log_rmse_all=float("nan"),
                rel_rmse_high_vd005=float("nan"),
                rel_rmse_high_vd070=float("nan"),
                max_abs_log_err=float("nan"),
                status=f"failed: {exc}",
            )
            comp = None
            model = None
        self.cache[key] = result
        row = {"tag": result.tag, **result.params, **{
            "loss": result.loss,
            "log_rmse_vd005": result.log_rmse_vd005,
            "log_rmse_vd070": result.log_rmse_vd070,
            "log_rmse_all": result.log_rmse_all,
            "rel_rmse_high_vd005": result.rel_rmse_high_vd005,
            "rel_rmse_high_vd070": result.rel_rmse_high_vd070,
            "max_abs_log_err": result.max_abs_log_err,
            "status": result.status,
        }}
        self.summary_rows.append(row)
        if result.status == "ok" and (self.best_result is None or result.loss < self.best_result.loss):
            self.best_result = result
            self.best_comp = comp
            self.best_model = model
            print(
                f"[best] {tag} loss={result.loss:.5g} log_rmse={result.log_rmse_all:.5g} "
                f"U0={params['U0']:.4g} XL={params['XL']:.3e} DVT={params['DVTSHIFT']:.4g} "
                f"DW={params['DeltaWGAA']:.3e} DT={params['DeltaTGAA']:.3e}",
                flush=True,
            )
        elif result.status == "ok":
            print(f"[eval] {tag} loss={result.loss:.5g}", flush=True)
        else:
            print(f"[fail] {tag} {result.status}", flush=True)
        self.write_summary()
        return result.loss

    def write_summary(self) -> None:
        if not self.summary_rows:
            return
        path = DATA_DIR / "fit_summary.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(self.summary_rows[0].keys()))
            writer.writeheader()
            writer.writerows(self.summary_rows)


def plot_results(comp: pd.DataFrame) -> None:
    colors = {0.05: "#1f77b4", 0.70: "#d62728"}
    labels = {0.05: "VD=0.05 V", 0.70: "VD=0.70 V"}

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.2), constrained_layout=True)
    for vd in [0.05, 0.70]:
        sub = comp[comp["Vd"] == vd].sort_values("Vg")
        axes[0].plot(sub["Vg"], sub["Id"], "o", color=colors[vd], ms=4.5, label=f"Reference {labels[vd]}")
        axes[0].plot(sub["Vg"], sub["Id_model"], "-", color=colors[vd], lw=2.0, label=f"Fitted VA {labels[vd]}")
        axes[1].plot(sub["Vg"], sub["log_error_dec"], "o-", color=colors[vd], ms=4.0, lw=1.6, label=labels[vd])
    axes[0].set_yscale("log")
    axes[0].set_xlabel("Gate voltage Vg (V)")
    axes[0].set_ylabel("Drain current Id (CSV unit, log scale)")
    axes[0].set_title("Simultaneous dual-Vd Id-Vg fit")
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
        fig.savefig(FIG_DIR / f"nfet_48nm_dualvd_fit.{ext}", dpi=300)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.4, 4.2), constrained_layout=True)
    for vd in [0.05, 0.70]:
        sub = comp[comp["Vd"] == vd].sort_values("Vg")
        ax.plot(sub["Vg"], sub["log_error_dec"], "o-", color=colors[vd], ms=4.0, lw=1.6, label=labels[vd])
    ax.axhline(0, color="black", lw=1.0)
    ax.axhline(0.1, color="gray", lw=0.9, ls="--")
    ax.axhline(-0.1, color="gray", lw=0.9, ls="--")
    ax.set_xlabel("Gate voltage Vg (V)")
    ax.set_ylabel("log10(Id_model) - log10(Id_ref) (decade)")
    ax.set_title("Log-domain residual")
    ax.grid(True, ls=":", alpha=0.55)
    ax.legend(fontsize=8)
    for ext in ["png", "svg"]:
        fig.savefig(FIG_DIR / f"nfet_48nm_dualvd_log_residual.{ext}", dpi=300)
    plt.close(fig)


def write_report(best: EvalResult, va_path: Path, comp: pd.DataFrame) -> Path:
    ref_ranges = []
    for vd in [0.05, 0.70]:
        sub = comp[comp["Vd"] == vd]
        ref_ranges.append(
            f"- VD={vd:.2f} V：Vg={sub['Vg'].min():.6g}–{sub['Vg'].max():.6g} V，"
            f"Id(ref)={sub['Id'].min():.6g}–{sub['Id'].max():.6g}"
        )
    quality_pass = (
        best.log_rmse_all <= 0.30
        and best.rel_rmse_high_vd005 <= 0.30
        and best.rel_rmse_high_vd070 <= 0.30
    )
    quality_status = "通过" if quality_pass else "未通过"
    vd070_hi = comp[comp["Vd"] == 0.70].sort_values("Vg").tail(1).iloc[0]
    vd005_hi = comp[comp["Vd"] == 0.05].sort_values("Vg").tail(1).iloc[0]
    quality_note = (
        "该参数集满足当前质量门限，可作为后续 SRAM/电路仿真的候选模型。"
        if quality_pass
        else (
            "该参数集仅代表当前搜索空间内的最小误差候选，不能作为有效的紧凑模型校准结果。"
            "主要证据是 log RMSE 仍接近 2 decade，且两条曲线高电流区相对 RMSE 接近 1。"
            "在 VD=0.70 V 的最高 Vg 点，参考 Id="
            f"{vd070_hi['Id']:.6g}，模型 Id={vd070_hi['Id_model']:.6g}；"
            "在 VD=0.05 V 的最高 Vg 点，参考 Id="
            f"{vd005_hi['Id']:.6g}，模型 Id={vd005_hi['Id_model']:.6g}。"
            "这说明当前 CSV 电流单位/归一化口径与 HSPICE 器件电流口径很可能不一致，"
            "或者仅调 U0、XL、DVTSHIFT、DeltaWGAA、DeltaTGAA 这 5 个参数不足以同时校准低电流区和强导通区。"
        )
    )
    txt = f"""# 48 nm NFET 双 Vd 同参 Verilog-A 拟合报告

## 1. 目标与数据

本流程使用 `Hspice/.ref_iv` 中 48 nm NFET 的两条 Id-Vg 参考曲线，在同一套 Verilog-A 实例参数下同时拟合：

{chr(10).join(ref_ranges)}

参考 CSV 的第二列 Id 已先按下式进行口径修正：

```text
Id_scaled = Id_original / 0.44893 * 3.9E-5 / 0.156
scale = {3.9e-5 / (0.44893 * 0.156):.12e}
```

`.ref_iv/backup_before_id_scale/` 中保留了缩放前的 CSV 备份；`.ref_iv/id_scale_summary.md` 记录了全部文件的缩放前后范围。本报告中的参考曲线和拟合误差均基于缩放后的 Id。

## 2. 固定参数与优化参数

固定参数：

| 参数 | 数值 |
|---|---:|
| L | {FIXED['L']:.12e} |
| W | {FIXED['W']:.12e} |
| NF | {FIXED['NF']:.6g} |
| EOT_0 | {FIXED['EOT_0']:.12e} |

优化参数：

| 参数 | 拟合值 |
|---|---:|
| U0 | {best.params['U0']:.12e} |
| XL | {best.params['XL']:.12e} |
| DVTSHIFT | {best.params['DVTSHIFT']:.12e} |
| DeltaWGAA | {best.params['DeltaWGAA']:.12e} |
| DeltaTGAA | {best.params['DeltaTGAA']:.12e} |

拟合后的 VA 文件：`{va_path.name}`。

## 3. 目标函数与计算方法

HSPICE 对同一个器件实例执行 `.DC Vg ... SWEEP Vd POI 2 0.05 0.70`。模型电流按参考 Vg 点插值后与 CSV 中的 Id 对比。主目标函数为两条曲线共同的 log-domain RMSE，并加入高电流区相对误差约束：

```text
log_error = log10(Id_model) - log10(Id_ref)
loss = RMSE(log_error_all)
       + 0.15 * RMSE(relative_error_high_current, VD=0.05)
       + 0.15 * RMSE(relative_error_high_current, VD=0.70)
```

采用 log-domain 的原因是 Id-Vg 曲线同时包含亚阈值区和强导通区，直接线性最小二乘会几乎只拟合大电流区。

## 4. 拟合结果

质量判定：**{quality_status}**。

{quality_note}

| 指标 | 数值 |
|---|---:|
| loss | {best.loss:.6g} |
| log RMSE, all | {best.log_rmse_all:.6g} decade |
| log RMSE, VD=0.05 V | {best.log_rmse_vd005:.6g} decade |
| log RMSE, VD=0.70 V | {best.log_rmse_vd070:.6g} decade |
| high-current relative RMSE, VD=0.05 V | {best.rel_rmse_high_vd005:.6g} |
| high-current relative RMSE, VD=0.70 V | {best.rel_rmse_high_vd070:.6g} |
| max absolute log error | {best.max_abs_log_err:.6g} decade |

![[figures/nfet_48nm_dualvd_fit.png]]

![[figures/nfet_48nm_dualvd_log_residual.png]]

## 5. 输出文件

- `data/fit_summary.csv`：全部候选参数和误差。
- `data/best_fit_points.csv`：参考点、模型点、相对误差和 log 误差。
- `best_params.json`：最佳参数、固定参数和误差指标。
- `cfet_nmos_lvt_48nm_dualvd_fit.va`：已写入固定参数和拟合参数的 VA 文件副本。
- `figures/nfet_48nm_dualvd_fit.png/.svg`：参考曲线与拟合曲线，以及点误差。
- `figures/nfet_48nm_dualvd_log_residual.png/.svg`：log-domain 残差。
"""
    path = WORK_DIR / "nfet_48nm_dualvd_fit_report.md"
    path.write_text(txt, encoding="utf-8")
    return path


def report_only() -> Path:
    payload = json.loads((WORK_DIR / "best_params.json").read_text(encoding="utf-8"))
    comp = pd.read_csv(DATA_DIR / "best_fit_points.csv")
    params = {k: float(v) for k, v in payload["params"].items()}
    metrics = payload["metrics"]
    best = EvalResult(
        tag=str(payload["best_tag"]),
        params=params,
        loss=float(metrics["loss"]),
        log_rmse_vd005=float(metrics["log_rmse_vd005"]),
        log_rmse_vd070=float(metrics["log_rmse_vd070"]),
        log_rmse_all=float(metrics["log_rmse_all"]),
        rel_rmse_high_vd005=float(metrics["rel_rmse_high_vd005"]),
        rel_rmse_high_vd070=float(metrics["rel_rmse_high_vd070"]),
        max_abs_log_err=float(metrics["max_abs_log_err"]),
        status="ok",
    )
    va_path = WORK_DIR / "cfet_nmos_lvt_48nm_dualvd_fit.va"
    plot_results(comp)
    return write_report(best, va_path, comp)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-evals", type=int, default=80)
    parser.add_argument("--seed", type=int, default=23)
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--skip-local", action="store_true")
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()

    if args.report_only:
        report = report_only()
        print(f"[done] report={report}", flush=True)
        return 0

    if not HSPICE_EXE.exists():
        raise FileNotFoundError(f"HSPICE executable not found: {HSPICE_EXE}")
    ensure_dirs(clean=args.clean)
    refs = read_ref()
    runner = FitRunner(refs, max_evals=args.max_evals)

    # Always evaluate the user-provided nominal parameter set first.
    x0 = params_to_vec(DEFAULT_TUNABLE)
    runner.objective(x0)

    remaining = max(0, args.max_evals - runner.counter)
    if remaining > 0:
        # differential_evolution does not accept a direct max-evaluation budget,
        # so choose a compact population/iteration count and let objective()
        # return a large penalty after the explicit budget is exhausted.
        popsize = 4
        maxiter = max(1, min(4, remaining // (popsize * len(BOUNDS))))
        result = differential_evolution(
            runner.objective,
            bounds=BOUNDS,
            seed=args.seed,
            popsize=popsize,
            maxiter=maxiter,
            polish=False,
            tol=0.03,
            updating="immediate",
            workers=1,
        )
        if (not args.skip_local) and runner.best_result is not None and runner.counter < args.max_evals:
            minimize(
                runner.objective,
                params_to_vec(runner.best_result.params),
                method="Nelder-Mead",
                options={
                    "maxfev": args.max_evals - runner.counter,
                    "xatol": 0.02,
                    "fatol": 0.01,
                    "disp": False,
                },
            )

    if runner.best_result is None or runner.best_comp is None:
        raise RuntimeError("No successful HSPICE candidate was produced")

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
        "reference_files": {
            "vd005": str(REF_DIR / "nfet_idvg_0_05V_48nm.csv"),
            "vd070": str(REF_DIR / "nfet_idvg_0_70V_48nm.csv"),
        },
    }
    (WORK_DIR / "best_params.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    report = write_report(best, va_path, comp)
    print(f"[done] best={best.tag} loss={best.loss:.6g}", flush=True)
    print(f"[done] report={report}", flush=True)
    print(f"[done] fitted_va={va_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
