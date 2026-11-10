# Changelog

## 2026-11-10 — repository cleanup

- Restore the README's five architecture/workflow diagrams and their explanations, with paths and execution boundaries updated to the current framework.
- Extract the common SDE, DRC, PEX, fitting, GDS conversion, and cell-runner code into `core/`.
- Keep one self-contained inverter example and the standard-cell generator resources.
- Add replaceable configuration packages, input checksums, isolated runs, and a local result catalog.
- Remove editor histories, caches, research reports, bulk simulation outputs, and personal planning files from the current repository tree.
- Document the previous layout and its last commit in `docs/history.md`; retain the existing Git commit chain.
- Enforce LF checkout for portable input checksums and provide a repository-content check.

This cleanup does not rerun commercial simulations or validate physical device performance. The inverter example uses synthetic RC values.
