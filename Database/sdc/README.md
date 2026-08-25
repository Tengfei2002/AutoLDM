# AutoLDM 组合标准单元支持库

本目录提供 30 个单输出组合标准单元的 pin manifest、testbench 参数和 HSPICE 适配脚本。
每个单元都由 `build_sdc_library.py` 生成独立 `TEST_PLAN`：包括穷举功能状态、显式时序弧、敏化条件和可选 DC 扫描。

## 与 TSMC 公开资料的关系

TSMC 的公开说明确认 Foundation IP 包含 high-density 和 high-performance 标准单元库，
但没有公开原厂完整单元清单、晶体管连接、版图坐标或特征化数据。本目录不是 TSMC 原厂库，
也不包含 TSMC PDK 数据；这里只参考公开说明中的库分类，建立适用于 AutoLDM 的常用逻辑单元集合。

官方资料：

- https://pr.tsmc.com/system/files/newspdf/THPGWQTHTH/NEWS_FILE_EN.pdf
- https://pr.tsmc.com/english/news/1224

## 文件关系

```text
catalog.json                    机器可读单元目录、真值表和器件数量
sdc_pin/<cell>.txt              R/C/FET/PORT 完整节点约定
sdc_tb/<cell>.txt               供电、负载、时序和判定阈值
sdc_pyscript/<cell>.py          完整独立脚本：单元规则、deck、HSPICE运行和结果分析
cell_runtime.py.inc             仅供生成器嵌入独立脚本，不是运行时依赖
build_sdc_library.py            确定性生成和静态检查入口
```

## 单元目录

| 单元 | 类别 | 输入 | 功能 | 测试策略 | 时序弧 | 晶体管数 |
|---|---|---|---|---|---:|---:|
| `inv` | basic | A | `Y = !A` | `inverter` | 1 | 2 |
| `buf` | basic | A | `Y = A` | `buffer` | 1 | 4 |
| `nand2` | basic | A,B | `Y = !(A & B)` | `static_unate` | 2 | 4 |
| `nand3` | basic | A,B,C | `Y = !(A & B & C)` | `static_unate` | 3 | 6 |
| `nand4` | basic | A,B,C,D | `Y = !(A & B & C & D)` | `static_unate` | 4 | 8 |
| `nor2` | basic | A,B | `Y = !(A | B)` | `static_unate` | 2 | 4 |
| `nor3` | basic | A,B,C | `Y = !(A | B | C)` | `static_unate` | 3 | 6 |
| `nor4` | basic | A,B,C,D | `Y = !(A | B | C | D)` | `static_unate` | 4 | 8 |
| `and2` | basic | A,B | `Y = A & B` | `static_unate` | 2 | 8 |
| `and3` | basic | A,B,C | `Y = A & B & C` | `static_unate` | 3 | 12 |
| `and4` | basic | A,B,C,D | `Y = A & B & C & D` | `static_unate` | 4 | 16 |
| `or2` | basic | A,B | `Y = A | B` | `static_unate` | 2 | 8 |
| `or3` | basic | A,B,C | `Y = A | B | C` | `static_unate` | 3 | 12 |
| `or4` | basic | A,B,C,D | `Y = A | B | C | D` | `static_unate` | 4 | 16 |
| `aoi21` | compound | A,B,C | `Y = !((A & B) | C)` | `compound_unate` | 4 | 6 |
| `aoi22` | compound | A,B,C,D | `Y = !((A & B) | (C & D))` | `compound_unate` | 8 | 8 |
| `aoi211` | compound | A,B,C,D | `Y = !((A & B) | C | D)` | `compound_unate` | 6 | 8 |
| `aoi221` | compound | A,B,C,D,E | `Y = !((A & B) | (C & D) | E)` | `compound_unate` | 12 | 10 |
| `oai21` | compound | A,B,C | `Y = !((A | B) & C)` | `compound_unate` | 4 | 6 |
| `oai22` | compound | A,B,C,D | `Y = !((A | B) & (C | D))` | `compound_unate` | 8 | 8 |
| `oai211` | compound | A,B,C,D | `Y = !((A | B) & C & D)` | `compound_unate` | 6 | 8 |
| `oai221` | compound | A,B,C,D,E | `Y = !((A | B) & (C | D) & E)` | `compound_unate` | 12 | 10 |
| `xor2` | arithmetic | A,B | `Y = A ^ B` | `non_unate` | 4 | 12 |
| `xnor2` | arithmetic | A,B | `Y = !(A ^ B)` | `non_unate` | 4 | 12 |
| `xor3` | arithmetic | A,B,C | `Y = A ^ B ^ C` | `non_unate` | 12 | 30 |
| `xnor3` | arithmetic | A,B,C | `Y = !(A ^ B ^ C)` | `non_unate` | 12 | 30 |
| `mux2` | mux | A,B,S | `Y = S ? B : A` | `mux` | 4 | 14 |
| `muxi2` | mux | A,B,S | `Y = !(S ? B : A)` | `mux` | 4 | 10 |
| `mux4` | mux | D0,D1,D2,D3,S0,S1 | `Y = D[S1:S0]` | `mux` | 12 | 36 |
| `maj3` | arithmetic | A,B,C | `Y = majority(A,B,C)` | `threshold` | 6 | 18 |

## 生成和检查

```powershell
python Database/sdc/build_sdc_library.py
python Database/sdc/build_sdc_library.py --check
python Database/sdc/build_sdc_library.py --cell mux4 --output-root <INPUT_MODEL目录>
python SKILL/autoldm-generate-sdc-cell/scripts/generate_cell.py --cell mux4 --output-root <INPUT_MODEL目录>
```

最后一条Skill命令还会检查独立导入、接口、deck数量和dry-run结果收集；目标已存在且确认需要替换时增加 `--force`。
选择单元时，`--cell <cell>`、三个同名单元文件和未来对应版图的物理节点标签必须一致。
当前检查能证明目录、逻辑表达式、真值表、manifest、显式时序弧及 deck 生成自洽；只有生成匹配版图和 R/C matrix 后，
才能执行 PEX/HSPICE。这里的内容不代表 foundry signoff、真实 RC 或 TSMC 特征化结果。
