"""Configuration packages, isolated execution, and a local SQLite catalog."""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
import uuid
import zipfile
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parents[1]
ROLES = {"layout", "params", "stack", "rules", "n_va", "p_va", "pin", "bench", "adapter", "r_matrix", "c_matrix"}
OPTIONS = {"md_layer", "bmd_layer", "backside_prefix", "strict_contact_face"}


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def resolve_profile(path, chain=()):
    """Inherited relative paths are relative to the manifest declaring them."""
    path = Path(path).resolve()
    if path in chain:
        raise ValueError(f"Configuration inheritance cycle: {path}")
    raw = read_json(path)
    allowed = {"schema_version", "id", "version", "description", "cell", "extends", "files", "sha256", "stages", "options", "provenance", "warnings"}
    if not isinstance(raw, dict) or set(raw) - allowed:
        raise ValueError(f"Unknown configuration fields in {path}")
    if raw.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")
    if any(not isinstance(raw.get(k, {}), dict) for k in ("files", "sha256", "options")):
        raise ValueError("files, sha256, and options must be objects")
    if raw.get("extends"):
        result = resolve_profile(path.parent / raw["extends"], (*chain, path))
    else:
        result = {"files": {}, "sha256": {}, "options": {}, "stages": ["pex"], "manifest_chain": []}
    for key in ("id", "version", "description", "cell", "stages", "provenance", "warnings"):
        if key in raw:
            result[key] = raw[key]
    for role, relative in raw.get("files", {}).items():
        if role not in ROLES or not isinstance(relative, str) or not relative:
            raise ValueError(f"Invalid input role/path: {role}")
        result["files"][role] = str((path.parent / relative).resolve())
        # A changed file must not silently inherit its parent's checksum.
        result["sha256"].pop(role, None)
    result["sha256"].update(raw.get("sha256", {}))
    result["options"].update(raw.get("options", {}))
    result["manifest"] = str(path)
    result["manifest_chain"].append({"path": str(path), "sha256": digest(path)})
    return result


def validate_profile(path):
    p = resolve_profile(path)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", p.get("id", "")):
        raise ValueError("id must be a portable single directory name")
    if not isinstance(p.get("version"), str) or not p["version"]:
        raise ValueError("version is required")
    if not re.fullmatch(r"[a-z][a-z0-9_]*", p.get("cell", "")):
        raise ValueError("cell is required")
    if not isinstance(p["stages"], list) or not p["stages"] or not all(isinstance(s, str) for s in p["stages"]) or len(p["stages"]) != len(set(p["stages"])) or set(p["stages"]) - {"sde", "drc", "pex"}:
        raise ValueError("stages must be a nonempty unique list of sde/drc/pex")
    if set(p["options"]) - OPTIONS:
        raise ValueError("Unknown PEX option")
    for key, value in p["options"].items():
        if key == "strict_contact_face":
            if not isinstance(value, bool):
                raise ValueError("strict_contact_face must be boolean")
        elif not isinstance(value, str) or not value:
            raise ValueError(f"{key} must be a nonempty string")
    required = set()
    if "sde" in p["stages"] or "drc" in p["stages"]:
        required |= {"layout", "params", "stack", "rules"}
    if "pex" in p["stages"]:
        required |= {"pin", "bench", "adapter", "n_va", "p_va", "r_matrix", "c_matrix"}
    if required - p["files"].keys():
        raise ValueError(f"Missing inputs: {sorted(required - p['files'].keys())}")
    for role, source in p["files"].items():
        if not Path(source).is_file():
            raise FileNotFoundError(f"{role}: {source}")
        if p["sha256"].get(role) != digest(source):
            raise ValueError(f"Checksum missing or changed for {role}; create a new package version")
    if "adapter" in p["files"]:
        tree = ast.parse(Path(p["files"]["adapter"]).read_text(encoding="utf-8-sig"))
        cells = [ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "CELL_ID" for t in n.targets)]
        if cells != [p["cell"]]:
            raise ValueError(f"Adapter CELL_ID {cells} does not match {p['cell']}")
    return p


def fork_profile(source, destination, name, changes):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name):
        raise ValueError("Invalid package id")
    p = validate_profile(source)
    replacements = {}
    for item in changes:
        role, sep, filename = item.partition("=")
        if not sep or role not in ROLES or not Path(filename).is_file():
            raise ValueError(f"Use --set role=existing-file: {item}")
        replacements[role] = str(Path(filename).resolve())
    p["files"].update(replacements)
    destination = Path(destination).resolve()
    if destination.exists():
        raise FileExistsError(destination)
    destination.mkdir(parents=True)
    output = {k: p[k] for k in ("cell", "stages", "options")}
    output.update(schema_version=1, id=name, version="1", description="Independent editable configuration package", files={}, sha256={}, provenance={"forked_from": p["id"], "version": p["version"]})
    output["warnings"] = p.get("warnings", [])
    output["provenance"]["source_provenance"] = p.get("provenance", {})
    if {"r_matrix", "c_matrix"} & replacements.keys():
        output["provenance"]["rc_origin"] = "user_replaced_requires_review"
    for role, source in p["files"].items():
        relative = f"inputs/{role}{Path(source).suffix}"
        target = destination / relative
        target.parent.mkdir(exist_ok=True)
        shutil.copy2(source, target)
        output["files"][role] = relative
        output["sha256"][role] = digest(target)
    write_json(destination / "profile.json", output)
    validate_profile(destination / "profile.json")
    return destination / "profile.json"


@contextmanager
def connect(local):
    folder = Path(local) / "catalog"
    folder.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(folder / "ldm.sqlite")
    try:
        db.execute("PRAGMA foreign_keys=ON")
        db.executescript((ROOT / "tools" / "schema.sql").read_text(encoding="utf-8"))
        with db:
            yield db
    finally:
        db.close()


def index_run(local, directory, manifest):
    with connect(local) as db:
        p = manifest["profile"]
        db.execute("INSERT INTO configuration_packages VALUES(?,?,?,?) ON CONFLICT(id,version) DO UPDATE SET manifest_path=excluded.manifest_path,payload=excluded.payload", (p["id"], p["version"], p["manifest"], json.dumps(p, ensure_ascii=False)))
        db.execute("INSERT INTO runs VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(run_id) DO UPDATE SET status=excluded.status,finished_at=excluded.finished_at,directory=excluded.directory,manifest_json=excluded.manifest_json", (manifest["run_id"], manifest["profile"]["id"], manifest["profile"]["version"], manifest["started_at"], manifest["finished_at"], manifest["status"], str(directory), json.dumps(manifest, ensure_ascii=False)))
        db.execute("DELETE FROM artifacts WHERE run_id=?", (manifest["run_id"],))
        for path in directory.rglob("*"):
            if path.is_file():
                db.execute("INSERT INTO artifacts(run_id,path,bytes,sha256) VALUES(?,?,?,?)", (manifest["run_id"], str(path.relative_to(directory)), path.stat().st_size, digest(path)))
        db.execute("DELETE FROM stages WHERE run_id=?", (manifest["run_id"],))
        for step in manifest["stages"]:
            db.execute("INSERT INTO stages VALUES(?,?,?,?,?)", (manifest["run_id"], step["name"], step["returncode"], step["status"], step["log"]))
        db.execute("DELETE FROM measurements WHERE run_id=?", (manifest["run_id"],))
        # Preserve original CSV rows, including status/warning fields. No inferred passes.
        for path in directory.rglob("*metrics.csv"):
            with path.open(encoding="utf-8-sig", newline="") as stream:
                for number, row in enumerate(csv.DictReader(stream), 1):
                    db.execute("INSERT INTO measurements(run_id,source,row_number,payload) VALUES(?,?,?,?)", (manifest["run_id"], str(path.relative_to(directory)), number, json.dumps(row, ensure_ascii=False)))


def run_profile(path, local, *, simulate=False, dry_run=False, hspice=""):
    p = validate_profile(path)
    for warning in p.get("warnings", []):
        print(f"Configuration note: {warning}")
    if simulate and dry_run:
        raise ValueError("simulate and dry_run are mutually exclusive")
    if simulate and "pex" not in p["stages"]:
        raise ValueError("This configuration has no simulation stage")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid.uuid4().hex[:10]
    directory = (Path(local) / "runs" / p["id"] / run_id).resolve()
    if directory.is_relative_to(ROOT):
        raise ValueError("Run data must be outside LDM_release")
    directory.mkdir(parents=True)
    inputs = directory / "inputs"
    inputs.mkdir()
    framework = directory / "framework"
    for script in (ROOT / "core").glob("*.py"):
        target = framework / "core" / script.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(script, target)
    for relative in ("ldm.py", "tools/workspace.py", "tools/schema.sql"):
        target = framework / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    snapshot = {}
    for role, source in p["files"].items():
        target = inputs / f"{role}{Path(source).suffix}"
        shutil.copy2(source, target)
        if digest(target) != p["sha256"][role]:
            raise ValueError(f"Input changed while snapshotting: {role}")
        snapshot[role] = target
    mode = "simulate" if simulate else "dry_run" if dry_run else "generate"
    manifest = {"schema_version": 1, "run_id": run_id, "started_at": now(), "finished_at": None, "status": "running", "mode": mode, "profile": p, "snapshot": {r: str(v.relative_to(directory)) for r, v in snapshot.items()}, "framework_sha256": {str(f.relative_to(ROOT)): digest(f) for f in [*sorted((ROOT / "core").glob("*.py")), ROOT / "tools/workspace.py", ROOT / "ldm.py"]}, "python": sys.version, "stages": [], "scientific_validation": "not_evaluated"}
    write_json(directory / "manifest.json", manifest)
    def execute(name, args):
        log = directory / f"{name}.log"
        with log.open("w", encoding="utf-8") as stream:
            result = subprocess.run([sys.executable, "-B", *map(str, args)], cwd=directory, stdout=stream, stderr=subprocess.STDOUT)
        manifest["stages"].append({"name": name, "returncode": result.returncode, "status": "passed" if result.returncode == 0 else "failed", "log": log.name})
        write_json(directory / "manifest.json", manifest)
        if result.returncode:
            raise RuntimeError(f"{name} failed ({result.returncode}); see {log}")
    try:
        if "sde" in p["stages"]:
            execute("sde", [framework / "core/gen_sde.py", snapshot["layout"], snapshot["params"], snapshot["stack"], "--design-rules", snapshot["rules"], "-o", directory / "sde" / "cell_sde.cmd"])
        if "drc" in p["stages"]:
            execute("drc", [framework / "core/gen_drc_report.py", *[snapshot[k] for k in ("layout", "params", "stack", "rules")], "-o", directory / "drc.txt"])
        if "pex" in p["stages"]:
            args = [framework / "core/run_cell.py", "--name", p["id"], "--cell", p["cell"], "--input-model-dir", inputs, "--output", directory / "outputs", "--no-plot"]
            for role, flag in {"pin": "--pin", "bench": "--bench", "adapter": "--cell-script", "n_va": "--n-va", "p_va": "--p-va", "r_matrix": "--r-matrix", "c_matrix": "--c-matrix"}.items():
                args += [flag, snapshot[role]]
            for key, value in p["options"].items():
                if isinstance(value, bool):
                    if value:
                        args.append("--" + key.replace("_", "-"))
                else:
                    args += ["--" + key.replace("_", "-"), value]
            if hspice:
                args += ["--hspice-cmd", hspice]
            if dry_run:
                args.append("--dry-run")
            elif not simulate:
                args.append("--generate-only")
            execute("pex", args)
        manifest["status"] = {"generate": "generated", "dry_run": "dry_run_completed", "simulate": "simulation_completed"}[mode]
        if simulate:
            manifest["scientific_validation"] = "see_adapter_results_and_warnings"
    except BaseException as exc:
        manifest["status"] = "failed"
        manifest["error"] = str(exc)
        raise
    finally:
        manifest["finished_at"] = now()
        write_json(directory / "manifest.json", manifest)
        index_run(local, directory, manifest)
        print(f"Run: {directory}\nStatus: {manifest['status']}")
    return directory


def audit_release():
    forbidden = {".git", ".history", "__pycache__", ".venv", "runs", "output", "dist"}
    files = []
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if relative.parts[0] == ".git":
            continue
        if set(relative.parts) & forbidden or path.is_symlink():
            raise ValueError(f"Forbidden release content: {relative}")
        if path.is_file():
            if path.stat().st_size > 10_000_000 or path.suffix in {".sqlite", ".db", ".pyc", ".log", ".lis"} or path.name.endswith(".local.json"):
                raise ValueError(f"Local/generated file in release: {relative}")
            files.append(path)
    for path in (ROOT / "configs").rglob("profile.json"):
        profile = validate_profile(path)
        if any(not Path(f).is_relative_to(ROOT) for f in profile["files"].values()):
            raise ValueError(f"External dependency in release profile: {path}")
        if any(not Path(m["path"]).is_relative_to(ROOT) for m in profile["manifest_chain"]):
            raise ValueError(f"External inherited manifest in release profile: {path}")
    return files


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-root", type=Path, default=ROOT.parent / "LDM_local")
    sub = parser.add_subparsers(dest="command", required=True)
    listing = sub.add_parser("list", help="Discover packages without executing adapters")
    listing.add_argument("--repository", type=Path, default=ROOT / "configs")
    check = sub.add_parser("validate")
    check.add_argument("profile", type=Path)
    fork = sub.add_parser("fork", help="Create an independent portable package; replace any input")
    fork.add_argument("profile", type=Path)
    fork.add_argument("destination", type=Path)
    fork.add_argument("--id", required=True)
    fork.add_argument("--set", action="append", default=[])
    run = sub.add_parser("run")
    run.add_argument("profile", type=Path)
    mode = run.add_mutually_exclusive_group()
    mode.add_argument("--simulate", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    run.add_argument("--hspice-cmd", default="")
    catalog = sub.add_parser("catalog")
    catalog.add_argument("--kind", choices=["runs", "configs", "legacy"], default="runs")
    catalog.add_argument("--query", default="")
    backup = sub.add_parser("backup-catalog")
    backup.add_argument("destination", type=Path)
    sub.add_parser("self-test")
    rebuild = sub.add_parser("reindex")
    rebuild.add_argument("--runs", type=Path)
    sub.add_parser("audit-release")
    export = sub.add_parser("export")
    export.add_argument("destination", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.local_root.resolve().is_relative_to(ROOT):
            raise ValueError("Local data/catalog must be outside LDM_release")
        if args.command == "list":
            for path in sorted(args.repository.rglob("profile.json")):
                p = resolve_profile(path)
                print(f"{p.get('id')}@{p.get('version')} [{p.get('cell')}] {path}")
        elif args.command == "validate":
            p = validate_profile(args.profile)
            print(f"VALID: {p['id']}@{p['version']}; stages={p['stages']}")
        elif args.command == "fork":
            print(fork_profile(args.profile, args.destination, args.id, args.set))
        elif args.command == "run":
            run_profile(args.profile, args.local_root, simulate=args.simulate, dry_run=args.dry_run, hspice=args.hspice_cmd)
        elif args.command == "catalog":
            with connect(args.local_root) as db:
                query = "%" + args.query + "%"
                sql = {"runs": "SELECT run_id,profile_id,status FROM runs WHERE profile_id LIKE ? ORDER BY started_at DESC LIMIT 50", "configs": "SELECT id,version,manifest_path FROM configuration_packages WHERE id LIKE ? ORDER BY id LIMIT 100", "legacy": "SELECT category,relative_path,file_count,logical_bytes FROM legacy_collections WHERE relative_path LIKE ? ORDER BY category,relative_path LIMIT 100"}[args.kind]
                for row in db.execute(sql, (query,)):
                    print(*row)
        elif args.command == "backup-catalog":
            destination = args.destination.resolve()
            if destination.exists() or destination.is_relative_to(ROOT):
                raise ValueError("Backup needs a new filename outside LDM_release")
            destination.parent.mkdir(parents=True, exist_ok=True)
            with connect(args.local_root) as source:
                target = sqlite3.connect(destination)
                try:
                    source.backup(target)
                finally:
                    target.close()
            print(destination)
        elif args.command == "self-test":
            return subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", str(ROOT / "tests"), "-v"]).returncode
        elif args.command == "reindex":
            for path in (args.runs or args.local_root / "runs").rglob("manifest.json"):
                record = read_json(path)
                if "run_id" in record and "snapshot" in record:
                    index_run(args.local_root, path.parent, record)
                    print(record["run_id"])
        elif args.command == "audit-release":
            files = audit_release()
            print(f"PASS: {len(files)} files, {sum(f.stat().st_size for f in files):,} bytes; all bundled profiles are self-contained")
        elif args.command == "export":
            files = audit_release()
            destination = args.destination.resolve()
            if destination.is_relative_to(ROOT) or destination.exists():
                raise ValueError("Export needs a new filename outside LDM_release")
            destination.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(destination, "x", zipfile.ZIP_DEFLATED) as archive:
                for path in files:
                    archive.write(path, Path("AutoLDM") / path.relative_to(ROOT))
            print(destination)
        return 0
    except (ValueError, OSError, RuntimeError, sqlite3.Error) as exc:
        print(f"LDM: {exc}", file=sys.stderr)
        return 2
