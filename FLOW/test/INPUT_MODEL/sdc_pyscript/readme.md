# 标准单元专用脚本

每个脚本使用标准单元名称命名：`<cell>.py`，并与以下文件对应：

```text
sdc_pyscript/<cell>.py
sdc_tb/<cell>.txt
sdc_pin/<cell>.txt
```

当前实现：

- `sram1.py`：6T SRAM 的 hold、read、write、write-trip、HSNM 和 RSNM；
- `inv.py`：CMOS 反相器的 DC 传输、瞬态延迟和两个输入状态的静态电流。

每个脚本必须提供以下接口：

```python
CELL_ID = "<cell>"

def validate(inc, bench, n_va, p_va): ...
def generate_decks(inc, bench, n_va, p_va, output): ...
def run_and_analyze(source, output, **runner_options): ...
```

`CELL_ID` 必须与文件名及 `run_cell.py --cell` 的值一致。完整调用说明见
`FLOW/test/README_HSPICE_FLOW.md`。
