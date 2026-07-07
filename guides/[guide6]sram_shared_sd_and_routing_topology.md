# CFET 6T SRAM Shared-SD and Routing Topology

本文档讨论四种 CFET 架构中连续扩散、上下层等电位合并、电位引出和最小
布线方案。分析顺序为电路网络、FEOL diffusion chain、MOL 垂直连接、
BEOL routing，不从 cell boundary 反推器件位置。

## 1. 分析符号

```text
A / G(NET) / B
```

表示一个晶体管，左右扩散分别为 A、B，gate 接 NET。

```text
A / G0 / B / G1 / C
```

表示两个相邻晶体管共用中间扩散 B。

其他符号：

```text
||MERGE||  上下 tier 同网，通过 MD/BMD/BVD/VMM 合并
||ISO||    上下 tier 不同网，必须保持介质隔离
CUT        该 tier 没有 active/nanosheet
DUMMY(X)   dummy gate 接 X，两侧扩散必须等电位
```

## 2. 6T SRAM 的两条基本 NFET 链

传统 6T SRAM 的四个 NFET 可以形成两条最小连续 active：

```text
Top row A:
BL / PG1(WL) / Q / PD1(QB) / VSS

Top row B:
VSS / PD2(Q) / QB / PG2(WL) / BLB
```

共享扩散：

- Row A 中间的 Q 同时是 PG1 和 PD1 的扩散端。
- Row B 中间的 QB 同时是 PD2 和 PG2 的扩散端。
- 同一 net 的共享扩散应为一个连续 EPI/contact 区，而不是两个 EPI 加金属桥。

两个 PFET 的最小功能 active 为：

```text
Bottom row A:
Q / PU1(QB) / VDD

Bottom row B:
VDD / PU2(Q) / QB
```

将 bottom row 与 top row 对齐后：

```text
Row A, top   : BL  / PG1(WL) / Q / PD1(QB) / VSS
Row A, bottom: CUT            / Q / PU1(QB) / VDD

Row B, top   : VSS / PD2(Q) / QB / PG2(WL) / BLB
Row B, bottom: VDD / PU2(Q) / QB / CUT
```

这正是 Abdi 等人的 6T CFET SRAM 中“四个 top NFET、两个 bottom PFET”
产生未使用垂直器件位置的原因。

## 3. 共享条件

### 3.1 同层 SD 共享

只有满足以下条件才允许把相邻 SD 合为一个 diffusion：

1. 两个相邻晶体管位于同一 tier、同一 active 类型。
2. 两个端点属于同一个 net。
3. 中间没有 active-cut、well 隔离或独立接触要求。

因此允许：

```text
PG1.Q = PD1.Q = Q
PD2.QB = PG2.QB = QB
```

不允许：

```text
PD1.VSS 与 PU1.VDD
PD2.VSS 与 PU2.VDD
BL 与 Q
QB 与 BLB
```

### 3.2 上下 gate 共享

反相器 gate 的逻辑 net 相同：

```text
PD1.G = PU1.G = QB
PD2.G = PU2.G = Q
```

因此：

- common-gate 架构可以使用一根贯穿上下 tier 的 gate。
- split-gate 架构使用独立上下 gate，但最终仍要接到同一个 Q 或 QB。
- split-gate 的独立性用于工艺、dummy 隔离和复杂逻辑，不改变 6T 反相器输入。

PG 位置不同：

```text
top PG gate = WL
bottom functional device = none
```

如果上下 gate 强制 common，PG 下方必须移除 bottom active。否则 WL 会控制
一个额外 PFET。

### 3.3 上下 SD 合并

允许合并：

```text
top PD1/PG1 output Q  ||MERGE|| bottom PU1 output Q
top PD2/PG2 output QB ||MERGE|| bottom PU2 output QB
```

必须隔离：

```text
top PD source VSS ||ISO|| bottom PU source VDD
top PG BL/BLB     ||ISO|| bottom unused/dummy region
```

Q/QB 合并点应各自唯一，避免同一个节点出现多个大面积并联 via，增加寄生
电容和拥塞。

## 4. 电位引出优先级

按必须程度排序：

1. `BL/BLB`：从 PG 外侧 diffusion 独立引出。
2. `WL`：连接 PG1、PG2 gate，不能误接 PU/PD gate。
3. `Q/QB`：既是共享 diffusion，又要垂直连接另一 tier，并交叉接到对侧 gate。
4. `VSS`：连接两个 PD 外侧 diffusion。
5. `VDD`：连接两个 PU 外侧 diffusion。

最困难的是 Q/QB，因为每个节点同时承担：

```text
PG diffusion
PD diffusion
PU diffusion
opposite inverter gate input
```

所以 Q/QB 不能都放在同一个平面上交叉。最少需要两种 routing resource：

```text
方案 A: Q 走 front MD/M0，QB 走 back BMD/BM0
方案 B: QB 走 front MD/M0，Q 走 back BMD/BM0
```

镜像 bitcell 可以交换 A/B，减少阵列级方向偏差。

## 5. 5T+1 论文提供的版图模板

Abdi 的版图示意可抽象为：

```text
horizontal active / nanosheet rows
vertical gate fingers
vertical MD or BMD columns at diffusion nodes
WL_n on upper metal
WL_p or backside control on backside metal
BVD connecting active/contact to backside routing
front and backside nets drawn as separate planes
```

应用到 6T 时：

- active 行保持水平连续。
- gate 作为窄的垂直 finger，切过 active。
- SD/contact 位于 gate 之间和 active 两端。
- Q/QB 的 MD/BMD 柱放在共享 diffusion 上。
- BL/BLB 从 PG 外侧引出。
- VDD/VSS 从 PU/PD 外侧引出。
- 图中的前后侧重叠不代表短路，只有显式 BVD/VMM 才表示连接。

## 6. mCFET common-gate

### FEOL

```text
Top A: BL  / PG1(WL) / Q  / PD1(QB) / VSS
Bot A: CUT            / Q  / PU1(QB) / VDD

Top B: VSS / PD2(Q)  / QB / PG2(WL) / BLB
Bot B: VDD / PU2(Q)  / QB / CUT
```

约束：

- active/gate 图形自由度最低。
- inverter 的上下 gate 可直接 common。
- PG 下方 bottom active 必须用 tier-selective nanosheet cut 移除。
- 不能通过独立 bottom gate 关闭多余 PFET。
- 无 VMM，Q/QB 的上下合并只能依赖 MD/BMD/BVD。
- shared MRW 位于 cell boundary 时可能限制 abutment。

最可行布线：

```text
Front M0/M1: Q、QB 的交叉耦合和 WL
Higher metal: BL、BLB
Back BM0: VDD、VSS
```

限制：

- Q/QB 至少一个节点必须升到更高层绕线。
- front routing track 消耗最大。
- cut mask 和 common-gate 寄生不可避免。

## 7. hDR common-gate + dense BM0

FEOL 与 mCFET common-gate 相同，仍然需要 PG 下方 cut。

dense BM0 的改进：

- BM0 pitch 从 `31 nm` 降为 `18 nm`。
- VDD/VSS 可以完全放到背面。
- 可把 Q 或 QB 中的一个局部交叉节点放到背面。

推荐资源分配：

```text
Front: WL, BL, BLB, Q
Back : VDD, VSS, QB
```

或采用镜像：

```text
Front: WL, BL, BLB, QB
Back : VDD, VSS, Q
```

Q/QB 上下合并：

- front 节点使用 MD。
- back 节点使用 BMD+BVD。
- 没有 VMM 时，背面节点必须选择无遮挡的 BVD 位置。

主要限制：

- common gate 和 active cut 问题没有解决。
- dense BM0 只改善后道，不改善 PG 下方无用器件。
- BVD 与 VDD/VSS rail 的 track 竞争需要显式检查。

## 8. hDR split-gate + standard BM0

### 方案 1：active cut

```text
Top A: BL  / PG1(WL) / Q  / PD1(QB) / VSS
Bot A: CUT            / Q  / PU1(QB) / VDD

Top B: VSS / PD2(Q)  / QB / PG2(WL) / BLB
Bot B: VDD / PU2(Q)  / QB / CUT
```

这是电气最干净的实现。

### 方案 2：等电位 dummy

```text
Top A: BL / PG1(WL) / Q / PD1(QB) / VSS
Bot A: Q  / DG1(VDD) / Q / PU1(QB) / VDD

Top B: VSS / PD2(Q) / QB / PG2(WL) / BLB
Bot B: VDD / PU2(Q) / QB / DG2(VDD) / QB
```

其中：

- DG1、DG2 是 bottom PFET dummy gate。
- PFET gate 接 `VDD`，保持关闭。
- dummy 两端分别同为 Q 或 QB，因此即使误导通也不形成新电流路径。

限制：

- dummy 增加 Q/QB 的 gate、junction 和 overlap 电容。
- 需要把 VDD 引到两个 dummy gate。
- standard BM0 pitch `31 nm`，无法像 denseBM0 一样自由分配多个背面信号。

最可行选择：

- 若工艺允许 tier-selective cut，选择 active cut。
- 若 cut 是主要工艺瓶颈，才选择等电位 dummy。
- Q/QB 仍采用一前一后或一层一高层的分离 routing。

## 9. sCFET split-gate + dense BM0 + VMM

sCFET 的 sequential patterning 允许 top/bottom active 独立定义，因此无需为了
保持 mask 对齐而保留 PG 下方完整 bottom active。

推荐 FEOL：

```text
Top A: BL  / PG1(WL) / Q  / PD1(QB) / VSS
Bot A:                 Q  / PU1(QB) / VDD

Top B: VSS / PD2(Q)  / QB / PG2(WL) / BLB
Bot B: VDD / PU2(Q)  / QB
```

即：

- top 保留两条完整的 `SD/G/SD/G/SD` NFET active。
- bottom 只保留两个 `SD/G/SD` PFET active island。
- PG 下方没有 bottom active，不需要 electrical dummy。
- PU/PD 上下 gate 分开加工，再在 gate contact 处接到 Q/QB。

推荐上下 SD 合并：

```text
Q : top shared diffusion -> MD -> vertical merge -> bottom PU1 diffusion
QB: top shared diffusion -> BMD/VMM -> bottom PU2 diffusion
```

Q/QB 可以互换前后面。只给被 bottom device 或 BMD 阻挡的节点使用 VMM。

推荐 routing plane：

```text
Front upper metal:
  WL, BL, BLB, Q local route

Back dense BM0:
  VDD, VSS, QB local route

Vertical:
  Q merge x1
  QB merge x1
  VMM x1 maximum
```

为什么这是四种架构中最可行的方案：

1. 两条 top active 各共享一个内部 SD，FEOL 最小。
2. bottom 只有两个功能 PFET island，无 dummy 寄生。
3. Q/QB 各只有一个上下合并点。
4. Q/QB 分属前后 routing plane，不发生同层交叉。
5. dense BM0 为 VDD/VSS 和一个存储节点提供足够 track。
6. VMM 只解决一个局部阻塞，不被滥用为所有网络的通孔。
7. 所有结构可以封装在 cell boundary 内，避免 shared MRW 边界冲突。

## 10. 最优模板

综合电气、FEOL 和后道约束，推荐以 sCFET 为最终模板：

```text
TOP NFET ROW A
BL --[SD]-- PG1(WL) --[Q shared SD]-- PD1(QB) --[VSS]

BOTTOM PFET ISLAND A
                         [Q]-- PU1(QB) --[VDD]

TOP NFET ROW B
VSS --[SD]-- PD2(Q) --[QB shared SD]-- PG2(WL) --[BLB]

BOTTOM PFET ISLAND B
[VDD]-- PU2(Q) --[QB]
```

引出：

```text
BL/BLB : PG outer SD -> MD -> upper bitline metal
WL     : PG1/PG2 gate contact -> upper wordline metal
Q      : shared SD + PU1 output -> front local route -> opposite Q-gate
QB     : shared SD + PU2 output -> BMD/VMM -> back local route -> opposite QB-gate
VSS    : PD outer SD -> BCT/BVD -> backside VSS rail
VDD    : PU outer SD -> BMD -> backside VDD rail
```

镜像单元交换 Q/QB 的前后 routing plane：

```text
Cell A: Q front, QB back
Cell B: QB front, Q back
```

这样更适合阵列 abutment，并可平均 Q/QB 的寄生差异。

## 11. 必须验证的规则

版图生成器至少应检查：

1. 每条 top active 必须严格是 `SD/G/SD/G/SD`。
2. Row A 中间 SD 必须唯一标记为 Q。
3. Row B 中间 SD 必须唯一标记为 QB。
4. bottom PU 输出必须与对应 Q/QB 垂直对齐。
5. VDD 与 VSS 不得共享 contact/via。
6. common gate 下 PG 位置必须存在 bottom active cut。
7. dummy 模式必须满足 dummy 两侧同网且 PFET gate 接 VDD。
8. Q/QB 不得在同一 routing layer 发生几何交叉。
9. 每个 storage node 只允许一个主要 vertical merge。
10. VMM 数量和用途必须显式定义，不能自动遍历所有 SD 添加。

## 12. 结论边界

文献明确支持：

- 6T SRAM 的电路拓扑和未充分利用的 CFET stack。
- 5T+1 版图中的 active/gate/MD/BMD/BVD 前后面模板。
- common/split gate、BM0 pitch 和 VMM 的架构能力。
- sCFET 独立 top/bottom pattern 和 cell-boundary 内 routing 的优势。

本文对四种 6T SRAM 的具体 routing plane 分配属于在上述公开信息基础上的
DTCO 推导。最终 mask enclosure、via 数量和 exact track index 仍需结合
目标 PDK 或明确的论文版图尺寸进一步校准。
