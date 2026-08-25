---
name: autoldm-standard-cell-layout
description: Generate or revise AutoLDM CFET standard-cell rectangle layouts and GDS by deriving layer, grid, contact, and power-rail conventions from a known working reference cell, then validating SDE and GDS roundtrip. Use for INV, NAND, NOR, AOI, OAI, latch, SRAM-adjacent cells, or other standard-cell layout inputs under FLOW; do not use to claim foundry signoff or real extracted RC.
---

# AutoLDM Standard-Cell Layout

Generate a target layout from a verified local reference instead of freehand coordinates. Treat the working reference as the source of this repository's layout convention; treat the stack and design-rule files as the source of layer/Z behavior.

## Required context

Before editing, identify:

- the target logical cell and its transistor `S/G/D/B` network;
- a reference cell that already completes the current SDE flow;
- the target project's layout, params, stack, rules, GDS converter, and output paths;
- whether the request includes only layout or also pin, bench, RC, PEX, and simulation files.

Use `FLOW/test/INPUT_MODEL/test_gds.txt` as the default reference only when the user has not named a different verified reference. Do not infer permission to change common generators or unrelated cells.

## Load task-specific guidance

- Read [references/cfet-sram-layer-template.md](references/cfet-sram-layer-template.md) when the working SRAM is the reference or when comparing layer-by-layer with it.
- Read [references/topology-planning.md](references/topology-planning.md) before placing a new logic topology or changing gate order and shared diffusion.
- Read [references/autoldm-contract.md](references/autoldm-contract.md) before writing files or running the final validation sequence.
- Use [references/inverter-spec.example.json](references/inverter-spec.example.json) only as a reviewed one-gate example when the working SRAM remains the reference; do not reuse its topology for another cell.

## Workflow

1. Inspect the verified reference layout, target stack, parameters, rules, and existing target files. Preserve user changes and record which files are reference-only.
2. Run `scripts/layout_contract.py summarize <reference-layout>` and derive the current tile width, gate pitch/phase, S/D contact phase, layer dimensions, and VDD/VSS rail convention. Do not copy remembered coordinates when the reference can be measured.
3. Establish the transistor topology and gate order. Confirm that every shared gate and S/D column represents compatible electrical nodes. Stop if the requested topology cannot be represented by the current single-row CFET template without an unsupported diffusion break or isolation feature.
4. Create a reviewed JSON rectangle specification containing `cell_name`, `unit`, comments, and ordered rectangles. Render it with `scripts/render_layout.py <spec.json> <target_gds.txt>`; do not write binary GDS directly.
5. Run `scripts/layout_contract.py validate --reference <reference> --candidate <target> --ports <comma-separated-ports>`. Fix every ERROR. Explain any WARNING using the target stack and rules.
6. Run the target copy of `gen_sde.py --validate-only` and require a successful preflight with no structural errors.
7. Convert text to GDS with the target project's `txt2gds.py`, convert it back with `gds2txt.py`, and use `scripts/layout_contract.py exact` to compare parsed positive-area rectangles and labels. Remove only the roundtrip temporary file after resolving and checking its path.
8. If pin/RC/PEX work is in scope, verify that layout labels, pin manifest nodes, matrix contacts, FET nodes, and PEX ports agree. Clearly mark artificial RC as synthetic; never present it as extracted data.
9. Report the reference, topology, gate order, tile count, per-layer purpose, rail ranges, validation outcomes, and remaining non-signoff limitations.

## Non-negotiable checks

- Keep project name and logical cell name separate.
- Extend the M0 VSS and BM0 VDD rails to the standard cell's full effective X extent: their `x1` must equal the minimum X and their `x2` must equal the maximum X of all positive-area, non-power-rail layout shapes. The rails may extend beyond the layer-1 cell boundary. Ignore zero-area locator/metadata rows when calculating this extent, and keep the local V0/BV0 at the source contact.
- Keep gate and labeled MD/BMD centers on the measured reference phases unless a different verified reference justifies a change.
- Ensure boundary tile count matches functional gate count unless dummy/reserved tiles are explicitly modeled and supported.
- Never hide incompatible nodes behind a combined label.
- Do not call a layout correct solely because HSPICE passes: HSPICE may be using a pin manifest and synthetic RC that are independent of geometry.
- Describe success as "conforms to the current AutoLDM reference contract and generates successfully," not as foundry LVS/signoff.
