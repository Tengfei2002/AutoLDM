# inv_test：CFET 反相器输入、版图、虚拟 RC 与运行说明

## 1. 项目范围

`FLOW/inv_test` 是独立的反相器测试工程。它包含完整 `INPUT_MODEL`、文本版图及 GDS、SDE/DRC 输入、反相器 pin/bench/专用 Python 脚本、虚拟 R/C matrix、PEX 生成和 HSPICE 调度入口。

本工程的目标是检查自动化流程的文件关系和标准单元切换方式。当前 R/C 数值是为流程联调人工设定的数据，不是版图提取结果，也不能用于模型标定、性能结论或签核。

## 2. 目录与数据关系

```text
inv_test/
├─ run_inv_test.ps1                 # 本工程统一入口
├─ gen_sde.py                       # 通用 SDE 命令生成
├─ gen_drc_report.py                # 通用文本版图检查
├─ gen_pex.py                       # 通用 pin/RC 到 PEX 转换
├─ run_cell.py                      # 通用标准单元调度
├─ INPUT_MODEL/
│  ├─ inv_test_gds.txt              # 反相器文本版图
│  ├─ inv_test.gds                  # 文本版图转换后的 GDS
│  ├─ inv_test_params.txt           # 器件几何、材料、掺杂、网格
│  ├─ inv_test_stacked.txt          # 层号、Z 范围、材料
│  ├─ inv_test_design_rules.txt     # 版图与接触检查规则
│  ├─ inv_test_fet_n.va             # NMOS 模型
│  ├─ inv_test_fet_p.va             # PMOS 模型
│  ├─ sdc_pin/inv.txt               # 反相器端口、器件和 RC 请求
│  ├─ sdc_tb/inv.txt                # 反相器测试条件
│  └─ sdc_pyscript/inv.py           # 反相器 deck 与结果分析
├─ SDE/
│  ├─ inv_test_r_cMatrix.spi        # 虚拟电阻数据
│  ├─ inv_test_c_cMatrix.spi        # 虚拟电容数据
│  ├─ inv_test_r_sde.cmd            # 生成的电阻提取命令
│  └─ inv_test_c_sde.cmd            # 生成的电容提取命令
├─ Hspice/                           # PEX、deck 和仿真结果
└─ OUTPUT/inv_test_drc_report.txt    # DRC 报告
```

工程名和标准单元名是两个不同参数：

- 工程名固定为 `inv_test`，用于版图、参数、模型、matrix 和输出文件前缀；
- 标准单元名固定为 `inv`，用于选择 `sdc_pin/inv.txt`、`sdc_tb/inv.txt` 和 `sdc_pyscript/inv.py`。

## 3. 反相器版图

文本版图定义一只上层 NMOS `N1` 和一只下层 PMOS `P1`。两只器件共用输入栅极 `A`，漏极连接为输出 `Y`；N1 源极连接 `VSS`，P1 源极通过背侧金属连接 `VDD`。

当前端口和内部节点关系如下：

| 外部端口 | 内部连接 | 用途 |
|---|---|---|
| `A` | `N1_G_A`、`P1_G_A` | 公共栅极输入 |
| `Y` | `N1_SD_Y`、`P1_SD_Y` | 公共漏极输出 |
| `VSS` | `N1_SD_VSS` | NMOS 源极与体端 |
| `VDD` | `P1_SD_VDD` | PMOS 源极与体端 |

使用的主要层号为：1（domain）、7（gate）、16（MD）、17（vertical）、18（V0）、19（M0）、51（BMD）、52（BV0）、53（BM0）。版图尺寸、矩形坐标和标签以 `INPUT_MODEL/inv_test_gds.txt` 为准。

`INPUT_MODEL/inv_test.gds` 已由该文本文件生成。修改文本版图后，应重新执行：

```powershell
python .\INPUT_MODEL\txt_gds_trans\txt2gds.py `
  .\INPUT_MODEL\inv_test_gds.txt `
  .\INPUT_MODEL\inv_test.gds
```

## 4. 全部 INPUT 的处理原则

- 版图文件已经替换为两管反相器结构，只保留 A/Y/VDD/VSS 四个外部端口。
- `inv_test_params.txt`、`inv_test_stacked.txt` 和 `inv_test_design_rules.txt` 保留现有 CFET 技术假设，内部文件名引用已统一为 `inv_test_*`。
- N/P Verilog-A 文件保留已有器件模型。模型的默认有效沟道长度为 16 nm、宽度为 35 nm、指数量为 1；没有用虚构数据改写器件电学模型。
- pin manifest 使用 `A/Y/VDD/VSS` 和 `N1/P1`，与文本版图节点及虚拟 matrix 一致。
- testbench 当前使用 `VDD=0.7 V`、输出负载 `5 fF`、输入上升/下降时间 `20 ps`、瞬态停止时间 `4 ns`、DC 步长 `1 mV`。
- `inv.py` 生成 DC 传输、瞬态延迟、输入低电平静态电流和输入高电平静态电流四个测试 deck。

## 5. 虚拟 RC 参数

### 电阻

| 电阻项 | 连接 | 数值 |
|---|---|---:|
| `R_A_N1_G_A` | A 到 NMOS 栅 | 8 Ω |
| `R_A_P1_G_A` | A 到 PMOS 栅 | 12 Ω |
| `R_Y_N1_SD_Y` | Y 到 NMOS 漏 | 10 Ω |
| `R_Y_P1_SD_Y` | Y 到 PMOS 漏 | 14 Ω |
| `R_VDD_P1_SD_VDD` | VDD 到 PMOS 源 | 9 Ω |
| `R_VSS_N1_SD_VSS` | VSS 到 NMOS 源 | 7 Ω |

### 电容

| 电容项 | 连接 | 数值 |
|---|---|---:|
| `C_A_Y` | A 到 Y | 0.90 fF |
| `C_A_VDD` | A 到 VDD | 0.25 fF |
| `C_A_VSS` | A 到 VSS | 0.30 fF |
| `C_Y_VDD` | Y 到 VDD | 0.55 fF |
| `C_Y_VSS` | Y 到 VSS | 0.65 fF |
| `C_VDD_VSS` | VDD 到 VSS | 1.20 fF |

这些值只用于确认节点映射、PEX 拼接、deck 生成和调度逻辑。得到真实提取结果后，直接替换 `SDE/inv_test_r_cMatrix.spi` 和 `SDE/inv_test_c_cMatrix.spi`，但必须保留 pin manifest 请求的节点对，或者同步修改 `sdc_pin/inv.txt`。

## 6. 运行方法

在 `FLOW/inv_test` 目录运行。

只生成并检查所有文件，不调用真实 HSPICE：

```powershell
& .\run_inv_test.ps1 -DryRun -NoPlot
```

生成 SDE、DRC、PEX 和四个 HSPICE deck，但不执行仿真：

```powershell
& .\run_inv_test.ps1 -GenerateOnly
```

执行完整流程并调用本机配置的 HSPICE：

```powershell
& .\run_inv_test.ps1
```

入口按顺序执行：

1. 根据版图、参数、层叠和规则生成 R/C SDE 命令；
2. 生成 DRC 报告，出现 ERROR 时停止；
3. 读取反相器 pin manifest 与 R/C matrix，生成 `INV_TEST_PEX`；
4. 生成并校验 DC、TRAN、LEAK0、LEAK1 deck；
5. 非 dry-run 且非 generate-only 时执行 HSPICE 并汇总指标。

## 7. 当前验证结果

已先执行 `run_inv_test.ps1 -DryRun -NoPlot`，再执行 `run_inv_test.ps1 -NoPlot` 调用真实 HSPICE。结果如下：

- SDE 命令生成成功；
- DRC 为 `ERROR=0`、`WARNING=0`、`INFO=1`、`PASS=26`；
- 唯一 INFO 表示当前只有一条 gate，因而没有可比较的 gate-to-gate spacing 对；
- GDS 回读得到 18 个矩形，层号、坐标和 A/Y/VDD/VSS 标签与文本版图一致；
- PEX 读取 10 个电阻节点、6 条电阻，4 个电容节点、6 条电容；
- PEX 子电路名称为 `INV_TEST_PEX`，外部端口为 `A Y VDD VSS`；
- PEX 零偏置验证、DC、TRAN、LEAK0、LEAK1 均由 HSPICE 执行并返回 0，未报告模型数值错误；
- DC 功能检查为 pass：`VM=0.34062 V`、`VOH=0.7 V`、`VOL=4.7132e-7 V`；
- 瞬态时序检查为 pass：`tPHL=21.888 ps`、`tPLH=21.288 ps`、`tr=32.081 ps`、`tf=33.297 ps`；
- 输入为 0 和 1 时的静态功耗分别约为 `1.3853 nW` 和 `0.23198 nW`。

实际结果位于 `Hspice/results/inv`，PEX 编译验证结果位于 `Hspice/results/inv_pex_validation`。

以上电学指标基于人工设定的 RC 和当前 Verilog-A 模型，只证明本工程的数据关系、生成逻辑和 HSPICE 调用可以完成。真实电学结论需要替换为实际提取 RC，并确认器件模型与目标工艺一致。
## 8. 结果图片与波形数据

不带 `-NoPlot` 运行时，`inv.py` 会从 HSPICE listing 的 `.print` 表中解析 DC 和瞬态波形，并生成以下文件：

- `Hspice/results/inv/figures/inv_test_pex_dc_waveform.png`：DC 传输曲线、`V(Y)=V(A)` 参考线、VM 标记和电源电流；
- `Hspice/results/inv/figures/inv_test_pex_tran_waveform.png`：输入/输出瞬态波形和电源电流；
- `Hspice/results/inv/figures/summary_metrics.png`：传播延迟、上升/下降时间和两个输入状态的静态功耗；
- `Hspice/results/inv/data/inv_test_pex_dc_waveform.csv`：DC 绘图原始数据；
- `Hspice/results/inv/data/inv_test_pex_tran_waveform.csv`：瞬态绘图原始数据。

使用 `-NoPlot` 时仍执行仿真和数值分析，但不重新生成 PNG。波形 CSV 仍会生成，便于后续使用其他工具绘图。