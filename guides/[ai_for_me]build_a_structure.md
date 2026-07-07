# Current Structure-Building Logic

本文档用较高层次解释当前 `gen_sde.py` 的工作方式，便于人工检查生成结构是否合理。

## 总体目标

`gen_sde.py` 将三类输入转换为 Sentaurus SDE command 文件：

```text
gds/test1_gds.txt
rules/layer_rule_1.txt
rules/cfet_arch.txt
```

输出：

```text
gen_sde.cmd
```

生成结果包括：

- 几何实体
- 金属 contact
- S/D doping
- mesh refinement
- `sde:build-mesh`

## 三类输入的角色

`gds/test1_gds.txt` 提供二维版图边界，尤其是：

- 1 号 layer：器件 boundary / substrate 外包络
- 7 号 layer：common gate

`layer_rule_1.txt` 提供三维层规则：

- `enable`
- `height`
- `start_z1`
- `end_z2`
- `material`

所有启用层必须满足：

```text
end_z2 - start_z1 == height
```

`cfet_arch.txt` 提供内部结构参数：

- channel 数量、尺寸与堆叠间隔
- High-k 厚度
- inner spacer 相关厚度
- S/D 外延扩展
- S/D doping
- mesh 设置

## 当前结构识别

当前结构关系以图示为准：

- 白色：`Gate`
- 红色薄层：`High-k`
- 青绿色小块：`Channel`
- 棕黄色区域：`Inner_spacer`
- 外侧区域：`S/D epi`

这意味着：

```text
S/D
  |
Channel 小块 + Inner_spacer 间隔
  |
High-k 薄层
  |
Gate 核心
  |
High-k 薄层
  |
Channel 小块 + Inner_spacer 间隔
  |
S/D
```

更具体地说：

- `Gate` 的几何边界来自 layout gate 层。
- `High-k` 紧贴 gate 外表面，而不是包覆 channel。
- `Channel` 不贯穿整个 gate，而是在 gate 左右两侧生成局部小块。
- `Inner_spacer` 与 channel 位于同一侧向 slab；channel 占窗口，inner spacer 填充窗口以外的 y/z 间隔。
- `S/D` 必须接触 channel 的外端面。

## 生成流程

### 1. 解析和校验

脚本读取 layout、layer rule 和 arch 参数。

若启用层的 z 高度不一致，立即停止生成，避免产生无效结构。

### 2. 生成衬底

`Substrate_1` 来自 1 号 layout 的 x/y 范围，以及 1 号 layer rule 的 z 范围。

### 3. 生成 Gate

若 7 号 layer 存在并启用，生成 `Gate_Common`。

如果 common gate 不可用，可使用 8/9/10 号 layer 扩展 split gate。

### 4. 生成 Channel

根据 `num_channel` 或 upper/lower 独立数量，生成上下层 channel。

每层生成左右两个 channel 小块，例如：

```text
ChannelLower_0_L
ChannelLower_0_R
ChannelUpper_1_L
ChannelUpper_1_R
```

左右小块的内边界由 gate 边界和 `high_k_thickness` 决定。

### 5. 生成 High-k

High-k 使用四个薄层表示：

```text
HighK_Gate_Left
HighK_Gate_Right
HighK_Gate_Front
HighK_Gate_Back
```

这些薄层直接贴 gate 外表面。

### 6. 生成 Inner Spacer

Inner spacer 是带 channel 窗口的隔离填充。

脚本通过几何切分生成：

- y 方向窗口之外的 `YMin/YMax`
- z 方向 channel 间隔处的 `ZGap_*`

这样可避免 inner spacer 与 channel 重叠。

### 7. 生成 S/D

上层和下层 S/D 分开生成：

```text
SD_Upper_Left
SD_Upper_Right
SD_Lower_Left
SD_Lower_Right
```

S/D 的 x 内边界直接接触左右 channel 小块的外端面。

### 8. 添加 Contact

脚本会对金属材料 region 添加 top/bottom contact。

当前使用：

```scheme
(sdegeo:set-contact (find-face-id (position ...)) "ContactName")
```

### 9. 添加 Doping

衬底不进行 doping。

默认 S/D doping：

```text
Upper S/D: ArsenicActiveConcentration = 8e19
Lower S/D: BoronActiveConcentration = 8e19
```

### 10. 添加 Mesh

脚本先定义窗口，再放置 refinement：

```text
Global_Win -> Global_Mesh_Size
Core_Win   -> Core_Mesh_Size
```

最终 mesh 输出名带有 `n@node@_` 前缀。

## 检查生成结果

运行：

```powershell
python gen_sde.py
```

生成后可检查 `gen_sde.cmd`：

- 不应出现 `HighK_Channel`。
- 应出现 `HighK_Gate_Left/Right/Front/Back`。
- 应出现左右 channel 小块。
- 不应出现 `Substrate_Doping`。
- `sde:build-mesh` 输出名应以 `n@node@_` 开头。
