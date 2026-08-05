# Prompt Guide for Maintaining `gen_sde.py`

当需要让 AI 或开发者修改 SDE 生成逻辑时，应以当前文件为约束提示。

## 目标

根据以下输入生成可在 Sentaurus Structure Editor 中执行的 `gen_sde.cmd`：

```text
gds/test1_gds.txt
rules/cfet_arch.txt
rules/layer_rule_1.txt
guides/[guide1]structure_parameters.md
guides/[guide2]build_structure_with_parameters.md
```

生成器入口为：

```text
gen_sde.py
```

默认输出为：

```text
gen_sde.cmd
```

## 必须遵守的结构理解

当前结构关系如下：

- `Gate` 是白色核心结构，common gate 来自 layout 7 号层。
- `High-k` 是红色薄层，紧贴并包覆 `Gate` 外表面。
- `Channel` 是青绿色小块，位于 gate 左右两侧；每层 channel 拆分为 `*_L` 和 `*_R`。
- `Inner_spacer` 是棕黄色隔离区域，与 channel 位于同一侧向 slab；channel 占据窗口，inner spacer 填充窗口之外的 y/z 间隔。
- `S/D` 必须与左右 channel 小块的外端面接触。

不要把 High-k 生成为包覆 channel 的壳层；不要把 channel 生成为贯穿 gate 的完整长条。

## 必须遵守的生成规则

1. 先解析 layout、arch 和 layer rule。
2. 对所有 `enable = true` 的 layer rule 校验：

```text
end_z2 - start_z1 == height
```

3. 若 7 号 layer 存在并启用，生成 common gate。
4. 若 7 号 layer 不存在，且 8/9/10 号 layer 均存在并启用，生成 split gate。
5. 按 `num_channel` 或 `num_channel_lower/num_channel_upeer` 决定上下层 channel 数量。
6. 按 `channel_length/channel_width/channel_thickness` 及其 upper/lower 覆盖参数生成左右 channel 小块。
7. High-k 只贴 gate 外表面，厚度为 `high_k_thickness`。
8. Inner spacer 使用 `inner_spacer_thickness` 表示隔离 slab 的物理意义，但具体 x 范围应与左右 channel 小块所在 slab 对齐，并在 y/z 中避开 channel 窗口。
9. S/D 外延的 y/z 外扩由 `sd_overgrowth_*` 或 upper/lower 独立参数决定，x 方向必须接触 channel 外端面。
10. 衬底不进行 doping。
11. S/D doping 默认：

```text
sd_upper_doping_species = ArsenicActiveConcentration
sd_upper_doping_concentration = 8e19
sd_lower_doping_species = BoronActiveConcentration
sd_lower_doping_concentration = 8e19
```

12. Mesh 输出名必须使用 `n@node@_` 前缀，例如 `n@node@_cfet_structure`。

## 修改后的检查项

修改 `gen_sde.py` 后，必须运行：

```powershell
python gen_sde.py
```

并检查生成的 `gen_sde.cmd`：

- 不应包含 `HighK_Channel*`。
- 应包含 `HighK_Gate_Left/Right/Front/Back`。
- 应包含 `ChannelLower_*_L/R` 和 `ChannelUpper_*_L/R`。
- 不应包含 `Substrate_Doping`。
- 最后一条 `sde:build-mesh` 输出名应以 `n@node@_` 开头。
