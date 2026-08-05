# How to Build the Structure

本文档面向实现者，说明 `gen_sde.py` 应如何根据参数搭建 SDE 结构。详细参数含义见 `[guide1]structure_parameters.md`，完整流程见 `[guide2]build_structure_with_parameters.md`。

## 输入

```text
layout:      gds/test1_gds.txt
arch:        rules/cfet_arch.txt
layer rule:  rules/layer_rule_1.txt
output:      gen_sde.cmd
```

layout 行格式：

```text
x1 y1 x2 y2 layer_num
```

layer rule 行格式：

```text
layer_num layer_name enable height start_z1 end_z2 material boundary ILD
```

arch 文件使用：

```text
parameter = value
```

值可以是数值、`true/false` 或字符串。

## 坐标方向

- `x`：Source-Gate-Drain 方向。
- `y`：gate width / channel width 方向。
- `z`：垂直堆叠方向。

## 预检查

对所有 `enable = true` 的 layer rule，必须先检查：

```text
end_z2 - start_z1 == height
```

若不满足，应停止生成并指出错误 layer 编号和原始规则行。

## 生成顺序

### 1. Substrate / Backside Reference

使用 layout 1 号层和 layer rule 1 号层作为整体 x/y 边界参考。

- x/y 来自 layout 1 号层。
- 无背部互连时，生成 `Substrate_1`；z 来自 1 号 layer rule 的 `start_z1/end_z2`，材料固定为 `Silicon`。
- 存在背部互连时，不生成 `Substrate_1`。背部互连层从下层晶体管下方开始，典型 z 范围为 BVMD `-0.030..0.000`、BM0 `-0.060..-0.030`、BV0 `-0.090..-0.060`。

### 2. Gate

Common gate：

- 若 7 号 layout 存在且 7 号 layer rule 启用，生成 `Gate_Common`。
- x/y 来自 layout 7 号层。
- z 来自 7 号 layer rule 的 `start_z1/end_z2`。
- material 来自 7 号 layer rule 的 `material`。

Split gate：

- 若 7 号层不可用，且 8/9/10 号层均存在并启用，则分别生成 `Gate_Upper`、`Gate_Lower`、`Gate_Merge`。

### 3. Channel

Channel 是图示中的青绿色小块，不是贯穿 gate 的完整长条。

数量：

- 若 `num_channel != -1`，上下层均采用 `num_channel`。
- 若 `num_channel = -1`，下层采用 `num_channel_lower`，上层采用 `num_channel_upeer`。

尺寸：

- x 总外包络由 `channel_length` 或 upper/lower 独立长度决定。
- y 宽度由 `channel_width` 或 upper/lower 独立宽度决定。
- z 厚度由 `channel_thickness` 决定。

每层 channel 拆成左右两个小块：

```text
left_channel_x1  = channel_center_x - selected_channel_length / 2
left_channel_x2  = gate_x1 - high_k_thickness
right_channel_x1 = gate_x2 + high_k_thickness
right_channel_x2 = channel_center_x + selected_channel_length / 2
```

命名示例：

```text
ChannelLower_0_L
ChannelLower_0_R
ChannelUpper_1_L
ChannelUpper_1_R
```

### 4. High-k

High-k 是图示中的红色薄层，紧贴并包覆 gate 外表面。

它不包覆 channel。

生成：

```text
HighK_Gate_Left
HighK_Gate_Right
HighK_Gate_Front
HighK_Gate_Back
```

厚度为 `high_k_thickness`。

### 5. Inner Spacer

Inner spacer 是图示中的棕黄色区域。

它与左右 channel 小块处在同一侧向 slab：

- channel 小块占据每层 y/z 窗口。
- inner spacer 填充窗口之外的 y/z 间隔。

因此 inner spacer 的 x 范围应与对应侧 channel slab 对齐，而不是贴裸 gate 侧壁。

### 6. S/D Epi

S/D 外延必须与 channel 外端面接触。

x 方向：

```text
left_sd_x1  = boundary_x1
left_sd_x2  = left_channel_x1
right_sd_x1 = right_channel_x2
right_sd_x2 = boundary_x2
```

y/z 外扩：

- `sd_overgrowth_y`
- `sd_overgrowth_z_up`
- `sd_overgrowth_z_down`

若全局参数为 `-1`，使用 upper/lower 独立参数。

### 7. Contacts

对金属 region 添加上下表面 contact。

当前金属材料集合：

```text
Tungsten
Copper
Metal
```

使用：

```scheme
(sdegeo:set-contact (find-face-id (position ...)) "ContactName")
```

不要使用会要求 BODY 的 `sdegeo:set-contact-boundary-faces`。

### 8. Doping

衬底不进行 doping。

若 `doping_enable = true`：

- `SD_Upper_Left/Right` 使用 `sd_upper_doping_species` 和 `sd_upper_doping_concentration`。
- `SD_Lower_Left/Right` 使用 `sd_lower_doping_species` 和 `sd_lower_doping_concentration`。

默认值：

```text
sd_upper_doping_species = ArsenicActiveConcentration
sd_upper_doping_concentration = 8e19
sd_lower_doping_species = BoronActiveConcentration
sd_lower_doping_concentration = 8e19
```

### 9. Meshing

`define-refinement-placement` 的第三个参数必须是 window 名称，不要传 `(get-body-list)`。

全局 mesh：

- 先定义 `Global_Win`。
- 再把 `Global_Mesh_Size` placement 到 `"Global_Win"`。

核心 mesh：

- 定义 `Core_Win`。
- 把 `Core_Mesh_Size` placement 到 `"Core_Win"`。

最终：

```scheme
(sde:build-mesh mesh_engine mesh_options mesh_output_name)
```

`mesh_output_name` 必须以 `n@node@_` 为前缀。
