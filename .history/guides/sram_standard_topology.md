# SRAM Standard Topology

## Potential aliases

| Alias | Net |
| --- | --- |
| P1 | BL |
| P2 | Q |
| P3 | VSS |
| P4 | VDD |
| P5 | QB |
| P6 | BLB |
| P7 | WL |

## Transistor endpoints

| Device | Type | Endpoint A | Gate | Endpoint B |
| --- | --- | --- | --- | --- |
| PG1 | NFET | P1 | P7 | P2 |
| PD1 | NFET | P2 | P5 | P3 |
| PU1 | PFET | P4 | P5 | P2 |
| PD2 | NFET | P3 | P2 | P5 |
| PU2 | PFET | P4 | P2 | P5 |
| PG2 | NFET | P5 | P7 | P6 |

## Physical sharing decisions

- `PG1-PD1` are adjacent in the lower half-row and share one physical `P2` S/D.
- `PD2-PG2` are adjacent in the mirrored upper half-row and share one physical `P5` S/D.
- `PD1-PU1` use a common gate at `P5`.
- `PD2-PU2` use a common gate at `P2`.
- The PFET `P2/P5` terminals are vertically aligned with the corresponding
  NFET storage node, but vertical merging is not assumed until MD/BMD/MRW and
  power-rail assignments are confirmed.

## MRW and via landing rule

- MRW always occupies the merged double-row window `y=56..68 nm`.
- MRW CPP centers must coincide with a gate center or the midpoint of adjacent
  gate centers.
- Current storage-node MRWs use adjacent-gate midpoints:
  `P2/Q: x=38..46 nm`, centered at 42 nm;
  `P5/QB: x=80..88 nm`, centered at 84 nm.
- An upper metal must fully cover its via projection.
- For 8 nm V1/V2 under 14 nm M1/M2, the landing metal provides 3 nm enclosure
  on the two width edges and the terminating edge.
- M0 uses its fixed track width, so an 8 nm V0 receives 1 nm enclosure on the
  corresponding three landing edges. Boundary supply vias are the exception
  because non-metal geometry may not exceed the cell boundary.

## Double-row placement

```text
upper half-row, mirrored: P3 / PD2(P2) / P5 / PG2(P7) / P6
lower half-row:           P1 / PG1(P7) / P2 / PD1(P5) / P3
```

Each minimum double-row placement unit is `1 CPP x 124 nm`, formed by two
head-to-head `1 CPP x 62 nm` half units. The standard 6T placement uses three
units along CPP. The upper NFET chain is shifted by one CPP so that `P2` and
`P5` occupy distinct shared-S/D and MRW sites. The full-cell envelope is
`3 CPP x 124 nm`.

```text
CPP column:       0              1                 2
upper row:                       PD2/PU2(P2)       PG2(P7)
lower row:        PG1(P7)        PD1/PU1(P5)
shared S/D:            P2                  P5
MRW site:              Q                   QB
```

## SDE generation

Run:

```bat
run_sram_standard_layout.bat
```

The batch file validates the layout and then generates:

```text
gds/sram_standard_6t.gds
layout_views/sram_standard_6t_frontside.png
layout_views/sram_standard_6t_backside.png
layout_views/sram_standard_6t_mixed.png
SDE/sram_standard_6t_sde.cmd
```

`gen_sram_standard_sde.py` reads all x/y geometry from
`gds/sram_standard_6t_gds.txt`. It reads z ranges and materials from
`rules/sram_standard_layer_rule.txt`, and device/doping/mesh hyperparameters
from `rules/sram_standard_arch.txt`.

The generated structure contains four physical common gates representing six
transistors, two sheets per tier, shared P2/P5 S/D regions, layout-driven
MD/BMD/MRW and interconnect, seven named electrical contacts, S/D doping and
the final `n@node@_sram_standard_6t` mesh command.
