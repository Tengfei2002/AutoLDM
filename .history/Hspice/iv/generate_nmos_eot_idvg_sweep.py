#!/usr/bin/env python3
"""Generate NMOS Id-Vg HSPICE decks with EOT_0 instance overrides."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
IV_DIR = ROOT / "Hspice" / "iv"
TEMPLATE = IV_DIR / "single_va_nmos_idvg.sp"

EOT_VALUES_NM = [0.90, 0.95, 1.00, 1.05, 1.10, 1.15, 1.20]


def eot_tag(eot_nm: float) -> str:
    return f"EOT{eot_nm:.2f}".replace(".", "_")


def main() -> int:
    template = TEMPLATE.read_text(encoding="utf-8")
    instance = "Xmn d g s b cfet_nmos_lvt L='LCH' W='WDEV' NF='NFDEV'"
    if instance not in template:
        raise SystemExit(f"cannot find expected instance line in {TEMPLATE}")

    for eot_nm in EOT_VALUES_NM:
        tag = eot_tag(eot_nm)
        eot_m = eot_nm * 1e-9
        deck = template.replace(
            "* Single Verilog-A NMOS Id-Vg sweep family for cfet_nmos_lvt.va.",
            f"* Single Verilog-A NMOS Id-Vg sweep family for cfet_nmos_lvt.va, {tag}.",
        )
        deck = deck.replace(
            instance,
            instance + f" EOT_0={eot_m:.2e}",
        )
        deck = deck.replace(
            "* PLOT_KIND idvg",
            f"* PLOT_KIND idvg\n* PLOT_EOT_0 {eot_m:.2e}",
        )
        out = IV_DIR / f"single_va_nmos_idvg_{tag}.sp"
        out.write_text(deck, encoding="utf-8")
        print(f"{eot_nm:.2f} nm -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
