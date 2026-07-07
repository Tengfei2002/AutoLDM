# HSPICE / Verilog-A Model Notes

本文说明 `fusion_ic_nmos_lvt.va` 和 `fusion_ic_pmos_lvt.va` 的作用、整体仿真结构，以及从 OA/layout 抽取到 HSPICE 后仿网表时需要准备的参数。这里的 OA 按 OpenAccess/layout 数据库或版图抽取对象理解；如果目标是具体模拟电路中的 op-amp/OA，器件与寄生部分仍然适用，testbench 指标需要替换为增益、带宽、相位裕度、CMRR、PSRR 等模拟指标。

## 这两个 `.va` 文件是什么

`fusion_ic_nmos_lvt.va` 和 `fusion_ic_pmos_lvt.va` 是 PHIMO-Fusion GAA 器件的 Verilog-A 紧凑模型，不是普通 HSPICE `.model` 参数卡。

它们分别定义：

```spice
module nmos_lvt(D, G, S, B)
module pmos_lvt(D, G, S, B)
```

在 HSPICE 中通过 `.hdl` 引入，然后像子电路一样实例化：

```spice
.hdl "fusion_ic_nmos_lvt.va"
.hdl "fusion_ic_pmos_lvt.va"

Xmn1 D G S B nmos_lvt L=16n W=100n NF=1
Xmp1 D G S B pmos_lvt L=16n W=200n NF=1
```

这两个文件的“玄机”主要有三点：

1. 它们把模型系数直接写进 Verilog-A 源码中。大量 `nnsce*`、`nnclm*`、`nnqua*`、`nnmob*`、`nncv*` 是神经网络权重和偏置，用于修正短沟道效应、CLM/速度饱和、量子效应/GIDL、迁移率和 C-V 行为。
2. 它们把物理模型和神经网络融合在一个 analog block 中。模型先做几何归一化和 NN 推理，再进入类 BSIM-CMG/GAA 的物理方程，最后得到 `ids`、`QG`、`QD`、`QS`、`GM/GDS` 和电容导数。
3. 它们只描述器件本征电学，不包含版图连接关系。真实单元的金属电阻、电容、浮空金属、inner/outer contact 节点，需要由 wrapper 或寄生抽取网表提供。

## 文件内部结构

两个文件结构基本一致，差别在于 `type` 极性、NN 权重和部分器件常数。

主要结构如下：

1. 头部和模块声明

```verilog
`include "constants.vams"
`include "disciplines.vams"
module nmos_lvt(D, G, S, B);
```

端口为四端 MOS 形式：`D/G/S/B`。

2. 公开 instance 参数

```verilog
parameter real L=1.6e-8;
parameter real W=3.5e-8;
parameter real NF=1;
parameter real U0 = 3.0e-2;
parameter real XL=1.2e-8;
parameter real DVTSHIFT=0.0;
parameter real DeltaWGAA = 0;
parameter real DeltaTGAA = 0;
parameter real EOT_0 = 1.1e-9;
```

通常网表实例只需要显式传 `L/W/NF`。`U0/XL/DVTSHIFT/DeltaWGAA/DeltaTGAA/EOT_0` 是工艺/校准类参数，默认值已经写在模型里，需要做 corner 或拟合时再覆盖。

3. 内部几何和归一化

模型内部将：

```verilog
WGAA = W
TGAA = 5.0e-9
NGAA = 3.0
Lg = L + XL
```

并用 `L/W/TGAA` 等变量做 NN 输入归一化。文件注释给出的适用范围是 `Lg: 16-100 nm`、`WGAA: 10-40 nm`，超出范围时结果属于外推，不应直接信任。

4. NN 权重区

主要分为：

- `SCE`: short-channel effect。
- `CLM / velocity saturation`: 沟道长度调制和速度饱和。
- `Quantum / GIDL`: 量子修正和栅诱导漏电。
- `Mobility`: 迁移率退化。
- `CV`: 电荷和电容修正。

这些参数不是版图参数，不应从 OA 中提取；它们是模型训练结果。

5. helper 函数和数值保护

模型定义了 `Sigmoid`、`Tanh`，以及 `lexp`、`lln`、`hypsmooth`、`smoothminx` 等宏，用来避免指数溢出、log 非法值和硬分段不连续。

6. analog 主体

analog block 的核心顺序是：

- 读取偏置：`vgs = type * V(G,S)`，`vds = type * V(D,S)`。
- 判断正反向工作模式。
- 计算有效几何：`Lg`、`Weff_UFCM`、`Ach`、`EOT`、`Cins`。
- 计算阈值、短沟道、DIBL、量子修正。
- 计算源端/漏端反型电荷 `qis/qid`。
- 计算准静态电流 `ids` 和 GIDL。
- 计算准静态电荷 `qg/qd/qs` 和寄生 overlap/fringe 电荷。
- 对端口贡献电流：DC 电流和/或 `ddt(Q)` 充放电电流。

需要注意：该版本中 DC 电流贡献和 charge 电流贡献附近有明显调试痕迹，例如 `//#########1111`、部分 `I(D,S)<+...` 被注释。做正式 PDK 化前，需要确认当前版本是否是“最终物理一致版”，尤其是 DC/AC/transient 是否同时启用所需贡献。

## 当前 HSPICE 工程的三层结构

当前目录中已有一个清晰的三层结构：

```text
Hspice/
  fusion_ic_nmos_lvt.va      本征 NMOS LVT Verilog-A 模型
  fusion_ic_pmos_lvt.va      本征 PMOS LVT Verilog-A 模型
  parasitics_wrapper.sp      器件实例 + 版图寄生 R/C wrapper
  compare_pref.sp            仿真 testbench、激励和测量
```

### 1. 器件模型层

由 `.va` 文件提供。它只关心单个 transistor 的端口和本征电学：

```spice
Xmp1 D G S B pmos_lvt L=16n W=200n NF=1
Xmn1 D G S B nmos_lvt L=16n W=100n NF=1
```

### 2. Wrapper / 寄生层

`parasitics_wrapper.sp` 定义了 `CFET_INV`、`S2FET_INV`、`IDEAL_INV`。以 `CFET_INV` 为例，它包含：

- PMOS/NMOS 本征器件实例。
- `Epi`、`Inner`、`Outer` 等内部节点。
- contact 电阻。
- gate/drain/source 路径的 RC 网络。
- 版图寄生电容矩阵。
- 浮空金属的泄放电阻，例如 `R_float_fix Tungsten_31 0 1G`。

这层才是 OA/layout 抽取结果真正落地的地方。

### 3. Testbench / 测量层

`compare_pref.sp` 做了：

```spice
.hdl "fusion_ic_nmos_lvt.va"
.hdl "fusion_ic_pmos_lvt.va"
.INCLUDE "parasitics_wrapper.sp"
.PARAM VDD_VAL = 0.7
.TRAN 0.1p '5*T_PER'
.MEAS TRAN ...
```

它负责电源、输入激励、负载、电路实例、仿真类型和测量指标。

## 从 OA/layout 完成 HSPICE wrapper 需要哪些参数

最小必需信息可以分为五类。

### 1. 器件实例参数

每个 transistor 至少需要：

- 器件类型：`nmos_lvt` 或 `pmos_lvt`。
- 四端连接：`D G S B`。
- `L`: 物理 gate length，单位要和模型一致，建议写成 `16n` 这类 SPICE 单位。
- `W`: GAA sheet width / effective WGAA 入口；当前模型内部 `WGAA = W`。
- `NF`: finger 或并联倍数。
- body 连接：NMOS 通常接 VSS，PMOS 通常接 VDD；CFET/堆叠结构要按实际 well/body 定义。

可选但重要的校准参数：

- `U0`: 低场迁移率标定。
- `XL`: gate length offset，模型中 `Lg = L + XL`。
- `DVTSHIFT`: 阈值整体平移。
- `DeltaWGAA`、`DeltaTGAA`: 几何偏差。
- `EOT_0`: 等效氧化层厚度基准。

### 2. 版图连接参数

从 OA/layout 需要得到：

- 每个器件的 gate/source/drain/body 对应 net。
- 被共享的 diffusion/epi 节点，例如 inverter 中 PMOS/NMOS 共用 output drain。
- 内部接触节点，例如 `NPGate_Epi_P`、`NPGate_Inner_P`、`NPGate_Outer`。
- 外部端口到内部节点的映射，例如 `IN -> NPGate_Outer`、`OUT -> NPDrain_Outer`。
- 浮空金属或 dummy metal 列表，必须加大电阻泄放到参考地，避免矩阵奇异。

### 3. 寄生电阻参数

wrapper 中每条电阻都应来自版图抽取或规则计算：

- contact resistance：epi 到 inner 的接触电阻。
- local metal resistance：inner 到 outer 的金属路径。
- shared node resistance：共享 drain/source/gate 的 T-network、delta-network 或 daisy-chain。
- external pin resistance：外部端口到 outer metal 的小电阻。

命名建议：

```spice
R_con_d_p   NPDrain_Epi   NPDrain_Inner_P  <value>
R_gate_0_1  NPGate_Outer  NPGate_Inner_N   <value>
R_ext_in    IN            NPGate_Outer     0.001
```

### 4. 寄生电容参数

至少需要生成节点对之间的电容矩阵：

- output/drain 对 gate 的电容。
- output/drain 对 source/VDD/VSS 的电容。
- gate 对 source/drain/body/floating metal 的电容。
- floating metal 对其他电学节点的电容。

命名建议：

```spice
C_0_1  NPDrain_Epi    NPDrain_Outer  <value>
C_0_2  NPDrain_Epi    NPGate_Outer   <value>
C_2_4  NPGate_Outer   NSource_Epi    <value>
```

电容单位用 F，电阻单位用 ohm。寄生电容不应重复计入 `.va` 的本征 C-V；`.va` 负责 intrinsic/overlap/fringe，本层负责 layout interconnect parasitic。

### 5. Testbench 参数

需要给定：

- 电源：`VDD_VAL`、VSS。
- 输入激励：PULSE/PWL/AC/DC sweep。
- 负载：`C_LOAD` 或下一级真实输入。
- 仿真类型：`.TRAN`、`.DC`、`.AC`、`.NOISE`。
- 测量：delay、rise/fall、average power、PDP、energy、gain/bandwidth 等。
- 温度：`.TEMP`。
- 输出保存：`.OPTION POST`、`.PROBE`。

## 一个完整 OA-to-HSPICE 输出应包含什么

建议自动生成以下文件：

```text
cell_name_tb.sp              顶层 testbench
cell_name_wrapper.sp         从 OA/layout 生成的器件 + 寄生 wrapper
fusion_ic_nmos_lvt.va        NMOS Verilog-A 模型
fusion_ic_pmos_lvt.va        PMOS Verilog-A 模型
cell_name_measure.inc        可选，统一放 .MEAS
cell_name_params.inc         可选，统一放 VDD、load、corner 参数
```

其中 wrapper 至少包含：

- `.SUBCKT <cell> <ports...>`。
- 所有 NMOS/PMOS Verilog-A 实例。
- 所有内部节点命名。
- contact / metal path 电阻。
- 寄生电容矩阵。
- 浮空节点泄放电阻。
- `.ENDS <cell>`。

顶层 testbench 至少包含：

- `.hdl` 引入两个 `.va`。
- `.include` 引入 wrapper。
- `.param` 定义电源、负载、时间参数。
- voltage/current source。
- DUT 实例。
- load。
- analysis。
- `.meas`。
- `.end`。

## 推荐生成流程

1. 从 OA/layout 读取器件实例、端口、net 和几何。
2. 将每个器件映射为 `X... nmos_lvt/pmos_lvt L=... W=... NF=...`。
3. 根据版图连接生成 `Epi -> Inner -> Outer -> Port` 的节点层级。
4. 从电阻抽取或几何规则生成 R 网络。
5. 从电容抽取或场求解结果生成 C 矩阵。
6. 对所有浮空金属加 `1G` 到地的泄放电阻。
7. 生成 wrapper `.SUBCKT`。
8. 生成 testbench，包含 `.hdl`、`.include`、激励和 `.meas`。
9. 跑 HSPICE，检查是否有 floating node、Verilog-A compile error、time step too small、charge/current double count 等问题。

## 常见风险

- 把 `.va` 当作普通 `.model` 使用：错误。必须用 `.hdl`。
- `W` 的物理含义混淆：当前模型内部 `WGAA = W`，不是传统 planar MOS 的总宽度。
- 超出训练范围：注释给出 `Lg: 16-100 nm`、`WGAA: 10-40 nm`。
- 版图寄生和模型本征电容重复计算：wrapper 只加 interconnect parasitic。
- 浮空金属未处理：HSPICE 可能矩阵奇异或收敛异常。
- DC 电流和 charge current 贡献版本不一致：当前 `.va` 有调试注释，正式使用前应确认目标分析所需的 `I(D,S)` 和 `ddt(Q)` 贡献是否正确打开。

## 两个 VA 的完整参数依赖

结论：这两个 `.va` 文件确实依赖工艺/模型参数。它们不是只由几何 `L/W/NF` 决定，而是由以下几类内容共同决定：

- HSPICE 实例传入参数：`L/W/NF` 等。
- 文件内部硬编码的 GAA 几何、材料、掺杂、迁移率、短沟道、C-V、数值稳定参数。
- 电流模型和电容模型两套神经网络权重。
- NMOS/PMOS 各自不同的 NN 数值权重。

非 NN 的公开参数和内部硬编码参数在 NMOS/PMOS 中基本相同；脚本比对后，非 NN 初始化参数中只有 `type` 不同：NMOS 为 `1.0`，PMOS 为 `-1.0`。注意当前两个文件中 `devsign` 都写成 `1.0`，真正区分 NMOS/PMOS 极性的主要入口是 `type` 和对应的 NN 权重。

### 公开 instance 参数

这些可以在网表实例中覆盖：

| 参数 | 默认值 | 作用 |
|---|---:|---|
| `L` | `1.6e-8` | 实例沟道长度入口，模型内部用 `Lg = L + XL`。 |
| `W` | `3.5e-8` | 当前模型中 `WGAA = W`，对应 GAA sheet width 入口，不是传统 planar MOS 总宽度。 |
| `NF` | `1` | 并联倍数或 finger 数，影响电流/电荷缩放。 |
| `U0` | `3.0e-2` | 低场迁移率基准。 |
| `XL` | `1.2e-8` | length offset。 |
| `DVTSHIFT` | `0.0` | 阈值整体平移。 |
| `DeltaWGAA` | `0` | GAA 宽度偏差。 |
| `DeltaTGAA` | `0` | GAA 厚度偏差。当前源码中部分 `Ach` 计算写成 `TGAA + DeltaWGAA`，正式使用前建议确认这是否为预期。 |
| `EOT_0` | `1.1e-9` | EOT 基准值，实际计算中会乘以 NN 输出 `cv_output14`。 |

### NN 输入归一化参数

| 参数 | 默认值 |
|---|---:|
| `tgaamax` | `5.0e-9` |
| `tgaamin` | `5.0e-9` |
| `wgaamax` | `4.0e-8` |
| `wgaamin` | `1.0e-8` |
| `lgaamax` | `1e-7` |
| `lgaamin` | `1.6e-8` |
| `netmax` | `1.0` |
| `netmin` | `-1.0` |

这些参数定义 NN 输入范围。文件注释说明模型训练/适用范围为 `Lg: 16-100 nm`、`WGAA: 10-40 nm`。

### GAA 几何、温度和极性参数

| 参数 | 默认值 | 作用 |
|---|---:|---|
| `TGAA` | `5.0e-9` | nanosheet 厚度。 |
| `WGAA` | `W` | nanosheet 宽度，由实例 `W` 驱动。 |
| `TFIN` | `6.0e-9` | fin/sheet 厚度相关参数。 |
| `HFIN` | `3.3e-8` | fin/sheet 高度相关参数。 |
| `NFIN` | `1.0` | fin 数，参与 binning。 |
| `NGAA` | `3.0` | GAA sheet 数。 |
| `TOXP` | `1.07464e-9` | 物理氧化层厚度相关参数。 |
| `TOXG` | `1.46e-9` | gate oxide 厚度相关参数。 |
| `DevTemp` | `300` | 器件温度。 |
| `type` | NMOS `1.0`, PMOS `-1.0` | 器件极性。 |
| `devsign` | `1.0` | 源码中保留的符号变量。 |

### 物理常数和材料常数

| 参数 | 默认值 |
|---|---:|
| `q` | `1.60219e-19` |
| `KboQ` | `8.617087e-5` |
| `pi` | `3.1415926` |
| `HBAR` | `1.05457e-34` |
| `MEL` | `9.11e-31` |
| `mx` | `0.916 * MEL` |
| `mxprime` | `0.190 * MEL` |
| `md` | `0.190 * MEL` |
| `mdprime` | `0.417 * MEL` |
| `gprime` | `4.0` |
| `gfactor` | `2.0` |
| `EPSROX` | `3.9` |
| `EPS0` | `8.8542e-12` |
| `EPSRSUB` | `11.9` |
| `epsratio` | `EPSRSUB / EPSROX` |
| `NC0SUB` | `2.86e25` |
| `NI0SUB` | `1.1e16` |
| `BG0SUB` | `1.12` |
| `EASUB` | `4.05` |
| `EGBULK` | `1.1` |

### 掺杂、功函数和 electrostatics 参数

| 参数 | 默认值 | 作用 |
|---|---:|---|
| `NBODY` | `1.0e23` | DC/I-V 段 body/channel doping。 |
| `NSD` | `2.0e26` | DC/I-V 段 source/drain doping。 |
| `NBODY_CV` | `5.0e21` | C-V 段 body/channel doping，在 analog 第二段中赋值。 |
| `NSD_CV` | `1.0e26` | C-V 段 source/drain doping，在 analog 第二段中赋值。 |
| `PHIG` | `4.47` | DC/I-V 段 gate work function。 |
| `PHIG_CV` | `4.37` | C-V 段 gate work function。 |
| `PHIN_i` | `0.05` | 阈值/势垒相关修正。 |
| `ALPHA_UFCM` | `0.5556` | UFCM 方程系数。 |
| `DELTA_1` | `0.02` | C-V overlap 平滑项。 |
| `QMFACTORCVfinal` | `0.0` | C-V 量子修正系数。 |

### Quantum / GIDL / 几何修正参数

完整非 NN 参数如下：

`WDIM0`, `WDIMR`, `WSSP0`, `WSSPR`, `DIM1H`, `DIMENSION1_i`, `DIM2H`, `DIMENSION2_i`, `DIM3H`, `DIMENSION3_i`, `DSSP1`, `DSSP2`, `DSSP3`, `SSP1_i`, `SSP2_i`, `SSP3_i`, `TSRE2`, `TDWSE2`, `TSRE3`, `TDWSE3`, `TSRQ1`, `TDWSQ1`, `TSRQ2`, `TDWSQ2`, `TSRQ3`, `TDWSQ3`, `WGAANOM`, `WSFE2`, `WSFE3`, `E2NOM_i`, `E3NOM_i`, `MFE2`, `MFE3`, `MFQ1`, `MFQ2`, `MFQ3`, `WSFQ1`, `WSFQ2`, `WSFQ3`, `MFQ1NOM_i`, `MFQ2NOM_i`, `MFQ3NOM_i`, `QMFACTOR_i`, `QMTCENCV_i`, `AQMTCEN`, `BQMTCEN`, `QM0`, `PQM`。

这些参数主要参与量子阈值修正、charge centroid、GIDL 和 GAA 几何缩放。

### Mobility 参数

完整非 NN 参数如下：

`ETAMOBTHIN`, `ETAMOB`, `ETAMOBTNI`, `ETAMOBIR`, `UA`, `UATHIN`, `UATSAT`, `UARTSC`, `UATNI`, `UAIR`, `EUTHIN`, `EU`, `EUPTSC`, `EUTNI`, `EUIR`, `U0ETAWSC`, `U0EMSM1`, `U0EMSM2`, `UDTHIN`, `UD`, `UDTSAT`, `UDPTSC`, `UCS_t`, `DMOBCLAMP`, `U0MULT`。

它们参与 `Dmob`、`Dmob_cv`、`ueff` 等计算。NN 的 mobility 输出会进一步修正 `UA_i`、`EU_i`、`U0_i`、`UD_i`、`ETAMOB_i`。

### Velocity saturation / CLM / current 参数

完整非 NN 参数如下：

`VSAT`, `VSAT1`, `VSATCV_t`, `PSAT_i`, `PSATCV_i`, `DELTAVSAT_i`, `DELTAVSATCV_i`, `PTWG_a`, `A1_t`, `A2_t`, `DVSATCLAMP`, `KSATIV`, `MEXP`, `DROUT`, `PVAG`, `PDIBL1`, `PDIBL2`, `PCLMG`, `PCLM`, `LPCLM`, `NPCLM`, `PPCLM`, `WPCLM`, `P2PCLM`, `PCLMCV_i`。

这些参数控制速度饱和、沟道长度调制、DIBL 输出电导和 C-V 中的 CLM 修正。

### Short-channel / subthreshold / DIBL 参数

完整非 NN 参数如下：

`DVT1`, `LDVT1`, `NDVT1`, `PDVT1`, `WDVT1`, `P2DVT1`, `DVT1SS`, `LDVT1SS`, `NDVT1SS`, `PDVT1SS`, `WDVT1SS`, `P2DVT1SS`, `DSUB`, `LDSUB`, `NDSUB`, `PDSUB`, `WDSUB`, `P2DSUB`, `LPE0`, `LLPE0`, `NLPE0`, `PLPE0`, `WLPE0`, `P2LPE0`, `CDSC`, `LCDSC`, `NCDSC`, `PCDSC`, `WCDSC`, `P2CDSC`, `CDSCD`, `LCDSCD`, `NCDSCD`, `PCDSCD`, `WCDSCD`, `P2CDSCD`, `CIT`, `LCIT`, `NCIT`, `PCIT`, `WCIT`, `P2CIT`, `DVT0`, `LDVT0`, `NDVT0`, `PDVT0`, `WDVT0`, `P2DVT0`, `ETA0`, `LETA0`, `NETA0`, `PETA0`, `WETA0`, `P2ETA0`, `DVTP0`, `LDVTP0`, `NDVTP0`, `PDVTP0`, `WDVTP0`, `P2DVTP0`, `DVTP1`, `LDVTP1`, `NDVTP1`, `PDVTP1`, `WDVTP1`, `P2DVTP1`, `K1RSCE`, `LK1RSCE`, `NK1RSCE`, `PK1RSCE`, `WK1RSCE`, `P2K1RSCE`。

带 `L/N/P/W/P2` 前缀的项是 binning 系数入口，用于通过 `Inv_L`、`Inv_NFIN`、`Inv_LNFIN`、`Inv_W`、`Inv_WL` 做尺寸相关修正。

### C-V 和 overlap/fringe 参数

完整非 NN 参数如下：

`CFS_i`, `CFD_i`, `CFS_i_CV`, `CFD_i_CV`, `vfbsdcv`, `CGSL_i`, `CKAPPAS_i`。

其中 `CFS_i_CV`、`CFD_i_CV` 在 C-V analog 段中赋值为 `1e-10`，用于 fringe charge：

```verilog
qgs_fr = T1 * CFS_i_CV * cv_output6 * vgs;
qgd_fr = T1 * CFD_i_CV * cv_output6 * (vgs - vds);
```

### NN 权重依赖

每个文件中还有大量训练后的 NN 权重和 bias。它们不是工艺参数本身，但决定模型如何从 `L/W/TGAA` 等输入推断短沟道、CLM、量子、迁移率和 C-V 修正。

每个 VA 文件的 NN 参数族数量如下：

| 前缀 | 数量 | 作用 |
|---|---:|---|
| `nnsce*` | 54 | short-channel effect。 |
| `nnclm*` | 194 | CLM / velocity saturation。 |
| `nnqua*` | 98 | quantum / GIDL。 |
| `nnmob*` | 58 | mobility。 |
| `nncv*` | 222 | C-V / charge。 |

NMOS 和 PMOS 的 NN 参数族相同，但具体数值不同，所以不能只替换 `type` 把 NMOS 变成 PMOS。

## 这个 VA 是怎样被构建的

这两个 VA 的构建逻辑不是“从 SDE 几何直接翻译成 Verilog-A”。它更像以下流程的产物：

1. 以 BSIM-CMG / GAA 物理模型为骨架。
2. 选定训练/适用范围：`Lg: 16-100 nm`、`WGAA: 10-40 nm`，以及固定或默认的 `TGAA/NGAA/EOT/doping/work-function` 范围。
3. 用 TCAD 或参考仿真/测试数据生成 I-V 和 C-V 数据集。
4. 将模型拆成若干物理效应模块：SCE、CLM/velocity saturation、quantum/GIDL、mobility、C-V。
5. 对每个模块训练小型神经网络，得到 `nnsce*`、`nnclm*`、`nnqua*`、`nnmob*`、`nncv*` 权重和 bias。
6. 把 Python/训练版模型展开成 Verilog-A：所有 NN 权重、归一化范围、物理常量和公式都直接写入源码。
7. 在 Verilog-A 中定义数值保护宏：`lexp`、`lln`、`hypsmooth`、`smoothminx`，避免仿真收敛时指数溢出、log 非法和硬分段不连续。
8. 在 `analog` block 中执行模型计算并向端口贡献电流。

当前源码内部有两个主要计算段：

1. I-V 段：使用不带 `_cap` 后缀的 NN 权重和 `NBODY/NSD/PHIG`，计算 `ids`，并贡献 DC 电流：

```verilog
I(D, S) <+ type * ids;
```

2. C-V 段：使用带 `_cap` 后缀的 NN 权重和 `NBODY_CV/NSD_CV/PHIG_CV/CFS_i_CV/CFD_i_CV`，计算 `QG/QD/QS`，并贡献充放电电流：

```verilog
I(G, S) <+ ddt(QG);
I(D, S) <+ ddt(QD);
```

也就是说，它是“电流模型 + 电荷模型”合并进一个 module 的写法。I-V 和 C-V 共享器件几何入口，但使用不同的 NN 权重和部分不同的工艺参数。这个设计可以减少 HSPICE wrapper 的复杂度，但正式建库时需要特别确认 DC、AC、TRAN 三种分析下电流和电荷是否没有漏贡献或重复贡献。
