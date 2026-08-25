# 标准单元拓扑到 CFET 版图的规划

## 先确定晶体管网络

生成坐标前，先写出每只晶体管的 `S/G/D/B` 和外部端口。优先读取目标单元的 `sdc_pin/<cell>.txt`；如果该文件不存在，根据用户给出的逻辑功能制定网络，并把推导出的晶体管连接明确列出供检查。

不要先画矩形再推断器件连接。

## CFET 对齐条件

当前模板把上层 NMOS 和下层 PMOS 放在共享 gate column 中。只有满足以下条件时才能把两个器件放在同一列：

- 两只器件的 gate 是同一个逻辑信号；
- 对应 S/D column 的共享或分离方式能够表达两个网络；
- MD、BMD、MRW 与 routing 不会造成不同逻辑网络短接。

如果上下器件 gate 不同，不得为了减少面积强行共用一个 layer-7 gate。

## Gate 顺序

对于多输入 NAND、NOR、AOI、OAI 等单元：

1. 分别列出 NMOS pull-down 与 PMOS pull-up 网络；
2. 寻找能让两个网络同时减少 diffusion break 的输入排列；
3. 将输入按参考 gate pitch 放到 gate column；
4. 只有同一电气节点才能共享相邻晶体管之间的 S/D column；
5. 如果无法用当前单行结构表达，停止并说明需要 diffusion break、额外 boundary 分段或新层规则。

不要用相同标签掩盖两个不同电气节点。

## Boundary 与 S/D

参考 SRAM 中一个正面积 Boundary 分段对应一个 gate pitch。目标 boundary 覆盖的参考 tile 数应与功能 gate 数匹配，除非目标结构明确包含 dummy/reserved tile，并且当前生成器能够区分它。

`gen_sde.py` 会根据 boundary 和 gate/spacer 位置生成 S/D。过宽 boundary 中只有少量 gate 会形成异常宽的边缘 S/D，因此必须在生成前运行 reference contract 检查。

## 电源与信号

- VSS 使用前侧 M0 rail；
- VDD 使用背侧 BM0 rail；
- 源极通过局部 MD/BMD 和 V0/BV0 接到长 rail；
- A、B 等输入使用参考中已经存在的 gate-access 模板；
- Y 和内部节点使用参考中已经存在的 S/D、MRW、V0、M0 模板；
- pin 标签、FET 节点名、R/C matrix 接触名必须形成可检查的一一映射。

## 完成条件

对任何新单元，交付说明至少列出：

- 参考单元路径；
- 晶体管拓扑；
- gate 顺序和 tile 数；
- 每层新增图形的用途；
- VDD/VSS rail 范围；
- reference contract、SDE 和 GDS roundtrip 结果；
- 尚未执行的真实 LVS/RC 提取项目。
