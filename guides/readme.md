# 使用 `gen_sde.py` 生成 SDE 文件

本文档说明如何使用 `AutoLDM/LD/gen_sde.py` 根据 layout、rules 和 guide1/guide2 中定义的参数流程生成 `gen_sde.cmd`。

## 1. 推荐运行方式

在终端进入 `AutoLDM/LD` 目录：

```powershell
cd C:\Users\Tengfei\Desktop\Project_DTCO\AutoLDM\LD
.\run_gen.bat
```

`run_gen.bat` 中先设置无后缀文件名，再自动拼出对应输入输出路径：

```bat
set "LAYOUT_NAME=test1"
set "ARCH_NAME=cfet"
set "LAYER_RULE_NAME=layer_rule_1"
set "OUTPUT_NAME=%LAYOUT_NAME%"
```

对应关系为：

```text
LAYOUT_NAME     -> gds/<LAYOUT_NAME>_gds.txt
ARCH_NAME       -> rules/<ARCH_NAME>_arch.txt
LAYER_RULE_NAME -> rules/<LAYER_RULE_NAME>.txt
OUTPUT_NAME     -> SDE/<OUTPUT_NAME>.cmd
```

默认情况下会读取：

```text
gds/test1_gds.txt
rules/cfet_arch.txt
rules/layer_rule_1.txt
```

并输出：

```text
SDE/test1.cmd
```

如果任一输入文件不存在，`run_gen.bat` 会在运行 Python 前给出明确的 `[ERROR]` 提示。若 `SDE` 输出文件夹不存在，bat 会自动创建。

可直接替换的示例组合：

```bat
rem Minimal common-gate CFET
set "LAYOUT_NAME=test1"
set "ARCH_NAME=cfet"
set "LAYER_RULE_NAME=layer_rule_1"

rem hDR dense BM0 example
set "LAYOUT_NAME=hdr_denseBM0"
set "ARCH_NAME=hdr_denseBM0"
set "LAYER_RULE_NAME=hdr_denseBM0_layer_rule"

rem hDR split-gate example
set "LAYOUT_NAME=hdr_split_gate"
set "ARCH_NAME=hdr_split_gate"
set "LAYER_RULE_NAME=hdr_split_gate_layer_rule"

rem sCFET example: split gate + dense BM0 + VMM
set "LAYOUT_NAME=scfet"
set "ARCH_NAME=scfet"
set "LAYER_RULE_NAME=scfet_layer_rule"
```

## 2. 直接运行 Python

也可以绕过 bat，直接运行 Python：

```powershell
python gen_sde.py
```

默认情况下，脚本会读取同样的默认文件并输出 `gen_sde.cmd`。若希望输出到 `SDE/<LAYOUT_NAME>.cmd`，请优先使用 `run_gen.bat`。

## 3. 自定义输入输出

`gen_sde.py` 支持按顺序传入 4 个可选参数：

```powershell
python gen_sde.py <layout_file> <arch_file> <layer_rule_file> <output_cmd_file>
```

例如：

```powershell
python gen_sde.py .\gds\test1_gds.txt .\rules\cfet_arch.txt .\rules\layer_rule_1.txt .\output\test1_sde.cmd
```

参数顺序固定为：

1. layout 文件
2. architecture 参数文件
3. layer rule 文件
4. 输出的 SDE command 文件

如果只传前面的部分参数，后面的路径会继续使用默认值。

## 4. 输入文件职责

`gds/test1_gds.txt` 提供二维版图矩形：

```text
x1 y1 x2 y2 layer_num
```

`rules/layer_rule_1.txt` 提供 layer 的三维规则：

```text
layer_num layer_name enable height start_z1 end_z2 material boundary ILD
```

`rules/cfet_arch.txt` 提供结构参数，包括：

- channel 数量、尺寸和堆叠间距
- gate、High-k、inner spacer 参数
- S/D 外延扩展参数
- doping 参数
- meshing 参数

这些参数的意义见：

```text
guides/[guide1]structure_parameters.md
```

完整搭建流程见：

```text
guides/[guide2]build_structure_with_parameters.md
```

论文结构解释与参数内涵见：

```text
guides/[guide3]paper_structure_explanation.md
```

## 5. 生成流程

运行脚本后，`gen_sde.py` 会按以下顺序生成结构：

1. 解析 layout、`cfet_arch.txt` 和 `layer_rule_1.txt`
2. 校验所有 `enable = true` 的 layer 是否满足 `end_z2 - start_z1 == height`
3. 无背部互连时生成 `Substrate_1`；存在 BM0/BVMD/BV0 等背部互连时跳过衬底
4. 生成 common gate 或 split gate
5. 生成上下层 channel
6. 生成 High-k 包覆层
7. 生成 inner spacer
8. 生成上下层 S/D 外延
9. 添加金属 contact
10. 根据 `doping_enable` 添加 doping
11. 根据 `meshing_enable` 添加 mesh refinement 和 `sde:build-mesh`
12. 写出 `.cmd` 文件

## 6. 常见设置

关闭 doping：

```text
doping_enable = false
```

开启 channel doping：

```text
channel_doping_enable = true
channel_doping_species = PhosphorusActiveConcentration
channel_doping_concentration = 1e15
```

默认 S/D doping：

```text
sd_upper_doping_species = ArsenicActiveConcentration
sd_upper_doping_concentration = 8e19
sd_lower_doping_species = BoronActiveConcentration
sd_lower_doping_concentration = 8e19
```

衬底不进行掺杂，生成文件中不会写入 `Substrate_Doping`。

关闭 meshing：

```text
meshing_enable = false
```

设置最终结构输出名前缀：

```text
mesh_output_name = n@node@_cfet_structure
```

让上下层 channel 数量独立：

```text
num_channel = -1
num_channel_upeer = 2
num_channel_lower = 2
```

让上下层 channel 尺寸独立：

```text
channel_length = -1
channel_upper_length = 0.026
channel_lower_length = 0.026

channel_width = -1
channel_upper_width = 0.021
channel_lower_width = 0.021
```

## 7. 常见报错

如果出现 layer 高度不匹配：

```text
Layer <n> z rule mismatch
```

需要检查 `rules/layer_rule_1.txt` 中对应行：

```text
end_z2 - start_z1 == height
```

如果出现缺少 layer：

```text
Missing enabled layer 1
Missing gate definition
```

需要检查：

- layout 文件中是否存在对应 `layer_num`
- `layer_rule_1.txt` 中对应 layer 是否为 `enable = true`
- common gate 需要启用 7 号层
- split gate 需要同时启用 8、9、10 号层

## 8. 输出文件

通过 `run_gen.bat` 生成的 `.cmd` 文件可在 Sentaurus SDE 环境中执行。默认输出为：

```text
AutoLDM/LD/SDE/test1.cmd
```

若使用自定义输出路径，则以命令行第 4 个参数为准。
