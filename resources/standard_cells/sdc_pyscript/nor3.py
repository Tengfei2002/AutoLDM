#!/usr/bin/env python3
"""Standalone checked HSPICE adapter for one single-output combinational cell."""

from __future__ import annotations

import csv
import json
import math
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from itertools import product
from pathlib import Path
from typing import Callable


SUBCKT_RE = re.compile(r"^\s*\.subckt\s+(\S+)(?:\s+(.*?))?\s*$", re.I)
MEASURE_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
    r"([+-]?(?:(?:\d+\.\d*)|(?:\.\d+)|(?:\d+))(?:[eEdD][+-]?\d+)?)\b"
)
MODEL_ERROR_RE = re.compile(r"(?:numerical\s+NaN|FPE:)", re.I)
HSPICE_INSTALL_CANDIDATES = (
    Path(r"C:\synopsys\Hspice_P-2019.06-SP1-1"),
    Path(r"C:\synopsys\Hspice_O-2018.09"),
)
DEFAULT_BENCH = {
    "cload": "5f",
    "trise": "20p",
    "tfall": "20p",
    "tdelay": "200p",
    "pulse_width": "400p",
    "period": "1n",
    "tstep": "1p",
    "tstop": "1.4n",
    "dc_step": "1m",
    "logic_low_max": "0.2",
    "logic_high_min": "0.8",
}


@dataclass(frozen=True)
class Subckt:
    name: str
    ports: tuple[str, ...]


@dataclass(frozen=True)
class CellSpec:
    cell_id: str
    inputs: tuple[str, ...]
    truth_table: tuple[int, ...]

    @property
    def ports(self) -> tuple[str, ...]:
        return (*self.inputs, "Y", "VDD", "VSS")


def _require_file(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    return resolved


def _engineering(raw: str) -> float:
    match = re.fullmatch(
        r"([+-]?(?:(?:\d+\.\d*)|(?:\.\d+)|(?:\d+))(?:e[+-]?\d+)?)"
        r"(meg|[fpnumkg])?",
        raw.strip().lower(),
    )
    if not match:
        raise ValueError(f"invalid engineering value: {raw!r}")
    scale = {None: 1.0, "f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6,
             "m": 1e-3, "k": 1e3, "meg": 1e6, "g": 1e9}
    return float(match.group(1)) * scale[match.group(2)]


def _parse_bench(path: Path) -> dict[str, str]:
    allowed = {
        "SUPPLY": {"vdd", "vss"},
        "LOAD": {"cload"},
        "TIMING": {"trise", "tfall", "tdelay", "pulse_width", "period", "tstep", "tstop", "dc_step"},
        "MEASURE": {"logic_low_max", "logic_high_min"},
    }
    values: dict[str, str] = {}
    section = ""
    for number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith(("*", "#", ";")):
            continue
        if line.startswith("(") and line.endswith(")"):
            section = line[1:-1].strip().upper()
            if section not in allowed:
                raise ValueError(f"{path}:{number}: unsupported section {section}")
            continue
        if section not in allowed or "=" not in line:
            raise ValueError(f"{path}:{number}: expected key=value")
        key, value = (part.strip() for part in line.split("=", 1))
        key = key.lower()
        if key not in allowed[section] or key in values or not value:
            raise ValueError(f"{path}:{number}: invalid or duplicate key {key!r}")
        values[key] = value
    if not {"vdd", "vss"}.issubset(values):
        raise ValueError(f"{path}: vdd and vss are required")
    bench = {**DEFAULT_BENCH, **values}
    vdd, vss = float(bench["vdd"]), float(bench["vss"])
    if vdd <= vss:
        raise ValueError(f"{path}: vdd must be greater than vss")
    for key in ("cload", "trise", "tfall", "tdelay", "pulse_width", "period", "tstep", "tstop", "dc_step"):
        if _engineering(bench[key]) <= 0:
            raise ValueError(f"{path}: {key} must be positive")
    low, high = _engineering(bench["logic_low_max"]), _engineering(bench["logic_high_min"])
    if not 0 < low < high < 1:
        raise ValueError(f"{path}: require 0 < logic_low_max < logic_high_min < 1")
    minimum_stop = _engineering(bench["tdelay"]) + _engineering(bench["pulse_width"]) + _engineering(bench["tfall"])
    if _engineering(bench["tstop"]) <= minimum_stop:
        raise ValueError(f"{path}: tstop does not cover both pulse edges")
    return bench


def _parse_subckt(path: Path, expected_ports: tuple[str, ...]) -> Subckt:
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    for index, line in enumerate(lines):
        match = SUBCKT_RE.match(line)
        if not match:
            continue
        name, raw_ports = match.groups()
        ports = (raw_ports or "").split()
        while index + 1 < len(lines) and lines[index + 1].lstrip().startswith("+"):
            index += 1
            ports.extend(lines[index].lstrip()[1:].split())
        actual = tuple(port.upper() for port in ports)
        if len(actual) != len(set(actual)) or set(actual) != set(expected_ports):
            raise ValueError(f"{path}: expected exactly {', '.join(expected_ports)}; got {', '.join(actual)}")
        return Subckt(name, tuple(ports))
    raise ValueError(f"{path}: no .subckt declaration found")


def _relative(target: Path, deck: Path) -> str:
    return os.path.relpath(target, deck.parent).replace("\\", "/")


def _header(deck: Path, inc: Path, n_va: Path, p_va: Path, bench: dict[str, str]) -> list[str]:
    return [
        "* Auto-generated AutoLDM combinational-cell test",
        ".option INGOLD=2 POST=2",
        f'.hdl "{_relative(n_va, deck)}"',
        f'.hdl "{_relative(p_va, deck)}"',
        f'.include "{_relative(inc, deck)}"',
        f".param VDD_VAL={bench['vdd']} VSS_VAL={bench['vss']}",
        ".param VCORE='VDD_VAL-VSS_VAL'",
        ".param " + " ".join(f"{key.upper()}={value}" for key, value in bench.items() if key not in {"vdd", "vss"}),
        "VVSS VSS 0 'VSS_VAL'",
        "VVDD VDD VSS 'VCORE'",
        "",
    ]


def _dut(cell: Subckt, spec: CellSpec) -> str:
    known = {port: port for port in spec.ports}
    return f"XDUT {' '.join(known[port.upper()] for port in cell.ports)} {cell.name}"


def _vectors(count: int) -> list[tuple[int, ...]]:
    return list(product((0, 1), repeat=count))


def _truth_deck(
    spec: CellSpec, cell: Subckt, vector: tuple[int, ...], expected: int,
    deck: Path, inc: Path, bench_path: Path, n_va: Path, p_va: Path,
) -> str:
    bench = _parse_bench(bench_path)
    bits = "".join(map(str, vector))
    sources = [
        f"V{name} {name} VSS " + ("'VCORE'" if value else "0")
        for name, value in zip(spec.inputs, vector)
    ]
    return "\n".join([
        f"* AUTOLDM_TEST=truth EXPECTED_Y={expected} VECTOR={bits}",
        *_header(deck, inc, n_va, p_va, bench),
        *sources,
        "CLOAD Y VSS 'CLOAD'",
        _dut(cell, spec),
        ".tran 'TSTEP' 'TSTOP'",
        ".measure tran VOUT_AVG AVG V(Y) FROM='TSTOP*0.75' TO='TSTOP'",
        ".measure tran IVDD_AVG AVG I(VVDD) FROM='TSTOP*0.75' TO='TSTOP'",
        ".print tran V(Y) I(VVDD)",
        ".end", "",
    ])


def _timing_pair(spec: CellSpec, input_index: int) -> tuple[tuple[int, ...], int, int] | None:
    vectors = _vectors(len(spec.inputs))
    truth = dict(zip(vectors, spec.truth_table))
    for low_vector in vectors:
        if low_vector[input_index]:
            continue
        high_vector = list(low_vector)
        high_vector[input_index] = 1
        high_tuple = tuple(high_vector)
        if truth[low_vector] != truth[high_tuple]:
            return low_vector, truth[low_vector], truth[high_tuple]
    return None


def _truth_at(spec: CellSpec, values: dict[str, int]) -> int:
    vector = tuple(int(values[name]) for name in spec.inputs)
    index = 0
    for bit in vector:
        index = 2 * index + bit
    return spec.truth_table[index]


def _timing_deck(
    spec: CellSpec, cell: Subckt, arc: dict[str, object],
    deck: Path, inc: Path, bench_path: Path, n_va: Path, p_va: Path,
) -> str:
    bench = _parse_bench(bench_path)
    changing = str(arc["pin"]).upper()
    condition = {str(key).upper(): int(value) for key, value in dict(arc["when"]).items()}
    y0, y1 = int(arc["y0"]), int(arc["y1"])
    sources = []
    for name in spec.inputs:
        if name == changing:
            sources.append(f"V{name} {name} VSS PULSE(0 'VCORE' 'TDELAY' 'TRISE' 'TFALL' 'PULSE_WIDTH' 'PERIOD')")
        else:
            value = condition.get(name, 0)
            sources.append(f"V{name} {name} VSS " + ("'VCORE'" if value else "0"))
    first_output_edge = "RISE" if y1 > y0 else "FALL"
    second_output_edge = "FALL" if y1 > y0 else "RISE"
    midpoint = "VSS_VAL+0.5*VCORE"
    condition_text = "_".join(f"{key}{value}" for key, value in sorted(condition.items())) or "NONE"
    return "\n".join([
        f"* AUTOLDM_TEST=timing ARC={arc['name']} ROLE={arc['role']} INPUT={changing} CONDITION={condition_text} Y0={y0} Y1={y1}",
        *_header(deck, inc, n_va, p_va, bench),
        *sources,
        "CLOAD Y VSS 'CLOAD'",
        _dut(cell, spec),
        ".tran 'TSTEP' 'TSTOP'",
        f".measure tran T_EDGE1 TRIG V({changing}) VAL='{midpoint}' RISE=1 TARG V(Y) VAL='{midpoint}' {first_output_edge}=1",
        f".measure tran T_EDGE2 TRIG V({changing}) VAL='{midpoint}' FALL=1 TARG V(Y) VAL='{midpoint}' {second_output_edge}=1",
        f".print tran V({changing}) V(Y) I(VVDD)",
        ".end", "",
    ])


def _dc_deck(
    spec: CellSpec, cell: Subckt, sweep: dict[str, object],
    deck: Path, inc: Path, bench_path: Path, n_va: Path, p_va: Path,
) -> str:
    bench = _parse_bench(bench_path)
    changing = str(sweep["pin"]).upper()
    condition = {str(key).upper(): int(value) for key, value in dict(sweep["when"]).items()}
    sources = []
    for name in spec.inputs:
        value = condition.get(name, 0)
        sources.append(f"V{name} {name} VSS " + ("0" if name == changing else ("'VCORE'" if value else "0")))
    return "\n".join([
        f"* AUTOLDM_TEST=dc INPUT={changing} EXPECTED0={sweep['y0']} EXPECTED1={sweep['y1']}",
        *_header(deck, inc, n_va, p_va, bench),
        *sources,
        "CLOAD Y VSS 'CLOAD'",
        _dut(cell, spec),
        f".dc V{changing} 0 'VCORE' 'DC_STEP'",
        ".measure dc VOUT0 FIND V(Y) AT=0",
        ".measure dc VOUT1 FIND V(Y) AT='VCORE'",
        f".measure dc VM WHEN V({changing})=V(Y) CROSS=1",
        f".print dc V({changing}) V(Y) I(VVDD)",
        ".end", "",
    ])


def _find_hspice(explicit: str, install_dir: str) -> Path:
    if explicit:
        path = Path(explicit).resolve()
        if path.is_file():
            return path
        raise FileNotFoundError(path)
    roots = ([Path(install_dir).resolve()] if install_dir else []) + list(HSPICE_INSTALL_CANDIDATES)
    for root in roots:
        for relative in (r"WIN64\hspice.com", r"WIN64\hspice.exe"):
            candidate = root / relative
            if candidate.is_file():
                return candidate
    discovered = shutil.which("hspice")
    if discovered:
        return Path(discovered).resolve()
    raise FileNotFoundError("Cannot find HSPICE. Pass --hspice-cmd or --install-dir.")


def _measurements(path: Path) -> dict[str, float]:
    values: dict[str, float] = {}
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = MEASURE_RE.match(line)
        if match:
            try:
                values[match.group(1).lower()] = float(match.group(2).replace("D", "E").replace("d", "e"))
            except ValueError:
                pass
    return values


def _deck_meta(deck: Path) -> dict[str, str]:
    first = deck.read_text(encoding="utf-8", errors="ignore").splitlines()[0]
    return dict(re.findall(r"([A-Z0-9_]+)=([^\s]+)", first.upper()))


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def configure(
    cell_id: str,
    inputs: tuple[str, ...],
    truth_table: tuple[int, ...],
    test_plan: dict[str, object],
) -> tuple[Callable, Callable, Callable]:
    spec = CellSpec(cell_id.lower(), tuple(name.upper() for name in inputs), tuple(int(value) for value in truth_table))
    if not re.fullmatch(r"[a-z][a-z0-9_]*", spec.cell_id):
        raise ValueError(f"invalid cell id: {cell_id!r}")
    if not spec.inputs or len(set(spec.inputs)) != len(spec.inputs):
        raise ValueError(f"{cell_id}: inputs must be unique and non-empty")
    if len(spec.truth_table) != 2 ** len(spec.inputs) or set(spec.truth_table) - {0, 1}:
        raise ValueError(f"{cell_id}: truth table length/value mismatch")
    plan = dict(test_plan)
    strategy = str(plan.get("strategy", ""))
    if strategy not in {"inverter", "buffer", "static_unate", "compound_unate", "non_unate", "mux", "threshold"}:
        raise ValueError(f"{cell_id}: unsupported test strategy {strategy!r}")
    timing_arcs = tuple(dict(arc) for arc in plan.get("timing_arcs", ()))
    dc_sweeps = tuple(dict(sweep) for sweep in plan.get("dc_sweeps", ()))
    arc_names: set[str] = set()
    for arc in timing_arcs:
        required = {"name", "role", "pin", "when", "y0", "y1"}
        if not required.issubset(arc):
            raise ValueError(f"{cell_id}: incomplete timing arc {arc}")
        name = str(arc["name"])
        pin = str(arc["pin"]).upper()
        condition = {str(key).upper(): int(value) for key, value in dict(arc["when"]).items()}
        if name in arc_names or pin not in spec.inputs or pin in condition:
            raise ValueError(f"{cell_id}: invalid or duplicate timing arc {name!r}")
        if set(condition) - set(spec.inputs) or set(condition.values()) - {0, 1}:
            raise ValueError(f"{cell_id}: invalid condition in arc {name!r}")
        values0 = {input_name: condition.get(input_name, 0) for input_name in spec.inputs}
        values1 = dict(values0)
        values0[pin], values1[pin] = 0, 1
        actual = (_truth_at(spec, values0), _truth_at(spec, values1))
        expected = (int(arc["y0"]), int(arc["y1"]))
        if actual != expected or actual[0] == actual[1]:
            raise ValueError(f"{cell_id}: arc {name!r} is not sensitized; expected={expected}, actual={actual}")
        arc_names.add(name)
    if not timing_arcs:
        raise ValueError(f"{cell_id}: test plan contains no timing arcs")
    for sweep in dc_sweeps:
        if not {"pin", "when", "y0", "y1"}.issubset(sweep):
            raise ValueError(f"{cell_id}: incomplete DC sweep {sweep}")

    def validate(inc: Path, bench: Path, n_va: Path, p_va: Path) -> None:
        _parse_subckt(_require_file(inc), spec.ports)
        _parse_bench(_require_file(bench))
        _require_file(n_va)
        _require_file(p_va)

    def generate_decks(inc: Path, bench: Path, n_va: Path, p_va: Path, output: Path) -> list[Path]:
        inc, bench, n_va, p_va = map(_require_file, (inc, bench, n_va, p_va))
        cell = _parse_subckt(inc, spec.ports)
        _parse_bench(bench)
        output = output.resolve()
        output.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []
        for vector, expected in zip(_vectors(len(spec.inputs)), spec.truth_table):
            bits = "".join(map(str, vector))
            path = output / f"{spec.cell_id}_truth_{bits}.sp"
            path.write_text(_truth_deck(spec, cell, vector, expected, path, inc, bench, n_va, p_va), encoding="utf-8")
            written.append(path)
        for arc in timing_arcs:
            slug = re.sub(r"[^a-z0-9_]+", "_", str(arc["name"]).lower())
            path = output / f"{spec.cell_id}_timing_{slug}.sp"
            path.write_text(_timing_deck(spec, cell, arc, path, inc, bench, n_va, p_va), encoding="utf-8")
            written.append(path)
        for index, sweep in enumerate(dc_sweeps, 1):
            path = output / f"{spec.cell_id}_dc_{index}.sp"
            path.write_text(_dc_deck(spec, cell, sweep, path, inc, bench, n_va, p_va), encoding="utf-8")
            written.append(path)
        return written

    def run_and_analyze(
        source: Path, output: Path, *, hspice_cmd: str = "", install_dir: str = "",
        license_server: str = "", rerun: bool = False, dry_run: bool = False,
        no_plot: bool = False,
    ) -> int:
        del no_plot
        source, output = source.resolve(), output.resolve()
        decks = [source] if source.is_file() else sorted(source.glob("*.sp"))
        if not decks:
            raise FileNotFoundError(f"no HSPICE decks found: {source}")
        output.mkdir(parents=True, exist_ok=True)
        raw_dir = output / "raw"
        raw_dir.mkdir(exist_ok=True)
        hspice = Path("hspice-dry-run") if dry_run else _find_hspice(hspice_cmd, install_dir)
        environment = os.environ.copy()
        if license_server:
            environment["SNPSLMD_LICENSE_FILE"] = license_server
            environment["LM_LICENSE_FILE"] = license_server
        status_rows: list[dict[str, object]] = []
        metric_rows: list[dict[str, object]] = []
        failed = False
        bench_vdd = bench_vss = None
        for deck in decks:
            run_dir = raw_dir / deck.stem
            run_dir.mkdir(exist_ok=True)
            prefix = run_dir / deck.stem
            listing = prefix.with_suffix(".lis")
            reused = not rerun and listing.is_file() and listing.stat().st_mtime >= deck.stat().st_mtime
            return_code = 0
            if not dry_run and not reused:
                completed = subprocess.run(
                    [str(hspice), "-i", deck.name, "-o", str(prefix)], cwd=deck.parent,
                    env=environment, text=True, capture_output=True, check=False,
                )
                return_code = completed.returncode
                (run_dir / "runner_stdout_stderr.txt").write_text(
                    completed.stdout + "\n" + completed.stderr, encoding="utf-8", errors="ignore"
                )
            numerical_error = listing.is_file() and bool(MODEL_ERROR_RE.search(listing.read_text(encoding="utf-8", errors="ignore")))
            status_rows.append({"deck": deck.name, "return_code": return_code, "reused": reused,
                                "model_numerical_error": numerical_error, "listing": str(listing)})
            meta = _deck_meta(deck)
            metrics: dict[str, object] = {"deck": deck.name, "test": meta.get("AUTOLDM_TEST", "validation")}
            if dry_run:
                metrics["analysis_status"] = "not_analyzed"
            elif return_code or numerical_error or not listing.is_file():
                metrics["analysis_status"] = "hspice_failed"
                failed = True
            elif meta.get("AUTOLDM_TEST"):
                measured = _measurements(listing)
                metrics.update(measured)
                if meta["AUTOLDM_TEST"] == "TRUTH":
                    if "vout_avg" not in measured:
                        metrics["analysis_status"] = "missing_vout_avg"
                        failed = True
                    else:
                        text = deck.read_text(encoding="utf-8", errors="ignore")
                        match = re.search(r"\.param\s+VDD_VAL=([^\s]+)\s+VSS_VAL=([^\s]+)", text, re.I)
                        if not match:
                            raise ValueError(f"{deck}: missing supply parameters")
                        bench_vdd, bench_vss = float(match.group(1)), float(match.group(2))
                        vcore = bench_vdd - bench_vss
                        low_match = re.search(r"\bLOGIC_LOW_MAX=([^\s]+)", text, re.I)
                        high_match = re.search(r"\bLOGIC_HIGH_MIN=([^\s]+)", text, re.I)
                        if not low_match or not high_match:
                            raise ValueError(f"{deck}: missing logic threshold parameters")
                        low_fraction = _engineering(low_match.group(1))
                        high_fraction = _engineering(high_match.group(1))
                        expected = int(meta["EXPECTED_Y"])
                        passed = (
                            measured["vout_avg"] >= bench_vss + high_fraction * vcore
                            if expected
                            else measured["vout_avg"] <= bench_vss + low_fraction * vcore
                        )
                        metrics["analysis_status"] = "ok" if passed else "logic_failed"
                        metrics["function_pass"] = "pass" if passed else "fail"
                        failed |= not passed
                elif meta["AUTOLDM_TEST"] == "DC":
                    required = {"vout0", "vout1", "vm"}
                    if not required.issubset(measured):
                        metrics["analysis_status"] = "missing_dc_measurements"
                        failed = True
                    else:
                        text = deck.read_text(encoding="utf-8", errors="ignore")
                        match = re.search(r"\.param\s+VDD_VAL=([^\s]+)\s+VSS_VAL=([^\s]+)", text, re.I)
                        low_match = re.search(r"\bLOGIC_LOW_MAX=([^\s]+)", text, re.I)
                        high_match = re.search(r"\bLOGIC_HIGH_MIN=([^\s]+)", text, re.I)
                        if not match or not low_match or not high_match:
                            raise ValueError(f"{deck}: missing supply or logic threshold parameters")
                        bench_vdd, bench_vss = float(match.group(1)), float(match.group(2))
                        vcore = bench_vdd - bench_vss
                        low_limit = bench_vss + _engineering(low_match.group(1)) * vcore
                        high_limit = bench_vss + _engineering(high_match.group(1)) * vcore
                        expected0, expected1 = int(meta["EXPECTED0"]), int(meta["EXPECTED1"])
                        endpoint0 = measured["vout0"] >= high_limit if expected0 else measured["vout0"] <= low_limit
                        endpoint1 = measured["vout1"] >= high_limit if expected1 else measured["vout1"] <= low_limit
                        passed = endpoint0 and endpoint1 and bench_vss <= measured["vm"] <= bench_vdd
                        metrics["analysis_status"] = "ok" if passed else "dc_failed"
                        metrics["function_pass"] = "pass" if passed else "fail"
                        failed |= not passed
                else:
                    passed = all(name in measured and math.isfinite(measured[name]) and measured[name] >= 0 for name in ("t_edge1", "t_edge2"))
                    metrics["analysis_status"] = "ok" if passed else "timing_failed"
                    metrics["timing_pass"] = "pass" if passed else "fail"
                    failed |= not passed
            else:
                metrics["analysis_status"] = "hspice_ok"
            metric_rows.append(metrics)
        _write_csv(output / "run_status.csv", status_rows)
        _write_csv(output / "summary_metrics.csv", metric_rows)
        (output / "run_manifest.json").write_text(json.dumps({
            "created_at": datetime.now().isoformat(timespec="seconds"), "cell_id": spec.cell_id,
            "input": str(source), "output": str(output), "hspice": str(hspice),
            "vdd": bench_vdd, "vss": bench_vss, "decks": status_rows,
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        return 1 if failed else 0

    return validate, generate_decks, run_and_analyze

# Cell-specific contract. The runtime above is embedded in this file.
# No other cell Python module is required when this file is loaded.
CELL_ID = "nor3"
INPUTS = ('A', 'B', 'C')
TRUTH_TABLE = (1, 0, 0, 0, 0, 0, 0, 0)
TEST_PLAN = {'strategy': 'static_unate',
 'truth_mode': 'exhaustive',
 'static_power_from_truth_decks': True,
 'timing_arcs': ({'name': 'a_1to0_1',
                  'role': 'input',
                  'pin': 'A',
                  'when': {'B': 0, 'C': 0},
                  'y0': 1,
                  'y1': 0},
                 {'name': 'b_1to0_1',
                  'role': 'input',
                  'pin': 'B',
                  'when': {'A': 0, 'C': 0},
                  'y0': 1,
                  'y1': 0},
                 {'name': 'c_1to0_1',
                  'role': 'input',
                  'pin': 'C',
                  'when': {'A': 0, 'B': 0},
                  'y0': 1,
                  'y1': 0}),
 'dc_sweeps': ()}
validate, generate_decks, run_and_analyze = configure(
    CELL_ID, INPUTS, TRUTH_TABLE, TEST_PLAN
)
