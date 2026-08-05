# HSPICE IV 自动化工作流

这个目录用于在 Windows 上用命令行运行 HSPICE，目标是尽量减少 GUI 操作，并让每次仿真的输入、输出和波形文件位置清晰可追踪。

## 文件说明

```text
iv_flow\
  run_hspice.py
  run_wv.py
  README.md
  cmd\
    run_hspice.cmd
    run_wv.cmd
    run_iv.cmd
    run_iv.ps1
    check_hspice_install.ps1
    configure_hspice_env.ps1
    open_awaves.cmd
    open_hspice_gui.cmd
  decks\
    single_nmos_output_iv.sp
    single_pmos_output_iv.sp
    circuit_inverter_dc_iv.sp
```

- `run_hspice.py`：单个 `.sp` 文件的一键仿真入口。
- `run_wv.py`：单独打开已有 HSPICE 波形文件的入口。
- `cmd\run_iv.ps1`：批量运行预设 IV deck 的 PowerShell 脚本。
- `cmd\check_hspice_install.ps1`：检查 HSPICE 安装路径、license server 和 `snpslmd` 状态。
- `cmd\configure_hspice_env.ps1`：把 HSPICE 和 license 配置写入当前 Windows 用户环境变量。
- `cmd\`：命令行入口目录，所有 `.cmd` 和 `.ps1` 工具脚本统一放在这里。
- `decks\`：示例 HSPICE netlist，也就是 `.sp` 输入文件。

## 单个 SP 一键仿真

在 `iv_flow` 目录下运行：

```powershell
python .\run_hspice.py .\decks\single_nmos_output_iv.sp
```

默认输出会放在 `.sp` 同级的同名文件夹下：

```text
decks\
  single_nmos_output_iv.sp
  single_nmos_output_iv\
    single_nmos_output_iv.lis
    single_nmos_output_iv.sw0
    single_nmos_output_iv.st0
    single_nmos_output_iv.pa0
    single_nmos_output_iv.valog
    single_nmos_output_iv.pvadir\
    manifest.json
```

也就是：

```text
xxx.sp
xxx\xxx.lis
xxx\xxx.sw0
xxx\manifest.json
```

## 仿真后自动打开 WaveView

如果想仿真结束后直接打开 Custom WaveView：

```powershell
python .\run_hspice.py .\decks\single_nmos_output_iv.sp -wv
```

默认 WaveView 路径：

```text
C:\synopsys\Custom WaveView O-2018.09-SP2\wv.exe
```

`-wv` 会优先打开 `.sw0`。如果是瞬态或 AC 仿真，则会尝试 `.tr0` 或 `.ac0`。

## 单独打开已有波形

如果已经仿真过，只想打开波形：

```powershell
python .\run_wv.py .\decks\single_nmos_output_iv.sp
```

给它 `.sp` 时，它会自动找：

```text
decks\single_nmos_output_iv\single_nmos_output_iv.sw0
```

也可以直接给输出目录：

```powershell
python .\run_wv.py .\decks\single_nmos_output_iv
```

或者直接给波形文件：

```powershell
python .\run_wv.py .\decks\single_nmos_output_iv\single_nmos_output_iv.sw0
```

## CMD 包装器

所有 `.cmd` 文件都放在 `cmd\` 目录下：

```powershell
.\cmd\run_hspice.cmd .\decks\single_nmos_output_iv.sp
.\cmd\run_wv.cmd .\decks\single_nmos_output_iv.sp
.\cmd\run_iv.cmd -Target all
```

打开 GUI 工具：

```powershell
.\cmd\open_hspice_gui.cmd
.\cmd\open_awaves.cmd
```

## 批量 IV 仿真

批量入口仍然是：

```powershell
.\cmd\run_iv.cmd -Target all
```

可选 target：

```powershell
.\cmd\run_iv.cmd -Target nmos
.\cmd\run_iv.cmd -Target pmos
.\cmd\run_iv.cmd -Target single
.\cmd\run_iv.cmd -Target circuit
.\cmd\run_iv.cmd -Target all
```

`run_iv.ps1` 会把批量结果放到：

```text
iv_flow\results\
```

这个批量 flow 适合做回归测试；`run_hspice.py` 更适合单个 `.sp` 的快速仿真。

## 示例 Deck

- `decks\single_nmos_output_iv.sp`：单个 NMOS 输出 IV，扫 `VDS` 和 `VGS`。
- `decks\single_pmos_output_iv.sp`：单个 PMOS 输出 IV，扫 `VSD` 和 `VSG`。
- `decks\circuit_inverter_dc_iv.sp`：inverter DC sweep，对比 `CFET_INV`、`S2FET_INV` 和 `IDEAL_INV`。

## 检查环境

检查 HSPICE 安装和 license：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\cmd\check_hspice_install.ps1
```

正常情况下应能看到：

```text
license server UP
snpslmd: UP
Users of hspice
Users of hspicewin
```

如果需要完整 license feature 列表：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\cmd\check_hspice_install.ps1 -FullLicenseStatus
```

## 常见输出文件

- `.lis`：HSPICE 主日志，包含 warning/error、`.PRINT` 输出和运行统计。
- `.sw0`：DC sweep 波形文件，当前 IV 仿真主要看它。
- `.tr0`：瞬态仿真波形文件。
- `.ac0`：AC 仿真波形文件。
- `.ms0`：`.MEASURE` 结果。
- `.st0`：状态文件。
- `.pa0`：后处理辅助文件。
- `.valog`：Verilog-A 编译日志。
- `.pvadir\`：Verilog-A 编译缓存目录。
- `manifest.json`：本次仿真的输入、输出、HSPICE 路径、license 和 WaveView 信息。
