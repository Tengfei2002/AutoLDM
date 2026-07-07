# AutoLDM 项目简介

AutoLDM 是一个面向 DTCO（Design-Technology Co-Optimization）流程的版图到器件结构自动生成项目。项目以二维版图文本、工艺/结构参数和层规则为输入，自动生成可在 Sentaurus SDE 中执行的 `.cmd` 结构建模脚本，用于快速构建 CFET、SRAM 等先进器件/电路单元的三维仿真结构。

项目当前的核心脚本为 `gen_sde.py`。该脚本会解析 GDS 转换得到的 layout txt 文件，结合 `rules` 目录中的架构参数与 layer rule，推导各层结构的空间位置、材料、接触、电极命名、掺杂与网格设置，并直接输出完整的 SDE command file。

## 主要功能

- 从版图矩形信息生成三维 SDE 几何结构。
- 支持基于规则文件定义 gate、channel、source/drain、metal、dielectric 等结构参数。
- 支持参数表达式解析，例如 `$var`、`@var@`、`@<a+b+0.1>@` 等形式。
- 根据版图中的 label/net 信息生成对应 metal contact，并保持命名可追踪。
- 支持 doping 与 mesh refinement 配置，便于后续 TCAD 仿真。
- 支持多组 SRAM 标准版图输入，用于验证不同 layout 版本下的泛化能力。

## 目录结构

```text
AutoLDM/
|-- gen_sde.py          # 核心生成脚本：layout/rules -> SDE .cmd
|-- gds/                # GDS 文件及其转换后的版图文本
|-- rules/              # 工艺架构参数与层规则文件
|-- output_SDE/         # 已生成的 SDE command 输出示例
|-- guides/             # 结构参数、建模流程和 SRAM/CFET 说明文档
`-- Hspice/             # HSPICE/寄生参数相关文件
```

## 输入与输出

典型输入包括：

- `gds/*.txt`：由版图提取得到的二维矩形信息，通常包含 `x1 y1 x2 y2 layer_num [label] [net]`。
- `rules/*_arch.txt`：器件结构、材料、掺杂、网格等硬参数。
- `rules/*_layer_rule.txt`：版图层到三维结构层的映射规则，包括高度、起止 z 坐标、材料、边界等。

典型输出为：

- `output_SDE/*.cmd`：可在 Sentaurus SDE 中执行的结构生成脚本。

## 基本运行方式

在项目根目录下运行：

```powershell
python gen_sde.py .\gds\standard_sram_v1_2.txt .\rules\standard_arch.txt .\rules\standard_layer_rule.txt -o .\output_SDE\standard_sram_v1_2_sde.cmd
```

命令格式为：

```powershell
python gen_sde.py <layout_txt> <arch_rule> <layer_rule> -o <output_cmd>
```

如果不指定 `-o/--output`，脚本会根据输入文件名生成默认输出路径。

## 适用场景

AutoLDM 适合用于先进器件结构的快速建模与规则验证，尤其适用于需要从 layout 自动生成 TCAD/SDE 几何结构的研究流程。通过将版图信息、结构参数和层规则分离，项目可以减少手工建模成本，并为不同 SRAM/CFET 版图版本之间的自动化结构生成和对比分析提供基础。
