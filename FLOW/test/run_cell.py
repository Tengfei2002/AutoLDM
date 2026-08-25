#!/usr/bin/env python3
"""Single entry point for matrix-to-PEX-to-standard-cell HSPICE validation."""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import sys
from pathlib import Path
from types import ModuleType

from gen_pex import generate_pex


def _existing_file(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"{label} not found: {resolved}")
    return resolved


def _cell_name(value: str) -> str:
    normalized = value.strip().lower()
    if not re.fullmatch(r"[a-z][a-z0-9_]*", normalized):
        raise ValueError(
            f"Invalid cell name {value!r}; use lowercase letters, digits, and underscores"
        )
    return normalized


def load_cell_adapter(path: Path) -> ModuleType:
    path = _existing_file(path, "cell adapter")
    sys.path.insert(0, str(path.parent))
    specification = importlib.util.spec_from_file_location(
        f"autoldm_cell_{path.stem}", path
    )
    if specification is None or specification.loader is None:
        raise ImportError(f"Cannot load cell adapter: {path}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    required = ("CELL_ID", "validate", "generate_decks", "run_and_analyze")
    missing = [name for name in required if not hasattr(module, name)]
    if missing:
        raise AttributeError(
            f"Cell adapter {path} is missing: {', '.join(missing)}"
        )
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate pin-RC/PEX, build cell-specific decks, run PEX validation, "
            "and collect HSPICE results with one checked command."
        )
    )
    parser.add_argument("--name", required=True, help="Project/output prefix")
    parser.add_argument("--cell", required=True, help="Standard-cell name, for example sram1 or inv")
    parser.add_argument("--input-model-dir", type=Path, required=True)
    parser.add_argument("--pin", type=Path, help="Optional override for sdc_pin/<cell>.txt")
    parser.add_argument("--c-matrix", type=Path, required=True)
    parser.add_argument("--r-matrix", type=Path, required=True)
    parser.add_argument("--n-va", type=Path, required=True)
    parser.add_argument("--p-va", type=Path, required=True)
    parser.add_argument("--bench", type=Path, help="Optional override for sdc_tb/<cell>.txt")
    parser.add_argument("--cell-script", type=Path, help="Optional override for sdc_pyscript/<cell>.py")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--subckt-name")
    parser.add_argument("--md-layer", default="MD")
    parser.add_argument("--bmd-layer", default="BMD")
    parser.add_argument("--backside-prefix", default="B")
    parser.add_argument("--strict-contact-face", action="store_true")
    parser.add_argument("--hspice-cmd", default="")
    parser.add_argument("--install-dir", default="")
    parser.add_argument(
        "--license-server",
        default=os.environ.get("SNPSLMD_LICENSE_FILE", ""),
    )
    parser.add_argument("--rerun", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-plot", action="store_true")
    parser.add_argument(
        "--generate-only",
        action="store_true",
        help="Stop after generating PEX, validation deck, and functional decks",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Do not run the generated zero-bias PEX validation deck",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        name = args.name.strip()
        if not name or any(character in name for character in "\\/:"):
            raise ValueError(f"Invalid project name: {args.name!r}")

        cell_name = _cell_name(args.cell)
        input_model_dir = args.input_model_dir.resolve()
        if not input_model_dir.is_dir():
            raise FileNotFoundError(
                f"input model directory not found: {input_model_dir}"
            )
        pin = _existing_file(
            args.pin or input_model_dir / "sdc_pin" / f"{cell_name}.txt",
            "pin manifest",
        )
        c_matrix = _existing_file(args.c_matrix, "C matrix")
        r_matrix = _existing_file(args.r_matrix, "R matrix")
        n_va = _existing_file(args.n_va, "N Verilog-A model")
        p_va = _existing_file(args.p_va, "P Verilog-A model")
        bench = _existing_file(
            args.bench or input_model_dir / "sdc_tb" / f"{cell_name}.txt",
            "cell benchmark",
        )
        adapter = load_cell_adapter(
            args.cell_script
            or input_model_dir / "sdc_pyscript" / f"{cell_name}.py"
        )
        adapter_cell_id = _cell_name(str(adapter.CELL_ID))
        if adapter_cell_id != cell_name:
            raise ValueError(
                f"Cell adapter CELL_ID={adapter.CELL_ID!r} does not match "
                f"--cell {cell_name!r}"
            )

        output = args.output.resolve()
        output.mkdir(parents=True, exist_ok=True)
        pin_rc = output / f"{name}_pin_spice.txt"
        library = output / f"{name}_pex.inc"
        validation_deck = output / f"{name}_pex_validate.sp"
        cell_id = adapter_cell_id
        deck_directory = output / "sp" / cell_id
        result_directory = output / "results" / cell_id
        validation_results = output / "results" / f"{cell_id}_pex_validation"

        print("[1/4] Generate numeric pin-RC and PEX include")
        generate_pex(
            pin,
            c_matrix,
            r_matrix,
            n_va,
            p_va,
            library,
            pin_rc_output=pin_rc,
            validation_output=validation_deck,
            subckt_name=args.subckt_name,
            md_layer=args.md_layer,
            bmd_layer=args.bmd_layer,
            backside_prefix=args.backside_prefix,
            strict_contact_face=args.strict_contact_face,
        )

        print(f"[2/4] Validate {cell_id} contract and generate decks")
        adapter.validate(library, bench, n_va, p_va)
        deck_directory.mkdir(parents=True, exist_ok=True)
        for stale_deck in deck_directory.glob("*.sp"):
            stale_deck.unlink()
        decks = adapter.generate_decks(
            library, bench, n_va, p_va, deck_directory
        )
        if not decks:
            raise RuntimeError(f"Cell adapter {cell_id} generated no decks")
        if args.generate_only:
            print("Generation completed; simulation skipped by --generate-only.")
            return 0

        runner_options = {
            "hspice_cmd": args.hspice_cmd,
            "install_dir": args.install_dir,
            "license_server": args.license_server,
            "rerun": args.rerun,
            "dry_run": args.dry_run,
        }
        if not args.skip_validation:
            print("[3/4] Run mandatory PEX compile/zero-bias validation")
            validation_code = adapter.run_and_analyze(
                validation_deck,
                validation_results,
                no_plot=True,
                **runner_options,
            )
            if validation_code:
                print("PEX validation failed; functional decks were not run.", file=sys.stderr)
                return 3
        else:
            print("[3/4] PEX validation skipped by explicit request")

        print(f"[4/4] Run and analyze {cell_id} functional decks")
        result = adapter.run_and_analyze(
            deck_directory,
            result_directory,
            no_plot=args.no_plot,
            **runner_options,
        )
        if result:
            print(
                "One or more HSPICE runs failed or reported a model numerical error.",
                file=sys.stderr,
            )
            return 4

        print(f"PEX library: {library}")
        print(f"Functional decks: {deck_directory}")
        print(f"Results: {result_directory}")
        return 0
    except Exception as exc:
        print(f"Consolidated cell flow failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())


