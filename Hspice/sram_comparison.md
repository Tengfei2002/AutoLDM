# Fusion-IC 6T SRAM HSPICE 指标仿真与 RC 对比报告

## 摘要

本文基于 `fusion_ic_nmos_lvt.va` 与 `fusion_ic_pmos_lvt.va` 构建 6T SRAM 单元，对 No-RC 与 RC candidate 两种配置进行 HSPICE 指标仿真。静态保持稳定性采用 hold butterfly 几何最大内嵌正方形法提取，读静态噪声容限采用 read-mode noise-source 注入法提取。报告同时给出读写延迟、读扰动、写入门槛、能量与泄漏功耗，并通过曲线图展示各指标的数据来源。

## 1. 仿真对象与固定条件

| 项目 | 设置 |
|---|---|
| NMOS | `Hspice/va/fusion_ic_nmos_lvt.va` |
| PMOS | `Hspice/va/fusion_ic_pmos_lvt.va` |
| SRAM | 6T bit-cell |
| VDD | `0.7 V` |
| 温度 | `25 degC` |
| 尺寸 | `L=16 nm`, `WPG=WPD=WPU=25 nm`, `NF=1` |
| 存储节点电容 | `CQ=CQB=1 fF` |
| bit-line 电容 | `CBL=CBLB=10 fF` |
| transient step | `0.2 ps` |
| RSNM noise step | `1 mV` |
| read delay 判据 | `WL=0.5VDD` 到 `BL-BLB=50 mV` |
| write delay 判据 | `WL=0.5VDD` 到 `Q=0.5VDD` |
| energy | `E = integral(VDD * abs(I(VDD_SRC)))` |

## 2. 电路网表结构与通俗电位名称

| 网表节点 | 通俗名称 | 作用 |
|---|---|---|
| `VDD` | 电源高电位 | PMOS pull-up 管源端供电 |
| `VSS` | 地电位 | NMOS pull-down 管源端参考地 |
| `WL` | 字线 | 控制 access NMOS |
| `BL` | 位线 | 读写 Q 侧节点 |
| `BLB` | 反位线 | 读写 QB 侧节点 |
| `Q` | 存储节点 | SRAM 内部真实存储节点 |
| `QB` | 互补存储节点 | 与 Q 互补的内部节点 |

No-RC 6T SRAM 电路：

![[sram_full_metrics/figures/sram6t_norc_schematic.png]]

RC candidate 网表图：

![[sram_full_metrics/figures/sram6t_rc_candidate_network.png]]

需要注意：当前 RC candidate 中 `R_QB_PU` 连接到 `PU2_QB_SD`，但 `XPU2` 的漏端在现有网表中直接连接到 `QB`，不是 `PU2_QB_SD`。因此 `R_QB_PU` 未串入 PU2 漏端路径。本文将该 RC 配置作为候选寄生网络进行对比，其结论对应当前网表连接关系。

## 3. 指标汇总

| 配置 | HSNM (mV) | RSNM (mV) | Read disturb (mV) | Read stability margin (mV) | Read delay (ps) | Write delay (ps) | Write-trip BL drop (mV) | Read energy (fJ) | Write energy (fJ) | Hold leakage (pW) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| No-RC | 268.00 | 108.00 | 143.70 | 206.30 | 15.20 | 37.40 | 454.00 | 0.029 | 0.039 | 1383.889 |
| RC candidate | 267.50 | 106.00 | 145.20 | 204.80 | 15.60 | 38.60 | 450.00 | 0.043 | 0.114 | 1386.834 |

## 4. 指标提取总览图

下图展示 read disturb、read stability margin、read delay、write delay 与 write-trip BL drop 在曲线中的提取位置。图中数值与 `summary_metrics.csv` 使用同一离散采样口径。

![[sram_full_metrics/figures/metric_extraction_annotation.png]]

## 5. 逐项指标定义、仿真方法与结果解释

### 5.1 HSNM: Hold Static Noise Margin

HSNM 表示 SRAM 在保持态抵抗静态噪声的能力。本流程用几何最大内嵌正方形法提取：

```text
HSNM = min(max_square_left_lobe, max_square_right_lobe)
```

其中 `max_square` 是完全位于 butterfly lobe 内部的最大轴对齐正方形边长。

结果：

- No-RC: `268.00 mV`
- RC candidate: `267.50 mV`

![[sram_full_metrics/figures/hold_snm_max_square_comparison.png]]

No-RC hold butterfly:

![[sram_full_metrics/figures/ideal_hold_butterfly.png]]

RC candidate hold butterfly:

![[sram_full_metrics/figures/rc_candidate_hold_butterfly.png]]

### 5.2 RSNM: Read Static Noise Margin

RSNM 表示读操作下 SRAM 抵抗读破坏的静态噪声容限。读态中：

```text
WL = VDD
BL = BLB = VDD
```

本文采用 read-mode noise-source 注入法提取 RSNM。read-mode butterfly 曲线作为读态 DC 响应的辅助观察，不作为 RSNM 的主提取方法。

对于初态 `Q=1, QB=0`：

```text
GQB = QB + VN
GQ  = Q  - VN
```

对于初态 `Q=0, QB=1`：

```text
GQB = QB - VN
GQ  = Q  + VN
```

其中 `GQB` 是控制 `PU1/PD1` 的反馈 gate，`GQ` 是控制 `PU2/PD2` 的反馈 gate。扫描 `VN`：

```text
VN: 0 -> 0.5 V, step = 1 mV
```

翻转判据：

```text
Q=1 初态: 第一次出现 V(Q) <= V(QB)
Q=0 初态: 第一次出现 V(QB) <= V(Q)
RSNM = min(VN_critical_Q1, VN_critical_Q0)
```

结果：

| 配置 | Q=1 初态临界噪声 | Q=0 初态临界噪声 | RSNM |
|---|---:|---:|---:|
| No-RC | 108.00 mV | 108.00 mV | 108.00 mV |
| RC candidate | 106.00 mV | 107.00 mV | 106.00 mV |

科研绘图说明：RSNM 图采用“双面板”呈现。左图保留完整 sweep 范围 `0-500 mV`，用于确认整体状态翻转；右图放大 `90-126 mV` 临界区，用于清楚展示 RSNM 竖线和交叉附近的曲线变化。横轴统一使用 `mV`，避免原先 `0-0.5 V` 比例尺压缩临界区的问题。

No-RC RSNM noise-source sweep:

![[sram_full_metrics/figures/ideal_rsnm_noise.png]]

RC candidate RSNM noise-source sweep:

![[sram_full_metrics/figures/rc_candidate_rsnm_noise.png]]

read-mode butterfly 曲线如下，用于辅助观察读态 DC 响应；RSNM 数值以上述 noise-source sweep 为准。

![[sram_full_metrics/figures/ideal_read_butterfly.png]]

![[sram_full_metrics/figures/rc_candidate_read_butterfly.png]]

### 5.3 Read disturb

Read disturb 描述读操作期间，原本为低电平的存储节点被 access transistor 和预充 bit-line 抬高的最大幅度。

```text
read_disturb = max(V(QB)) during read window
```

结果：

- No-RC: `143.70 mV`
- RC candidate: `145.20 mV`

![[sram_full_metrics/figures/ideal_read_waveform.png]]

![[sram_full_metrics/figures/rc_candidate_read_waveform.png]]

### 5.4 Read stability margin: 动态读稳定性辅助量

该指标不是标准 RSNM，仅用于解释瞬态 read disturb 距离 `VDD/2` 的余量。

```text
Read stability margin = VDD/2 - read_disturb
```

结果：

- No-RC: `206.30 mV`
- RC candidate: `204.80 mV`

### 5.5 Read delay

```text
read_delay = t(BL - BLB = 50 mV) - t(WL = 0.5VDD)
```

结果：

- No-RC: `15.20 ps`
- RC candidate: `15.60 ps`

![[sram_full_metrics/figures/ideal_read_bldiff.png]]

![[sram_full_metrics/figures/rc_candidate_read_bldiff.png]]

### 5.6 Write delay

```text
write_delay = t(Q = 0.5VDD) - t(WL = 0.5VDD)
```

结果：

- No-RC: `37.40 ps`
- RC candidate: `38.60 ps`

![[sram_full_metrics/figures/ideal_write_waveform.png]]

![[sram_full_metrics/figures/rc_candidate_write_waveform.png]]

### 5.7 Write-trip BL drop

Write-trip BL drop 表示写 0 时，需要将 BL 从 VDD 拉低多少，cell 才到达翻转临界点。该量是写能力 proxy，不等同于严格 WSNM。

```text
write_trip_BL_drop = VDD - VBL_at_crossing
```

结果：

- No-RC: `454.00 mV`
- RC candidate: `450.00 mV`

![[sram_full_metrics/figures/ideal_write_trip.png]]

![[sram_full_metrics/figures/rc_candidate_write_trip.png]]

### 5.8 Read/write energy

```text
energy = integral(VDD * abs(I(VDD_SRC))) dt
```

结果：

- Read energy:
  - No-RC: `0.029 fJ`
  - RC candidate: `0.043 fJ`
- Write energy:
  - No-RC: `0.039 fJ`
  - RC candidate: `0.114 fJ`

![[sram_full_metrics/figures/ideal_energy.png]]

![[sram_full_metrics/figures/rc_candidate_energy.png]]

### 5.9 Hold leakage

```text
P_leak = VDD * abs(I_VDD)
```

结果：

- No-RC: `1383.889 pW`
- RC candidate: `1386.834 pW`

## 6. 适用范围与网表说明

1. 本文 RC 结果对应 `RC candidate` 网表。该网表中 `R_QB_PU` 未串入 `XPU2` 漏端路径，因此 RC 影响应按当前候选网络解释。
2. Write-trip BL drop 是写能力 proxy。若需要与严格 WSNM/WRM 文献指标对齐，可进一步增加 write-mode noise-source WSNM 或 WL/BL write margin。
3. RSNM 当前 step 为 `1 mV`，因此数值精度约为 `±1 mV`。若需要更高精度，可在临界点附近做二分细扫。

## 7. Benchmark 口径说明

| 指标 | 当前是否可与 benchmark 比较 | 说明 |
|---|---|---|
| HSNM | 可有限比较 | 已使用几何最大内嵌正方形法；比较时需注意本文为单 cell 理想边界 |
| RSNM | 可有限比较 | 已使用 read-mode noise-source 法，但未做 PVT/Monte Carlo |
| Read disturb | 不直接等同 RSNM | 是瞬态扰动量 |
| Read/write delay | 只能与 cell-level benchmark 比较 | 不含 decoder、sense amp、write driver |
| Write-trip BL drop | 不可直接等同 WSNM/WRM | 当前是 BL sweep proxy |
| Energy | 不可直接与 macro power 比较 | 当前只统计 cell-level VDD energy |

## 8. 结论

1. No-RC RSNM 为 `108.00 mV`，RC candidate RSNM 为 `106.00 mV`。
2. RSNM 图采用全局 + 临界区放大双面板，横轴以 mV 标注，可同时展示完整 sweep 与临界翻转区域。
3. HSNM 由几何最大内嵌正方形提取，No-RC 为 `268.00 mV`，RC candidate 为 `267.50 mV`。
4. 在当前候选 RC 网络下，RC 主要表现为 RSNM 降低 `2.00 mV`、read disturb 增加 `1.50 mV`、read/write delay 增加，以及 write energy 增大。
