# SRAM reference metrics extracted from local papers

## Scope and extraction rule

This note summarizes SRAM-related metrics reported in the papers stored in this folder. Values are extracted from PDF text, captions, tables, and visually inspected key figures. When a value is read from a plotted figure rather than an explicit table/caption, it is marked as approximate. Papers that discuss transistor/platform technology but do not report SRAM cell or SRAM macro metrics are explicitly marked as not reporting a concrete SRAM benchmark.

## 1. Main SRAM metrics appearing in the papers

| Metric | Definition | How it is usually calculated or measured | Where it appears in these papers |
|---|---|---|---|
| Cell area | Physical bitcell footprint. Usually reported in `um^2` or `10^-3 um^2`. | Layout area per bitcell; sometimes effective macro area per bit includes periphery/KOZ overhead. | Abdi 2025, Lu 2025, Peng 2025, Yeap 2024 |
| SRAM macro density | Number of memory bits per chip area, usually `Mb/mm^2`. | `macro capacity / macro physical area`. | Yeap 2024 |
| HSNM | Hold static noise margin, cell stability when `WL=0`. | Hold-mode butterfly curve; SNM is the smaller maximum square inside the butterfly lobes. | Abdi 2025, Huang 2025, Shahin 2025 |
| RSNM/SNMR | Read static noise margin, cell stability during read. | Read-mode butterfly curve with read bias, usually `WL=VDD`, bit-lines precharged. Some papers call it SNMR. | Abdi 2025, Ha 2025, Huang 2025, Lu 2025, Peng 2025, Shahin 2025 |
| WSNM/WRM/write margin | Write ability; smaller write effort or larger margin means easier write. | Bit-line sweep, write butterfly, or write trip point. Exact method depends on paper. | Abdi 2025, Ha 2025, Lu 2025, Peng 2025, Shahin 2025 |
| Read delay/access delay | Time needed to read out the cell. | Often from `WL` activation to a bit-line voltage/drop threshold. Lu defines it from `WL=0.5*VDD` to `BL` drop of 200 mV. | Abdi 2025, Lu 2025, Peng 2025, Shahin 2025 |
| Write delay | Time needed for internal storage nodes to flip. | Lu defines it from `WL=0.5*VDD` to intersection of the two storage-node voltages. Other papers use operation-delay distributions. | Lu 2025, Peng 2025, Shahin 2025 |
| Read/write power | Dynamic power during read/write. | Transient current/power in read or write operation; commonly affected by WL/BL capacitance. | Lu 2025 |
| Leakage/hold current | Standby or hold current of SRAM cell/array. | Hold-state current, often at elevated temperature. | Ha 2025, Peng 2025 |
| Vmin | Minimum operating voltage for SRAM read/write or macro shmoo. | Shmoo plot or yield pass/fail versus voltage. | Yeap 2024 |
| Variability sigma | Robustness under variation. | Monte Carlo distributions; `sigma = mean / std`. 6-sigma is a common robustness target. | Abdi 2025, Shahin 2025 |
| RC parasitics | WL/BL/VDD/VSS resistance and capacitance per cell. | Field solver or extraction, then circuit simulation. | Abdi 2025, Lu 2025, Peng 2025 |

## 2. Cross-paper reference values

| Paper | Technology / object | Reported SRAM metrics and reference values | Notes |
|---|---|---|---|
| Abdi et al., 2025, `SRAM Scaling Opportunities Below 0.01 um^2...` | Double-row CFET SRAM, WL-folded bitcell, A7 exploration | Bitcell area: `0.011 um^2` for 69 nm height and `4*CPP` width; scaled A7 design reaches `0.009 um^2`; area reduction reported as `53%`; height reduction `21.7%`; mean HSNM about `310 mV`; mean RSNM about `145 mV`; WL folding improves read delay by `2x`; write margin improves by `162 mV`. | Strongly relevant for CFET SRAM DTCO. The paper also discusses 3-sigma HSNM/RSNM under nanosheet width variation; exact bar values are plotted, but the caption explicitly gives mean HSNM/RSNM. |
| Angelin Delighta et al., 2025, `Nanosheet transistors...` | Nanosheet transistor review | No concrete SRAM cell or SRAM macro benchmark value was found in the reviewed pages. | Useful as background for nanosheet/GAA devices, not as a direct SRAM metric reference. |
| Ha et al., 2025, `3D Stacked FET (3DSFET) Logic and SRAM...` | Experimental 3DSFET SRAM at 48 nm CPP, SDB, BSI | SRAM bitcell area reduction `>55%` versus their 3 nm node reference; at `VDD=0.7 V`, SNMR = `180 mV`; cell current = `17.2 uA/cell`; WRM = `250 mV`; SNMR drops to about `50 mV` at `VDD=0.3 V`; SRAM hold current decreases by `15.4%` at `125 degC` compared with GAA MBCFET. | Very relevant as an experimental SRAM reference. SNMR/WRM are measured from butterfly/write-margin plots. |
| Huang et al., 2025, `First Demonstration of Monolithic 3-Tier...` | Monolithic 3-tier transistor stacking, half-SRAM `(1PD/1PU/1PG)` | Measured half-SRAM HSNM/RSNM: at `VDD=2.0 V`, `300/170 mV`; at `VDD=1.75 V`, `280/140 mV`; at `VDD=1.5 V`, `240/90 mV`. | This is half-SRAM, not a complete 6T SRAM cell. Useful for experimental stacked-transistor stability reference, but not directly comparable to standard 6T SRAM at 0.7 V. |
| Lu et al., 2025, `Design Technology Co-Optimization for CFET SRAM...` | CFET 6T/8T SRAM, single-sided routing with BS-PDN versus double-sided signal/power routing | See detailed Table 1 below. Key values: 6T area `0.0109 um^2`; 8T area `0.0186 um^2`; 6T RSNM `128 -> 126 mV`; 6T write margin `281 -> 282 mV`; 6T read delay `321 -> 284 ps`; 6T write delay `75 -> 71 ps`; 6T read power `102 -> 66 uW`; 6T write power `98 -> 81 uW`. | Most directly useful for your current RC-aware SRAM analysis because it links parasitic R/C to delay, power, RSNM and write margin. |
| Peng et al., 2025, `PPA Scaling of Flip FET Technology Down to A2...` | FFET/CFFET SRAM roadmap down to A2, 256x256 array worst-case cell | SRAM device `Ioff = 2 pA`; Fig. 11 reports HD 6T SRAM area scaling down to A2, with CFFET area near the low `10^-3 um^2` range, and notes area halving due to array folding; Fig. 12 compares worst-case read delay, write delay, RSNM and write margin across A14-A2. | The PDF text does not expose exact Fig. 12 bar values. Treat this paper mainly as a roadmap/trend reference unless values are digitized from the figure. |
| Shahin et al., 2025, `CFET Beyond 3 nm SRAM Reliability...` | CFET 6T SRAM reliability under process and temperature variability | At `VDD=0.75 V`, `T=300 K`: read delay `37.59 ps`, write delay `34.47 ps`, HSNM `0.306 V`, RSNM `0.146 V`, WSNM `0.164 V`. At `398 K`: read delay `39.11 ps`, write delay `34.94 ps`, HSNM `0.280 V`, RSNM `0.121 V`, WSNM `0.205 V`. Monte Carlo std: RSNM `8.3 mV`, WSNM `15 mV`, HSNM `4.2 mV`; delay std: read `1.46 ps`, write `1.23 ps`; cell sigma: RSNM `17.4`, WSNM `11.2`, exceeding 6-sigma target. | Strong reference for reliability, variability and temperature sensitivity. |
| Xiong and Wu, 2024, `Building inverters with stacked complementary nanosheet transistors` | Commentary on stacked complementary nanosheet inverters | No SRAM metric is reported. Non-SRAM device/circuit values include top nFET threshold reduction `160 mV`, subthreshold swing about `74 mV/dec`, DIBL `47 mV/V`. | Relevant to CFET inverter/device background, not SRAM benchmarking. |
| Yeap et al., 2024, `2nm Platform Technology...` | TSMC N2 platform SRAM macro and qualification | HD SRAM macro density: 7 nm `25.0 Mb/mm^2`, 5 nm `32.2 Mb/mm^2`, 3 nm `34.1 Mb/mm^2`, 2 nm `37.9 Mb/mm^2` or about `38 Mb/mm^2`; HC SRAM Vmin improves by about `20 mV`; HD SRAM Vmin improves by `30-35 mV`; 256 Mb HD SRAM shmoo works down to about `0.4 V`; latch-up trigger `Vtrig > 1.7 V` versus FinFET about `1.45 V`; 1000 h HTOL passes with about `110 mV` margin. | Platform/macro-level reference, useful for density, Vmin and reliability targets rather than cell-level SNM. |

## 3. Detailed table from Lu et al. 2025

Lu et al. give the cleanest table-style SRAM benchmark among the local papers. The comparison is at `CPP=48 nm`.

| SRAM | Routing | Cell area (um^2) | RSNM (mV) | Write margin (mV) | Parasitic capacitance change | Read delay (ps) | Write delay (ps) | Read power (uW) | Write power (uW) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| CFET 6T | Single-sided signal routing with BS-PDN | 0.0109 | 128 | 281 | 1x | 321 | 75 | 102 | 98 |
| CFET 6T | Double-sided signal/power routing | 0.0109 | 126 | 282 | -24% to -31% | 284 | 71 | 66 | 81 |
| CFET 8T | Single-sided signal routing with BS-PDN | 0.0186 | 283 | 281 | 1x | 329 | 110 | 60 | 130 |
| CFET 8T | Double-sided signal/power routing | 0.0186 | 283 | 282 | -7% to -36% | 307 | 80 | 45 | 122 |

Interpretation:

- Double-sided routing mainly improves delay and power through lower WL/BL and storage-node capacitance.
- 6T RSNM slightly decreases from `128 mV` to `126 mV`, because the routing change affects read disturb.
- Write margin is nearly unchanged but slightly improved by about `0.4%`.
- 8T has about `70%` larger area than 6T, but RSNM is much larger (`283 mV`) because the read path is decoupled from the storage node.

## 4. Detailed table from Shahin et al. 2025

The paper uses a CFET 6T SRAM framework with 32 SRAM cells and peripheral circuits. Monte Carlo SPICE simulations use 1000 samples and TCAD-derived threshold-voltage variations.

| Temperature | Read delay (ps) | Write delay (ps) | HSNM (V) | RSNM (V) | WSNM (V) |
|---:|---:|---:|---:|---:|---:|
| 300 K | 37.59 | 34.47 | 0.306 | 0.146 | 0.164 |
| 348 K | 37.88 | 34.44 | 0.293 | 0.134 | 0.183 |
| 398 K | 39.11 | 34.94 | 0.280 | 0.121 | 0.205 |

Additional variability values:

| Quantity | Reported value |
|---|---:|
| nFET VTH sigma | 16 mV |
| pFET VTH sigma | 15 mV |
| RSNM sigma | 8.3 mV |
| WSNM sigma | 15 mV |
| HSNM sigma | 4.2 mV |
| Read delay sigma | 1.46 ps |
| Write delay sigma | 1.23 ps |
| RSNM cell sigma, mean/std | 17.4 |
| WSNM cell sigma, mean/std | 11.2 |
| Robustness target mentioned | 6 sigma |

Interpretation:

- Higher temperature weakens read and hold stability: RSNM decreases from `146 mV` to `121 mV`, HSNM from `306 mV` to `280 mV`.
- WSNM increases from `164 mV` to `205 mV`, because pFET degradation helps overpower the previous stored state during write.
- Read delay increases with temperature, from `37.59 ps` to `39.11 ps`.

## 5. Detailed table from Huang et al. 2025

Huang et al. report a measured half-SRAM based on monolithic three-tier transistor stacking. This is not a full 6T SRAM, so values should be used as a stacked-device experimental reference only.

| VDD | HSNM (mV) | RSNM (mV) |
|---:|---:|---:|
| 2.0 V | 300 | 170 |
| 1.75 V | 280 | 140 |
| 1.5 V | 240 | 90 |

Interpretation:

- Both HSNM and RSNM decrease as VDD decreases.
- RSNM is consistently smaller than HSNM, matching the usual SRAM rule that read access weakens stability.

## 6. How these values should guide your HSPICE SRAM work

For your own Fusion-IC SRAM simulations, the most useful reference ranges from these papers are:

| Metric | Literature reference range from this folder | Practical meaning for your HSPICE results |
|---|---:|---|
| 6T cell area, advanced CFET | about `0.009-0.011 um^2` | Layout target for aggressively scaled CFET SRAM. Not directly comparable if your geometry is not a complete layout. |
| RSNM/SNMR | about `121-180 mV` for several 6T/3DSFET examples; 8T can reach about `283 mV` | Your RSNM should be extracted by butterfly, not inferred from transient read disturb. |
| HSNM | about `280-310 mV` in CFET examples at nominal/high VDD | Hold butterfly should normally be larger than read butterfly. |
| WSNM/WRM | about `164-282 mV` depending on method and VDD | Write metric depends strongly on definition; always state whether it is write margin, WSNM, or bit-line trip. |
| Read delay | about `37-39 ps` in Shahin CFET 6T; `284-321 ps` in Lu array/interconnect benchmark | Delay depends heavily on load, bit-line length, sensing threshold and array size. You must report threshold and capacitance. |
| Write delay | about `34-35 ps` in Shahin; `71-110 ps` in Lu | Same caution as read delay; node-crossing definition matters. |
| Read power | `45-102 uW` in Lu table | Must be tied to operation window and array/cell setup. |
| Write power | `81-130 uW` in Lu table | Strongly affected by BL/WL capacitance. |
| Macro density | up to about `37.9-38 Mb/mm^2` for 2 nm N2 HD SRAM | Macro-level target; includes peripheral/layout efficiency, not just bitcell area. |
| Vmin | 256 Mb HD SRAM shmoo down to about `0.4 V`; N2 improves HC/HD Vmin by about `20/30-35 mV` | Vmin requires statistical macro/yield or shmoo, not a single-cell transient pass. |
| Robustness sigma | RSNM cell sigma `17.4`, WSNM cell sigma `11.2`; target `>6 sigma` | Useful target for Monte Carlo. A single nominal SRAM result is not a reliability result. |

## 7. Recommended metric set for your future SRAM reports

For a clean DTCO-style SRAM report, use the following hierarchy:

1. Basic functionality: Hold-Q1, Hold-Q0, Read-Q1, Read-Q0, Write-0, Write-1.
2. Stability: HSNM, RSNM, WSNM from DC butterfly/write-margin sweeps.
3. Dynamic behavior: read disturb, read delay, write delay.
4. Power/energy: read power/energy, write power/energy, hold leakage.
5. Reliability: Monte Carlo sigma of HSNM/RSNM/WSNM and delays.
6. Layout/PPA: cell area, macro density, extracted WL/BL/VDD/VSS R/C.

For your current HSPICE data, the transient read-disturb value is only a functionality/stability warning indicator. It is not a substitute for RSNM. The literature values above should be used as reference context after the RC topology is valid and the formal DC SNM decks are implemented.
