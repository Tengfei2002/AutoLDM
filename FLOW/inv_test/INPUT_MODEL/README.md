# inv_test 输入文件说明

本目录中的输入分为工程输入和标准单元输入。工程输入使用 `inv_test_` 前缀；标准单元输入使用单元名 `inv`。

## 工程输入

| 文件 | 作用 | 当前处理方式 |
|---|---|---|
| `inv_test_gds.txt` | 可读版图矩形、层号和端口标签 | 已改为一对 CFET 上下层晶体管构成的反相器 |
| `inv_test.gds` | 由文本版图转换得到的 GDS | 由 `txt_gds_trans/txt2gds.py` 生成 |
| `inv_test_params.txt` | 纳米片、源漏、材料、掺杂和网格参数 | 沿用当前技术假设，文件引用已改为 `inv_test_*` |
| `inv_test_stacked.txt` | 版图层对应的 Z 范围和材料 | 沿用当前 CFET 层叠定义 |
| `inv_test_design_rules.txt` | 文本版图与接触结构的检查规则 | 用于 `gen_sde.py` 和 `gen_drc_report.py` |
| `inv_test_fet_n.va` | NMOS Verilog-A 模型 | 沿用已有模型，不在本次虚拟化范围内 |
| `inv_test_fet_p.va` | PMOS Verilog-A 模型 | 沿用已有模型，不在本次虚拟化范围内 |

## 标准单元输入

| 文件 | 作用 |
|---|---|
| `sdc_pin/inv.txt` | 定义端口 A/Y/VDD/VSS、N1/P1 连接以及所需 R/C 项 |
| `sdc_tb/inv.txt` | 定义电源、负载、瞬态时间和逻辑阈值 |
| `sdc_pyscript/inv.py` | 生成反相器专用 deck，并分析仿真结果 |

三份标准单元输入必须使用相同单元名。当前运行参数是 `--cell inv`。

## 版图端口

- `A`：N1 和 P1 的公共栅极输入；
- `Y`：N1 和 P1 的公共漏极输出；
- `VSS`：N1 源极的前侧金属端口；
- `VDD`：P1 源极的背侧金属端口。

详细版图结构、虚拟 RC 值和运行命令见项目根目录的 `README_INV_TEST.md`。