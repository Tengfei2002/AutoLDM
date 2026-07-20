# AutoLDM 项目说明

AutoLDM 是一个面向 DTCO（Design-Technology Co-Optimization）流程的自动化项目，用于从版图、规则文件和器件模型出发，生成 SDE 结构脚本、HSPICE 仿真 deck，并对 SRAM 与 CFET/VA 模型结果进行可视化和参数校准。

项目当前包含两条主要流程：

- SDE 结构生成：由 layout txt 与 rules 文件生成 Sentaurus SDE `.cmd`。
- HSPICE 电学验证：生成 SRAM RC deck、单管 Id-Vg/Id-Vd deck、参数扫描 deck，并用 Python 生成科研绘图。

## 目录结构

```text
AutoLDM/
|-- gen_sde.py                         # layout/rules -> SDE .cmd 的核心生成脚本
|-- readme.md                          # 本说明文档
|-- gds/                               # GDS 及其转换后的 layout txt
|-- rules/                             # 工艺结构参数与 layer rule
|-- guides/                            # 结构参数、建模流程和说明文档
|-- output_SDE/
|   |-- sde_cmd/                       # SDE command 输出
|   |-- rc_raphreal/                   # SRAM schematic 映射与 RC matrix
|   `-- rc_sp/                         # SRAM HSPICE deck 输出
`-- Hspice/
    |-- va/                            # CFET Verilog-A 模型
    |-- iv/                            # HSPICE deck、脚本、结果和 PNG
    |-- iv_flow/                       # HSPICE 运行封装脚本
    `-- wt_cfet/                       # 外部 CSV 参考曲线
```

## SDE 结构生成

核心脚本：

```text
gen_sde.py
```

基本命令：

```powershell
python gen_sde.py .\gds\standard_sram_v1_2.txt .\rules\standard_arch.txt .\rules\standard_layer_rule.txt -o .\output_SDE\sde_cmd\standard_sram_v1_2_sde.cmd
```

通用格式：

```powershell
python gen_sde.py <layout_txt> <arch_rule> <layer_rule> -o <output_cmd>
```

典型输入：

- `gds/*.txt`：版图矩形与 label/net 信息。
- `rules/*_arch.txt`：器件结构、材料、掺杂、网格等参数。
- `rules/*_layer_rule.txt`：版图层到三维结构层的映射规则。

典型输出：

- `output_SDE/sde_cmd/*.cmd`：可在 Sentaurus SDE 中运行的结构生成脚本。

## SRAM RC HSPICE 流程

SRAM 的 RC 信息来自：

```text
output_SDE/rc_raphreal/sram_schematic.txt
output_SDE/rc_raphreal/n18_cMatrix.spi
output_SDE/rc_raphreal/n19_cMatrix.spi
```

生成脚本：

```text
Hspice/iv/generate_sram_mapped_rc.py
Hspice/iv/split_sram_decks.py
```

主要输出：

```text
output_SDE/rc_sp/standard_sram.sp
Hspice/iv/standard_sram.sp
Hspice/iv/standard_sram_tran.sp
Hspice/iv/standard_sram_snm.sp
Hspice/iv/standard_sram_mapped_rc_report.txt
```

说明：

- `generate_sram_mapped_rc.py` 根据 `sram_schematic.txt` 中的命名关系，从 `n18_cMatrix.spi` 和 `n19_cMatrix.spi` 查找对应 RC。
- 对缺失或明显异常的同网 RC，脚本使用对称节点或相邻有限路径给出合理近似。
- 测试高阻隔离使用 `1e16`。
- deck 中加入 `GSHUNT=1e-12` 以增强 DC/SNM 收敛。
- `split_sram_decks.py` 将完整 deck 拆分为 transient 和 SNM/DC 两个独立 deck，避免 `.ALTER` 继承导致的仿真干扰。

运行示例：

```powershell
python Hspice\iv\generate_sram_mapped_rc.py
python Hspice\iv\split_sram_decks.py
python Hspice\iv_flow\run_hspice.py Hspice\iv\standard_sram_tran.sp --results-dir Hspice\iv\results
python Hspice\iv_flow\run_hspice.py Hspice\iv\standard_sram_snm.sp --results-dir Hspice\iv\results
python Hspice\iv\plot_hspice_results.py --results Hspice\iv\results --png Hspice\iv\png
```

SRAM 图像输出：

```text
Hspice/iv/png/sram_read_transient.png
Hspice/iv/png/sram_write_transient.png
Hspice/iv/png/sram_hold_retention.png
Hspice/iv/png/sram_supply_current.png
Hspice/iv/png/sram_snm_butterfly.png
Hspice/iv/png/sram_ncurve.png
```

## 单管 VA Id-Vg / Id-Vd 验证

Verilog-A 模型：

```text
Hspice/va/cfet_nmos_lvt.va
Hspice/va/cfet_pmos_lvt.va
```

单管 deck：

```text
Hspice/iv/single_va_nmos_idvg.sp
Hspice/iv/single_va_nmos_idvd.sp
Hspice/iv/single_va_pmos_idvg.sp
Hspice/iv/single_va_pmos_idvd.sp
```

运行方式：

```powershell
python Hspice\iv_flow\run_hspice.py Hspice\iv\single_va_nmos_idvg.sp --results-dir Hspice\iv\results
python Hspice\iv_flow\run_hspice.py Hspice\iv\single_va_nmos_idvd.sp --results-dir Hspice\iv\results
python Hspice\iv_flow\run_hspice.py Hspice\iv\single_va_pmos_idvg.sp --results-dir Hspice\iv\results
python Hspice\iv_flow\run_hspice.py Hspice\iv\single_va_pmos_idvd.sp --results-dir Hspice\iv\results
python Hspice\iv\plot_hspice_results.py --results Hspice\iv\results --png Hspice\iv\png
```

图像输出：

```text
Hspice/iv/png/single_va_nmos_idvg.png
Hspice/iv/png/single_va_nmos_idvd.png
Hspice/iv/png/single_va_pmos_idvg.png
Hspice/iv/png/single_va_pmos_idvd.png
```

## CSV 与 VA 曲线对比

参考 CSV：

```text
Hspice/wt_cfet/CFET_N4.40_14000.csv
```

基础对比脚本：

```text
Hspice/iv/plot_compare_wt_cfet_nmos_idvg.py
```

输出：

```text
Hspice/iv/png/compare_wt_cfet_vs_va_nmos_idvg.png
```

该图用于比较 WT CFET CSV 与 `single_va_nmos_idvg.sp` 中 `L16_W25, VDS=0.05/0.35/0.70 V` 的 HSPICE 曲线。

## EOT_0 参数扫描

`cfet_nmos_lvt.va` 中 `EOT_0` 已在 `instance_parameter_list` 中，因此无需复制或修改 `.va` 文件，可以直接在 HSPICE 实例上覆盖：

```spice
Xmn d g s b cfet_nmos_lvt L='LCH' W='WDEV' NF='NFDEV' EOT_0=9.50e-10
```

生成脚本：

```text
Hspice/iv/generate_nmos_eot_idvg_sweep.py
Hspice/iv/plot_compare_eot_nmos_idvg.py
```

EOT 扫描值：

```text
0.90, 0.95, 1.00, 1.05, 1.10, 1.15, 1.20 nm
```

deck 输出：

```text
Hspice/iv/single_va_nmos_idvg_EOT0_90.sp
Hspice/iv/single_va_nmos_idvg_EOT0_95.sp
Hspice/iv/single_va_nmos_idvg_EOT1_00.sp
Hspice/iv/single_va_nmos_idvg_EOT1_05.sp
Hspice/iv/single_va_nmos_idvg_EOT1_10.sp
Hspice/iv/single_va_nmos_idvg_EOT1_15.sp
Hspice/iv/single_va_nmos_idvg_EOT1_20.sp
```

结果目录：

```text
Hspice/iv/results_eot/
```

图像输出：

```text
Hspice/iv/png/compare_wt_cfet_vs_va_nmos_idvg_EOT_sweep.png
Hspice/iv/png/compare_wt_cfet_vs_va_nmos_idvg_EOT_sweep_logy.png
```

## NMOS Id-Vg 自动拟合流程

自动拟合脚本：

```text
Hspice/iv/fit_nmos_idvg_params.py
```

该流程保持名义 `L/W/NF` 不变：

```verilog
L  = 1.6e-8
W  = 2.5e-8
NF = 1
```

并只通过实例参数覆盖以下 Verilog-A 参数：

```verilog
U0
XL
DVTSHIFT
DeltaWGAA
DeltaTGAA
EOT_0
```

运行方式：

```powershell
python Hspice\iv\fit_nmos_idvg_params.py --max-local 72
```

如果已有 HSPICE 结果，只重新解析和画图：

```powershell
python Hspice\iv\fit_nmos_idvg_params.py --max-local 72 --reuse
```

第二版全范围拟合目录：

```text
Hspice/iv/fit_nmos_idvg_vmax1/
```

关键输出：

```text
Hspice/iv/fit_nmos_idvg_vmax1/fit_summary.csv
Hspice/iv/fit_nmos_idvg_vmax1/fit_best_vmax1_params.json
Hspice/iv/fit_nmos_idvg_vmax1/fit_best_vmax1_curve.csv
Hspice/iv/fit_nmos_idvg_vmax1/fit_visual_vmax1_params.json
Hspice/iv/fit_nmos_idvg_vmax1/fit_visual_vmax1_curve.csv
```

全局 `log + high-current` 混合最优：

```text
tag = fit_l202
U0 = 0.016
XL = 1.2e-8
DVTSHIFT = 0.0
DeltaWGAA = 0.0
DeltaTGAA = -1e-9
EOT_0 = 9.5e-10
```

对应图：

```text
Hspice/iv/png/compare_wt_cfet_vs_va_nmos_idvg_fit_best_vmax1.png
Hspice/iv/png/compare_wt_cfet_vs_va_nmos_idvg_fit_best_vmax1_logy.png
```

偏高电流区视觉最优：

```text
tag = fit_l230
U0 = 0.020
XL = 1.6e-8
DVTSHIFT = -0.02
DeltaWGAA = 0.0
DeltaTGAA = -1e-9
EOT_0 = 9.5e-10
```

对应图：

```text
Hspice/iv/png/compare_wt_cfet_vs_va_nmos_idvg_fit_visual_vmax1.png
Hspice/iv/png/compare_wt_cfet_vs_va_nmos_idvg_fit_visual_vmax1_logy.png
```

## 关键 VA 参数含义

```verilog
parameter real L = 1.6e-8;
parameter real W = 2.5e-8;
parameter real NF = 1;
```

名义沟道长度、名义器件宽度和等效 finger/fin/nanosheet 数量。本项目的拟合流程中固定不改。

```verilog
parameter real U0 = 3.0e-2;
```

低场迁移率参数，主要影响电流幅值，尤其是中高 `VGS` 区。

```verilog
parameter real XL = 1.2e-8;
```

有效沟道长度修正。模型中使用 `Lg = L + XL`，因此 `XL` 增大通常会降低电流。

```verilog
parameter real DVTSHIFT = 0.0;
```

阈值电压偏移量，主要控制 Id-Vg 曲线左右移动。

```verilog
parameter real DeltaWGAA = 0;
parameter real DeltaTGAA = 0;
```

模型内部 GAA 等效宽度和厚度修正，不改变 deck 中的名义 `W/L`，但会改变有效截面和电流。

```verilog
parameter real EOT_0 = 1.1e-9;
```

等效氧化层厚度，影响栅控能力、栅电容、亚阈值斜率和开启形状。

## HSPICE Runner

统一运行入口：

```text
Hspice/iv_flow/run_hspice.py
```

示例：

```powershell
python Hspice\iv_flow\run_hspice.py Hspice\iv\standard_sram_tran.sp --results-dir Hspice\iv\results
```

runner 会自动：

- 查找 HSPICE 可执行文件。
- 设置 license 环境变量。
- 建立结果目录。
- 保存 `.lis/.sw0` 等输出。
- 写入 `manifest.json`。

## Git 提交参考

查看状态：

```powershell
git status
```

提交全部改动：

```powershell
git add -A
git commit -m "add hspice sram rc flow and iv fitting results"
git push
```

如果不希望提交大量 HSPICE 中间结果，可以改为只 `git add` 脚本、deck、README 和关键 PNG/CSV。
