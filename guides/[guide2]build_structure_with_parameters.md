# Build Structure with Parameters

本文档描述如何从 layout、`layer_rule_1.txt` 和 `cfet_arch.txt` 出发，从头搭建 CFET 三维结构。凡是结构量由 `[guide1]structure_parameters.md` 定义，流程中直接引用 guide1 的变量名。

## 1. 输入文件

结构搭建需要三类输入：

- layout 文件：提供各版图层的二维 `x1/y1/x2/y2/layer_num`。
- `rules/layer_rule_1.txt`：提供每个 `layer_num` 的 `enable`、`height`、`start_z1`、`end_z2`、`material` 等三维层规则。
- `rules/cfet_arch.txt`：提供 channel、gate、spacer、S/D、doping、meshing 等结构参数。

在正式生成前，应先解析全部输入，并建立两个索引：

- 以 `layer_num` 为键的 layout 字典。
- 以 `layer_num` 为键的 layer rule 字典。

`cfet_arch.txt` 中的值允许为数值、布尔值和字符串。数值用于几何尺寸和浓度，布尔值用于开关，字符串用于材料名、掺杂物种、mesh engine 和 mesh options。

## 2. 坐标与层校验

坐标方向遵守 guide1：

- `x`：Source-Gate-Drain 方向。
- `y`：栅宽方向/沟道宽度方向。
- `z`：垂直堆叠方向。

对所有 `enable = true` 的 layer rule，必须先检查：

```text
end_z2 - start_z1 == height
```

若不满足，应立即报错并停止后续生成。错误信息应指出对应的 `layer_num`、该行规则内容，以及 `height/start_z1/end_z2` 的不匹配关系。

`enable = false` 的层不参与当前 SDE 结构生成；即使 layout 中存在同名层，也应被屏蔽。

## 3. 处理衬底与背部互连参考

1 号 layer `boundary` 始终决定器件的 x/y 有效边界，但不一定生成实体衬底。

生成条件：

- layout 中存在 `layer_num = 1`。
- `layer_rule_1.txt` 中 `layer_num = 1` 且 `enable = true`。

无背部互连时，生成 `Substrate_1`：

- `x1/x2/y1/y2` 来自 layout 1 号层。
- `z1 = start_z1`。
- `z2 = end_z2`。
- 当前实现中衬底材料固定为 `Silicon`。
- 若后续需要由规则驱动，可改为使用 1 号层的 `material`。

存在背部互连时，不生成 `Substrate_1`。判定条件包括：

- `bm0_mode != none`。
- 或启用了 52/53/54 等背部互连 layer，并且 layout 中存在对应矩形。

此时 BVMD/BM0/BV0 等背部互连层应使用各自 layer rule 的 `start_z1/end_z2`，从下层晶体管下方的 `z = 0` 以下开始堆叠，而不是从衬底下方开始。典型设置为：

```text
52 BVMD ... -0.030  0.000
53 BM0  ... -0.060 -0.030
54 BV0  ... -0.090 -0.060
```

## 4. 生成 Gate

### Common Gate

若 layout 中存在 7 号层，且 layer rule 中 7 号层 `enable = true`，则生成 common gate。

几何范围：

- `x1/x2/y1/y2` 来自 layout 7 号层。
- `z1 = start_z1`。
- `z2 = end_z2`。

材料：

- 使用 7 号层的 `material`。

注意：实际 gate 实体的 x/y/z 范围由 layout 7 号层和 layer rule 7 号层决定。图示关系中 gate 是白色核心区域。

### Split Gate

若 7 号层不存在，且 8、9、10 号层均存在并启用，可按 split gate 逻辑生成：

- `gate_upper` 对应 8 号层。
- `gate_lower` 对应 9 号层。
- `gate_merge` 对应 10 号层。

每个部分的 `x/y` 范围来自对应 layout 层，`z` 范围来自对应 layer rule 的 `start_z1/end_z2`，材料来自对应 layer rule 的 `material`。

当前 `gen_sde.py` 对 split gate 只保留扩展入口，完整生成逻辑需要继续实现。

## 5. 决定 Channel 数量

先读取 `num_channel`：

- 若 `num_channel != -1`，上层和下层均采用 `num_channel`。
- 若 `num_channel = -1`，下层采用 `num_channel_lower`，上层采用 `num_channel_upeer`。

注意：`num_channel_upeer` 保持当前 rules 文件中的拼写。

## 6. 决定 Channel 尺寸

channel 的中心位置：

- `channel_center_x`
- `channel_center_y`

channel 的 z 向厚度：

- `channel_thickness`

下层 channel 的 x 向长度：

- 若 `channel_length != -1`，采用 `channel_length`。
- 若 `channel_length = -1`，采用 `channel_lower_length`。

上层 channel 的 x 向长度：

- 若 `channel_length != -1`，采用 `channel_length`。
- 若 `channel_length = -1`，采用 `channel_upper_length`。

下层 channel 的 y 向宽度：

- 若 `channel_width != -1`，采用 `channel_width`。
- 若 `channel_width = -1`，采用 `channel_lower_width`。

上层 channel 的 y 向宽度：

- 若 `channel_width != -1`，采用 `channel_width`。
- 若 `channel_width = -1`，采用 `channel_upper_width`。

`channel_length` 定义左右 channel 小块的总外包络。中间由 gate 和 High-k 占据，实际 channel 拆成左右两个青绿色小块。

先计算 channel 总外包络：

```text
channel_outer_x1 = channel_center_x - channel_length_selected / 2
channel_outer_x2 = channel_center_x + channel_length_selected / 2
channel_y1 = channel_center_y - channel_width_selected / 2
channel_y2 = channel_center_y + channel_width_selected / 2
```

再按 gate 和 High-k 位置拆分左右小块：

```text
left_channel_x1 = channel_outer_x1
left_channel_x2 = gate_x1 - high_k_thickness
right_channel_x1 = gate_x2 + high_k_thickness
right_channel_x2 = channel_outer_x2
```

## 7. 生成下层 Channel 堆叠

从衬底顶部 `z = 0` 开始堆叠。

对每一条下层 channel：

1. 当前 z 坐标先增加 `channel_mdi_thickness`。
2. channel 下边界为当前 z。
3. channel 上边界为当前 z 加 `channel_thickness`。
4. 生成 `ChannelLower_i_L` 和 `ChannelLower_i_R` 两个左右 channel 小块。
5. 当前 z 坐标增加 `channel_thickness`。

`channel_mdi_thickness` 是 spacing 参数，本身不生成实体。

## 8. 生成上下层间隔

下层 channel 全部生成后：

1. 当前 z 坐标增加一次 `channel_mdi_thickness`。
2. 当前 z 坐标再增加 `mdi_thickness`。

`mdi_thickness` 表示上下器件之间的介质隔离厚度，当前流程中只改变上层 channel 的 z 位置，不生成独立 MDI 实体。

## 9. 生成上层 Channel 堆叠

上层 channel 的堆叠方式与下层相同，只是数量和尺寸使用上层选择结果。

对每一条上层 channel：

1. 当前 z 坐标增加 `channel_mdi_thickness`。
2. channel 下边界为当前 z。
3. channel 上边界为当前 z 加 `channel_thickness`。
4. 生成 `ChannelUpper_i_L` 和 `ChannelUpper_i_R` 两个左右 channel 小块。
5. 当前 z 坐标增加 `channel_thickness`。

## 10. 生成 High-k

High-k 是紧贴 gate 外表面的红色薄层，不包覆 channel。

厚度：

- `high_k_thickness`

x 向薄层：

```text
left_high_k_x1 = gate_x1 - high_k_thickness
left_high_k_x2 = gate_x1
right_high_k_x1 = gate_x2
right_high_k_x2 = gate_x2 + high_k_thickness
```

y 向薄层可贴在 gate 的前后表面：

```text
front_high_k_y1 = gate_y1 - high_k_thickness
front_high_k_y2 = gate_y1
back_high_k_y1 = gate_y2
back_high_k_y2 = gate_y2 + high_k_thickness
```

材料使用 `HfO2`。

## 11. 生成 Inner Spacer

Inner spacer 是图中的棕黄色区域。它不是贴在裸 gate 上，也不是一整块无孔竖墙；它与左右 channel 小块处在同一侧向 slab 中，channel 小块占据窗口，inner spacer 填充窗口之外的间隔区域。

几何逻辑：

- 左侧 inner spacer 的 x 范围与左侧 channel 小块一致：`left_channel_x1` 到 `left_channel_x2`。
- 右侧 inner spacer 的 x 范围与右侧 channel 小块一致：`right_channel_x1` 到 `right_channel_x2`。
- 其 z 向应覆盖 gate 的有效高度范围。
- 与 channel 重叠的位置应被 channel 窗口打断，避免实体互相穿插。

因此在每个 channel 的 y/z 窗口中生成青绿色 channel；在窗口之外的 y/z 间隔中生成棕黄色 inner spacer。

## 12. 生成 S/D 外延

S/D 外延分为四个区域：

- `SD_Lower_Left`
- `SD_Lower_Right`
- `SD_Upper_Left`
- `SD_Upper_Right`

x 向外边界来自 1 号 boundary layout：

- 左侧外边界为 boundary `x1`。
- 右侧外边界为 boundary `x2`。

x 向内边界必须与 channel 接触：

```text
lower_left_x2 = lower_left_channel_x1
lower_right_x1 = lower_right_channel_x2
upper_left_x2 = upper_left_channel_x1
upper_right_x1 = upper_right_channel_x2
```

y 向扩展：

- 若 `sd_overgrowth_y != -1`，上下层都使用 `sd_overgrowth_y`。
- 若 `sd_overgrowth_y = -1`，上层使用 `sd_upper_overgrowth_y`，下层使用 `sd_lower_overgrowth_y`。

z 向向上扩展：

- 若 `sd_overgrowth_z_up != -1`，上下层都使用 `sd_overgrowth_z_up`。
- 若 `sd_overgrowth_z_up = -1`，上层使用 `sd_upper_overgrowth_z_up`，下层使用 `sd_lower_overgrowth_z_up`。

z 向向下扩展：

- 若 `sd_overgrowth_z_down != -1`，上下层都使用 `sd_overgrowth_z_down`。
- 若 `sd_overgrowth_z_down = -1`，上层使用 `sd_upper_overgrowth_z_down`，下层使用 `sd_lower_overgrowth_z_down`。

对每一层 S/D：

```text
sd_y1 = channel_y1 - selected_sd_overgrowth_y
sd_y2 = channel_y2 + selected_sd_overgrowth_y
sd_z1 = first_channel_z1 - selected_sd_overgrowth_z_down
sd_z2 = last_channel_z2 + selected_sd_overgrowth_z_up
```

材料当前可按器件类型区分：

- 上层 S/D：`Silicon`
- 下层 S/D：`SiGe`

## 13. Boolean 合并

生成所有 cuboid 后，对同一结构组中相邻或同名区域进行 boolean unite。

典型组包括：

- `ChannelLower`
- `ChannelUpper`
- `HighK`
- `SD`
- `Gate`

合并后需要更新 region 名称映射，后续 doping、contact、mesh placement 应引用有效 region 名称。

## 14. 添加 Contact

对材料为金属的 region 添加 contact。

金属材料判定列表：

- `Tungsten`
- `Copper`
- `Metal`

每个金属 region 可在 z 向上表面和下表面分别定义 contact：

- top contact 位于 `z_max`。
- bottom contact 位于 `z_min`。

contact 的 x/y 位置可使用该金属 region 的中心点。

## 15. 添加 Doping

先读取 `doping_enable`：

- 若 `doping_enable = false`，跳过全部 doping。
- 若 `doping_enable = true`，继续生成以下 profile。

上层 S/D doping：

- 物种：`sd_upper_doping_species`
- 浓度：`sd_upper_doping_concentration`
- 作用区域：`SD_Upper_Left`、`SD_Upper_Right`

下层 S/D doping：

- 物种：`sd_lower_doping_species`
- 浓度：`sd_lower_doping_concentration`
- 作用区域：`SD_Lower_Left`、`SD_Lower_Right`

衬底不进行掺杂，不生成 `Substrate_Doping`。

沟道 doping：

- 若 `channel_doping_enable = false`，跳过沟道 doping。
- 若 `channel_doping_enable = true`，使用 `channel_doping_species` 和 `channel_doping_concentration` 作用于所有 `ChannelLower`/`ChannelUpper` 区域。

## 16. 添加 Meshing

先读取 `meshing_enable`：

- 若 `meshing_enable = false`，跳过全部 meshing。
- 若 `meshing_enable = true`，继续生成全局网格和核心区网格。

全局网格：

```text
Global_Mesh_Size:
global_mesh_max_x global_mesh_max_y global_mesh_max_z
global_mesh_min_x global_mesh_min_y global_mesh_min_z
```

全局网格 placement 作用于显式定义的 `Global_Win`，不要把 `(get-body-list)` 直接传给 `define-refinement-placement`。

核心区网格窗口：

- x/y 范围来自 1 号 boundary layout。
- z 下边界为 `core_mesh_window_z_min`。
- z 上边界为 `core_mesh_window_z_max`。

核心区网格：

```text
Core_Mesh_Size:
core_mesh_max_x core_mesh_max_y core_mesh_max_z
core_mesh_min_x core_mesh_min_y core_mesh_min_z
```

核心区网格 placement 作用于 `Core_Win`。

最后调用 mesh 引擎：

```text
sde:build-mesh mesh_engine mesh_options mesh_output_name
```

## 17. 输出

最终输出应包含：

- SDE 建模命令。
- 几何实体。
- boolean 合并命令。
- contact 定义。
- doping profile 和 placement。
- mesh refinement 和 build-mesh 命令。

生成顺序应保持为：

```text
parse inputs
validate enabled layer rules
build substrate only when backside interconnect is absent
build gate
build channels
build high-k
build inner spacer
build S/D epi
boolean unite
add contacts
add doping
add meshing
write output
```

这个顺序能保证后续步骤引用的 region 已经存在，也能让 doping 和 meshing 作用在最终的结构区域上。
