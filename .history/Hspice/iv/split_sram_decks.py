#!/usr/bin/env python3
"""Split generated SRAM deck into independent transient and DC/SNM decks."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "Hspice" / "iv" / "standard_sram.sp"
TRAN = ROOT / "Hspice" / "iv" / "standard_sram_tran.sp"
SNM = ROOT / "Hspice" / "iv" / "standard_sram_snm.sp"


def main() -> int:
    text = SRC.read_text(encoding="utf-8")
    marker = ".ALTER HOLD_SNM_Q_SWEEP"
    if marker not in text:
        raise SystemExit(f"cannot find marker: {marker}")
    prefix, dc_tail = text.split(marker, 1)
    if ".ALTER READ_Q1" not in prefix:
        raise SystemExit("cannot find transient alters")
    head, tran_tail = prefix.split(".ALTER READ_Q1", 1)

    tran_text = (
        head
        + ".ALTER READ_Q1"
        + tran_tail.rstrip()
        + "\n\n.END\n"
    )
    snm_text = (
        head
        + marker
        + dc_tail.rstrip()
        + "\n"
    )

    TRAN.write_text(tran_text, encoding="utf-8")
    SNM.write_text(snm_text, encoding="utf-8")
    print(f"Wrote: {TRAN}")
    print(f"Wrote: {SNM}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
