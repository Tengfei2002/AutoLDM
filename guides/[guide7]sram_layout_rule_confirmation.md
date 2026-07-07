# CFET 6T SRAM 规则确认表

状态：**允许继续参数化结构与版图预检查，但不得声明 LVS/完整 DRC 通过。**

本文是四套 SRAM 输入的当前权威规则。坐标、器件拓扑、层定义和待确认项均以本文及
`rules/sram_*`、`gds/sram_*` 为准。

## 1. 坐标与单元边界

| 参数 | 当前值 | 角色 | 来源 |
| --- | ---: | --- | --- |
| `ch` | 108 nm | x 方向单元高度，决定性超参数 | USER |
| `cpp` | 42 nm | y 方向接触栅极节距，决定性超参数 | PARAM/PAPER |
| `cpp_count_y` | 2 | 单元 y 尺寸包含 2 CPP | ABDI |
| `mmp` | 18 nm | 当前 SRAM 金属节距假设 | USER |
| `sram_mmp_count_x` | 6 | x 尺寸包含 6 MMP | ABDI |

必须满足：

```text
x = CH/MMP direction
y = CPP/channel-transport direction
z = CFET vertical stack
cell x size = ch = mmp * sram_mmp_count_x = 108 nm
cell y size = cpp * cpp_count_y = 84 nm
```

`cell_width` 和 `cell_height` 仅保留为兼容别名，不再参与尺寸推导。

## 2. SRAM 拓扑

| Device | Type | Tier | Gate | Terminal A | Terminal B |
| --- | --- | --- | --- | --- | --- |
| PG1 | NMOS | upper | WL | BL | Q |
| PD1 | NMOS | upper | QB | Q | VSS |
| PU1 | PMOS | lower | QB | Q | VDD |
| PD2 | NMOS | upper | Q | VSS | QB |
| PG2 | NMOS | upper | WL | QB | BLB |
| PU2 | PMOS | lower | Q | VDD | QB |

上层共享扩散链：

```text
BL / PG1(WL) / Q / PD1(QB) / VSS
VSS / PD2(Q) / QB / PG2(WL) / BLB
```

下层功能 PFET 岛：

```text
Q / PU1(QB) / VDD
VDD / PU2(Q) / QB
```

不存在下层 PG active 的位置直接不生成 active；不再使用 cut 图层或 SDE 布尔切割。

## 3. 四种结构

| Architecture | Upper | Lower | Gate | BM0 | VMM |
| --- | --- | --- | --- | ---: | --- |
| mCFET common gate | NFET | PFET | common | 31 nm | no |
| hDR dense BM0 | NFET | PFET | common | 18 nm | no |
| hDR split gate | NFET | PFET | split | 31 nm | no |
| sCFET | NFET | PFET | split | 18 nm | yes |

mCFET 基准现已开启 `BVMD/BM0/BV0`，不再是 frontside-only 控制结构。

## 4. FEOL 尺寸主从关系

active 不再作为 GDS/TXT 图层。以下超参数在 `_arch.txt` 中直接定义器件几何：

```text
n_active_width / p_active_width
n_active_left_center_x / n_active_right_center_x
p_active_left_center_x / p_active_right_center_x
n_channel_material / p_channel_material
```

当前值为：

```text
NFET active width = 18 nm
PFET active width = 14 nm
left device-column center  = 18 nm
right device-column center = 90 nm
```

`channel_width`、上下层 channel width、gate span 和 EPI span 不再作为
独立强制输入。gate/EPI 尺寸按下式派生：

```text
gate x span >= active x width + 2 * gate_extension_x_each_side
EPI x span = active x width + 2 * epi_extension_x_each_side
```

当前：

```text
gate_extension_x_each_side = 9 nm
epi_extension_x_each_side  = 4 nm
gate length along y        = 14 nm
outer EPI length along y   = 9 nm
shared EPI length along y  = 18 nm
```

因此 18 nm NFET active 超参数导出 36/26 nm gate/EPI span，
14 nm PFET active 导出 32/22 nm gate/EPI span。这些是派生值，不是独立输入。

## 5. 前侧和背侧层堆叠

| Layer | z range (um) | Material | Purpose |
| ---: | --- | --- | --- |
| 18 VMD | 0.150..0.180 | W | local/device routing abstraction |
| 19 M0 | 0.180..0.210 | Cu | y-preferred |
| 20 VM0 | 0.210..0.240 | W | M0 to M1 |
| 21 M1 | 0.240..0.270 | Cu | x-preferred |
| 22 V1 | 0.270..0.300 | W | M1 to M2 |
| 23 M2 | 0.300..0.330 | Cu | y-preferred |
| 52 BVMD | -0.030..0.000 | W | backside local/device routing abstraction |
| 53 BM0 | -0.060..-0.030 | Cu | backside routing |
| 54 BV0 | -0.090..-0.060 | W | lower backside via abstraction |

M2/V1 当前 DTCO 参数：

```text
m2_pitch = 18 nm
m2_cd = 10 nm
via_cd = 8 nm
via_enclosure = 1 nm
via_min_spacing = 10 nm
```

其中 1 nm enclosure 由 `(10-8)/2` 派生；10 nm 相邻 via 边缘间距由
`18-8` 派生。它们是当前抽象规则，不是工业 PDK 规则。

## 6. “合法堆叠”的含义

一个 via/contact 只有同时满足以下条件才算合法：

1. z 连续：下层顶面等于 via 底面，via 顶面等于上层底面。
2. xy 包围：via 投影必须同时落在上下两层同 net 金属内部，并满足 enclosure。
3. net 一致：下层、via、上层必须属于同一个 net。
4. 层次允许：不得无定义地跳过金属层；跨层长接触必须有独立 layer rule。
5. 间距合法：via 与异 net via、金属、gate 和 active 需满足各自 spacing。
6. 端点闭合：从器件 gate/SD 到 pin 的每一步都必须有实体重叠或合法接触。

当前 `M0 -> VM0 -> M1 -> V1 -> M2` 的 z 邻接已经定义。
但 `device SD/gate -> MD/VMD` 以及 `lower SD -> BVMD` 仍是抽象接口：
现有规则没有论文可确认的 contact 高度、扩散包围和 gate-contact 间距。
因此现在可以生成结构和进行矩形预检查，但不能声称所有器件端子已通过工业规则合法落孔。

## 7. 当前检查范围

`validate_sram_layout.py` 当前检查：

- CH、CPP、MMP 边界闭合；
- 六管 gate net 和 S/D net 标签；
- Q/QB 共享扩散；
- gate/EPI 相对 active 超参数的派生尺寸；
- TXT/GDS 中不存在禁止使用的 L101/L102；
- M0/M1/M2/BM0 轨道对齐；
- 同层异 net 面积重叠；
- VMM 是否符合架构开关；
- 基于允许层间连接表建立 net 图；
- `WL/BL/BLB/Q/QB/VDD/VSS` 是否各自形成一个连通分量。

当前不执行：

- LVS；
- 完整 foundry DRC；
- contact/via 到器件端子的工业级 enclosure/spacing。

当前连通图来自 TXT 矩形、net 标签和允许层间相邻关系，不是从 GDS/SDE
寄生提取获得。验证成功消息只能称为
`geometry/topology/connectivity precheck passed`。

## 8. 待确认项

1. 论文未给出 SRAM 专用 M2 pitch/CD；当前暂用 `18/10 nm`。
2. BM0 CD 当前暂用 10 nm，论文主要确认的是 31/18 nm pitch。
3. MD/BMD、gate contact 和 diffusion contact 的工业级尺寸及 enclosure 尚无数据。
4. Q-front/QB-back 的 plane assignment 仍是 DTCO 布线选择，不是论文唯一解。

以上四项不会阻止当前结构搭建，但会阻止“完整 DRC/LVS 通过”的结论。
