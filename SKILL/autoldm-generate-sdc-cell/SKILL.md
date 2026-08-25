---
name: autoldm-generate-sdc-cell
description: Generate and validate one AutoLDM combinational standard-cell SDC triplet (`sdc_pin`, standalone `sdc_pyscript`, and `sdc_tb`) by catalog cell name. Use when preparing or replacing the three cell-specific INPUT_MODEL files; do not use it for GDS layout generation, extracted physical RC, or sequential-cell characterization.
---

# AutoLDM 单个标准单元文件生成

使用 `scripts/generate_cell.py`，不要手工复制另一个单元后只替换名称。生成器从 `Database/sdc/build_sdc_library.py` 读取唯一的单元逻辑、端口、晶体管拓扑和测试计划定义，并输出同名单元三件套。

## 操作

1. 确认项目根目录包含 `Database/sdc/build_sdc_library.py` 和 `Database/sdc/cell_runtime.py.inc`。
2. 先运行 `python scripts/generate_cell.py --list` 确认单元在当前组合单元目录中。
3. 运行 `python scripts/generate_cell.py --cell <cell> --output-root <INPUT_MODEL或Database/sdc目录>`。目标文件已存在时，只有用户明确要求替换或更新才加 `--force`。
4. 检查命令返回 `PASS`，并向用户报告三个绝对路径。脚本会加载生成的独立Python文件、创建临时子电路接口、生成测试deck，并执行dry-run结果收集检查。

## 必须保持的约定

- 三个文件的基本名必须等于小写单元名：`sdc_pin/<cell>.txt`、`sdc_pyscript/<cell>.py`、`sdc_tb/<cell>.txt`。
- 端口顺序为输入端、`Y`、`VDD`、`VSS`，并且pin manifest、PEX子电路和版图标签必须一致。
- `<cell>.py`必须内含完整运行时代码，不能导入`_comb_cell.py`、其他单元脚本或`Database`/`FLOW` Python模块。
- 默认bench参数可以在同名tb文件外部修改；脚本中的默认值只补齐未提供项，`vdd`和`vss`仍要求在tb中明确给出。
- 该Skill不生成真实版图RC，不替代PEX，也不声称产生foundry标准单元。

需要增加目录外的新组合单元或理解当前30个单元范围时，读取 [references/cell_contract.md](references/cell_contract.md)。
