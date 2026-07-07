# SRAM DTCO SDE Model

本文档说明四种 6T CFET SRAM 的版图坐标、轨道约束、输入文件和生成流程。

## 1. 坐标约定

- `x`：Cell Height 和金属 track 方向。
- `y`：CPP 和沟道输运方向。
- `z`：CFET 上下器件堆叠方向。

SRAM 沿 `y` 方向使用 4 CPP。Gate 垂直于沟道：

- gate 沿 `x` 的最小延伸长度为 `29 nm`，同网络 gate 可以继续延长。
- gate 沿 `y` 的长度为 `14 nm`。
- gate 中线必须位于 `CPP/2 + n * CPP`。

版图图片为了与 SRAM 论文的阅读方向一致，会旋转 90 度显示：

- 图片横轴：CPP / transistor-column 方向。
- 图片纵轴：Cell Height / metal-track 方向。
- txt 和 SDE 内部坐标不旋转，避免改变三维结构定义。

## 2. 6T SRAM 拓扑优先规则

版图首先满足六管电路拓扑，之后才进行 track 分配：

```text
BL -- PG1 -- Q -- PU1/PD1  <cross-coupled>  PU2/PD2 -- QB -- PG2 -- BLB
       |                                                   |
       +---------------------- WL --------------------------+
```

横向晶体管列固定为：

```text
PG1 | PU1/PD1 | PU2/PD2 | PG2
```

- `PU1/PD1` 构成左反相器，输出为 `Q`，gate 接 `QB`。
- `PU2/PD2` 构成右反相器，输出为 `QB`，gate 接 `Q`。
- `PG1` 在 `WL` 控制下连接 `BL` 与 `Q`。
- `PG2` 在 `WL` 控制下连接 `BLB` 与 `QB`。
- CFET 的 PU/PD 可以在上下 tier 共用同一平面 footprint。
- Metal track 只能约束走线位置，不能改变上述晶体管邻接关系。

该排列参考 Abdi 等人的 6T CFET SRAM 拓扑和版图示意。论文也指出传统
6T CFET SRAM 的面积形式为 `6*MMP*(2*CPP)`，因此版图应采用横向
SRAM bitcell 视图，而不是窄长竖条。

## 3. 四种比较架构

参数参考 Yang 等人的 Double-Flip Sequential CFET 论文 Fig. 1 和 Table I。

| 架构 | CH / M0 track | Gate | BM0 pitch | VMM | 主要特点 |
| --- | --- | --- | --- | --- | --- |
| `sram_6t_mcfet_cg` | `62 nm / 3.5T` | common | 无背面 BM0 | 无 | 前侧承担电源与信号 |
| `sram_6t_hdr_denseBM0` | `62 nm / 3.5T` | common | `18 nm` | 无 | dense BM0 释放前侧信号资源 |
| `sram_6t_hdr_split_gate` | `62 nm / 3.5T` | split | `31 nm` | 无 | 上下器件 gate 独立 |
| `sram_6t_scfet` | `54 nm / 3T` | split | `18 nm` | 有 | split gate、dense BM0 和 VMM 组合 |

统一参数：

```text
CPP = 42 nm
CPP count = 4
M0 pitch/CD = 18/10 nm
```

`3.5T` 结构的 M0 中线为 `4 + n*18 nm`；`3T` sCFET 的 M0 中线为
`9 + n*18 nm`。边界处的半轨由 cell boundary 截断。

## 4. 版图数据源

版图坐标只保存在：

```text
gds/sram_6t_mcfet_cg_gds.txt
gds/sram_6t_hdr_denseBM0_gds.txt
gds/sram_6t_hdr_split_gate_gds.txt
gds/sram_6t_scfet_gds.txt
```

每行格式：

```text
x1 y1 x2 y2 layer_num label net
```

主要 layer：

| Layer | 含义 |
| ---: | --- |
| 1 | Cell boundary |
| 111 | Gate marker |
| 121 / 122 | NFET / PFET S/D |
| 17 / 18 | VMM / VMD |
| 19 / 20 / 21 | M0 / VM0 / M1 |
| 52 / 53 / 54 | BVMD / BM0 / BV0 |

`gen_sram_sde.py` 不保存 SRAM 互连平面坐标。它解释上述矩形，并从 layer rule
读取材料和 z 范围。NFET/PFET active 不再作为 101/102 版图层，而由 arch 中的
active width、左右器件列中心和 channel material 超参数在生成时派生。

## 5. 参数文件职责

`rules/sram_*_arch.txt` 保存：

- CPP、CPP 数和 Cell Height。
- M0/M1/BM0 pitch、CD、方向和 track origin。
- common/split gate 模式。
- channel、High-k、inner spacer、S/D、掺杂和网格参数。

`rules/sram_*_layer_rule.txt` 保存：

- layer 是否启用。
- layer 的 z 起止位置和厚度。
- 材料与 ILD。

## 6. 生成流程

运行：

```bat
run_sram_gen.bat
```

执行顺序：

1. `validate_sram_layout.py` 检查 boundary、CPP、gate CD、track、同层异网重叠和抽象 net 连通图。
2. `txt_to_gds.py` 从 GDS txt 生成同名 GDSII，并把 label/net 写为 GDS text。
3. `gen_sram_sde.py` 读取 GDS txt、arch 和 layer rule，生成 `SDE/*_sde.cmd`。
4. `draw_sram_layout.py` 从同一个 GDS txt 生成正面、背面和混合版图。

图像位于：

```text
layout_views/*_frontside.png
layout_views/*_backside.png
layout_views/*_mixed.png
layout_views/*_coordinates.csv
```

`.cmd` 需要在 Sentaurus Structure Editor 中执行，才会得到
`n@node@_*_sde.tdr`。
