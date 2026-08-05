from __future__ import annotations

import re
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


BASE = Path(__file__).resolve().parent
OUT_STEM = BASE / "ref_iv_idvg_all_curves"

plt.rcParams.update({
    "font.family": "Arial",
    "font.size": 9,
    "axes.labelsize": 10,
    "axes.titlesize": 11,
    "legend.fontsize": 7.5,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "axes.linewidth": 0.9,
    "lines.linewidth": 1.55,
    "svg.fonttype": "none",
})


def parse_name(path: Path) -> tuple[str, float, int]:
    match = re.match(r"(?P<dev>[np]fet)_idvg_(?P<vd>0_\d+)V_(?P<lg>\d+)nm\.csv$", path.name)
    if not match:
        raise ValueError(f"Unexpected file name: {path.name}")
    dev = match.group("dev").upper()
    vd = float(match.group("vd").replace("_", "."))
    lg = int(match.group("lg"))
    return dev, vd, lg


def main() -> None:
    csv_files = sorted(BASE.glob("*_idvg_*V_*nm.csv"))
    if not csv_files:
        raise SystemExit(f"No IV CSV files found in {BASE}")

    color_map = {
        ("NFET", 0.05): "#1f77b4",
        ("NFET", 0.70): "#d95f02",
        ("PFET", 0.05): "#2ca02c",
        ("PFET", 0.70): "#d62728",
    }
    linestyle_map = {
        44: "-",
        48: "--",
    }
    marker_map = {
        44: "o",
        48: "s",
    }

    fig, ax = plt.subplots(figsize=(7.2, 4.9))

    for path in csv_files:
        dev, vd, lg = parse_name(path)
        df = pd.read_csv(path)
        if list(df.columns[:2]) != ["Vg", "Id"]:
            raise ValueError(f"{path.name} must have first two columns Vg,Id")
        df = df[["Vg", "Id"]].dropna().sort_values("Vg")
        label = f"{dev}, Vd={vd:.2f} V, L={lg} nm"
        ax.semilogy(
            df["Vg"],
            df["Id"].abs(),
            color=color_map[(dev, vd)],
            linestyle=linestyle_map.get(lg, "-"),
            marker=marker_map.get(lg, "o"),
            markersize=3.2,
            markerfacecolor="white",
            markeredgewidth=0.75,
            label=label,
        )

    ax.set_title("Reference Id–Vg curves")
    ax.set_xlabel("Gate voltage, Vg (V)")
    ax.set_ylabel("|Drain current|, |Id| (A)")
    ax.grid(True, which="major", color="0.75", linewidth=0.65, alpha=0.65)
    ax.grid(True, which="minor", color="0.85", linewidth=0.45, alpha=0.45)
    ax.tick_params(direction="in", which="both", top=True, right=True)
    ax.legend(
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
        frameon=True,
        borderaxespad=0.0,
        handlelength=2.4,
    )
    fig.tight_layout()
    fig.savefig(OUT_STEM.with_suffix(".png"), dpi=300, bbox_inches="tight")
    fig.savefig(OUT_STEM.with_suffix(".svg"), bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
