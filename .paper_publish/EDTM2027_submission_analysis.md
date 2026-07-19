# EDTM 2027 投稿可行性分析与投稿方案

分析日期：2026-07-15  
目标会议：11th IEEE Electron Devices Technology and Manufacturing (EDTM) Conference, Fukuoka, Japan, March 8-11, 2027  
本地 CFP：`C:\Users\Tengfei\Desktop\Project_DTCO\AutoLDM\.paper_publish\EDTM2027-CallForPapers_FINAL.pdf`

## 1. 总体判断

当前仓库内容具备投递 EDTM 2027 的基础，但不建议以“全部内容”原样投递。更合理的做法是从仓库中抽取一条清晰主线，整理成 3-page camera-ready conference paper。

推荐投稿定位：

> A layout-to-circuit DTCO automation flow for GAA/nanosheet SRAM using Verilog-A compact models and parasitic-aware HSPICE metric extraction

中文表达：

> 面向 GAA/nanosheet SRAM 的 layout-to-circuit DTCO 自动化流程：从版图/规则生成 SDE 结构与 RC-aware HSPICE deck，并提取 SRAM cell-level 稳定性、读写速度和寄生影响指标。

适配度评估：

| 维度 | 评价 |
|---|---|
| 与 EDTM CFP 匹配度 | 较高。CFP 的 Modeling and Simulation 明确包含 DTCO/STCO、parasitic elements、benchmarking、methodologies；Memory Technologies 也覆盖 memory modeling、read/write、scaling。 |
| 当前完成度 | 中等偏上。已有自动化脚本、Verilog-A 模型、HSPICE deck、SRAM 指标表、科研图、RC candidate 分析。 |
| 当前最大风险 | 正式 extracted-RC 尚未完全闭环；当前 RC 结果是 diagnostic candidate，不应包装成最终 post-layout RC 结论。 |
| 可投稿策略 | 可以投 methodology / workflow paper；不宜投“器件性能突破”或“最终 SRAM PPA benchmark”论文。 |
| 是否建议投 | 建议投，但需要在 2026-10 中旬投稿截止前补强 RC 合法性、指标定义和对比基线。 |

结论：可以投 EDTM 2027，但应投“建模与仿真方法”方向，而不是把当前数值当作最终先进节点 SRAM benchmark。

## 2. CFP 对应关系

从 CFP 文本看，最匹配的 technical area 是：

1. Modeling and Simulation
   - electron devices, interconnects, TCAD, benchmarking
   - DTCO/STCO
   - parasitic elements
   - methodologies

2. Memory Technologies
   - volatile memories
   - SRAM scaling
   - modeling
   - read/write behavior
   - memory-centric computing/AI

3. Advanced Logic Devices
   - GAA
   - nanosheets
   - interconnects

优先选择：

> Modeling and Simulation

备选关键词里再体现 SRAM/GAA/nanosheet。

原因：当前仓库最强的是流程、模型连接、deck 生成、指标提取和 RC 诊断，而不是某个器件结构的最终实验或 TCAD benchmark。

## 3. 仓库中可支撑论文的材料

### 3.1 自动化流程

可用材料：

- `gen_sde.py`
- `rules/`
- `gds/`
- `output_SDE/sde_cmd/`
- `output_SDE/rc_raphreal/`
- `output_SDE/rc_sp/standard_sram.sp`
- `readme.md`
- `guides/`

可写成论文中的 flow：

```text
layout text + architecture rules + layer rules
        -> SDE command generation
        -> schematic/RC mapping
        -> HSPICE SRAM deck generation
        -> Verilog-A compact-model simulation
        -> automated SRAM metric extraction and visualization
```

建议图：

- 一张 overall flow chart
- 输入/输出文件关系图
- 6T SRAM topology/RC mapping schematic

### 3.2 Verilog-A / compact model 校准

可用材料：

- `Hspice/va/fusion_ic_nmos_lvt.va`
- `Hspice/va/fusion_ic_pmos_lvt.va`
- `Hspice/iv_calibration_summary.md`
- `Hspice/iv/fit_nmos_idvg_vmax1/fit_summary.csv`
- `Hspice/iv/fit_nmos_idvg_vmax1/fit_best_vmax1_params.json`
- `Hspice/iv/png/compare_wt_cfet_vs_va_nmos_idvg_fit_best_vmax1.png`
- `Hspice/nfet_48nm_dualvd_fit/`
- `Hspice/pfet_48nm_dualvd_fit/`

当前可报告结果：

- NMOS best fit:
  - `log_rmse_all = 0.0789 decade`
  - `rel_rmse_high = 18.5%`
  - `max_rel_err_high = 26.6%`
  - fitted parameters: `U0=0.016`, `XL=12 nm`, `DeltaTGAA=-1 nm`, `EOT_0=0.95 nm`

- 48 nm calibration summary:
  - NMOS log RMSE all about `0.1215 decade`
  - PFET log RMSE all about `0.1983 decade`
  - PFET high-current error worse than NMOS, should be stated as limitation

论文中应谨慎表述为：

> The compact model interface and calibration loop were established and verified against reference IV curves.

不要表述为：

> The model achieves universal predictive accuracy.

### 3.3 SRAM 指标提取

可用材料：

- `Hspice/sram_full_metrics/run_full_metrics.py`
- `Hspice/sram_full_metrics/data/summary_metrics.csv`
- `Hspice/sram_full_metrics/figures/`
- `Hspice/sram_comparison.md`
- `Hspice/sram_workflow.md`

当前数值：

| Metric | No-RC | RC candidate |
|---|---:|---:|
| HSNM | 268.0 mV | 267.5 mV |
| RSNM | 108.0 mV | 106.0 mV |
| Read disturb | 143.7 mV | 145.2 mV |
| Read stability margin | 206.3 mV | 204.8 mV |
| Read delay | 15.20 ps | 15.429 ps |
| Write delay | 37.263 ps | 38.524 ps |
| Write-trip BL drop | 453.36 mV | 449.36 mV |
| Read energy | 0.0295 fJ | 0.0425 fJ |
| Write energy | 0.0390 fJ | 0.1136 fJ |
| Hold leakage | 1383.9 pW | 1386.8 pW |

注意：由于之前已经发现 energy window 的定义存在口径问题，如果论文空间有限，建议弱化或删除 read/write energy，除非先完成以下修正：

- 明确积分窗口对应操作完成点；
- 或扣除 baseline leakage；
- 或只报告 fixed-window cell supply energy，并明确不是 macro energy。

### 3.4 RC 诊断与局限

可用材料：

- `Hspice/sram_rc_array_analysis.md`
- `Hspice/sram_clean/`
- `output_SDE/rc_raphreal/n18_cMatrix.spi`
- `output_SDE/rc_raphreal/n19_cMatrix.spi`
- `output_SDE/rc_sp/standard_sram.sp`

当前客观状态：

- 现有 RC candidate 可以跑通 Hold/Read/Write。
- 但原始 extracted-RC 映射存在 floating node / empty row-column / pairwise shortest-path compression 等问题。
- `sram_rc_array_analysis.md` 明确指出当前 RC 不能作为最终 SRAM performance conclusion。

投稿时应这样写：

> A diagnostic RC candidate is used to validate the metric-extraction path and expose parasitic-network sensitivities. The extracted-RC reconstruction problem is analyzed as part of the methodology.

不应这样写：

> We have completed a fully accurate post-layout RC SRAM benchmark.

这是审稿风险最高的一点。

## 4. 外部文献与定位

相关外部背景：

1. Zhang et al., "New-Generation Design-Technology Co-Optimization (DTCO): Machine-Learning Assisted Modeling Framework", arXiv:1904.10269.  
   该文强调 ML/NN surrogate model 可用于 DTCO 中预测 device and circuit electrical characteristics。你的工作可以定位为：不是单纯 surrogate model，而是把 Verilog-A compact model、layout/RC、HSPICE SRAM metric extraction 连接成自动化 flow。

2. Kam, "Deep Learning Assisted Compact Modeling of Nanoscale Transistor", arXiv:2107.06167.  
   该文强调 physics-based compact model 可通过 neural network 改善，且模型可实现为 Verilog-A 进入 circuit simulation。你的仓库中的 Fusion/PHIMO-style Verilog-A 模型与这一方向一致。

3. Patil et al., "An Accurate Process Induced Variability Aware Compact Model-based Circuit Performance Estimation for Design-Technology Co-optimization", arXiv:2109.00849.  
   该文把 compact model accuracy 与 SRAM/RO circuit FoM 连接起来，说明器件模型误差会传递到 SRAM 指标。你的论文可以强调 device-to-SRAM metric closure。

4. Shen et al., "Deep-Learning-Based Pre-Layout Parasitic Capacitance Prediction on SRAM Designs", arXiv:2507.06549.  
   该文指出 SRAM parasitics 会导致 pre-layout 与 post-layout simulation discrepancy，并关注 parasitic-aware simulation。你的工作不是预测寄生，而是从已有 layout/RC 映射到 SPICE 并做指标提取，属于互补方向。

这些文献说明当前主题是合理的，但也提示审稿人会关注：

- 是否有可信 RC；
- 是否有与 reference/TCAD/测量数据的 calibration；
- 是否有比手工流程更清楚的自动化收益；
- SRAM metrics 是否定义严谨。

## 5. 建议论文题目

推荐题目：

> An Automated Layout-to-HSPICE DTCO Flow for Parasitic-Aware GAA SRAM Metric Extraction

更强调 Verilog-A compact model：

> Compact-Model-Based DTCO Flow for Parasitic-Aware GAA/Nanosheet SRAM Evaluation

更保守、更适合当前完成度：

> A Reproducible HSPICE Metric-Extraction Flow for Compact-Model-Based GAA SRAM DTCO

不建议题目：

> High-Performance GAA SRAM with Optimized RC Parasitics

原因：当前还没有足够证据支持“高性能优化结果”。

## 6. 摘要可写内容

建议摘要结构，约 150-200 words：

1. 背景：
   - advanced GAA/nanosheet nodes require rapid device-to-circuit feedback for SRAM DTCO;
   - compact models and parasitic-aware circuit simulation are both needed.

2. 问题：
   - manual transfer from layout/rules/RC to HSPICE SRAM metrics is error-prone;
   - SRAM stability and read/write metrics require consistent testbenches.

3. 方法：
   - propose an automated flow from layout/rule files to SDE command generation, RC-aware HSPICE deck construction, Verilog-A compact-model simulation, and SRAM metric extraction.

4. 结果：
   - demonstrate on a 6T SRAM cell using GAA/nanosheet Verilog-A models at `VDD=0.7 V`;
   - extract HSNM, RSNM, read disturb, read/write delays, and write-trip BL drop;
   - show No-RC vs diagnostic RC candidate differences, e.g. RSNM `108 -> 106 mV`, read delay `15.20 -> 15.43 ps`, write delay `37.26 -> 38.52 ps`.

5. 贡献：
   - reproducible metric extraction;
   - RC mapping diagnostics;
   - foundation for compact-model-based SRAM DTCO.

摘要中不建议强调 energy，除非先修正积分口径。

## 7. 关键词建议

建议关键词：

- Design-technology co-optimization
- SRAM
- Gate-all-around
- Nanosheet FET
- Verilog-A compact model
- HSPICE
- Parasitic-aware simulation
- Static noise margin
- Layout-to-circuit automation

## 8. 引言可写内容

引言建议三段：

第一段：技术背景

- GAA/nanosheet device scaling increases the need for DTCO.
- SRAM is sensitive to device strength, parasitic RC, and compact-model accuracy.
- AI-era chips make SRAM density/latency/stability increasingly important.

第二段：现有 gap

- Device model calibration, layout/RC extraction, and SRAM circuit metrics are often handled as disconnected steps.
- Manual deck construction can introduce node-mapping and parasitic-network errors.
- A reproducible flow is needed to connect compact models to SRAM-level metrics.

第三段：本文贡献

可以列 3 点：

1. A layout/rule-to-SDE and HSPICE deck generation flow.
2. A Verilog-A compact-model-based SRAM testbench suite with HSNM/RSNM/read/write metrics.
3. A parasitic mapping diagnostic methodology that reveals RC reconstruction errors and quantifies a diagnostic RC candidate.

## 9. 方法部分可写内容

建议分成 4 小节。

### 9.1 Flow Overview

放一张流程图：

```text
Layout TXT / Rules
   -> SDE .cmd
   -> Schematic labels + RC matrix
   -> SRAM HSPICE deck
   -> Verilog-A compact models
   -> HSPICE simulation
   -> Python metric extraction + figures
```

对应仓库材料：

- `gen_sde.py`
- `rules/`
- `output_SDE/`
- `Hspice/iv_flow/run_hspice.py`
- `Hspice/sram_full_metrics/run_full_metrics.py`

### 9.2 Compact Model and Calibration

可以写：

- NMOS/PMOS use Fusion/PHIMO-style Verilog-A compact models.
- Instance parameters include `L`, `W`, `NF`, `U0`, `XL`, `DVTSHIFT`, `DeltaWGAA`, `DeltaTGAA`, `EOT_0`.
- Calibration is performed against reference `Id-Vg` curves.

可放一张图：

- `compare_wt_cfet_vs_va_nmos_idvg_fit_best_vmax1.png`

可放一个小表：

| Parameter | Best value |
|---|---:|
| `U0` | 0.016 |
| `XL` | 12 nm |
| `DeltaTGAA` | -1 nm |
| `EOT_0` | 0.95 nm |

以及拟合质量：

| Metric | Value |
|---|---:|
| log RMSE all | 0.0789 decade |
| high-current relative RMSE | 18.5% |

### 9.3 SRAM Testbenches and Metrics

写清楚每个指标定义：

- HSNM: hold butterfly maximum square.
- RSNM: read-mode noise-source injection.
- Read disturb: max disturbed storage-node voltage during read transient.
- Read delay: `WL=0.5VDD` to `BL-BLB=50mV`.
- Write delay: `WL=0.5VDD` to `Q=0.5VDD`.
- Write-trip BL drop: DC BL sweep crossing.

建议暂时不把 energy/leakage 放主表；如果要放，必须写清口径限制。

### 9.4 Parasitic Network Construction and Diagnostics

这是当前论文最有价值也最危险的部分。

可以写：

- RC matrices are mapped from schematic labels to HSPICE internal nodes.
- All-pair shortest-path compression can create nonphysical parallel shortcuts.
- Floating/empty rows reveal invalid terminal mapping.
- A diagnostic RC candidate is used to validate the end-to-end metric extraction.

必须如实写：

> The diagnostic RC candidate is not claimed as a sign-off extracted RC network.

这样反而显得专业，不容易被审稿人抓住。

## 10. 结果部分可写内容

建议只放 2-3 张图 + 1 张表，因为 EDTM 是 3-page camera-ready。

### Figure 1: End-to-end flow

自制流程图，覆盖 layout/rules -> SDE -> RC/HSPICE -> metrics。

### Figure 2: Compact model calibration

使用：

- `Hspice/iv/png/compare_wt_cfet_vs_va_nmos_idvg_fit_best_vmax1.png`

说明：

- reference and Verilog-A compact-model simulation agree within `0.0789 decade` log RMSE for the selected NMOS calibration.

### Figure 3: SRAM metric extraction

使用或重绘：

- `Hspice/sram_full_metrics/figures/metric_extraction_annotation.png`

或者拆成：

- HSNM/RSNM 图；
- read/write waveform 图。

### Table 1: No-RC vs Diagnostic RC Candidate

建议表格：

| Metric | No-RC | Diagnostic RC | Delta |
|---|---:|---:|---:|
| HSNM | 268.0 mV | 267.5 mV | -0.5 mV |
| RSNM | 108.0 mV | 106.0 mV | -2.0 mV |
| Read disturb | 143.7 mV | 145.2 mV | +1.5 mV |
| Read delay | 15.20 ps | 15.43 ps | +1.5% |
| Write delay | 37.26 ps | 38.52 ps | +3.4% |
| Write-trip BL drop | 453.36 mV | 449.36 mV | -4.0 mV |

建议不要把 `read_energy` 和 `write_energy` 放入主表，除非先改口径。原因是当前 `0.2-1.2 ns` fixed-window integration 会包含静态电流积分，审稿人可能质疑。

## 11. 结论部分可写内容

结论应保守而明确：

1. A reproducible compact-model-based SRAM DTCO flow was established.
2. The flow connects layout/rule inputs, RC mapping, Verilog-A compact models, HSPICE simulation, and automatic metric extraction.
3. On a 6T GAA/nanosheet SRAM cell, the flow extracts HSNM/RSNM/read-write timing and write-trip metrics.
4. Diagnostic RC results show small but measurable degradation in RSNM and timing.
5. The RC reconstruction audit shows that parasitic topology validity is as important as RC values, motivating future work on sign-off-grade RC preservation and array-level validation.

## 12. 当前不足与投稿前必须补强项

### 必须补强

1. 修复或明确限定 RC 网络
   - 当前 RC candidate 不能被写成 final extracted RC。
   - 最好在投稿前得到一个无 floating node、无 artificial shortcut、来源可追踪的 clean RC netlist。

2. 统一 RSNM 定义
   - 如果叫 RSNM，最好用 read butterfly max-square 或清楚说明使用 read-mode noise-source SNM。
   - 当前文档中已经从 transient proxy 区分出来，这是正确方向。

3. 删除或弱化 energy
   - 当前 energy fixed window 有口径争议。
   - 若保留，需改成 event-based energy 或 subtract leakage baseline。

4. 给出自动化收益
   - 例如 deck 生成时间、手工步骤减少、指标数量、可复现实验目录。
   - EDTM 审稿人需要看到 methodology 的实际价值。

5. 把图改成论文风格
   - 统一英文标注；
   - 字体和线宽满足 IEEE 双栏；
   - 不使用 Obsidian `![[...]]` 语法；
   - 图注必须说明 testbench 条件。

### 建议补强

1. 增加 2-3 个参数 sweep
   - `DeltaTGAA`
   - `EOT_0`
   - `VDD`
   - `BL capacitance`

2. 增加一个 ablation
   - No-RC
   - C-only
   - R-only
   - RC candidate

3. 增加 Monte Carlo 或 PVT
   - 若时间不够，至少做 VDD sweep。

4. 对比手工 deck 或传统流程
   - 强调自动化减少 node mapping error。

## 13. 三页论文建议版面

### Page 1

- Title
- Abstract
- Keywords
- Introduction
- Contribution list
- Figure 1: overall flow

### Page 2

- Method
  - Verilog-A compact model interface
  - IV calibration
  - SRAM testbench definitions
  - RC mapping diagnostics
- Figure 2: calibration curve or SRAM testbench schematic

### Page 3

- Results
  - main SRAM metric table
  - one waveform/metric extraction figure
- Limitations / discussion
- Conclusion
- References

3-page paper 不要试图塞进全部内容。主线必须清楚。

## 14. 投稿前时间计划

当前日期：2026-07-15  
CFP 标注投稿截止：Mid-October 2026

建议计划：

| 时间 | 任务 |
|---|---|
| 2026-07-15 至 2026-07-31 | 修复 RC flow 或明确 diagnostic RC 边界；确定最终题目和 technical area。 |
| 2026-08-01 至 2026-08-20 | 补充 VDD/EOT/DeltaTGAA 或 RC ablation sweep。 |
| 2026-08-21 至 2026-09-05 | 重画英文论文图，整理主表。 |
| 2026-09-06 至 2026-09-20 | 写 3-page 初稿。 |
| 2026-09-21 至 2026-10-05 | 内部审稿，压缩文字，修正 claim。 |
| 2026-10-06 至 2026-10 中旬 | 最终 IEEE 模板排版和提交。 |

## 15. 建议最终 claim 强度

可以安全 claim：

- We developed a reproducible layout-to-HSPICE DTCO flow.
- The flow integrates Verilog-A compact models with SRAM-level metric extraction.
- The flow identifies parasitic-network construction issues that can invalidate SRAM RC simulations.
- A diagnostic RC candidate demonstrates measurable impact on SRAM stability and timing.

不要 claim：

- Sign-off-accurate post-layout SRAM performance.
- State-of-the-art SRAM PPA.
- Fully validated GAA SRAM macro.
- Accurate array-level energy.

## 16. 推荐投稿方案

最终推荐：

1. Technical Area:
   - Primary: Modeling and Simulation
   - Secondary: Memory Technologies

2. Paper type:
   - 3-page conference paper
   - Methodology + compact-model + SRAM case study

3. Core contribution:
   - end-to-end reproducible DTCO automation flow
   - SRAM metric extraction suite
   - RC topology diagnostics

4. Case study:
   - 6T GAA/nanosheet SRAM bitcell at `VDD=0.7 V`
   - No-RC vs diagnostic RC candidate

5. 最终题目建议：
   - `A Reproducible HSPICE Metric-Extraction Flow for Compact-Model-Based GAA SRAM DTCO`

这是当前仓库最稳、最不容易被审稿人反驳的投稿路线。

## 17. 参考资料

- EDTM 2027 CFP, local file: `.paper_publish/EDTM2027-CallForPapers_FINAL.pdf`
- Zhang et al., "New-Generation Design-Technology Co-Optimization (DTCO): Machine-Learning Assisted Modeling Framework", arXiv:1904.10269, https://arxiv.org/abs/1904.10269
- Kam, "Deep Learning Assisted Compact Modeling of Nanoscale Transistor", arXiv:2107.06167, https://arxiv.org/abs/2107.06167
- Patil et al., "An Accurate Process Induced Variability Aware Compact Model-based Circuit Performance Estimation for Design-Technology Co-optimization", arXiv:2109.00849, https://arxiv.org/abs/2109.00849
- Shen et al., "Deep-Learning-Based Pre-Layout Parasitic Capacitance Prediction on SRAM Designs", arXiv:2507.06549, https://arxiv.org/abs/2507.06549

