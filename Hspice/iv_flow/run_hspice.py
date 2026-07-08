#!/usr/bin/env python3
"""One-command HSPICE runner for Windows.

Example:
    python run_hspice.py decks/single_nmos_output_iv.sp

Outputs are written next to the deck by default:
    decks/single_nmos_output_iv.sp
    decks/single_nmos_output_iv/single_nmos_output_iv.sw0
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


FLOW_DIR = Path(__file__).resolve().parent
DEFAULT_LICENSE = "27000@LAPTOP-K9QP6UAM"
DEFAULT_WAVEVIEW = Path(r"C:\synopsys\Custom WaveView O-2018.09-SP2\wv.exe")
HSPICE_INSTALL_CANDIDATES = [
    Path(r"C:\synopsys\Hspice_P-2019.06-SP1-1"),
    Path(r"C:\synopsys\Hspice_O-2018.09"),
]


def find_hspice(explicit_cmd: str | None, explicit_install_dir: str | None) -> Path:
    if explicit_cmd:
        cmd = Path(explicit_cmd)
        if cmd.exists():
            return cmd
        raise FileNotFoundError(f"HSPICE command not found: {cmd}")

    install_dirs: list[Path] = []
    if explicit_install_dir:
        install_dirs.append(Path(explicit_install_dir))
    install_dirs.extend(HSPICE_INSTALL_CANDIDATES)

    for install_dir in install_dirs:
        for rel in (r"WIN64\hspice.com", r"WIN64\hspice.exe"):
            candidate = install_dir / rel
            if candidate.exists():
                return candidate

    path_cmd = shutil.which("hspice")
    if path_cmd:
        return Path(path_cmd)

    raise FileNotFoundError(
        "Cannot find HSPICE. Pass --hspice-cmd or --install-dir."
    )


def build_run_dir(deck: Path, run_name: str | None, results_dir: str | None) -> Path:
    folder_name = run_name or deck.stem
    if results_dir:
        run_dir = Path(results_dir).resolve() / folder_name
    else:
        run_dir = deck.parent / folder_name
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def find_waveform(output_prefix: Path) -> Path | None:
    for suffix in (".sw0", ".tr0", ".ac0"):
        candidate = output_prefix.with_suffix(suffix)
        if candidate.exists():
            return candidate
    matches = sorted(output_prefix.parent.glob(f"{output_prefix.name}.*"))
    for candidate in matches:
        if candidate.suffix.lower() in {".sw0", ".tr0", ".ac0", ".mt0", ".ms0"}:
            return candidate
    return None


def open_waveview(wv_cmd: str, waveform: Path) -> subprocess.Popen:
    wv_path = Path(wv_cmd)
    if not wv_path.exists():
        raise FileNotFoundError(f"Custom WaveView not found: {wv_path}")
    return subprocess.Popen([str(wv_path), str(waveform)])


def write_manifest(
    run_dir: Path,
    deck: Path,
    hspice_cmd: Path,
    output_prefix: Path,
    license_server: str,
    return_code: int,
    waveview_cmd: str | None = None,
    waveview_file: Path | None = None,
) -> None:
    manifest = {
        "deck": str(deck),
        "hspice_cmd": str(hspice_cmd),
        "license_server": license_server,
        "output_prefix": str(output_prefix),
        "return_code": return_code,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "outputs": sorted(p.name for p in run_dir.glob(f"{output_prefix.name}*")),
        "waveview_cmd": waveview_cmd,
        "waveview_file": str(waveview_file) if waveview_file else None,
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Run one HSPICE .sp deck and collect outputs next to the deck."
    )
    parser.add_argument("deck", help="Path to the .sp deck.")
    parser.add_argument(
        "--run-name",
        default="",
        help="Result folder name. Defaults to the deck stem.",
    )
    parser.add_argument(
        "--results-dir",
        default="",
        help="Optional root folder. By default, use the deck's parent folder.",
    )
    parser.add_argument("--hspice-cmd", default="", help="Explicit hspice.com path.")
    parser.add_argument("--install-dir", default="", help="Explicit HSPICE install dir.")
    parser.add_argument(
        "--license-server",
        default=os.environ.get("SNPSLMD_LICENSE_FILE", DEFAULT_LICENSE),
        help="FLEXlm license server, for example 27000@LAPTOP-K9QP6UAM.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the command without running HSPICE.",
    )
    parser.add_argument(
        "-wv",
        "--waveview",
        action="store_true",
        help="Open the generated waveform in Custom WaveView after a successful run.",
    )
    parser.add_argument(
        "--wv-cmd",
        default=str(DEFAULT_WAVEVIEW),
        help="Path to Custom WaveView wv.exe.",
    )
    args = parser.parse_args(argv)

    deck = Path(args.deck).resolve()
    if not deck.exists():
        raise FileNotFoundError(f"Deck not found: {deck}")
    if deck.suffix.lower() != ".sp":
        raise ValueError(f"Expected a .sp deck, got: {deck}")

    hspice_cmd = find_hspice(args.hspice_cmd or None, args.install_dir or None)
    run_dir = build_run_dir(deck, args.run_name or None, args.results_dir or None)
    output_prefix = run_dir / deck.stem

    env = os.environ.copy()
    env["SNPSLMD_LICENSE_FILE"] = args.license_server
    env["LM_LICENSE_FILE"] = args.license_server
    if args.install_dir:
        install_dir = str(Path(args.install_dir).resolve())
    else:
        install_dir = str(hspice_cmd.parent.parent)
    env["installdir_P-2019.06-SP1-1"] = install_dir
    env["installdir_O-2018.09"] = install_dir

    cmd = [str(hspice_cmd), "-i", deck.name, "-o", str(output_prefix)]

    print(f"HSPICE: {hspice_cmd}")
    print(f"Deck: {deck}")
    print(f"License: {args.license_server}")
    print(f"Run dir: {run_dir}")
    if args.waveview:
        print(f"WaveView: {args.wv_cmd}")
    print("Command:")
    print("  " + " ".join(f'"{part}"' if " " in part else part for part in cmd))

    if args.dry_run:
        write_manifest(
            run_dir,
            deck,
            hspice_cmd,
            output_prefix,
            args.license_server,
            0,
            args.wv_cmd if args.waveview else None,
        )
        return 0

    completed = subprocess.run(cmd, cwd=deck.parent, env=env)
    waveform = find_waveform(output_prefix)
    write_manifest(
        run_dir,
        deck,
        hspice_cmd,
        output_prefix,
        args.license_server,
        completed.returncode,
        args.wv_cmd if args.waveview else None,
        waveform,
    )

    lis_path = output_prefix.with_suffix(".lis")
    if completed.returncode != 0:
        print(f"HSPICE failed with exit code {completed.returncode}.")
        print(f"Check: {lis_path}")
        return completed.returncode

    print("Done.")
    print(f"Listing: {lis_path}")
    if waveform:
        print(f"Waveform: {waveform}")
    else:
        print(f"Waveform not found near: {output_prefix}")
    print(f"Manifest: {run_dir / 'manifest.json'}")
    if args.waveview:
        if not waveform:
            print("WaveView was requested, but no waveform file was found.")
            return 2
        open_waveview(args.wv_cmd, waveform)
        print(f"Opened Custom WaveView: {waveform}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
