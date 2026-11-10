# Development and commit rules

Use this source directory as the development worktree. Keep experiment data, credentials, and machine-specific configuration outside it.

Before committing, run:

```sh
python -B tools/check_repository.py
python -B ldm.py self-test
git diff --check
git status --short
git diff --cached --stat
```

The content check rejects editor histories, generated simulation output, local databases, secrets/configuration files, and single files exceeding the project's 10 MB limit. This is a project policy, not GitHub's own size limit. Small test fixtures, configuration manifests, CSV reference data, and source `.sp`/`.va` files can be legitimate tracked inputs.

Commit related code, focused tests, and documentation together. Keep one purpose per commit. Inspect the staged files before pushing. Use tags for stable versions and generate release archives from a verified version rather than maintaining another manually copied source tree.

LF line endings are required by `.gitattributes`: the bundled configuration checksums describe the exact file bytes. When deliberately replacing an input, create a new configuration-package version and record its new checksum. Do not silently update a package that has already been used for an experiment.

The minimal suite uses Python's standard library and synthetic RC; commercial HSPICE/Sentaurus execution and scientific-model validation require separate environments and results.

Third-party model copyright notices are retained. No repository-wide license is added by this cleanup, and the presence of a model or paper in historical commits is not a new grant of redistribution rights.

Vendored Verilog-A models retain their existing formatting. Their path-specific Git whitespace attribute suppresses inherited trailing-space and indentation-style findings; model equations and parameters are not changed by formatting checks.
