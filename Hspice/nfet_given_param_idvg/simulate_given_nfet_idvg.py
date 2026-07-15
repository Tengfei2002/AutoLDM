from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
HSPICE_DIR = ROOT / "Hspice"
WORK_DIR = Path(__file__).resolve().parent
DECK_DIR = WORK_DIR / "decks"
RESULT_DIR = WORK_DIR / "results"
DATA_DIR = WORK_DIR / "data"
FIG_DIR = WORK_DIR / "figures"
VA_TEMPLATE = HSPICE_DIR / "va" / "cfet_nmos_lvt.va"
REF_DIR = HSPICE_DIR / ".ref_iv"
HSPICE_EXE = Path(r"C:\synopsys\Hspice_P-2019.06-SP1-1\WIN64\hspice.com")

PARAMS = {
    "L": 1.6e-8,
    "W": 3.5e-8,
    "NF": 1.0,
    "U0": 3.0e-2,
    "XL": 1.2e-8,
    "DVTSHIFT": 0.0,
    "DeltaWGAA": 0.0,
    "DeltaTGAA": 0.0,
    "EOT_0": 1.1e-9,
}

FLOAT_RE = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eEdD][-+]?\d+)?")


def ensure_dirs() -> None:
    for path in [DECK_DIR, RESULT_DIR, DATA_DIR, FIG_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def write_deck() -> Path:
    rel_va = os.path.relpath(VA_TEMPLATE, DECK_DIR).replace("\\", "/")
    vg_points = np.linspace(-0.12, 1.42, 309)
    vg_text = " ".join(f"{v:.7g}" for v in vg_points)
    deck = DECK_DIR / "given_nfet_idvg.sp"
    deck.write_text(
        f"""***********************************************************************
* Given NFET parameter Id-Vg simulation
***********************************************************************
.OPTION POST=2 INGOLD=2 PROBE NOMOD
.TEMP 25

.HDL "{rel_va}"

Vd d 0 DC 0
Vg g 0 DC 0
Vs s 0 DC 0
Vb b 0 DC 0

Xmn d g s b cfet_nmos_lvt
+ L={PARAMS['L']:.12e} W={PARAMS['W']:.12e} NF={PARAMS['NF']:.12e}
+ U0={PARAMS['U0']:.12e} XL={PARAMS['XL']:.12e} DVTSHIFT={PARAMS['DVTSHIFT']:.12e}
+ DeltaWGAA={PARAMS['DeltaWGAA']:.12e} DeltaTGAA={PARAMS['DeltaTGAA']:.12e}
+ EOT_0={PARAMS['EOT_0']:.12e}

.DC Vg POI {len(vg_points)} {vg_text} SWEEP Vd POI 2 0.05 0.70
.PRINT DC V(g) V(d) I(Vd) PAR('-I(Vd)')

.END
""",
        encoding="utf-8",
    )
    return deck


def run_hspice(deck: Path) -> Path:
    out_prefix = RESULT_DIR / "given_nfet_idvg"
    env = os.environ.copy()
    env.setdefault("SNPSLMD_LICENSE_FILE", "27000@LAPTOP-K9QP6UAM")
    env.setdefault("LM_LICENSE_FILE", "27000@LAPTOP-K9QP6UAM")
    proc = subprocess.run(
        [str(HSPICE_EXE), "-i", deck.name, "-o", str(out_prefix)],
        cwd=str(DECK_DIR),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=120,
    )
    (RESULT_DIR / "given_nfet_idvg.stdout.txt").write_text(proc.stdout, encoding="utf-8", errors="ignore")
    lis = RESULT_DIR / "given_nfet_idvg.lis"
    if proc.returncode != 0 or not lis.exists():
        raise RuntimeError(f"HSPICE failed, return={proc.returncode}")
    return lis


def parse_lis(lis: Path) -> pd.DataFrame:
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
        rows.append((vals[1], vals[2], abs(vals[4])))
    df = pd.DataFrame(rows, columns=["Vg", "Vd", "Id"])
    df["Vd"] = np.where(np.abs(df["Vd"] - 0.05) < np.abs(df["Vd"] - 0.70), 0.05, 0.70)
    return df.sort_values(["Vd", "Vg"]).reset_index(drop=True)


def load_ref() -> dict[float, pd.DataFrame]:
    refs = {}
    for vd, name in [(0.05, "nfet_idvg_0_05V_48nm.csv"), (0.70, "nfet_idvg_0_70V_48nm.csv")]:
        path = REF_DIR / name
        if path.exists():
            refs[vd] = pd.read_csv(path)
    return refs


def make_plots(df: pd.DataFrame, refs: dict[float, pd.DataFrame]) -> None:
    colors = {0.05: "#1f77b4", 0.70: "#d62728"}
    fig, ax = plt.subplots(figsize=(7.0, 4.8), constrained_layout=True)
    for vd in [0.05, 0.70]:
        sub = df[df["Vd"] == vd]
        ax.plot(sub["Vg"], sub["Id"], lw=2.1, color=colors[vd], label=f"HSPICE given params, VD={vd:.2f} V")
        if vd in refs:
            ax.plot(refs[vd]["Vg"], refs[vd]["Id"], "o", ms=4.0, color=colors[vd], alpha=0.65, label=f"Reference 48nm, VD={vd:.2f} V")
    ax.set_yscale("log")
    ax.set_xlabel("Gate voltage Vg (V)")
    ax.set_ylabel("Drain current Id (A from -I(Vd), log scale)")
    ax.set_title("NFET Id-Vg with specified VA parameters")
    ax.grid(True, which="both", ls=":", alpha=0.55)
    ax.legend(fontsize=8)
    for ext in ["png", "svg"]:
        fig.savefig(FIG_DIR / f"given_nfet_idvg.{ext}", dpi=300)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.0, 4.8), constrained_layout=True)
    for vd in [0.05, 0.70]:
        sub = df[df["Vd"] == vd]
        ax.plot(sub["Vg"], sub["Id"], lw=2.1, color=colors[vd], label=f"VD={vd:.2f} V")
    ax.set_xlabel("Gate voltage Vg (V)")
    ax.set_ylabel("Drain current Id (A from -I(Vd))")
    ax.set_title("NFET Id-Vg, linear scale")
    ax.grid(True, ls=":", alpha=0.55)
    ax.legend(fontsize=8)
    for ext in ["png", "svg"]:
        fig.savefig(FIG_DIR / f"given_nfet_idvg_linear.{ext}", dpi=300)
    plt.close(fig)


def write_summary(df: pd.DataFrame) -> None:
    rows = []
    for vd in [0.05, 0.70]:
        sub = df[df["Vd"] == vd]
        for vg in [0.0, 0.3, 0.7, 1.0, 1.2]:
            idx = int(np.argmin(np.abs(sub["Vg"].to_numpy() - vg)))
            r = sub.iloc[idx]
            rows.append({"Vd": vd, "target_Vg": vg, "sampled_Vg": r["Vg"], "Id": r["Id"]})
    pd.DataFrame(rows).to_csv(DATA_DIR / "given_nfet_idvg_key_points.csv", index=False)
    md = f"""# 指定 NFET 参数的 Id-Vg HSPICE 仿真

## 参数

| 参数 | 数值 |
|---|---:|
| L | {PARAMS['L']:.12e} |
| W | {PARAMS['W']:.12e} |
| NF | {PARAMS['NF']:.6g} |
| U0 | {PARAMS['U0']:.12e} |
| XL | {PARAMS['XL']:.12e} |
| DVTSHIFT | {PARAMS['DVTSHIFT']:.12e} |
| DeltaWGAA | {PARAMS['DeltaWGAA']:.12e} |
| DeltaTGAA | {PARAMS['DeltaTGAA']:.12e} |
| EOT_0 | {PARAMS['EOT_0']:.12e} |

## 仿真设置

- VA 模型：`Hspice/va/cfet_nmos_lvt.va`
- 温度：25 °C
- 扫描：`.DC Vg POI ... SWEEP Vd POI 2 0.05 0.70`
- Vg 范围：-0.12 V 到 1.42 V
- 输出电流：`Id = abs(-I(Vd))`

## 曲线

![[figures/given_nfet_idvg.png]]

![[figures/given_nfet_idvg_linear.png]]

## 输出文件

- `data/given_nfet_idvg.csv`：完整 Id-Vg 数据。
- `data/given_nfet_idvg_key_points.csv`：关键 Vg 采样点。
- `figures/given_nfet_idvg.png/.svg`：log 坐标 Id-Vg，并叠加 48nm 参考点。
- `figures/given_nfet_idvg_linear.png/.svg`：线性坐标 Id-Vg。
"""
    (WORK_DIR / "given_nfet_idvg_report.md").write_text(md, encoding="utf-8")


def main() -> int:
    ensure_dirs()
    deck = write_deck()
    lis = run_hspice(deck)
    df = parse_lis(lis)
    df.to_csv(DATA_DIR / "given_nfet_idvg.csv", index=False)
    refs = load_ref()
    make_plots(df, refs)
    write_summary(df)
    print(f"[done] csv={DATA_DIR / 'given_nfet_idvg.csv'}")
    print(f"[done] report={WORK_DIR / 'given_nfet_idvg_report.md'}")
    print(f"[done] figure={FIG_DIR / 'given_nfet_idvg.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
