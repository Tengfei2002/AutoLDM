# 现有 SRAM-RC 阵列逐条审计与修复建议

## 结论

现有 RC 阵列的主要问题不是某一个电阻数字“稍微不准”，而是**把分布式 RC 网络压缩成同一 net 内所有端点的两两最短路径电阻**，并额外加入若干对称近似和 1 µΩ alias。这会产生重复并联路径、改变等效电阻、掩盖原始 open edge，并可能破坏器件端点的矩阵连接。新建 clean RC 网表在 Hold-Q=1 的矩阵建立阶段仍报告三个空行/列，因此当前 RC 不能用于 SRAM 性能结论。

## 1. 审计对象

审计对象为 [sram_clean/decks/sram6t_rc.inc](sram_clean/decks/sram6t_rc.inc)。它保留了现有映射报告中的 42 个电阻和 25 个电容：7 个端口电阻、2 个 gate alias、30 个 R-map 路径/近似项，以及 20 个 region-to-region 电容和 5 fF 外部测试负载不计入该 25 个抽取 C。

## 2. 电阻逐条审计

### 2.1 端口到 access/WL 路径

| 元件 | 数值 | 来源属性 | 审计结论 |
|---|---:|---|---|
| `R_BL` | 21.9571 Ω | extracted path | 可保留；用于 BL_PORT 到 PG1 source/drain 的路径 |
| `R_BLB` | 25.6802 Ω | extracted path | 可保留；与 BL 路径不完全对称是合理的 |
| `R_WL1` | 7.03199 Ω | extracted path | 可保留 |
| `R_WL2` | 7.03199 Ω | extracted path | 可保留，但需确认两个 gate 的真实接触是否共享同一 contact |
| `R_WL12` | 13.1976 Ω | path sum | 不应与 `R_WL1/R_WL2` 同时作为独立端到端边直接并入；可能重复表示同一路径 |

BL/BLB/WL 的四个端口路径是最容易追溯的部分。`R_WL12` 如果来自同一 gate trunk 的路径和，不应再与两条端口路径组成全连接三角形，除非原始 RC matrix 确实包含这三条独立边。

### 2.2 Q 网络

| 元件 | 数值 | 来源属性 | 审计结论 |
|---|---:|---|---|
| `R_Q0` | 52.4800 Ω | direct extracted | 可保留 |
| `R_Q1` | 134.3127 Ω | shortest path | 可作为候选端到端值，但不是原始分布网络 |
| `R_Q2` | 85.0947 Ω | shortest path | 可作为候选值 |
| `R_Q3` | 85.0947 Ω | symmetric approximation | 不应直接视为 extracted；需原始矩阵或镜像几何证明 |
| `R_Q4` | 131.973 Ω | shortest path | 与 Q1/Q2/Q3 同时加入会形成多条并联 shortcut，改变 Q 等效阻抗 |
| `R_Q5` | 95.0226 Ω | shortest path | 同上 |
| `R_Q6` | 95.0226 Ω | symmetric approximation | 近似项，不能作为正式 RC |
| `R_Q7` | 219.4074 Ω | shortest path | 同上 |
| `R_Q8` | 219.4074 Ω | symmetric approximation | 近似项，不能作为正式 RC |
| `R_Q9` | 1 µΩ | same-net alias | 只能用于明确相同 net 的端点合并；不应代替缺失的 extracted connection |

Q 网已经有 `Q_NODE→PG1_PD1_Q_SD`、`Q_NODE→PU1_Q_SD`、`Q_NODE→PD2_Q_GATE` 和 `Q_NODE→PU2_Q_GATE`。再加入所有端点之间的 Q4–Q8，会把多条最短路径当成真实并行导线，通常显著降低等效电阻。这是当前 RC 数值最严重的建模问题。

### 2.3 QB 网络

`R_QB0–R_QB9` 与 Q 网络镜像。`R_QB0=52.48 Ω`、`R_QB1=134.3127 Ω`、`R_QB2/R_QB3=85.0947 Ω`、`R_QB4=132.3689 Ω`、`R_QB5/R_QB6=56.3822 Ω`、`R_QB7/R_QB8=177.2061 Ω`、`R_QB9=1 µΩ`。

其中 Q B 网络的 `R_QB0`、`R_QB1` 是可追溯候选；`R_QB2/R_QB3`、`R_QB6`、`R_QB8` 是对称或近似项；所有 QB 端点两两互联会产生同样的并联 shortcut。Q 与 QB 不应仅因几何对称就复制数值，必须保留原始 net/contact 对应关系。

### 2.4 VDD/VSS 网络

| 元件 | 数值 | 审计结论 |
|---|---:|---|
| `R_VDD1/R_VDD2` | 38.5094 Ω | 端口到两个 PMOS source 的路径，可作为候选 |
| `R_VDD3` | 1 µΩ | 若两个 source 共享同一 contact 可保留，否则是人为短路 |
| `R_VSS1/R_VSS2` | 40.5686 Ω | 端口到两个 NMOS source 的候选路径 |
| `R_VSS3` | 81.1372 Ω | 由两条 source 路径相加得到的额外边；与 VSS1/VSS2 同时存在会制造非原始并联回路，建议删除 |

VSS3 是一个明确的拓扑风险：如果 VSS1 和 VSS2 已经把两个 source 接到 VSS_PORT，VSS3 不是必需连接；如果它代表原始中间导线，必须从原始 R matrix 直接导入，而不能用路径和再造一条边。

## 3. 电容逐条审计

当前 20 个 `C_*` 是 region-to-region mutual capacitance，均为正值，数量级约 `2.8e-20–5.67e-17 F`；最大项为：

```text
C_WL_Q   = 40.638 fF
C_WL_QB  = 56.711 fF
C_Q_QB   = 93.747 fF
C_VSS_Q  = 18.814 fF
C_VSS_QB = 19.001 fF
```

正值和数量级本身没有明显非法项，但仍有三个重要问题：

1. 只有 mutual C，不等于完整 Maxwell capacitance matrix；需要确认原始抽取文件是否还包含每个 region 对 ground 的 self-capacitance。
2. 若原始 C matrix 已经是 terminal-to-terminal reduced matrix，直接将所有 pairwise C 加回可能重复计数。
3. 每个内部器件端点必须能通过 RC 网络连接到这些电容节点；否则 C 数值正确也不能修复空行/列。

因此当前不能仅根据“所有 C 都为正”判定电容阵列正确。

## 4. 失败证据

全新 `sram6t_rc.inc` 的 Hold-Q=1 运行报告：

```text
Empty row/column at node (xsram.pu1_qb_gate)
Empty row/column at node (xsram.pu2_q_gate)
Empty row/column at node (xsram.pu2_vdd_sd)
```

加入 1 TΩ 和 1 GΩ shunt 后仍然报告相同节点，因此不能把问题解释为单纯缺少一个泄漏电阻。当前最可能的根因是：RC reduced netlist 的端点划分与 Fusion VA 器件 terminal stamp 不一致，或者 pairwise reduction 形成了不被 HSPICE 视为有效端口连接的内部节点。

## 5. 已尝试的修复

新增 [sram6t_rc_candidate.inc](sram_clean/decks/sram6t_rc_candidate.inc)，删除 Q/QB 全连接最短路径边，仅保留可追溯的端口—器件路径、明确的 gate alias 和原始 mutual C。该候选仅用于验证“去除重复并联 shortcut”是否能改善矩阵；它不是原始抽取 RC 的等价替代。验证 deck 为 [19_sram_rc_candidate_hold1.sp](sram_clean/decks/19_sram_rc_candidate_hold1.sp)。候选运行后 `PU2_VDD_SD` 的空行/列消失，但 `PU1_QB_GATE` 与 `PU2_Q_GATE` 仍然存在；因此删去 all-pairs 电阻是必要但不充分的修复。

进一步的 candidate-2 [sram6t_rc_gate_direct.inc](sram_clean/decks/sram6t_rc_gate_direct.inc) 将 PMOS gate 恢复为 6T 拓扑规定的直接 `QB/Q` 连接，所有空行/列消失，Hold/Read/Write 六个 case 均通过。该修复保留 R/C 数值不变，验证的是端点拓扑问题，而不是电阻调参；但它不等价于保留 PMOS gate 的分布式 RC。

## 6. 建议

1. 从原始 `n19_cMatrix.spi/n18_cMatrix.spi` 直接保留分布式 R/C 网表，不要用所有节点两两 shortest path 代替原网表。
2. 重新核对 schematic label 到 extracted contact 的一对一映射，特别是 `PU1_QB_GATE`、`PU2_Q_GATE`、`PU2_VDD_SD`。
3. 对 R matrix 中的 `Inf/open` 边保留 open 语义；不要用 1 µΩ alias 或对称值掩盖缺失连接。
4. 对每个 net 输出图连通性、节点度、端口可达性和等效电阻；对 C matrix 输出 self-C、mutual-C 和总电容。
5. candidate Hold 只有在无 `Empty row/column`、无 FPE/NaN 且 Q/QB 保持后，才继续 candidate Read/Write；正式报告应同时保留原始 RC blocked 记录。
