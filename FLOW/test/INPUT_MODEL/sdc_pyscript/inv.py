#!/usr/bin/env python3
"""Generate, run, and analyze HSPICE tests for a CMOS inverter PEX cell."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path


CELL_ID = "inv"
REQUIRED_PORTS = ("A", "Y", "VDD", "VSS")
DEFAULT_BENCH = {
    "cload": "5f",
    "trise": "20p",
    "tfall": "20p",
    "tdelay": "500p",
    "pulse_width": "1n",
    "period": "2n",
    "tstep": "1p",
    "tstop": "4n",
    "dc_step": "1m",
    "logic_low_max": "0.2",
    "logic_high_min": "0.8",
}
HSPICE_INSTALL_CANDIDATES = (
    Path(r"C:\synopsys\Hspice_P-2019.06-SP1-1"),
    Path(r"C:\synopsys\Hspice_O-2018.09"),
)
SUBCKT_RE = re.compile(r"^\s*\.subckt\s+(\S+)(?:\s+(.*?))?\s*$", re.IGNORECASE)
NUMBER_RE = re.compile(r"^[+-]?(?:(?:\d+\.\d*)|(?:\.\d+)|(?:\d+))(?:[eEdD][+-]?\d+)?$")
MEASURE_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
    r"([+-]?(?:(?:\d+\.\d*)|(?:\.\d+)|(?:\d+))(?:[eEdD][+-]?\d+)?)\b"
)
MODEL_ERROR_RE = re.compile(r"(?:numerical\s+NaN|FPE:)", re.IGNORECASE)


@dataclass(frozen=True)
class InverterCell:
    name: str
    ports: tuple[str, ...]


def require_file(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    return resolved


def parse_subckt(path: Path) -> InverterCell:
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    for index, raw_line in enumerate(lines):
        match = SUBCKT_RE.match(raw_line)
        if not match:
            continue
        name, raw_ports = match.groups()
        ports = (raw_ports or "").split()
        next_index = index + 1
        while next_index < len(lines) and lines[next_index].lstrip().startswith("+"):
            ports.extend(lines[next_index].lstrip()[1:].split())
            next_index += 1
        actual = {port.upper() for port in ports}
        expected = set(REQUIRED_PORTS)
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        if missing or extra:
            raise ValueError(
                f"{path}: expected exactly {', '.join(REQUIRED_PORTS)}; "
                f"missing={missing}, extra={extra}"
            )
        return InverterCell(name=name, ports=tuple(ports))
    raise ValueError(f"{path}: no .subckt declaration found")


def engineering_value(raw_value: str) -> float:
    text = raw_value.strip().lower()
    match = re.fullmatch(
        r"([+-]?(?:(?:\d+\.\d*)|(?:\.\d+)|(?:\d+))(?:e[+-]?\d+)?)"
        r"(meg|[fpnumkg])?",
        text,
    )
    if not match:
        raise ValueError(f"invalid numeric value: {raw_value!r}")
    scales = {
        None: 1.0,
        "f": 1e-15,
        "p": 1e-12,
        "n": 1e-9,
        "u": 1e-6,
        "m": 1e-3,
        "k": 1e3,
        "meg": 1e6,
        "g": 1e9,
    }
    return float(match.group(1)) * scales[match.group(2)]


def parse_bench(path: Path) -> dict[str, str]:
    allowed = {
        "SUPPLY": {"vdd", "vss"},
        "LOAD": {"cload"},
        "TIMING": {"trise", "tfall", "tdelay", "pulse_width", "period", "tstep", "tstop", "dc_step"},
        "MEASURE": {"logic_low_max", "logic_high_min"},
    }
    values: dict[str, str] = {}
    section: str | None = None
    for number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith(("*", "#", ";")):
            continue
        if line.startswith("(") and line.endswith(")"):
            section = line[1:-1].strip().upper()
            if section not in allowed:
                raise ValueError(f"{path}:{number}: unsupported section ({section})")
            continue
        if section not in allowed or "=" not in line:
            raise ValueError(f"{path}:{number}: expected key=value inside a supported section")
        key, value = (item.strip() for item in line.split("=", 1))
        key = key.lower()
        if key not in allowed[section] or key in values or not value:
            raise ValueError(f"{path}:{number}: invalid or duplicate key {key!r}")
        values[key] = value

    if not {"vdd", "vss"}.issubset(values):
        raise ValueError(f"{path}: both vdd and vss are required")
    try:
        if Decimal(values["vdd"]) <= Decimal(values["vss"]):
            raise ValueError(f"{path}: vdd must be greater than vss")
    except InvalidOperation as exc:
        raise ValueError(f"{path}: vdd and vss must be plain decimal voltages") from exc

    bench = {**DEFAULT_BENCH, **values}
    for key in ("cload", "trise", "tfall", "tdelay", "pulse_width", "period", "tstep", "tstop", "dc_step"):
        if engineering_value(bench[key]) <= 0:
            raise ValueError(f"{path}: {key} must be positive")
    low = engineering_value(bench["logic_low_max"])
    high = engineering_value(bench["logic_high_min"])
    if not (0.0 < low < high < 1.0):
        raise ValueError(f"{path}: require 0 < logic_low_max < logic_high_min < 1")
    if engineering_value(bench["tstop"]) < engineering_value(bench["tdelay"]) + engineering_value(bench["pulse_width"]):
        raise ValueError(f"{path}: tstop is too short for the configured input pulse")
    return bench


def relative_path(target: Path, deck_path: Path) -> str:
    return os.path.relpath(target, deck_path.parent).replace("\\", "/")


def header(deck_name: str, deck_path: Path, inc: Path, n_va: Path, p_va: Path, bench: dict[str, str]) -> list[str]:
    parameters = " ".join(
        f"{key.upper()}={value}" for key, value in bench.items() if key not in {"vdd", "vss"}
    )
    return [
        f"* Auto-generated inverter PEX test: {deck_name}",
        ".option INGOLD=2 POST=2",
        f'.hdl "{relative_path(n_va, deck_path)}"',
        f'.hdl "{relative_path(p_va, deck_path)}"',
        f'.include "{relative_path(inc, deck_path)}"',
        f".param VDD_VAL={bench['vdd']} VSS_VAL={bench['vss']}",
        ".param VCORE='VDD_VAL-VSS_VAL'",
        f".param {parameters}",
        "VVSS VSS 0 'VSS_VAL'",
        "VVDD VDD VSS 'VCORE'",
        "",
    ]


def dut_line(cell: InverterCell) -> str:
    nodes = {port: port for port in REQUIRED_PORTS}
    return f"XDUT {' '.join(nodes[port.upper()] for port in cell.ports)} {cell.name}"


def dc_deck(cell: InverterCell, common: list[str]) -> str:
    return "\n".join([
        *common,
        "VA A VSS 0",
        "CLOAD Y VSS 'CLOAD'",
        dut_line(cell),
        ".dc VA 0 'VCORE' 'DC_STEP'",
        ".measure dc VOH FIND V(Y) AT=0",
        ".measure dc VOL FIND V(Y) AT='VCORE'",
        ".measure dc VM WHEN V(A)=V(Y) CROSS=1",
        ".print dc V(A) V(Y) I(VVDD)",
        ".end",
        "",
    ])


def transient_deck(cell: InverterCell, common: list[str]) -> str:
    midpoint = "VSS_VAL+0.5*VCORE"
    low = "VSS_VAL+0.1*VCORE"
    high = "VSS_VAL+0.9*VCORE"
    return "\n".join([
        *common,
        "VA A VSS PULSE(0 'VCORE' 'TDELAY' 'TRISE' 'TFALL' 'PULSE_WIDTH' 'PERIOD')",
        "CLOAD Y VSS 'CLOAD'",
        dut_line(cell),
        ".tran 'TSTEP' 'TSTOP'",
        f".measure tran TPHL TRIG V(A) VAL='{midpoint}' RISE=1 TARG V(Y) VAL='{midpoint}' FALL=1",
        f".measure tran TPLH TRIG V(A) VAL='{midpoint}' FALL=1 TARG V(Y) VAL='{midpoint}' RISE=1",
        f".measure tran TR_OUT TRIG V(Y) VAL='{low}' RISE=1 TARG V(Y) VAL='{high}' RISE=1",
        f".measure tran TF_OUT TRIG V(Y) VAL='{high}' FALL=1 TARG V(Y) VAL='{low}' FALL=1",
        ".print tran V(A) V(Y) I(VVDD)",
        ".end",
        "",
    ])


def leakage_deck(cell: InverterCell, common: list[str], input_high: bool) -> str:
    input_value = "'VCORE'" if input_high else "0"
    return "\n".join([
        *common,
        f"VA A VSS {input_value}",
        "CLOAD Y VSS 'CLOAD'",
        dut_line(cell),
        ".tran 'TSTEP' 'TSTOP'",
        ".measure tran IVDD_AVG AVG I(VVDD) FROM='TSTOP/2' TO='TSTOP'",
        ".measure tran VOUT_AVG AVG V(Y) FROM='TSTOP/2' TO='TSTOP'",
        ".print tran V(A) V(Y) I(VVDD)",
        ".end",
        "",
    ])


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_hspice(explicit_cmd: str, explicit_install_dir: str) -> Path:
    if explicit_cmd:
        candidate = Path(explicit_cmd).resolve()
        if candidate.is_file():
            return candidate
        raise FileNotFoundError(f"HSPICE executable not found: {candidate}")
    install_dirs: list[Path] = []
    if explicit_install_dir:
        install_dirs.append(Path(explicit_install_dir).resolve())
    install_dirs.extend(HSPICE_INSTALL_CANDIDATES)
    for install_dir in install_dirs:
        for relative in (r"WIN64\hspice.com", r"WIN64\hspice.exe"):
            candidate = install_dir / relative
            if candidate.is_file():
                return candidate
    discovered = shutil.which("hspice")
    if discovered:
        return Path(discovered).resolve()
    raise FileNotFoundError("Cannot find HSPICE. Pass --hspice-cmd or --install-dir.")


def collect_decks(source: Path) -> list[Path]:
    source = source.resolve()
    if source.is_file():
        if source.suffix.lower() != ".sp":
            raise ValueError(f"Expected a .sp deck, got: {source}")
        return [source]
    if not source.is_dir():
        raise FileNotFoundError(source)
    decks = sorted(path.resolve() for path in source.glob("*.sp"))
    if not decks:
        raise FileNotFoundError(f"No .sp files found in: {source}")
    return decks


def listing_has_model_error(listing: Path) -> bool:
    if not listing.is_file():
        return False
    return bool(MODEL_ERROR_RE.search(listing.read_text(encoding="utf-8", errors="ignore")))


def hspice_environment(hspice: Path, license_server: str) -> dict[str, str]:
    environment = os.environ.copy()
    if license_server:
        environment["SNPSLMD_LICENSE_FILE"] = license_server
        environment["LM_LICENSE_FILE"] = license_server
    install_dir = str(hspice.parent.parent)
    environment["installdir_P-2019.06-SP1-1"] = install_dir
    environment["installdir_O-2018.09"] = install_dir
    return environment


def run_one(deck: Path, raw_dir: Path, hspice: Path, license_server: str, rerun: bool, dry_run: bool) -> dict[str, object]:
    run_dir = raw_dir / deck.stem
    run_dir.mkdir(parents=True, exist_ok=True)
    prefix = run_dir / deck.stem
    listing = prefix.with_suffix(".lis")
    command = [str(hspice), "-i", deck.name, "-o", str(prefix)]
    status: dict[str, object] = {
        "deck": str(deck),
        "deck_name": deck.name,
        "deck_sha256": sha256(deck),
        "run_dir": str(run_dir),
        "listing": str(listing),
        "command": command,
        "reused": False,
        "return_code": None,
    }
    if not rerun and listing.is_file() and listing.stat().st_mtime >= deck.stat().st_mtime:
        status["reused"] = True
        status["return_code"] = 0
        status["model_numerical_error"] = listing_has_model_error(listing)
        return status
    if dry_run:
        status["return_code"] = 0
        status["dry_run"] = True
        return status
    completed = subprocess.run(
        command,
        cwd=deck.parent,
        env=hspice_environment(hspice, license_server),
        text=True,
        capture_output=True,
        check=False,
    )
    (run_dir / "runner_stdout_stderr.txt").write_text(
        completed.stdout + "\n" + completed.stderr,
        encoding="utf-8",
        errors="ignore",
    )
    status["return_code"] = completed.returncode
    status["outputs"] = sorted(path.name for path in run_dir.glob(f"{deck.stem}.*"))
    status["model_numerical_error"] = listing_has_model_error(listing)
    return status


def to_float(token: str) -> float | None:
    value = token.strip().replace("D", "E").replace("d", "e")
    if not NUMBER_RE.fullmatch(value):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_measurements(listing: Path) -> dict[str, float]:
    measurements: dict[str, float] = {}
    for line in listing.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = MEASURE_RE.match(line)
        if not match:
            continue
        value = to_float(match.group(2))
        if value is not None:
            measurements[match.group(1).lower()] = value
    return measurements


def deck_test_name(deck: Path) -> str:
    lowered = deck.stem.lower()
    for name in ("leak0", "leak1", "tran", "dc"):
        if lowered.endswith(f"_{name}"):
            return name
    return "validation"


def deck_supply(deck: Path) -> tuple[float, float]:
    text = deck.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"\.param\s+VDD_VAL\s*=\s*([^\s]+)\s+VSS_VAL\s*=\s*([^\s]+)", text, re.IGNORECASE)
    if not match:
        return float("nan"), float("nan")
    vdd = to_float(match.group(1))
    vss = to_float(match.group(2))
    return (
        float("nan") if vdd is None else vdd,
        float("nan") if vss is None else vss,
    )


def deck_fraction(deck: Path, name: str, default: float) -> float:
    text = deck.read_text(encoding="utf-8", errors="ignore")
    match = re.search(rf"\b{name}\s*=\s*([^\s]+)", text, re.IGNORECASE)
    if not match:
        return default
    try:
        return engineering_value(match.group(1))
    except ValueError:
        return default


def analyze_measurements(deck: Path, listing: Path) -> dict[str, object]:
    test = deck_test_name(deck)
    measured = parse_measurements(listing)
    result: dict[str, object] = {"analysis_status": "ok", **measured}
    if test == "validation":
        return {"analysis_status": "hspice_ok"}

    vdd, vss = deck_supply(deck)
    result.update({"vdd_v": vdd, "vss_v": vss})
    if test == "dc":
        required = {"voh", "vol", "vm"}
        if not required.issubset(measured):
            return {"analysis_status": "missing_dc_measurements"}
        vcore = vdd - vss
        low_limit = vss + deck_fraction(deck, "LOGIC_LOW_MAX", 0.2) * vcore
        high_limit = vss + deck_fraction(deck, "LOGIC_HIGH_MIN", 0.8) * vcore
        passed = measured["voh"] >= high_limit and measured["vol"] <= low_limit and vss <= measured["vm"] <= vdd
        result["function_pass"] = "pass" if passed else "fail"
    elif test == "tran":
        required = {"tphl", "tplh", "tr_out", "tf_out"}
        if not required.issubset(measured):
            return {"analysis_status": "missing_transient_measurements"}
        passed = all(math.isfinite(measured[name]) and measured[name] >= 0 for name in required)
        result["timing_pass"] = "pass" if passed else "fail"
    elif test in {"leak0", "leak1"}:
        required = {"ivdd_avg", "vout_avg"}
        if not required.issubset(measured):
            return {"analysis_status": "missing_leakage_measurements"}
        result["static_power_w"] = abs((vdd - vss) * measured["ivdd_avg"])
    return result


def write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def validate(inc: Path, bench: Path, n_va: Path, p_va: Path) -> None:
    """Validate inverter ports, benchmark syntax, and model inputs."""
    inc = require_file(inc)
    bench = require_file(bench)
    require_file(n_va)
    require_file(p_va)
    parse_subckt(inc)
    parse_bench(bench)


def generate_decks(inc: Path, bench: Path, n_va: Path, p_va: Path, output: Path) -> list[Path]:
    """Generate inverter DC, transient, and two leakage-state decks."""
    inc = require_file(inc)
    bench = require_file(bench)
    n_va = require_file(n_va)
    p_va = require_file(p_va)
    cell = parse_subckt(inc)
    configuration = parse_bench(bench)
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    builders = {
        "dc": lambda common: dc_deck(cell, common),
        "tran": lambda common: transient_deck(cell, common),
        "leak0": lambda common: leakage_deck(cell, common, False),
        "leak1": lambda common: leakage_deck(cell, common, True),
    }
    written: list[Path] = []
    for name, builder in builders.items():
        deck_path = output / f"{inc.stem}_{name}.sp"
        common = header(name, deck_path, inc, n_va, p_va, configuration)
        deck_path.write_text(builder(common), encoding="utf-8")
        written.append(deck_path)
        print(f"Wrote: {deck_path}")
    return written


def run_and_analyze(
    source: Path,
    output: Path,
    *,
    hspice_cmd: str = "",
    install_dir: str = "",
    license_server: str = "",
    rerun: bool = False,
    dry_run: bool = False,
    no_plot: bool = False,
) -> int:
    """Run HSPICE and create inverter status, metric, raw-data, and manifest outputs."""
    del no_plot
    decks = collect_decks(source)
    output = output.resolve()
    raw_dir = output / "raw"
    data_dir = output / "data"
    figure_dir = output / "figures"
    for directory in (raw_dir, data_dir, figure_dir):
        directory.mkdir(parents=True, exist_ok=True)
    hspice = Path(hspice_cmd or "hspice-dry-run") if dry_run else find_hspice(hspice_cmd, install_dir)

    status_rows: list[dict[str, object]] = []
    metric_rows: list[dict[str, object]] = []
    failed = False
    for deck in decks:
        status = run_one(deck, raw_dir, hspice, license_server, rerun, dry_run)
        test = deck_test_name(deck)
        return_code = int(status.get("return_code") or 0)
        numerical_error = bool(status.get("model_numerical_error", False))
        status_rows.append({
            "deck": deck.name,
            "test": test,
            "return_code": return_code,
            "reused": status.get("reused", False),
            "model_numerical_error": numerical_error,
            "listing": status["listing"],
            "run_dir": status["run_dir"],
        })
        print(f"{deck.name}: {'reused' if status.get('reused') else 'ran'} (return={return_code})")
        if dry_run:
            metric_rows.append({"deck": deck.name, "test": test, "analysis_status": "not_analyzed"})
            continue
        if return_code != 0 or numerical_error:
            failed = True
            analysis_status = "model_numerical_error" if numerical_error else "hspice_failed"
            metric_rows.append({"deck": deck.name, "test": test, "analysis_status": analysis_status})
            continue
        listing = Path(str(status["listing"]))
        if not listing.is_file():
            failed = True
            metric_rows.append({"deck": deck.name, "test": test, "analysis_status": "missing_listing"})
            continue
        metrics = analyze_measurements(deck, listing)
        metric_rows.append({"deck": deck.name, "test": test, **metrics})
        if metrics.get("analysis_status") not in {"ok", "hspice_ok"}:
            failed = True
        if metrics.get("function_pass") == "fail" or metrics.get("timing_pass") == "fail":
            failed = True

    write_rows(output / "run_status.csv", status_rows)
    write_rows(data_dir / "summary_metrics.csv", metric_rows)
    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "cell_id": CELL_ID,
        "input": str(Path(source).resolve()),
        "output": str(output),
        "hspice": str(hspice),
        "license_server": license_server,
        "decks": status_rows,
    }
    (output / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return 1 if failed else 0


