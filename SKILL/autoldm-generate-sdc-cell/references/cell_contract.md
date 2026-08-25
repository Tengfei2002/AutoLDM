# AutoLDM标准单元三件套约定

## 当前目录

当前生成器支持30个单输出组合单元：

`inv`、`buf`、`nand2`、`nand3`、`nand4`、`nor2`、`nor3`、`nor4`、`and2`、`and3`、`and4`、`or2`、`or3`、`or4`、`aoi21`、`aoi22`、`aoi211`、`aoi221`、`oai21`、`oai22`、`oai211`、`oai221`、`xor2`、`xnor2`、`xor3`、`xnor3`、`mux2`、`muxi2`、`mux4`、`maj3`。

不包含DFF、latch、clock-gating、tristate或多输出单元，因为这些单元需要不同的状态、时钟或高阻测试框架。

## 文件职责

- `sdc_pin/<cell>.txt`定义R/C符号节点、FET端点和端口顺序，供后续矩阵映射和PEX使用。这里不是实际抽取RC数值。
- `sdc_pyscript/<cell>.py`单文件包含输入、真值表、显式时序弧、敏化条件、deck生成、HSPICE执行和结果解析。复制到其他INPUT_MODEL目录时不需要公共Python模块。
- `sdc_tb/<cell>.txt`定义供电、负载、输入边沿、仿真时长、DC步长和逻辑判定阈值。`vdd`、`vss`必须外部明确填写，其余项目可以由脚本默认值补齐。

## 增加新组合单元

在`Database/sdc/build_sdc_library.py`的`CELLS`中添加唯一记录：小写名称、输入端口元组、PDN导通表达式、分类和逻辑说明。PDN表达式描述输出应为0时下拉网络的导通条件，只允许使用已声明输入以及`~`、`&`、`|`。随后运行：

```powershell
python Database/sdc/build_sdc_library.py
python Database/sdc/build_sdc_library.py --check
```

生成器会计算真值表、构造互补静态CMOS网络、验证上下拉网络逻辑、计算显式时序敏化条件并生成三件套。不要只添加真值表而跳过晶体管网络验证。
