# 6T CFET SRAM Topology, Potentials, and Geometry

本文档先定义电路，再定义几何。任何版图压缩都不得改变这里的 S/G/D 网络。

## 1. 六个晶体管的固定连接

NMOS 的 source/drain 在物理上近似对称。对 pass-gate 使用 `T1/T2` 表示两个
扩散端，避免在读写过程中错误地把某一端永久称为 source。

| Device | Type / tier | S or T1 | Gate | D or T2 |
| --- | --- | --- | --- | --- |
| `PU1` | PMOS / bottom | `VDD` | `QB` | `Q` |
| `PD1` | NMOS / top | `VSS` | `QB` | `Q` |
| `PG1` | NMOS / top | `BL` | `WL` | `Q` |
| `PU2` | PMOS / bottom | `VDD` | `Q` | `QB` |
| `PD2` | NMOS / top | `VSS` | `Q` | `QB` |
| `PG2` | NMOS / top | `BLB` | `WL` | `QB` |

其中：

- 左反相器 `PU1/PD1` 的输入是 `QB`，输出是 `Q`。
- 右反相器 `PU2/PD2` 的输入是 `Q`，输出是 `QB`。
- `PG1/PG2` 共用 `WL`，分别把 `BL/BLB` 接到 `Q/QB`。
- `Q` 和 `QB` 必须互补，稳态只允许 `(VDD, 0)` 或 `(0, VDD)`。

## 2. 保持状态

### 保存 1：Q=VDD，QB=0

| Device | S/T1 | G | D/T2 | State |
| --- | ---: | ---: | ---: | --- |
| `PU1` | `VDD` | `0` | `VDD` | ON |
| `PD1` | `VSS` | `0` | `VDD` | OFF |
| `PU2` | `VDD` | `VDD` | `0` | OFF |
| `PD2` | `VSS` | `VDD` | `0` | ON |
| `PG1` | `BL=X` | `WL=0` | `Q=VDD` | OFF |
| `PG2` | `BLB=X` | `WL=0` | `QB=0` | OFF |

### 保存 0：Q=0，QB=VDD

| Device | S/T1 | G | D/T2 | State |
| --- | ---: | ---: | ---: | --- |
| `PU1` | `VDD` | `VDD` | `0` | OFF |
| `PD1` | `VSS` | `VDD` | `0` | ON |
| `PU2` | `VDD` | `0` | `VDD` | ON |
| `PD2` | `VSS` | `0` | `VDD` | OFF |
| `PG1` | `BL=X` | `WL=0` | `Q=0` | OFF |
| `PG2` | `BLB=X` | `WL=0` | `QB=VDD` | OFF |

`X` 表示 bitline 可浮置或保持预充电值，但访问管关闭，不参与单元保持。

## 3. 读取

读取前：

```text
BL = VDD
BLB = VDD
WL = 0
```

随后 `WL` 升到 `VDD`。

### 读取 Q=1

- `PG1` 两端约为 `BL=VDD`、`Q=VDD`，BL 基本不放电。
- `PG2` 两端初始为 `BLB=VDD`、`QB=0`。
- 放电路径为 `BLB -> PG2 -> QB -> PD2 -> VSS`。
- 因此 `BLB` 下降，`BL` 保持高电位。

### 读取 Q=0

- 放电路径为 `BL -> PG1 -> Q -> PD1 -> VSS`。
- 因此 `BL` 下降，`BLB` 保持高电位。

读取期间 PG 的“source”是瞬时低电位侧，因此不能在版图网络中固定指定。

## 4. 写入

### 写 Q=0、QB=1

```text
BL  = 0
BLB = VDD
WL  = VDD
```

`PG1` 将 Q 拉低；Q 降低使 `PU2` 导通、`PD2` 关闭，QB 被拉高。交叉耦合
正反馈完成翻转。

### 写 Q=1、QB=0

```text
BL  = VDD
BLB = 0
WL  = VDD
```

`PG2` 将 QB 拉低；QB 降低使 `PU1` 导通、`PD1` 关闭，Q 被拉高。

写入结束后 `WL` 回到 0，BL/BLB 回到预充电或浮置状态。

## 5. CFET tier 使用

依据 Abdi 等人的 6T CFET SRAM 图：

- top tier：`PG1、PD1、PD2、PG2` 四个 NFET。
- bottom tier：`PU1、PU2` 两个 PFET。
- PG 下方的 bottom-tier PFET footprint 不参与 6T 电路。
- 传统 6T CFET 因此存在未使用堆叠器件，并需要 top/bottom active 或
  nanosheet cut 防止形成多余器件。

common/split gate 只是物理 gate 实现方式。即使使用 split gate，
`PU1/PD1` 仍必须同时接 `QB`，`PU2/PD2` 仍必须同时接 `Q`。

## 6. 参考尺寸链

依据 Yang 等人的 asymmetric sheet-width 图：

```text
W_N active = 18 nm
W_P active = 14 nm
Gate extension = 9 nm / side
EPI extension = 4 nm / side
CPP = 42 nm
Gate length = 14 nm
```

由此得到：

| Geometry | Calculation | Size |
| --- | --- | ---: |
| NFET gate span | `18 + 2*9` | `36 nm` |
| PFET gate span | `14 + 2*9` | `32 nm` |
| NFET EPI span | `18 + 2*4` | `26 nm` |
| PFET EPI span | `14 + 2*4` | `22 nm` |

CPP 方向采用以下尺寸闭合：

```text
EPI 9 + gate-to-EPI region 5 + gate 14
      + gate-to-EPI region 5 + EPI 9 = CPP 42 nm
```

因此不能把 gate 和 EPI 仅按视觉比例随意缩放。

## 7. 当前建模边界

当前模型使用上述网络和尺寸作为 DTCO 近似，不声称复刻论文未公开的完整
mask rule。未由论文明确给出的 contact enclosure、cut mask、局部 via
landing 和最小间距必须作为独立参数，而不能从图片像素反推为精确工艺值。

## 8. 连续扩散链

一个两栅 active 行的基本形式是：

```text
SD0 / G0 / SD1 / G1 / SD2
```

它表示两个相邻晶体管，`SD1` 是共享扩散。6T SRAM 的 top-tier NFET
可以直接写成两条最小链：

```text
N-row A: BL  / PG1(WL) / Q  / PD1(QB) / VSS
N-row B: VSS / PD2(Q)  / QB / PG2(WL) / BLB
```

因此 top tier 只需要：

- 两条连续 active。
- 每条 active 两个 gate。
- 每条 active 三个 SD 区。
- Q/QB 同时是 PG 与 PD 的共享扩散，不应拆成两个相邻 EPI 再用金属连接。

Bottom-tier PFET 的功能链只有一个 gate：

```text
P-row A: Q   / PU1(QB) / VDD
P-row B: VDD / PU2(Q)  / QB
```

为了和 top tier 两栅 pitch 对齐，可以表示为：

```text
P-row A: CUT-or-DUMMY / Q / PU1(QB) / VDD
P-row B: VDD / PU2(Q) / QB / CUT-or-DUMMY
```

`CUT-or-DUMMY` 如何实现取决于架构，不允许默认生成一个正常工作的额外 PFET。

## 9. 上下层共享条件

### 可以共享的 gate

```text
PD1 gate = PU1 gate = QB
PD2 gate = PU2 gate = Q
```

在 common-gate 架构中，这两个位置可以直接使用贯穿上下 tier 的 common
gate。在 split-gate 架构中也可以分别生成上下 gate，然后通过 gate
contact 合并到同一个 net。

PG 位置不能简单共享有效器件：

```text
top PG gate = WL
bottom device = unused in conventional 6T
```

common gate 会把 WL 同时施加到底层潜在 PFET，所以必须通过 active/nanosheet
cut，或通过严格的等电位 dummy 结构消除其电路功能。

### 可以合并的上下 SD

以下位置上下层同电位：

```text
PD1 output = PU1 output = Q
PD2 output = PU2 output = QB
```

可使用 MD/BMD、BVD 或 VMM 形成垂直 Q/QB 合并点。

以下位置必须隔离：

```text
PD1 source = VSS, PU1 source = VDD
PD2 source = VSS, PU2 source = VDD
```

即使它们平面投影相邻或重叠，也不能使用同一个 contact、via 或连续金属。

## 10. 四种架构的最简可布线拓扑

以下结论中的 SRAM 电路链来自 Abdi 的 6T CFET SRAM；架构能力来自 Yang
等人的 `(h)DR`、`denseBM0`、`split-gate` 和 `sCFET/VMM` 对比。论文没有
逐一给出这四种 6T SRAM mask，因此 routing 选择属于依据公开架构能力所作
的 DTCO 推导。

### 10.1 mCFET common-gate

能力：

- 上下 gate 必须共用。
- BM0 pitch 为 `31 nm`。
- 没有 VMM。
- top/bottom active 和 gate 图形独立性最低。

最简链：

```text
Top A: BL  / PG1(WL) / Q  / PD1(QB) / VSS
Bot A: CUT            / Q  / PU1(QB) / VDD

Top B: VSS / PD2(Q)  / QB / PG2(WL) / BLB
Bot B: VDD / PU2(Q)  / QB / CUT
```

共享：

- `PD1/PU1` 共用 QB gate。
- `PD2/PU2` 共用 Q gate。
- Q、QB 各设置一个上下层垂直合并点。

必须处理：

- PG1、PG2 下方的 bottom PFET 必须 cut。
- VDD/VSS 必须分开接触。
- Q/QB 垂直连接依赖普通 MD/BMD 路径，不能假设 VMM。

这是四种架构中 FEOL 最受限、前后道最难布线的 6T 实现。

### 10.2 hDR common-gate + dense BM0

FEOL 链与 mCFET common-gate 相同：

```text
Top A: BL  / PG1(WL) / Q  / PD1(QB) / VSS
Bot A: CUT            / Q  / PU1(QB) / VDD

Top B: VSS / PD2(Q)  / QB / PG2(WL) / BLB
Bot B: VDD / PU2(Q)  / QB / CUT
```

区别：

- common gate 规则不变，PG 下方仍需要 cut。
- dense BM0 pitch 为 `18 nm`，可把 VDD/VSS 和一个或两个局部存储节点连接
  移到背面。
- Q/QB 的上下合并仍使用 MD/BMD/BVD，不具备 sCFET 的 VMM bypass。

最简布线分工：

```text
Front: WL, BL, BLB, necessary Q/QB local cross-couple
Back : VDD, VSS, optional Q/QB landing
```

dense BM0 减少的是 routing 占用，不减少晶体管数量，也不自动消除 cut。

### 10.3 hDR split-gate + standard BM0

最简功能链仍是：

```text
Top A: BL  / PG1(WL) / Q  / PD1(QB) / VSS
Bot A: ISO / DUMMY   / Q  / PU1(QB) / VDD

Top B: VSS / PD2(Q)  / QB / PG2(WL) / BLB
Bot B: VDD / PU2(Q)  / QB / DUMMY / ISO
```

split-gate 提供两种 bottom-PG 处理方式：

1. **物理 cut**：仍切断 bottom active，电气最干净。
2. **等电位 dummy**：dummy 两侧 SD 都接 Q 或都接 QB，bottom gate 独立接
   `VDD` 使 PFET 关闭。

等电位 dummy 的示意：

```text
Bot A: Q / DummyPG1(VDD) / Q / PU1(QB) / VDD
Bot B: VDD / PU2(Q) / QB / DummyPG2(VDD) / QB
```

它避免功能性额外晶体管，但增加寄生电容和 gate/VDD routing。没有公开
mask 数据时，默认应优先使用物理 cut；dummy 只能作为显式可选模式。

split gate 的主要收益是：

- PG bottom gate 可独立关闭。
- PU/PD gate 可以独立形成后再接到同一个 Q/QB net。
- 不应把 split gate 错误理解为 PU/PD 使用不同逻辑输入。

### 10.4 sCFET split-gate + dense BM0 + VMM

功能链：

```text
Top A: BL  / PG1(WL) / Q  / PD1(QB) / VSS
Bot A: ISO-or-DUMMY  / Q  / PU1(QB) / VDD

Top B: VSS / PD2(Q)  / QB / PG2(WL) / BLB
Bot B: VDD / PU2(Q)  / QB / ISO-or-DUMMY
```

最简可布线选择：

- PG 位使用 split gate，bottom PG gate 独立关闭。
- bottom dummy 两端设置为同一存储节点，或使用独立 bottom active cut。
- Q、QB 各使用一个 top-MD 到 bottom-BMD 的垂直合并点。
- 其中一个受阻的局部节点可使用 VMM 绕过 bottom device；不应给所有 net
  无差别添加 VMM。
- dense BM0 承担 VDD/VSS 及必要的局部节点。

推荐最小连接资源：

```text
Q vertical merge  : 1
QB vertical merge : 1
VMM bypass        : 0 or 1, only for the geometrically blocked node
VDD backside rail : 1
VSS backside rail : 1
BL/BLB front vias : 2
WL gate contacts  : 2, may join on upper metal
```

sCFET 的优势是独立 top/bottom pattern、split gate、dense BM0 和 VMM
组合，使上述连接可以封装在 cell boundary 内。它不是通过增大 SD 或任意
压缩 CPP 获得优势。

## 11. 建模顺序

以后生成 SRAM 必须按以下顺序：

1. 写出 top/bottom diffusion chain。
2. 检查每个共享 SD 的 net 是否相同。
3. 检查每个上下重叠 gate 是 common、split-connected 还是 isolated。
4. 检查每个上下 SD 是 merge、isolated 还是 dummy-equipotential。
5. 决定 cut、MD/BMD、BVD、VMM。
6. 最后才把结构放到 CPP/MMP track 上。

禁止从最终 cell boundary 反向均分空间来决定晶体管位置。
