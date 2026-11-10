# 单元适配脚本

每个 `<cell>.py` 都是完整的独立脚本，内含 HSPICE deck 生成、运行、结果解析、`CELL_ID`、`INPUTS`、`TRUTH_TABLE` 和该单元独立的 `TEST_PLAN`。运行时不导入 `_comb_cell.py` 或其他单元脚本。`../cell_runtime.py.inc` 只供生成器构造独立脚本，不能由 FLOW 直接调用。
