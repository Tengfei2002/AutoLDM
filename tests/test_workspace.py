"""Behavioral checks for portable packages, isolation, and the minimal flow."""
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.workspace import validate_profile, resolve_profile, fork_profile, write_json, digest, run_profile, index_run, read_json, connect


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        temp_root = Path(os.environ.get("LDM_TEST_TMP", ROOT.parent / "LDM_local/test_tmp")).resolve()
        temp_root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="ldm test space ", dir=temp_root)
        self.base = Path(self.temp.name)
        def cleanup():
            if not self.base.resolve().is_relative_to(temp_root) or self.base.resolve() == temp_root:
                raise ValueError("Unsafe test cleanup target")
            self.temp.cleanup()
        self.addCleanup(cleanup)

    def fork(self):
        return fork_profile(ROOT / "configs/minimal_inv/profile.json", self.base / "package", "custom_inv", [])

    def test_fork_is_self_contained_and_relocatable(self):
        profile = self.fork()
        shutil.move(profile.parent, self.base / "relocated")
        p = validate_profile(self.base / "relocated/profile.json")
        self.assertTrue(all(Path(f).is_relative_to(self.base / "relocated") for f in p["files"].values()))

    def test_changed_input_is_rejected(self):
        profile = self.fork()
        p = validate_profile(profile)
        with Path(p["files"]["bench"]).open("a") as stream:
            stream.write("\n% intentional change\n")
        with self.assertRaisesRegex(ValueError, "Checksum"):
            validate_profile(profile)

    def test_inherited_paths_use_declaring_directory(self):
        profile = self.fork()
        child = self.base / "other/profile.json"
        write_json(child, {"schema_version": 1, "id": "child", "version": "2", "extends": "../package/profile.json"})
        self.assertEqual(validate_profile(profile)["files"], validate_profile(child)["files"])

    def test_inheritance_cycle_is_rejected(self):
        profile = self.base / "cycle.json"
        write_json(profile, {"schema_version": 1, "extends": "cycle.json"})
        with self.assertRaisesRegex(ValueError, "cycle"):
            resolve_profile(profile)

    def test_override_requires_its_own_checksum(self):
        profile = self.fork()
        child = self.base / "child.json"
        bench = self.base / "new_bench.txt"
        bench.write_text("changed", encoding="utf-8")
        write_json(child, {"schema_version": 1, "extends": "package/profile.json", "files": {"bench": "new_bench.txt"}})
        with self.assertRaisesRegex(ValueError, "Checksum"):
            validate_profile(child)

    def test_cell_mismatch_and_unknown_field_are_rejected(self):
        profile = self.fork()
        p = read_json(profile)
        p["cell"] = "nand2"
        write_json(profile, p)
        with self.assertRaisesRegex(ValueError, "CELL_ID"):
            validate_profile(profile)
        p["cell"] = "inv"
        p["typo"] = 1
        write_json(profile, p)
        with self.assertRaisesRegex(ValueError, "Unknown"):
            validate_profile(profile)

    def test_replacement_package_uses_new_bench(self):
        bench = self.base / "bench.txt"
        original = validate_profile(ROOT / "configs/minimal_inv/profile.json")
        bench.write_bytes(Path(original["files"]["bench"]).read_bytes() + b"\n% local variant\n")
        profile = fork_profile(ROOT / "configs/minimal_inv/profile.json", self.base / "variant", "variant", [f"bench={bench}"])
        self.assertEqual(validate_profile(profile)["sha256"]["bench"], digest(bench))
        self.assertNotEqual(original["sha256"]["bench"], digest(bench))

    def test_minimal_generation_and_catalog_rebuild(self):
        directory = run_profile(ROOT / "configs/minimal_inv/profile.json", self.base / "local")
        manifest = read_json(directory / "manifest.json")
        self.assertEqual(manifest["status"], "generated")
        self.assertEqual(manifest["scientific_validation"], "not_evaluated")
        decks = list((directory / "outputs/sp/inv").glob("*.sp"))
        self.assertEqual(len(decks), 4)
        netlist = (directory / "outputs/minimal_inv_pex.inc").read_text()
        self.assertIn(".subckt MINIMAL_INV_PEX A Y VDD VSS", netlist)
        resistors = {line.split()[0]: float(line.split()[3]) for line in netlist.splitlines() if line.startswith("R_")}
        self.assertEqual(resistors["R_A_N1_G_A"], 8)
        self.assertEqual(resistors["R_VSS_N1_SD_VSS"], 7)
        self.assertEqual(len(resistors), 6)
        self.assertIn("ERROR=0", (directory / "drc.txt").read_text())
        self.assertEqual(len(list((directory / "sde").glob("*.cmd"))), 2)
        index_run(self.base / "local", directory, manifest)
        index_run(self.base / "local", directory, manifest)
        with connect(self.base / "local") as db:
            self.assertEqual(db.execute("SELECT count(*) FROM runs").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT count(*) FROM stages").fetchone()[0], 3)
            self.assertGreater(db.execute("SELECT count(*) FROM artifacts").fetchone()[0], 10)

    def test_failed_stage_is_recorded(self):
        profile = self.fork()
        p = read_json(profile)
        adapter = profile.parent / p["files"]["adapter"]
        adapter.write_text("CELL_ID = 'inv'\nraise RuntimeError('intentional adapter failure')\n", encoding="utf-8")
        p["sha256"]["adapter"] = digest(adapter)
        write_json(profile, p)
        with self.assertRaisesRegex(RuntimeError, "pex failed"):
            run_profile(profile, self.base / "local")
        with connect(self.base / "local") as db:
            self.assertEqual(db.execute("SELECT status FROM runs").fetchone()[0], "failed")

    def test_release_can_run_from_another_directory(self):
        isolated = self.base / "isolated release"
        shutil.copytree(ROOT, isolated, ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache"))
        result = subprocess.run([sys.executable, "-B", str(isolated / "ldm.py"), "--local-root", str(self.base / "external data"), "run", str(isolated / "configs/minimal_inv/profile.json"), "--dry-run"], cwd=self.base, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("dry_run_completed", result.stdout)


if __name__ == "__main__":
    unittest.main()
