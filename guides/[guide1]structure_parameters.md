# Structure Parameters in `rules`

本文档罗列 `AutoLDM/LD/rules` 中当前出现的全部结构参数，并说明它们的物理/几何意义，以及在结构搭建过程中何时被采用、何时被屏蔽。

当前规则文件主要有两类：

- `cfet_arch.txt`：CFET 内部结构参数，如沟道数量、沟道尺寸、High-k 厚度、源漏外延扩展量等。
- `layer_rule_1.txt`：版图层到三维结构层的规则表，如层编号、z 向高度范围、材料、是否启用等。

代码参考关系：

- `gen_sde.py`：当前 SDE 生成流程中最完整地使用这些参数。
- `gen_arch.py`：生成 OBJ/MTL 结构模型，也使用部分参数，但对 split gate、上/下层独立参数的支持比 `gen_sde.py` 少。

## 坐标约定

- `x` 方向：Source-Gate-Drain 方向，也是源漏左右分布方向。
- `y` 方向：栅宽方向/沟道宽度方向。
- `z` 方向：垂直堆叠方向，从下层晶体管底部附近的 `z = 0` 开始向上堆叠沟道、MDI 和上层器件。无背部互连时，衬底通常在 `z < 0`；存在背部互连时，不生成衬底，背部互连层直接从下层晶体管下方继续向负 z 方向堆叠。

## `layer_rule_1.txt` 字段参数

规则表格式：

```text
layer_num layer_name enable height start_z1 end_z2 material boundary ILD
```

| 参数 | 物理/几何意义 | 被什么过程参考 | 采用/屏蔽规则 |
| --- | --- | --- | --- |
| `layer_num` | 版图层编号，是二维 layout 和三维层规则之间的索引。 | `parse_rules()` 建立规则字典；`build_substrate()` 查找 1 号层；`build_gate()` 查找 7 号层。指南中还定义 8/9/10 可用于 split gate。 | 若 layout 中没有对应层，或生成逻辑没有专门处理该层，则该层不会生成结构。 |
| `layer_name` | 层名称/工艺层语义，例如 `boundary`、`gate`、`M0` 等。 | 当前 `gen_sde.py`、`gen_arch.py` 主要按 `layer_num` 处理，未实际读取该字段参与几何计算。 | 目前作为人类可读注释使用；修改名称不会改变当前生成结构。 |
| `enable` | 是否启用该层规则。 | `gen_sde.py` 只把 `enable = true` 的层放入 `rules_data`；`gen_arch.py` 会读取所有层，但只对启用层做高度一致性校验。 | 在 `gen_sde.py` 中，`false` 层被直接跳过，即使 layout 中有对应层也不会生成。`gen_arch.py` 对特定层是否生成还取决于后续代码是否引用该层编号。 |
| `height` | 该层在 z 方向的物理厚度。 | 解析规则时用于校验 `end_z2 - start_z1 == height`。 | 对 `enable = true` 的层必须满足一致性，否则生成中止。当前几何生成主要使用 `start_z1/end_z2`，`height` 主要承担校验作用。 |
| `start_z1` | 该层 z 方向下边界。 | 衬底、gate 等 layout 层转换为三维 cuboid 时作为下表面坐标。 | 只有被启用且被生成流程引用的层才采用。 |
| `end_z2` | 该层 z 方向上边界。 | 衬底、gate 等 layout 层转换为三维 cuboid 时作为上表面坐标。 | 只有被启用且被生成流程引用的层才采用。 |
| `material` | 该层版图内部实体材料。 | `gen_sde.py` 的 gate 结构使用 7 号层材料；金属材料还用于判断是否添加 contact。 | `build_substrate()` 当前固定使用 `Silicon`，不会采用 1 号层的 `material` 字段；gate 会采用该字段。 |
| `boundary` | 该层版图的最大有效区域定义。 | 当前生成脚本未实际读取该字段。 | 目前被屏蔽，仅作为规则表中的语义字段保留。 |
| `ILD` | 层内未被实体填充区域的介质材料。 | 当前生成脚本未实际读取该字段。 | 目前被屏蔽；ILD 背景或空隙填充需要后续生成逻辑显式支持。 |

### 当前 layer 编号的结构语义

- `1 boundary`：器件有效边界。当前必须存在，始终提供整体结构和 S/D 的 x/y 范围；无背部互连时还用于生成 `Substrate_1` 的 z 范围。若存在背部互连，`Substrate_1` 被屏蔽，1 号层只作为 x/y 边界参考。
- `7 gate`：common gate。若 layout 与规则中存在并启用 7 号层，则生成一个整体 gate。
- `8 gate_upper`、`9 gate_lower`、`10 gate_merge`：指南中定义为 split gate 的三个部分；当前 `gen_sde.py` 只保留了扩展入口，尚未实现实际生成。
- 其他金属/通孔层如 `M0`、`VM0`、`BM0`、`BVMD`、`BV0` 等：当 `generic_layers_enable = true` 且对应 layer rule 与 layout 均存在时，会作为通用 cuboid 生成；金属材料会自动添加 contact。背部层应以 `z = 0` 下方为起点，而不是以衬底底部为起点。

## `cfet_arch.txt` 结构参数

### 0. 架构模式参数

| 参数 | 物理/几何意义 | 被什么过程参考 | 采用/屏蔽规则 |
| --- | --- | --- | --- |
| `architecture` | 架构名称，例如 `mCFET_CG`、`hDR_denseBM0`、`hDR_split_gate`、`sCFET`。 | 文档、文件组合选择、后续模式扩展。 | 当前主要作为架构标签；具体结构由 `gate_mode`、`bm0_mode`、`vmm_enable`、layer rule 和 gds 共同决定。 |
| `gate_mode` | gate 模式，`common` 或 `split`。 | `gen_sde.py` 的 gate 生成逻辑。 | `common` 对应启用 layer 7；`split` 对应禁用 layer 7 并启用 layer 8/9/10。实际是否生效仍由 layer rule 与 gds 是否提供对应层决定。 |
| `bm0_mode` | backside BM0 模式，`none`、`standard` 或 `dense`。 | 文档和示例文件选择；generic layer 生成；衬底生成判断。 | 当前通过启用 layer rule 中 BM0/BV/BVMD 等层并在 gds 中提供矩形来实现。若 `bm0_mode != none`，或启用了 52/53/54 等背部互连层，`build_substrate()` 会跳过 `Substrate_1`。 |
| `vmm_enable` | 是否启用 VMM bypass 相关层。 | 文档和示例文件选择；generic layer 生成。 | 当前通过启用 layer 17/18 等 VMM/VMD 层并在 gds 中提供矩形实现。 |
| `generic_layers_enable` | 是否把非核心启用 layer 作为通用 cuboid 生成。 | `build_generic_layout_layers()`。 | 为 `true` 时，layout 中存在且 layer rule 启用的非 1/7/8/9/10 层都会生成；为 `false` 时 BM0/VMM/MD/BMD 等通用层被屏蔽。 |
| `hybrid_orientation_enable` | hybrid top-bottom orientation 的模式开关。 | 当前作为参数入口保留。 | 当前不改变几何或材料；需要 TCAD mobility/stress/orientation 数据后才能实际进入物理模型。 |
| `channel_width_mode` | channel 宽度模式，如 `symmetric`、`upper_lower_asymmetric`、未来的 `np_asymmetric`。 | channel width 参数选择。 | 当前支持 `channel_width = -1` 时使用 `channel_upper_width/channel_lower_width`。N/P 独立宽度还需扩展。 |
| `standard_setting_note` | 对该 arch 文件对应标准设置的文字说明。 | 人类阅读。 | 不参与计算。 |

### 1. 沟道数量

| 参数 | 物理/几何意义 | 被什么过程参考 | 采用/屏蔽规则 |
| --- | --- | --- | --- |
| `num_channel` | 全局沟道数量；表示上层器件和下层器件各自包含的纳米片/沟道条数。 | `build_cfet_core()` 中决定 `stack_channels()` 循环次数；`gen_arch.py` 中决定上下层 channel z 坐标列表。 | 若 `num_channel != -1`，上下层都采用该值，此时 `num_channel_upeer` 和 `num_channel_lower` 被屏蔽。若 `num_channel = -1`，分别采用上/下层独立数量。 |
| `num_channel_upeer` | 上层器件沟道数量。注意文件中拼写为 `upeer`，代码也按此拼写读取。 | `gen_sde.py` 在 `num_channel = -1` 时作为上层 channel 数量；`gen_arch.py` 同样兼容该拼写。 | 仅在 `num_channel = -1` 时生效；否则被 `num_channel` 屏蔽。 |
| `num_channel_lower` | 下层器件沟道数量。 | `gen_sde.py` 在 `num_channel = -1` 时作为下层 channel 数量；`gen_arch.py` 同样使用。 | 仅在 `num_channel = -1` 时生效；否则被 `num_channel` 屏蔽。 |

### 2. 单元排布与版图尺度

| 参数 | 物理/几何意义 | 被什么过程参考 | 采用/屏蔽规则 |
| --- | --- | --- | --- |
| `arrangement` | CFET 上下器件的排布模式。注释中 `1` 表示 symmetrical arrangement，`2` 表示 parallel arrangement。 | 当前生成脚本未实际读取。 | 目前被屏蔽；改变该值不会改变当前结构。 |
| `cell_height` | 标准单元整体高度，通常对应 layout 中 cell 的 y 向边界或设计规则尺度。 | 当前生成脚本未实际读取。 | 目前被屏蔽；结构 x/y 范围主要来自 layout 坐标和 channel 参数。 |
| `cpp` | Contacted Poly Pitch，相邻接触栅中心距。 | 当前生成脚本未实际读取。 | 目前被屏蔽；gate 位置来自 layout，核心 channel 位置来自 `channel_center_x/y`。 |

### 3. 垂直堆叠、介质与侧墙厚度

| 参数 | 物理/几何意义 | 被什么过程参考 | 采用/屏蔽规则 |
| --- | --- | --- | --- |
| `channel_thickness` | 单条沟道/纳米片在 z 方向的厚度。 | channel z 坐标堆叠；每条 channel cuboid 的 `z_end - z_start`。 | 始终生效，是核心必需参数。 |
| `channel_mdi_thickness` | 沟道之间的介质间隔厚度，也用于下层第一条 channel 与 `z = 0` 之间、上下层 channel 堆叠中的间隔。 | channel 垂直堆叠过程。 | 始终生效；它本身不生成实体，只改变 channel 的 z 位置。 |
| `inner_spacer_thickness` | 内侧墙/内间隔层厚度，对应图中的棕黄色区域。它填充在每层 channel 窗口之外的间隔区域，用于隔离 gate/High-k 与 S/D。 | inner spacer 生成。 | 始终生效。当前结构中 inner spacer 与 channel 处在 gate 两侧同一侧向 slab：channel 占窗口，inner spacer 填窗口之外的区域。 |
| `gate_spacer_thickness` | 栅极侧墙厚度，通常对应 gate 外侧 spacer。 | 当前生成脚本未实际读取。 | 目前被屏蔽；当前 inner spacer 使用 `inner_spacer_thickness`。 |
| `high_k_thickness` | High-k 栅介质厚度，对应图中的红色薄层。 | High-k 生成。 | 始终生效。High-k 紧贴并包覆 gate 外表面，而不是包覆 channel。 |
| `mdi_thickness` | 上下层器件之间的中间介质隔离厚度。 | 下层 channel 堆叠完成后，进入上层 channel 前增加 z 间距。 | 始终生效；它本身不生成实体，只改变上层 channel 的 z 位置。 |

### 4. Gate 尺寸

| 参数 | 物理/几何意义 | 被什么过程参考 | 采用/屏蔽规则 |
| --- | --- | --- | --- |
| `gate_length` | gate 在 x 方向的参考设计长度。 | 当前 SDE 几何主要由 gate layout 边界决定。 | 当前 common gate 的实际 x/y/z 边界来自 layout 7 号层和 layer rule，不由该值决定。 |
| `gate_width` | gate 在 y 方向的宽度。按注释可用于推导 `channel_length = gate_width + 2*high_k_thickness + 2*inner_spacer_thickness`。 | 当前生成脚本未直接读取。 | 目前被屏蔽；若需要约束 channel/gate 关系，需要在上游规则生成或校验中实现。 |
| `gate_upper_length` | 上层 gate 长度。 | 当前生成脚本未实际读取。 | 目前被屏蔽；`gate_length = -1` 的分层 gate 尺寸逻辑尚未实现。 |
| `gate_lower_length` | 下层 gate 长度。 | 当前生成脚本未实际读取。 | 目前被屏蔽；同上。 |
| `gate_upper_width` | 上层 gate 宽度。 | 当前生成脚本未实际读取。 | 目前被屏蔽；同上。 |
| `gate_lower_width` | 下层 gate 宽度。 | 当前生成脚本未实际读取。 | 目前被屏蔽；同上。 |

### 5. Channel 尺寸与位置

| 参数 | 物理/几何意义 | 被什么过程参考 | 采用/屏蔽规则 |
| --- | --- | --- | --- |
| `channel_center_x` | channel 总外包络的 x 方向中心坐标。 | 左右 channel 小块的外包络边界计算；S/D 左右边界计算。 | 始终生效。 |
| `channel_center_y` | 所有 channel 的 y 方向中心坐标。 | channel y 边界计算；High-k y 包覆；S/D y 外扩。 | 始终生效。 |
| `channel_width` | 全局 channel y 方向宽度，对应图中的青绿色小块在 y 方向的宽度。 | channel y 边界、S/D y 基准边界。 | 若 `channel_width != -1`，上下层均采用该值，`channel_upper_width` 和 `channel_lower_width` 被屏蔽。若 `channel_width = -1`，分别采用上/下层独立宽度。 |
| `channel_length` | channel 左右小块的总外包络 x 方向长度。中间被 gate 和 High-k 占据，实际生成时拆成 gate 左右两侧 channel 小块。 | channel 左右外边界、S/D x 内边界。 | 若 `channel_length != -1`，上下层均采用该值，`channel_upper_length` 和 `channel_lower_length` 被屏蔽。若 `channel_length = -1`，分别采用上/下层独立长度。 |
| `channel_upper_length` | 上层 channel x 方向长度。 | 上层 channel x 边界、上层 S/D x 内边界。 | 仅在 `channel_length = -1` 时生效。 |
| `channel_lower_length` | 下层 channel x 方向长度。 | 下层 channel x 边界、下层 S/D x 内边界。 | 仅在 `channel_length = -1` 时生效。 |
| `channel_upper_width` | 上层 channel y 方向宽度。 | 上层 channel y 边界、上层 S/D y 边界。 | 仅在 `channel_width = -1` 时生效。 |
| `channel_lower_width` | 下层 channel y 方向宽度。 | 下层 channel y 边界、下层 S/D y 边界。 | 仅在 `channel_width = -1` 时生效。 |

### 6. S/D 外延扩展

| 参数 | 物理/几何意义 | 被什么过程参考 | 采用/屏蔽规则 |
| --- | --- | --- | --- |
| `sd_overgrowth_y` | 全局 S/D 外延在 y 方向向两侧的扩展量。 | S/D cuboid 的 `y1/y2` 计算。 | 若 `sd_overgrowth_y != -1`，上下层均采用该值，`sd_upper_overgrowth_y` 和 `sd_lower_overgrowth_y` 被屏蔽。若 `sd_overgrowth_y = -1`，分别采用上/下层独立值。 |
| `sd_overgrowth_z_up` | 全局 S/D 外延相对 channel 组上边界向上的扩展量。 | S/D cuboid 的 `z_max` 计算。 | 若 `sd_overgrowth_z_up != -1`，上下层均采用该值，`sd_upper_overgrowth_z_up` 和 `sd_lower_overgrowth_z_up` 被屏蔽。若为 `-1`，采用独立值。 |
| `sd_overgrowth_z_down` | 全局 S/D 外延相对 channel 组下边界向下的扩展量。 | S/D cuboid 的 `z_min` 计算。 | 若 `sd_overgrowth_z_down != -1`，上下层均采用该值，`sd_upper_overgrowth_z_down` 和 `sd_lower_overgrowth_z_down` 被屏蔽。若为 `-1`，采用独立值。 |
| `sd_upper_overgrowth_y` | 上层 S/D 外延 y 方向扩展量。 | 上层 S/D `y1/y2`。 | 仅在 `sd_overgrowth_y = -1` 时生效。 |
| `sd_lower_overgrowth_y` | 下层 S/D 外延 y 方向扩展量。 | 下层 S/D `y1/y2`。 | 仅在 `sd_overgrowth_y = -1` 时生效。 |
| `sd_upper_overgrowth_z_up` | 上层 S/D 外延向上扩展量。 | 上层 S/D `z_max`。 | 仅在 `sd_overgrowth_z_up = -1` 时生效。 |
| `sd_upper_overgrowth_z_down` | 上层 S/D 外延向下扩展量。 | 上层 S/D `z_min`。 | 仅在 `sd_overgrowth_z_down = -1` 时生效。 |
| `sd_lower_overgrowth_z_up` | 下层 S/D 外延向上扩展量。 | 下层 S/D `z_max`。 | 仅在 `sd_overgrowth_z_up = -1` 时生效。 |
| `sd_lower_overgrowth_z_down` | 下层 S/D 外延向下扩展量。 | 下层 S/D `z_min`。 | 仅在 `sd_overgrowth_z_down = -1` 时生效。 |

### 7. Doping 掺杂参数

| 参数 | 物理/几何意义 | 被什么过程参考 | 采用/屏蔽规则 |
| --- | --- | --- | --- |
| `doping_enable` | 掺杂生成总开关。 | `add_doping()`。 | 为 `true` 时生成上层 S/D、下层 S/D 掺杂；为 `false` 时整个 doping 流程跳过，下面所有 doping 参数被屏蔽。衬底不进行掺杂。 |
| `sd_upper_doping_species` | 上层 N 型 S/D 外延掺杂物种，默认使用 `ArsenicActiveConcentration`。 | `SD_Upper_Doping` constant profile。 | 仅在 `doping_enable = true` 时生效。 |
| `sd_upper_doping_concentration` | 上层 N 型 S/D 外延掺杂浓度，默认使用 `8e19`。 | `SD_Upper_Left` 与 `SD_Upper_Right` 区域。 | 仅在 `doping_enable = true` 时生效。 |
| `sd_lower_doping_species` | 下层 S/D 外延掺杂物种。 | `SD_Lower_Doping` constant profile。 | 仅在 `doping_enable = true` 时生效。 |
| `sd_lower_doping_concentration` | 下层 P 型 S/D 外延掺杂浓度，默认使用 `8e19`。 | `SD_Lower_Left` 与 `SD_Lower_Right` 区域。 | 仅在 `doping_enable = true` 时生效。 |
| `channel_doping_enable` | 沟道轻掺杂开关。 | `add_doping()` 中的 channel profile placement。 | 仅在 `doping_enable = true` 且 `channel_doping_enable = true` 时生成；为 `false` 时 `channel_doping_species` 和 `channel_doping_concentration` 被屏蔽。 |
| `channel_doping_species` | 沟道掺杂物种。 | `Channel_Doping` constant profile。 | 仅在 `doping_enable = true` 且 `channel_doping_enable = true` 时生效。 |
| `channel_doping_concentration` | 沟道掺杂浓度。 | 所有 `ChannelLower`/`ChannelUpper` 区域。 | 仅在 `doping_enable = true` 且 `channel_doping_enable = true` 时生效。 |

### 8. Meshing 网格参数

| 参数 | 物理/几何意义 | 被什么过程参考 | 采用/屏蔽规则 |
| --- | --- | --- | --- |
| `meshing_enable` | 网格生成总开关。 | `add_meshing()`。 | 为 `true` 时写入 refinement 和 `sde:build-mesh` 命令；为 `false` 时整个 meshing 流程跳过，下面所有 meshing 参数被屏蔽。 |
| `global_mesh_max_x` | 全局网格 x 方向最大尺寸。 | `Global_Mesh_Size`。 | 仅在 `meshing_enable = true` 时生效。 |
| `global_mesh_max_y` | 全局网格 y 方向最大尺寸。 | `Global_Mesh_Size`。 | 仅在 `meshing_enable = true` 时生效。 |
| `global_mesh_max_z` | 全局网格 z 方向最大尺寸。 | `Global_Mesh_Size`。 | 仅在 `meshing_enable = true` 时生效。 |
| `global_mesh_min_x` | 全局网格 x 方向最小尺寸。 | `Global_Mesh_Size`。 | 仅在 `meshing_enable = true` 时生效。 |
| `global_mesh_min_y` | 全局网格 y 方向最小尺寸。 | `Global_Mesh_Size`。 | 仅在 `meshing_enable = true` 时生效。 |
| `global_mesh_min_z` | 全局网格 z 方向最小尺寸。 | `Global_Mesh_Size`。 | 仅在 `meshing_enable = true` 时生效。 |
| `core_mesh_window_z_min` | 核心细网格窗口的 z 方向下边界。 | `Core_Win` ref/eval window。 | 仅在 `meshing_enable = true` 时生效；x/y 边界仍由 boundary layout 决定。 |
| `core_mesh_window_z_max` | 核心细网格窗口的 z 方向上边界。 | `Core_Win` ref/eval window。 | 仅在 `meshing_enable = true` 时生效。 |
| `core_mesh_max_x` | 核心区网格 x 方向最大尺寸。 | `Core_Mesh_Size`。 | 仅在 `meshing_enable = true` 时生效。 |
| `core_mesh_max_y` | 核心区网格 y 方向最大尺寸。 | `Core_Mesh_Size`。 | 仅在 `meshing_enable = true` 时生效。 |
| `core_mesh_max_z` | 核心区网格 z 方向最大尺寸。 | `Core_Mesh_Size`。 | 仅在 `meshing_enable = true` 时生效。 |
| `core_mesh_min_x` | 核心区网格 x 方向最小尺寸。 | `Core_Mesh_Size`。 | 仅在 `meshing_enable = true` 时生效。 |
| `core_mesh_min_y` | 核心区网格 y 方向最小尺寸。 | `Core_Mesh_Size`。 | 仅在 `meshing_enable = true` 时生效。 |
| `core_mesh_min_z` | 核心区网格 z 方向最小尺寸。 | `Core_Mesh_Size`。 | 仅在 `meshing_enable = true` 时生效。 |
| `mesh_engine` | SDE 调用的网格生成后端，例如 `snmesh`。 | `sde:build-mesh` 第一个参数。 | 仅在 `meshing_enable = true` 时生效。 |
| `mesh_options` | 网格生成选项，例如 `-a -c boxmethod`。 | `sde:build-mesh` 第二个参数。 | 仅在 `meshing_enable = true` 时生效。 |
| `mesh_output_name` | 网格输出名称；最终生成结构应使用 `n@node@_` 作为前缀，例如 `n@node@_cfet_structure`。 | `sde:build-mesh` 第三个参数。 | 仅在 `meshing_enable = true` 时生效。 |

## 结构搭建过程中的参数引用顺序

1. 读取 layout、`layer_rule_1.txt`、`cfet_arch.txt`。
2. 对启用层检查 `end_z2 - start_z1 == height`。不满足时终止生成。
3. 处理衬底/背部参考：
   - x/y 范围始终来自 layout 1 号层。
   - 若不存在背部互连，生成 `Substrate_1`，z 范围来自 layer rule 1 号层的 `start_z1/end_z2`，材料固定为 `Silicon`。
   - 若存在背部互连，跳过 `Substrate_1`；背部互连层由各自 layer rule 的 `start_z1/end_z2` 决定，并从下层晶体管下方即 `z = 0` 以下开始堆叠。
4. 生成 gate：
   - common gate：若 7 号 layout 和启用的 7 号 layer rule 同时存在，生成 `Gate_Common`。
   - x/y 范围来自 layout 7 号层。
   - z 范围来自 layer rule 7 号层的 `start_z1/end_z2`。
   - 材料来自 layer rule 7 号层的 `material`。
   - split gate：指南定义为 8/9/10 号层组合，但当前 `gen_sde.py` 尚未实现。
5. 生成下层 channel：
   - 数量由 `num_channel` 或 `num_channel_lower` 决定。
   - x/y 中心由 `channel_center_x/y` 决定。
   - x 尺寸由 `channel_length` 或 `channel_lower_length` 决定。
   - y 尺寸由 `channel_width` 或 `channel_lower_width` 决定。
   - z 堆叠由 `channel_mdi_thickness` 和 `channel_thickness` 决定。
6. 跳过上下层之间的间隔：
   - 先增加一次 `channel_mdi_thickness`，再增加 `mdi_thickness`。
   - 这两个间隔当前不生成独立实体。
7. 生成上层 channel：
   - 数量由 `num_channel` 或 `num_channel_upeer` 决定。
   - 尺寸由全局 channel 参数或 upper 独立参数决定。
8. 生成 High-k：
   - High-k 是紧贴 gate 外表面的红色薄层。
   - x 方向的 High-k 左/右薄层分别贴在 `gate_x1` 和 `gate_x2` 外侧，厚度为 `high_k_thickness`。
   - High-k 不包覆 channel。
9. 生成 inner spacer：
    - inner spacer 是棕黄色区域。
    - 它与左右 channel 小块处在同一侧向 slab 中：channel 小块占据每层窗口，inner spacer 填充窗口之外的 y/z 间隔。
    - 它用于隔开 gate/High-k 与 S/D，但不阻断 S/D 与 channel 的接触。
10. 生成 S/D 外延：
    - x 外边界来自 boundary layout 的左右边界。
    - x 内边界直接与左右 channel 小块的外端面接触。
    - y/z 扩展量由全局 `sd_overgrowth_*` 或上/下层独立 `sd_upper_*`、`sd_lower_*` 决定。
11. 添加 contact、doping 和 meshing：
    - 同类 region 可做 boolean unite。
    - 金属材料 region 添加 contact。
    - 当 `doping_enable = true` 时，根据 `sd_upper_doping_*`、`sd_lower_doping_*` 和可选的 `channel_doping_*` 生成掺杂 profile；衬底不进行掺杂。
    - 当 `meshing_enable = true` 时，根据 `global_mesh_*`、`core_mesh_*`、`mesh_engine`、`mesh_options` 和 `mesh_output_name` 生成网格设置。

## 当前已出现但未被当前生成脚本采用的参数

以下参数存在于规则文件中，但当前 `gen_sde.py`/`gen_arch.py` 不会实际改变结构：

- `arrangement`
- `cell_height`
- `cpp`
- `gate_spacer_thickness`
- `gate_width`
- `gate_upper_length`
- `gate_lower_length`
- `gate_upper_width`
- `gate_lower_width`
- `layer_name`
- `boundary`
- `ILD`

这些参数可以作为后续扩展入口。例如：用 `arrangement` 控制上下层 channel 的 x/y 对齐方式；用 `cell_height/cpp` 校验 layout；用 `gate_upper_*` 和 `gate_lower_*` 支持 split gate 或 `gate_length = -1` 时的上下层独立 gate 尺寸；用 `ILD` 自动生成介质背景。
