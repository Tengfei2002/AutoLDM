# Historical files and repository migration

The repository was reorganized on 2026-11-10. The previous default-branch commit is:

[`a025e74dc4a9702109dfb2962c775422ce3ac793`](https://github.com/Tengfei2002/AutoLDM/tree/a025e74dc4a9702109dfb2962c775422ce3ac793).

The existing commit chain is retained. Old files are removed from the current tree rather than copied into another tracked archive directory.

| Previous location | Current disposition |
|---|---|
| `FLOW/test/gen_sde.py`, `gen_drc_report.py`, `gen_pex.py`, `run_cell.py` | Common framework in `core/` |
| `FLOW/test/INPUT_MODEL/txt_gds_trans/` | GDS conversion utilities in `core/` |
| `FLOW/inv_test/` | Minimal configuration in `configs/minimal_inv/` and adapter in `adapters/inv.py` |
| `Database/sdc/` | Standard-cell generator, catalog, and resources in `resources/standard_cells/` |
| `fitness/fit_hspice_va.py` | `core/fit_hspice_va.py`, with explicit input/output paths |
| Other `FLOW/` projects and fitted-model outputs | Historical commit and separately managed local research data |
| `Database/StandardCellsGDS/` | Historical layout resources; inspect the original files in the previous commit |
| `SKILL/` | Historical automation wrappers; their old paths are not the supported current interface |
| `.Referance_Paper/`, `.paper_publish/`, `PKU_TODO/`, `.readme/` | Historical research/reference material, excluded from the software distribution |
| `.history/`, `__pycache__/` | Editor snapshots and generated caches, excluded from current commits |

## Retrieve a historical file

After cloning the repository, inspect a file without replacing the current framework:

```sh
git show a025e74dc4a9702109dfb2962c775422ce3ac793:readme.md
git log --all -- FLOW/test/gen_pex.py
```

Use the commit link above to browse old binary documents or layouts. Historical paths and assumptions do not imply that an old project can run in the current layout without migration.

## Research-data boundaries

Local prompt records, experiment catalogs, reports, and retained results belong in a sibling data directory such as `LDM_local/`; they are not uploaded by this repository. Data explicitly deleted during local retention cleanup is not restored by this source-code update. Some local experiments were never committed to GitHub.

## History size

Before cleanup, the default-branch tree contained 9,819 files, with 8,604 editor-history files. The GitHub repository metadata reported approximately 64 MB of repository storage. The much larger former local `.git` directory is not evidence that the same data was pushed to GitHub.

No commit ancestry is rewritten by this cleanup. Historical files remain retrievable from earlier commits, so their storage does not disappear merely because they are absent from the latest tree.
