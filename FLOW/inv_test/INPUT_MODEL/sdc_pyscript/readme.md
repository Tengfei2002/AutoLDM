# 反相器专用测试脚本

本目录当前仅包含 `inv.py`。该脚本负责生成反相器的 DC 传输、瞬态延迟和输入为 0/1 时的静态电流测试 deck，并负责解析对应的 HSPICE 结果。

它和以下两个同名单元文件配套使用：

```text
sdc_pyscript/inv.py
sdc_tb/inv.txt
sdc_pin/inv.txt
```

脚本提供通用调度器 `run_cell.py` 所需的接口：

```python
CELL_ID = "inv"

def validate(inc, bench, n_va, p_va): ...
def generate_decks(inc, bench, n_va, p_va, output): ...
def run_and_analyze(source, output, **runner_options): ...
```

`CELL_ID`、文件名以及 `run_cell.py --cell inv` 必须一致。完整输入和运行方法见项目根目录的 `README_INV_TEST.md`。