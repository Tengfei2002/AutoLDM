# Paper-Based Structure Explanation

本文档参考 `paper/Yang 等 - Double-Flip Sequential CFET Superior 3T Library Efficiency and PPA.pdf`，结合当前 `rules/cfet_arch.txt`、`rules/layer_rule_1.txt` 和 `gen_sde.py`，解释 CFET/sCFET 结构之间的关系与参数内涵。

## 1. 文章主线

论文讨论的是 double-flip sequential CFET，简称 sCFET。它的核心目标不是单纯堆叠一个三维器件，而是在标准单元库层面同时获得：

- split-gate 能力
- dense backside BM0 routing
- vertical local interconnect VMM
- 3-track standard cell 可布线性
- 更高 layout efficiency 和更好的 PPA

论文的组织逻辑可以概括为：

1. common-gate CFET 的限制：上下器件共用 gate，缺少独立 gate 控制，不利于 transmission gate 和复杂逻辑。
2. split-gate CFET 的价值：上下或左右 gate 可独立控制，提高逻辑表达能力，但会引入额外 gate parasitic capacitance。
3. double-flip sequential process 的意义：通过顺序加工 top/bottom device，降低 monolithic CFET 的高深宽比工艺困难，并支持 split-gate 和 dense backside routing。
4. 标准单元效率比较：从 DR、hDR、hDR denseBM0、hDR split-gate 到 sCFET，逐步改善 cell area 和 layout efficiency。
5. PPA 优化：通过 gate/MD/BMD 面积、电容调节、VGG thickness、hybrid orientation、asymmetric sheet width 优化频率、功耗和 rise/fall balance。

## 2. 论文中的关键结构对象

### Gate

Gate 是控制 channel 的核心电极。论文中对 common-gate 和 split-gate 的区分非常关键：

- common-gate：上下器件 gate 共享控制，结构简单，但独立控制能力弱。
- split-gate：不同器件或不同极性的 gate 可被分离控制，支持更复杂标准单元，但会增加 gate parasitic capacitance。

在本项目中：

- layout 7 号层对应 common gate。
- `Gate_Common` 的 x/y 范围来自 `gds/test1_gds.txt` 中 7 号层。
- `Gate_Common` 的 z 范围来自 `layer_rule_1.txt` 中 7 号层的 `start_z1/end_z2`。
- `material` 当前来自 layer rule，默认为 `Tungsten`。

图示颜色关系中，gate 对应白色核心区域。它不是 channel，也不是 spacer。

### High-k

High-k 是 gate dielectric，位于 gate 与半导体受控区域之间。论文中提到 high-k/dipole 和 RMG 过程，说明 high-k 是 gate stack 的一部分，会直接影响 gate capacitance。

在本项目中：

- High-k 对应红色薄层。
- High-k 紧贴并包覆 gate 外表面。
- High-k 不应该被理解为包覆 channel 的壳层。
- 参数 `high_k_thickness` 决定这层薄介质的厚度。

当前 `gen_sde.py` 生成：

```text
HighK_Gate_Left
HighK_Gate_Right
HighK_Gate_Front
HighK_Gate_Back
```

这与论文中 gate capacitance sensitivity 的物理含义一致：改变 gate-facing dielectric/metal 几何，会改变 parasitic gate capacitance。

### Channel

Channel 是实际导电和受 gate 控制的半导体区域。论文中 Fig.7-9 强调 sheet width、晶向和上下层器件差异对 Ion、Ieff、功率密度、rise/fall delay 的影响。

在本项目中：

- Channel 对应青绿色小块。
- 它不是贯穿整个 gate 的长条。
- 每一层 channel 在 gate 左右两侧分别生成局部小块。

命名示例：

```text
ChannelLower_0_L
ChannelLower_0_R
ChannelUpper_1_L
ChannelUpper_1_R
```

相关参数：

- `num_channel` / `num_channel_lower` / `num_channel_upeer`：上下层 channel 数量。
- `channel_thickness`：每层 channel 的 z 向厚度。
- `channel_mdi_thickness`：channel 层间介质间隔。
- `mdi_thickness`：上下器件之间的中间介质隔离。
- `channel_length`：左右 channel 小块的总外包络 x 向长度。
- `channel_width`：channel 的 y 向宽度，也与论文中的 sheet width / active sheet width 概念对应。
- `channel_upper_width` / `channel_lower_width`：为论文提到的 asymmetric sheet width 优化预留参数入口。

论文中提到将 active sheet width 从 21 nm 缩小到 14 nm 可降低 power density；增大较弱器件的 sheet width 可缓解 NMOS/PMOS Ion mismatch。这对应本项目中的 `channel_upper_width/channel_lower_width` 以及后续可扩展的 N/P 独立 width 设定。

### Inner Spacer

Inner spacer 是 gate stack 与 S/D 之间的隔离区域。根据用户提供图示，棕黄色区域对应 inner spacer。

在本项目中应理解为：

- Inner spacer 与左右 channel 小块处在同一侧向 slab。
- Channel 小块占据每层窗口。
- Inner spacer 填充 channel 窗口之外的 y/z 间隔。
- Inner spacer 不能被简单理解成一整块贴在裸 gate 侧壁上的连续竖墙。
- Inner spacer 的作用是隔离 gate/High-k 与 S/D，同时不阻断 S/D 与 channel 的接触。

相关参数：

- `inner_spacer_thickness`：inner spacer 的结构尺度参数。
- 当前实现中，inner spacer 的 x 范围与左右 channel slab 对齐，y/z 中避开 channel 窗口。

### S/D Epi

Source/Drain epitaxy 是驱动电流的注入/收集区域。论文中 EPI、pEPI/nEPI、S/D stressor 和 sheet width 共同影响 Ion 与 PPA。

在本项目中：

- S/D 必须与 channel 小块的外端面接触。
- 左侧 S/D 从 boundary 左边界延伸到左 channel 外端面。
- 右侧 S/D 从右 channel 外端面延伸到 boundary 右边界。
- S/D 的 y/z 外扩由 overgrowth 参数控制。

相关参数：

- `sd_overgrowth_y`
- `sd_overgrowth_z_up`
- `sd_overgrowth_z_down`
- `sd_upper_overgrowth_y`
- `sd_lower_overgrowth_y`
- `sd_upper/lower_overgrowth_z_up/down`

当前 doping：

- 上层 S/D：`ArsenicActiveConcentration = 8e19`
- 下层 S/D：`BoronActiveConcentration = 8e19`
- 衬底不进行 doping。

## 3. sCFET 架构含义

### Sequential vs Monolithic

论文比较了 monolithic CFET 和 sequential CFET。

Monolithic CFET 同时加工上下器件，mask 少，但高深宽比刻蚀、共享 gate、routing conflict 等问题更强。

Sequential CFET 将 top/bottom device 分开加工：

- top device 和 bottom device 可使用独立 mask。
- top/bottom gate 可更容易 split。
- 通过 double-flip process 实现 backside/frontside 的加工与互连。
- 工艺复杂度提高，但设计自由度显著提高。

在参数上，这意味着本项目不能只支持一个单一统一 channel/gate 参数，而应保留：

- upper/lower channel 数量
- upper/lower channel width
- upper/lower S/D overgrowth
- upper/lower doping
- split gate 扩展入口

### Dense BM0 与 VMM

论文强调 dense backside BM0 和 VMM bypass 对 3T library efficiency 的贡献。

BM0 是 backside routing resource，dense BM0 可以提高布线密度。VMM 是 vertical local interconnect，可以绕过 bottom device，从而减少资源冲突。

当前 `gen_sde.py` 已能把启用的 BM0/BVMD/BV0/VMM/VMD 等非核心 layer 作为通用 cuboid 生成。它们仍不是完整的标准单元 routing network，但已经可以表达论文中 dense BM0/VMM 的局部几何入口。生成时应遵守：

- 启用对应 layer 的 `enable`。
- 从 layout 中读取 x/y。
- 从 layer rule 中读取 z 和 material。
- 金属层自动添加 top/bottom contact。
- 只要存在背部互连，就不生成衬底；背部互连从下层晶体管下方的 `z = 0` 以下开始，而不是从衬底下方开始。

### Split-gate 与寄生电容

论文 Fig.4-6 的核心提醒是：split-gate 能改善标准单元表达能力，但会增加 gate parasitic capacitance。尤其 gate-to-BMD、gate-to-MD、VGG thickness 等会影响 RO frequency。

这与本项目参数的关系是：

- `gate` 的高度、面积、和附近介质/金属层位置会影响寄生电容。
- `high_k_thickness` 改变 gate dielectric 的几何关系。
- `mdi_thickness` 和未来的 MD/BMD 参数会影响 gate-to-MD/BMD facing area。
- `mesh` 的核心窗口需要覆盖 gate/High-k/channel/S/D 接触区，避免电容敏感区域网格过粗。

### Hybrid Orientation 与 Asymmetric Sheet Width

论文强调 hybrid top-bottom orientation 和 asymmetric sheet width 可优化 NMOS/PMOS Ion mismatch。

本项目中与之最接近的参数入口是：

- `channel_upper_width`
- `channel_lower_width`
- `channel_width = -1` 时启用上下层独立宽度

如果后续要进一步拟合论文中的优化，应扩展为 N/P 独立参数，例如：

```text
channel_n_width
channel_p_width
channel_upper_n_width
channel_upper_p_width
channel_lower_n_width
channel_lower_p_width
```

这样才能表达 “weaker device placed on top and enlarged sheet width” 这类优化。

## 4. 当前参数体系与论文概念映射

| 论文概念 | 项目参数/文件 | 当前含义 |
| --- | --- | --- |
| CPP | `cpp` | 标准单元 x 向 pitch 参考值，目前主要保留为设计参数 |
| CH | `cell_height` | 标准单元高度参考值 |
| Gate | layout 7, `layer_rule_1.txt` layer 7 | gate 几何主体 |
| Split gate | layer 8/9/10 | 预留 split-gate 生成入口 |
| High-k/dipole | `high_k_thickness` | gate 外表面红色介质薄层 |
| Nanosheet/channel | `num_channel`, `channel_*` | 左右 channel 小块数量、尺寸、位置 |
| MDI/eMDI | `mdi_thickness`, `channel_mdi_thickness` | channel 间隔与上下器件隔离 |
| Inner spacer | `inner_spacer_thickness` | channel 窗口外的棕黄色隔离区域 |
| S/D EPI | `sd_overgrowth_*` | S/D 外延 y/z 包络扩展 |
| N/P doping | `sd_upper/lower_doping_*` | 上下层 S/D 掺杂 |
| Mesh sensitivity | `global_mesh_*`, `core_mesh_*` | 核心结构区网格控制 |
| Final node output | `mesh_output_name` | `n@node@_` 前缀输出名 |

## 5. 对当前建模的解释

当前 `gen_sde.py` 是面向论文中局部 CFET cross-section 的结构生成器，而不是完整标准单元库生成器。它重点表达：

- gate stack 的几何主体
- High-k 与 gate 的贴合关系
- 左右 channel 小块
- inner spacer 的窗口隔离作用
- S/D 与 channel 的接触
- 上下层器件堆叠
- S/D doping 和 mesh 设置

它暂时不完整表达：

- dense BM0 routing 的完整网络拓扑
- VMM bypass 的完整电连接语义
- MD/BMD 电容结构
- 多 cell library placement/routing
- N/P 独立晶向与独立 sheet width 的完整映射

因此，当前参数体系适合先建立单器件/局部截面的 SDE 结构；若要进一步复现论文中的 PPA 结论，需要扩展互连层、MD/BMD 层、电容提取边界和 N/P 独立参数。

## 6. 建模时最容易误解的点

1. High-k 不是包 channel，而是贴 gate。
2. Channel 不是白色区域；图示中青绿色小块才是 channel。
3. Inner spacer 不是青绿色小块；棕黄色区域才是 inner spacer。
4. S/D 必须接触 channel 外端面，不能被 inner spacer 阻断。
5. 衬底不进行 doping；当存在 BM0/BVMD/BV0 等背部互连时，衬底实体也不生成。
6. sCFET 的价值主要来自结构与布线协同，不只是单个 transistor 几何。

这些规则应优先于旧脚本或旧文档中的描述。
