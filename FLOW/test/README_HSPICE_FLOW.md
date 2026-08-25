# AutoLDM：按标准单元名称执行 PEX 与 HSPICE 测试

本文说明 `FLOW/test` 中从 R/C matrix 到 PEX、标准单元测试 deck、HSPICE 执行和结果整理的本地流程。
SDE 建模、DRC 和远端寄生提取不在本文范围内。

## 一、当前设计

流程由两个通用脚本和一组标准单元专用输入组成：

```text
run_cell.py
├─ gen_pex.py
└─ INPUT_MODEL/
   ├─ sdc_pyscript/<cell>.py
   ├─ sdc_tb/<cell>.txt
   └─ sdc_pin/<cell>.txt
```

职责如下：

- `gen_pex.py`：读取 pin manifest、R/C matrix 和 N/P Verilog-A 模型，生成 pin-RC、PEX 子电路和 validation deck；
- `run_cell.py`：根据 `--cell` 解析三个同名单元文件，检查执行顺序并传播失败状态；
- `sdc_pyscript/<cell>.py`：定义该单元的端口、测试 deck、指标计算和通过条件；
- `sdc_tb/<cell>.txt`：定义该单元的供电、负载、时序和测量参数；
- `sdc_pin/<cell>.txt`：定义该单元的 R/C 请求、晶体管连接和 PEX 外部端口。

`gen_pex.py` 和 `run_cell.py` 不随标准单元更换。标准单元专用内容使用统一名称关联。

## 二、标准单元名称与文件路径

假设标准单元名称为 `inv`，对应文件固定为：

```text
INPUT_MODEL/sdc_pyscript/inv.py
INPUT_MODEL/sdc_tb/inv.txt
INPUT_MODEL/sdc_pin/inv.txt
```

执行参数为：

```text
--cell inv
```

`run_cell.py` 会自动解析上述三个路径。通常不需要分别传入 `--cell-script`、`--bench` 和 `--pin`。
这三个参数仍作为可选覆盖项保留，用于临时验证非标准路径中的文件。

单元名称必须以小写字母开头，只能包含小写字母、数字和下划线。脚本中的 `CELL_ID` 必须与文件名和
`--cell` 完全一致，否则流程停止。

### `CellType` 与 `NAME` 的区别

`CellType` 和 `NAME` 处理不同内容：

| 名称 | 用途 | 当前示例 |
|---|---|---|
| `CellType` | 选择 `<cell>.py`、`<cell>.txt` bench 和 `<cell>.txt` pin | `sram1` 或 `inv` |
| `NAME` | 当前工程前缀，用于 GDS、参数、R/C matrix、VA 模型和 PEX 输出名称 | `test` |

因此 pin 文件不再使用 `${NAME}_pin.txt`。它由 `CellType` 确定，例如 `sdc_pin/inv.txt`。
R/C matrix 仍属于本次工程和提取结果，当前仍按 `${NAME}_c_cMatrix.spi`、`${NAME}_r_cMatrix.spi` 读取。

## 三、当前标准单元文件

```text
INPUT_MODEL/
├─ sdc_pyscript/
│  ├─ sram1.py
│  ├─ inv.py
│  └─ readme.md
├─ sdc_tb/
│  ├─ sram1.txt
│  ├─ inv.txt
│  └─ README.md
└─ sdc_pin/
   ├─ sram1.txt
   ├─ inv.txt
   └─ README.md
```

原目录 `py_test4inc` 和 `test_bench` 已分别重命名为 `sdc_pyscript` 和 `sdc_tb`。
原 `INPUT_MODEL/test_pin.txt` 已迁移为 `INPUT_MODEL/sdc_pin/sram1.txt`。

## 四、SRAM1 专用实现

`INPUT_MODEL/sdc_pyscript/sram1.py` 要求 PEX 子电路端口为：

```text
BL BLB WL VDD VSS Q QB
```

它生成以下测试：

- smoke；
- hold；
- read0、read1；
- write0、write1；
- write-trip 0/1；
- HSNM；
- RSNM。

它读取 `INPUT_MODEL/sdc_tb/sram1.txt`，并使用 `INPUT_MODEL/sdc_pin/sram1.txt` 定义的 SRAM 晶体管连接和端口。

## 五、INV 专用实现

`INPUT_MODEL/sdc_pyscript/inv.py` 要求 PEX 子电路端口为：

```text
A Y VDD VSS
```

其中：

- `A`：输入；
- `Y`：反相输出；
- `VDD`：正电源；
- `VSS`：参考电源。

脚本生成四个 deck：

| deck | 内容 | 主要输出 |
|---|---|---|
| `dc` | 输入从 0 扫到 `VDD-VSS` | `VOH`、`VOL`、翻转点 `VM`、DC 功能判定 |
| `tran` | 输入脉冲包含一次上升和一次下降 | `TPHL`、`TPLH`、输出上升/下降时间 |
| `leak0` | 输入保持低电平 | 平均电源电流、输出平均电压、静态功耗 |
| `leak1` | 输入保持高电平 | 平均电源电流、输出平均电压、静态功耗 |

`INPUT_MODEL/sdc_tb/inv.txt` 当前定义：

- `vdd`、`vss`；
- 输出负载 `cload`；
- 输入上升/下降时间；
- 输入延迟、脉宽和周期；
- 瞬态步长、停止时间和 DC 扫描步长；
- 低电平最大比例和高电平最小比例。

`INPUT_MODEL/sdc_pin/inv.txt` 当前定义一个 NMOS 和一个 PMOS，并输出 `A/Y/VDD/VSS` 四端 PEX 子电路。
其中物理节点名称必须与反相器的 R/C matrix 一致。当前仓库没有 INV 专用 R/C matrix，因此现阶段可以验证
INV 脚本、bench、pin 语法和 deck 生成，但不能使用 SRAM matrix 完成 INV PEX 数值生成。

## 六、pin manifest 格式

每个 `sdc_pin/<cell>.txt` 包含四个段：

```text
(R){...}
R_<first>_<second>

(C){...}
C_<first>_<second>

(FET){...}{S,G,D,B}
<instance> S=<node> G=<node> D=<node> B=<node> ...

(PORT){...}
<port>=<physical_node>
```

规则如下：

1. `(R)` 和 `(C)` 中声明的节点必须能在对应 R/C matrix 中找到；
2. R/C 请求名称中的两个节点必须能根据声明唯一解析；
3. FET 实例名以 `N` 或 `P` 开头，用于选择 N/P Verilog-A 模块；
4. `S/G/D/B` 必须全部给出；
5. `(PORT)` 顺序决定 PEX `.subckt` 的端口顺序；
6. `(PORT)` 中每个端口必须映射到物理节点。

## 七、单元脚本接口

每个 `sdc_pyscript/<cell>.py` 必须提供：

```python
CELL_ID = "<cell>"

def validate(inc, bench, n_va, p_va):
    ...

def generate_decks(inc, bench, n_va, p_va, output):
    ...

def run_and_analyze(source, output, **runner_options):
    ...
```

接口要求：

- `validate` 检查 PEX 端口、bench 格式和模型文件；
- `generate_decks` 返回实际写出的 `.sp` 文件列表；
- `run_and_analyze` 执行 HSPICE、检查 listing、生成状态和指标文件，并用返回码表示成功或失败；
- HSPICE 返回 `0` 后仍需检查 listing 中的模型数值错误；
- 单元功能或时序判定失败时应返回非零值。

## 八、FLOW.cmd 调用

`FLOW/FLOW.cmd` 中只需要修改：

```powershell
$CellType = "sram1"
```

运行反相器时改为：

```powershell
$CellType = "inv"
```

本地阶段调用为：

```powershell
python "$ProjectRoot\run_cell.py" `
  --name "${env:NAME}" `
  --cell "$CellType" `
  --input-model-dir "$INPUTLocation" `
  --c-matrix "$SDELocation\${env:NAME}_c_cMatrix.spi" `
  --r-matrix "$SDELocation\${env:NAME}_r_cMatrix.spi" `
  --n-va "$INPUTLocation\${env:NAME}_fet_n.va" `
  --p-va "$INPUTLocation\${env:NAME}_fet_p.va" `
  --output "$HspiceLocation" `
  --strict-contact-face
```

`FLOW.cmd` 使用 PowerShell 语法。应在 PowerShell 中执行。

## 九、只运行本地阶段

在仓库根目录运行 SRAM1：

```powershell
python FLOW\test\run_cell.py `
  --name test `
  --cell sram1 `
  --input-model-dir FLOW\test\INPUT_MODEL `
  --c-matrix FLOW\test\SDE\test_c_cMatrix.spi `
  --r-matrix FLOW\test\SDE\test_r_cMatrix.spi `
  --n-va FLOW\test\INPUT_MODEL\test_fet_n.va `
  --p-va FLOW\test\INPUT_MODEL\test_fet_p.va `
  --output FLOW\test\Hspice `
  --strict-contact-face
```

只生成 PEX 和功能 deck：

```text
--generate-only
```

检查调度但不运行 HSPICE：

```text
--dry-run --no-plot
```

强制重新运行：

```text
--rerun
```

临时跳过 PEX validation：

```text
--skip-validation
```

## 十、输出目录

功能 deck 按标准单元隔离：

```text
Hspice/
├─ <name>_pin_spice.txt
├─ <name>_pex.inc
├─ <name>_pex_validate.sp
├─ sp/
│  ├─ sram1/
│  │  └─ <name>_pex_*.sp
│  └─ inv/
│     └─ <name>_pex_*.sp
└─ results/
   ├─ sram1/
   ├─ sram1_pex_validation/
   ├─ inv/
   └─ inv_pex_validation/
```

不同标准单元不会从同一个 `sp` 目录读取旧 deck。每次生成前，流程会删除当前 `sp/<cell>` 中已有的 `.sp` 文件，避免同一单元的旧测试 deck 被再次执行。

退出码：

| 退出码 | 含义 |
|---|---|
| `0` | 生成、validation 和功能测试成功 |
| `2` | 输入、路径、解析、PEX 或单元脚本生成失败 |
| `3` | PEX validation 失败 |
| `4` | 功能测试、模型数值检查或指标判定失败 |

## 十一、新增标准单元

以 `nand2` 为例，需要添加：

```text
INPUT_MODEL/sdc_pyscript/nand2.py
INPUT_MODEL/sdc_tb/nand2.txt
INPUT_MODEL/sdc_pin/nand2.txt
```

并准备与 `sdc_pin/nand2.txt` 物理节点名称一致的 NAND2 R/C matrix。然后执行：

```text
--cell nand2
```

不修改 `gen_pex.py` 和 `run_cell.py`。`FLOW.cmd` 只修改 `$CellType`。

## 十二、当前验证结果

本次改造已完成：

- `run_cell.py --help` 检查；
- Python 语法检查；
- `inv.py` 接口加载检查；
- `inv.txt` bench 解析检查；
- `inv.txt` pin manifest 语法检查；
- 使用临时最小 INV R/C matrix 完成 pin、PEX、validation deck 和四个功能 deck 生成；
- 完整 INV runner dry-run；
- matrix、pin、VA 和数值化 pin 文件的 UTF-8 BOM 兼容性检查；
- 三类同名文件路径解析检查。

INV 完整 PEX 数值生成和真实 HSPICE 仿真需要先生成 INV 专用 R/C matrix。


