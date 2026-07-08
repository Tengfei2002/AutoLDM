#!/usr/bin/env python3
"""Open HSPICE waveform output with Custom WaveView.

Examples:
    python run_wv.py decks/single_nmos_output_iv.sp
    python run_wv.py decks/single_nmos_output_iv/single_nmos_output_iv.sw0
    python run_wv.py decks/single_nmos_output_iv
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


DEFAULT_WAVEVIEW = Path(r"C:\synopsys\Custom WaveView O-2018.09-SP2\wv.exe")
WAVEFORM_SUFFIXES = (".sw0", ".tr0", ".ac0", ".mt0", ".ms0")


def find_waveform_for_sp(deck: Path) -> Path | None:
    output_dir = deck.parent / deck.stem
    for suffix in WAVEFORM_SUFFIXES:
        candidate = output_dir / f"{deck.stem}{suffix}"
        if candidate.exists():
            return candidate
    return find_waveform_in_dir(output_dir)


def find_waveform_in_dir(directory: Path) -> Path | None:
    if not directory.exists():
        return None
    for suffix in WAVEFORM_SUFFIXES:
        matches = sorted(directory.glob(f"*{suffix}"))
        if matches:
            return matches[0]
    return None


def resolve_waveform(target: Path) -> Path:
    target = target.resolve()
    if target.is_file() and target.suffix.lower() == ".sp":
        waveform = find_waveform_for_sp(target)
    elif target.is_dir():
        waveform = find_waveform_in_dir(target)
    elif target.is_file():
        waveform = target
    else:
        raise FileNotFoundError(f"Target not found: {target}")

    if not waveform:
        raise FileNotFoundError(f"No waveform found for: {target}")
    return waveform.resolve()


def open_waveview(wv_cmd: Path, waveform: Path) -> subprocess.Popen:
    if not wv_cmd.exists():
        raise FileNotFoundError(f"Custom WaveView not found: {wv_cmd}")
    return subprocess.Popen([str(wv_cmd), str(waveform)])


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Open a waveform, a run directory, or an .sp deck in Custom WaveView."
    )
    parser.add_argument("target", help=".sp deck, waveform file, or output directory.")
    parser.add_argument(
        "--wv-cmd",
        default=str(DEFAULT_WAVEVIEW),
        help="Path to Custom WaveView wv.exe.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the WaveView command without launching it.",
    )
    args = parser.parse_args(argv)

    waveform = resolve_waveform(Path(args.target))
    wv_cmd = Path(args.wv_cmd)

    print(f"WaveView: {wv_cmd}")
    print(f"Waveform: {waveform}")
    if args.dry_run:
        return 0

    open_waveview(wv_cmd, waveform)
    print("Opened Custom WaveView.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
