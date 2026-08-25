#!/usr/bin/env python3
"""Generate and verify one AutoLDM standalone SDC cell triplet."""

from __future__ import annotations

import argparse
import ast
import importlib.util
import sys
import tempfile
from pathlib import Path


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def get_root(explicit: Path | None) -> Path:
    root = explicit.resolve() if explicit else Path(__file__).resolve().parents[3]
    required = (
        root / "Database" / "sdc" / "build_sdc_library.py",
        root / "Database" / "sdc" / "cell_runtime.py.inc",
    )
    if not all(path.is_file() for path in required):
        raise FileNotFoundError(f"AutoLDM generator inputs not found under: {root}")
    return root


def check_imports(script: Path) -> None:
    tree = ast.parse(script.read_text(encoding="utf-8"), filename=str(script))
    forbidden = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names = (node.module or "",)
        elif isinstance(node, ast.Import):
            names = tuple(alias.name for alias in node.names)
        else:
            continue
        forbidden.extend(
            name for name in names
            if name == "_comb_cell" or name.startswith(("Database", "FLOW"))
        )
    if forbidden:
        raise ValueError(f"{script}: external project imports: {forbidden}")


def verify(cell: str, pin: Path, script: Path, bench: Path) -> None:
    for path in (pin, script, bench):
        if not path.is_file() or path.stem != cell:
            raise ValueError(f"invalid generated path: {path}")
    check_imports(script)
    module = load_module(script, f"autoldm_generated_{cell}")
    required = (
        "CELL_ID", "INPUTS", "TRUTH_TABLE", "TEST_PLAN",
        "validate", "generate_decks", "run_and_analyze",
    )
    missing = [name for name in required if not hasattr(module, name)]
    if missing or module.CELL_ID != cell:
        raise ValueError(f"{script}: contract mismatch; missing={missing}")

    with tempfile.TemporaryDirectory(prefix=f"autoldm_{cell}_skill_") as temp:
        temp_root = Path(temp)
        ports = (*tuple(module.INPUTS), "Y", "VDD", "VSS")
        include = temp_root / f"{cell}.inc"
        n_va, p_va = temp_root / "n.va", temp_root / "p.va"
        include.write_text(
            f".subckt {cell}_check {' '.join(ports)}\n.ends {cell}_check\n",
            encoding="utf-8",
        )
        n_va.write_text("// interface check\n", encoding="utf-8")
        p_va.write_text("// interface check\n", encoding="utf-8")
        module.validate(include, bench, n_va, p_va)
        deck_dir = temp_root / "sp"
        decks = module.generate_decks(include, bench, n_va, p_va, deck_dir)
        expected = (
            2 ** len(module.INPUTS)
            + len(module.TEST_PLAN["timing_arcs"])
            + len(module.TEST_PLAN["dc_sweeps"])
        )
        if len(decks) != expected:
            raise ValueError(f"{cell}: generated {len(decks)} decks, expected {expected}")
        if module.run_and_analyze(
            deck_dir, temp_root / "results", dry_run=True, no_plot=True
        ):
            raise ValueError(f"{cell}: dry-run result collection failed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--cell", help="catalog cell name, for example inv or mux4")
    choice.add_argument("--list", action="store_true", help="list supported cells")
    parser.add_argument("--project-root", type=Path, help="AutoLDM project root")
    parser.add_argument("--output-root", type=Path, help="parent of the three sdc directories")
    parser.add_argument("--force", action="store_true", help="replace existing files")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = get_root(args.project_root)
    builder = load_module(
        root / "Database" / "sdc" / "build_sdc_library.py",
        "autoldm_sdc_builder",
    )
    names = tuple(item.name for item in builder.CELLS)
    if args.list:
        print("\n".join(names))
        return 0

    cell = args.cell.strip().lower()
    if cell not in names:
        raise ValueError(f"unsupported cell {cell!r}; use --list")
    output = args.output_root.resolve() if args.output_root else root / "Database" / "sdc"
    targets = (
        output / "sdc_pin" / f"{cell}.txt",
        output / "sdc_pyscript" / f"{cell}.py",
        output / "sdc_tb" / f"{cell}.txt",
    )
    existing = [path for path in targets if path.exists()]
    if existing and not args.force:
        paths = "\n".join(str(path) for path in existing)
        raise FileExistsError(
            "targets exist; use --force only when replacement is intended:\n" + paths
        )

    pin, script, bench = builder.generate_cell(cell, output)
    verify(cell, pin, script, bench)
    print(f"PASS: generated and verified standalone triplet for {cell}")
    for path in (pin, script, bench):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
