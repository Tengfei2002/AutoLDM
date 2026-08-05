# SRAM HSPICE 指标仿真流程：以流程打通为目标

本文档覆盖原有 `sram_workflow.md`。当前阶段的目标不是与文献 benchmark 严格对齐，而是建立一套可复用、可运行、每个指标都有数值输出的 SRAM HSPICE 流程。后续更换新的 VA、RC 或 SRAM 结构时，应按本文顺序推进。

## 1. 总体原则

流程必须逐级验证，不能直接从完整 SRAM + RC 开始。

1. 单器件验证：先验证 `fusion_ic_nmos_lvt.va` 与 `fusion_ic_pmos_lvt.va` 的 IV 曲线。
2. 反相器验证：确认 NMOS/PMOS 组合后可形成合理 VTC、翻转阈值和瞬态响应。
3. No-RC SRAM：在无寄生 RC 条件下确认 6T SRAM 可保持、可读、可写。
4. RC SRAM：只在 No-RC 通过后加入 RC。若 extracted-RC 出现悬浮节点或矩阵奇异，应先用诊断性 RC candidate 打通流程，不得把异常 extracted-RC 作为正式结论。
5. 指标提取：每个指标必须有明确 testbench、提取公式、数值结果和曲线图。

## 2. 当前固定仿真条件

| 项目 | 当前设置 |
|---|---|
| NMOS VA | `Hspice/va/fusion_ic_nmos_lvt.va` |
| PMOS VA | `Hspice/va/fusion_ic_pmos_lvt.va` |
| SRAM | 6T bit-cell |
| VDD | `0.7 V` |
| 温度 | `25 degC` |
| 器件尺寸 | `L=16 nm`, `WPG=WPD=WPU=25 nm`, `NF=1` |
| 存储节点电容 | `CQ=CQB=1 fF` |
| bit-line 电容 | `CBL=CBLB=10 fF` |
| 瞬态步长 | `0.2 ps` |
| read delay 判据 | `WL=0.5VDD` 到 `BL-BLB=50 mV` |
| write delay 判据 | `WL=0.5VDD` 到 `Q=0.5VDD` |
| energy 计算 | `E = integral(VDD * abs(I(VDD_SRC)))` |

## 3. 当前输出指标

当前阶段采用“正式指标 + 流程 proxy 指标”的组合，保证所有量都有数值。

| 指标 | 类型 | 测试方法 | 计算方法 |
|---|---|---|---|
| HSNM | 正式静态指标 | `WL=0`, `BL=BLB=VDD`，DC butterfly | 在 butterfly 两个 lobe 内几何搜索最大内嵌正方形，取较小边长 |
| RSNM | 正式读静态指标 | `WL=VDD`, `BL=BLB=VDD`，在反馈 gate 中注入等幅反向 DC noise | 扫描 noise，取 Q=1/Q=0 两个初态刚好翻转的较小临界噪声 |
| Read disturb | 动态读稳定性 | 初始 `Q=VDD`, `QB=0`，`BL=BLB=VDD`，拉高 WL | 读窗口内 `max(V(QB))` |
| Read stability margin | 流程 proxy | 使用 read disturb transient | `VDD/2 - max(V(QB))` |
| Read delay | 动态读速度 | read transient | `t(BL-BLB=50mV) - t(WL=0.5VDD)` |
| Write delay | 动态写速度 | write-0 transient | `t(Q=0.5VDD) - t(WL=0.5VDD)` |
| Write-trip BL drop | 写入能力 proxy | `WL=VDD`, `BLB=VDD`，DC 扫 `BL` | `VDD - VBL_at_crossing(Q=QB)` |
| Read energy | 单元读能量 | read transient | 对 `VDD*abs(I(VDD_SRC))` 积分 |
| Write energy | 单元写能量 | write transient | 对 `VDD*abs(I(VDD_SRC))` 积分 |
| Hold leakage | 保持态泄漏 | hold DC/op | `VDD*abs(I_VDD)` |

说明：标准 RSNM 已改用 noise-source 注入法提取，不再依赖失败的 read-mode 强制 Q sweep butterfly。`Read stability margin = VDD/2 - read disturb` 仍保留为动态读扰动 proxy，用于辅助解释瞬态读稳定性，但不再替代 RSNM。

## 4. 推荐执行顺序

### 4.1 单器件 IV

目的：确认 VA 模型的基本电流、电压和导通方向合理。

需要检查：

- NMOS `Id-Vg`：`Vgs` 增大时 `Id` 应增大；
- PMOS `Id-Vg`：按 PMOS 极性应表现出合理导通；
- `Id-Vd`：低场线性区与高场饱和趋势应合理；
- off leakage 不应出现数量级异常；
- 曲线不应出现明显不连续、NaN 或非物理跳变。

### 4.2 反相器

目的：确认 NMOS/PMOS 组合后可以形成 SRAM 所需双稳态基础。

需要检查：

- DC VTC 从高电平翻转到低电平；
- 翻转点处于合理范围；
- 瞬态输入翻转后输出能够稳定到 rail；
- rise/fall delay 不出现负值或异常大值；
- 静态泄漏数量级合理。

### 4.3 No-RC SRAM

目的：建立干净基线。

必须通过：

- hold 不翻转；
- read 不破坏原始状态；
- write 能成功翻转；
- delay、energy、leakage 可提取；
- HSNM butterfly 可计算；
- RSNM noise-source sweep 可计算；
- read stability proxy 可计算。

### 4.4 RC SRAM

目的：检查 RC 对 SRAM 指标的影响。

若原始 extracted-RC 出现如下问题：

```text
Empty row/column at node ...
singular matrix
floating node
```

应判定为 RC 拓扑未通过，不应继续把该 RC 作为正式数据。流程打通阶段允许使用诊断性 `RC candidate`，但报告中必须明确其不是最终 extracted-RC。

## 5. 图和数据产物

当前流程的主要产物位于：

| 类型 | 位置 |
|---|---|
| 指标汇总 CSV | `Hspice/sram_full_metrics/data/summary_metrics.csv` |
| 曲线 CSV | `Hspice/sram_full_metrics/data/` |
| PNG/SVG 曲线图 | `Hspice/sram_full_metrics/figures/` |
| 对比报告 | `Hspice/sram_comparison.md` |
| 本流程文档 | `Hspice/sram_workflow.md` |

每张科研图应同时保留 `.png` 与 `.svg`。Markdown 中使用 `![[...png]]` 插入 PNG，SVG 用于后续论文级矢量编辑。

## 6. 当前流程判据

本阶段判定“打通”的标准如下：

1. No-RC 和 RC candidate 均有完整数值表；
2. 所有指标均不是空值；
3. 标准 RSNM 通过 noise-source sweep 给出数值；
4. 使用 `Read stability margin` 作为辅助动态读稳定性结果；
5. 所有曲线图可在 Markdown 中通过 `![[...]]` 显示；
6. 对 extracted-RC 的问题必须单独说明，不能隐藏。

## 7. 后续升级方向

流程打通后，下一阶段再提高 benchmark 可比性：

1. 进一步提高 RSNM 提取精度，例如将 `1 mV` noise step 改为二分细扫或 PVT/Monte Carlo；
2. 用标准 write static noise margin 或 WL/BL write margin 替代 write-trip proxy；
3. 加入 bit-line、word-line、precharge、sense amplifier 与 write driver；
4. 将 cell-only energy 拆分为 cell、BL、WL、peripheral energy；
5. 修复原始 extracted-RC 中的悬浮节点和 pin 映射问题。
