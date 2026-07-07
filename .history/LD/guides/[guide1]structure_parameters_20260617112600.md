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
- `z` 方向：垂直堆叠方向，从衬底顶部 `z = 0` 开始向上堆叠沟道、MDI 和上层器件；衬底通常在 `z < 0`。

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

- `1 boundary`：衬底/器件有效边界。当前必须存在，提供衬底的 x/y 范围，并通过 `start_z1/end_z2` 提供衬底 z 范围。
- `7 gate`：common gate。若 layout 与规则中存在并启用 7 号层，则生成一个整体 gate。
- `8 gate_upper`、`9 gate_lower`、`10 gate_merge`：指南中定义为 split gate 的三个部分；当前 `gen_sde.py` 只保留了扩展入口，尚未实现实际生成。
- 其他金属/通孔层如 `M0`、`VM0`、`BM0` 等：当前规则表中已列出，但默认 `enable = false`，且当前核心生成流程未展开互连结构。

## `cfet_arch.txt` 结构参数

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
| `inner_spacer_thickness` | 内侧墙厚度，用于隔离 gate/high-k 与 S/D 外延。 | inner spacer 生成；S/D 的 x 边界计算。 | 始终生效。`gen_sde.py` 中 S/D 内边界为 channel 边界外侧再减/加 `inner_spacer_thickness + high_k_thickness`。 |
| `gate_spacer_thickness` | 栅极侧墙厚度，通常对应 gate 外侧 spacer。 | 当前生成脚本未实际读取。 | 目前被屏蔽；当前 inner spacer 使用 `inner_spacer_thickness`。 |
| `high_k_thickness` | High-k 栅介质厚度。 | High-k 包覆结构生成；S/D x 边界计算。 | 始终生效。High-k 在 channel 的 y/z 方向外扩该厚度；S/D 避开 high-k 厚度。 |
| `mdi_thickness` | 上下层器件之间的中间介质隔离厚度。 | 下层 channel 堆叠完成后，进入上层 channel 前增加 z 间距。 | 始终生效；它本身不生成实体，只改变上层 channel 的 z 位置。 |

### 4. Gate 尺寸

| 参数 | 物理/几何意义 | 被什么过程参考 | 采用/屏蔽规则 |
| --- | --- | --- | --- |
| `gate_length` | gate 在 x 方向的有效长度，当前主要用于 High-k 在 x 方向的生成范围。 | `gen_sde.py` 中 `hk_x1/hk_x2 = channel_center_x +/- gate_length/2`。 | 当前 High-k 生成采用该值；实际 gate cuboid 的 x/y/z 边界来自 layout 7 号层和 layer rule，不由该值决定。 |
| `gate_width` | gate 在 y 方向的宽度。按注释可用于推导 `channel_length = gate_width + 2*high_k_thickness + 2*inner_spacer_thickness`。 | 当前生成脚本未直接读取。 | 目前被屏蔽；若需要约束 channel/gate 关系，需要在上游规则生成或校验中实现。 |
| `gate_upper_length` | 上层 gate 长度。 | 当前生成脚本未实际读取。 | 目前被屏蔽；`gate_length = -1` 的分层 gate 尺寸逻辑尚未实现。 |
| `gate_lower_length` | 下层 gate 长度。 | 当前生成脚本未实际读取。 | 目前被屏蔽；同上。 |
| `gate_upper_width` | 上层 gate 宽度。 | 当前生成脚本未实际读取。 | 目前被屏蔽；同上。 |
| `gate_lower_width` | 下层 gate 宽度。 | 当前生成脚本未实际读取。 | 目前被屏蔽；同上。 |

### 5. Channel 尺寸与位置

| 参数 | 物理/几何意义 | 被什么过程参考 | 采用/屏蔽规则 |
| --- | --- | --- | --- |
| `channel_center_x` | 所有 channel 的 x 方向中心坐标。 | channel x 边界计算；High-k x 范围计算；S/D 左右边界计算。 | 始终生效。 |
| `channel_center_y` | 所有 channel 的 y 方向中心坐标。 | channel y 边界计算；High-k y 包覆；S/D y 外扩。 | 始终生效。 |
| `channel_width` | 全局 channel y 方向宽度。 | channel y 边界、High-k 包覆边界、S/D y 基准边界。 | 若 `channel_width != -1`，上下层均采用该值，`channel_upper_width` 和 `channel_lower_width` 被屏蔽。若 `channel_width = -1`，分别采用上/下层独立宽度。 |
| `channel_length` | 全局 channel x 方向长度。 | channel x 边界、S/D x 内边界。 | 若 `channel_length != -1`，上下层均采用该值，`channel_upper_length` 和 `channel_lower_length` 被屏蔽。若 `channel_length = -1`，分别采用上/下层独立长度。 |
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

## 结构搭建过程中的参数引用顺序

1. 读取 layout、`layer_rule_1.txt`、`cfet_arch.txt`。
2. 对启用层检查 `end_z2 - start_z1 == height`。不满足时终止生成。
3. 生成衬底：
   - x/y 范围来自 layout 1 号层。
   - z 范围来自 layer rule 1 号层的 `start_z1/end_z2`。
   - 当前材料固定为 `Silicon`。
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
   - z/y 方向包覆 channel，并按 `high_k_thickness` 外扩。
   - `gen_sde.py` 中 x 范围由 `channel_center_x +/- gate_length/2` 决定。
9. 生成 inner spacer：
   - 厚度由 `inner_spacer_thickness` 决定。
   - 位置位于 high-k 外侧，用于隔开 gate/high-k 和 S/D。
10. 生成 S/D 外延：
    - x 外边界来自 boundary layout 的左右边界。
    - x 内边界由 channel 边界、`inner_spacer_thickness`、`high_k_thickness` 决定。
    - y/z 扩展量由全局 `sd_overgrowth_*` 或上/下层独立 `sd_upper_*`、`sd_lower_*` 决定。\
11. doping 和 meshing 相关内容
12. 后处理：
    - 同类 region 可做 boolean unite。
    - 金属材料 region 添加 contact。
    - 当前 doping 和 meshing 参数写死在脚本中，不来自 `rules`。（这句删掉，在11中完成）

## 当前已出现但未被当前生成脚本采用的参数

以下参数存在于规则文件中，但当前 `gen_sde.py`/`gen_arch.py` 不会实际改变结构：

- `arrangement`
- `cell_height`
- `cpp`
- `gate_spacer_thickness`
- `gate_width`
- `gate_upper_length` 当gate_length = -1时启用，下面几项相同
- `gate_lower_length`
- `gate_upper_width`
- `gate_lower_width`
- `layer_name`
- `boundary`
- `ILD`

这些参数可以作为后续扩展入口。例如：用 `arrangement` 控制上下层 channel 的 x/y 对齐方式；用 `cell_height/cpp` 校验 layout；用 `gate_upper_*` 和 `gate_lower_*` 支持 split gate；用 `ILD` 自动生成介质背景。
