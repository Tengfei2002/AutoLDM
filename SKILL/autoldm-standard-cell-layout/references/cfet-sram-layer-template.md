# 已验证 SRAM 的 CFET 层模板

## 使用方法

当参考文件是 `FLOW/test/INPUT_MODEL/test_gds.txt` 时，按本文件理解层用途和坐标规律。生成目标单元前仍需运行 `layout_contract.py summarize`，避免参考文件变化后继续使用旧数值。

## 基准网格

- Boundary 基本分段宽度：`0.042 um`；
- Gate：宽 `0.012 um`，Y 长度 `0.040 um`；
- Gate X pitch：`0.042 um`；
- 参考 gate center：`0.021 + n*0.042 um`；
- 参考 S/D contact center：`0.000 + n*0.042 um`；
- Gate 与相邻 S/D contact center 的距离：`0.021 um`。

目标单元如果平移了原点，应同时平移 boundary、gate、MD/BMD、via 和 routing，不能只平移部分层。

## 层级约定

| 层 | 角色 | SRAM 中的有效模板 |
|---:|---|---|
| 1 | Boundary/domain | 42 nm 宽的正面积分段 |
| 7 | 共享 CFET gate | 12 nm × 40 nm，Y=`0.011–0.051` |
| 16 | 上层 MD | 宽 12 nm；S/D 或 gate 按节点需要延长到 Y=0.068 或电源侧 Y=-0.006 |
| 17 | MRW | 12 nm × 12 nm，Y=`0.056–0.068` |
| 18 | V0 | 10 nm × 10 nm，MD enclosure 1 nm |
| 19 | M0 | 外部/内部信号和 VSS rail |
| 51 | 下层 BMD | 宽 12 nm；PMOS S/D 与 gate landing |
| 52 | BV0 | 10 nm × 10 nm，BMD enclosure 1 nm |
| 53 | BM0 | VDD rail |

## 电源轨

SRAM 的电源轨不是源极处的局部方块：

```text
VSS L19: y=-0.011..0.011 um
VDD L53: y=-0.011..0.011 um
```

两条 rail 的有效高度均为 `0.022 um`。VSS 和 VDD 的 X 范围必须完全覆盖标准单元的有效图形范围：`x1` 等于全部正面积、非电源轨图形的最小 X，`x2` 等于这些图形的最大 X。电源轨允许超出 L1 cell boundary；零面积定位或元数据记录不参与最小/最大 X 计算。当前 SRAM 的有效范围为 `-0.006..0.174 um`。

V0/BV0 保持在源极接触列，rail 在 X 方向延长。不要把 MD/BMD 源极接触本身错误地扩展成整条 rail。

## 可复用的信号访问形状

- 外部 gate 类访问可参考 WL 的 V0/M0 位置；
- 内部 gate 或存储节点访问可参考 Q/QB 的 `y=0.037–0.049` M0 与 `y=0.038–0.048` V0；
- 上下层共享 S/D 节点可参考 Q/QB 的 MRW、V0 和 M0 组合；
- 位于边界附近的接触在 SRAM 中是允许形式，不能只因接近边界就判断为错误。

## 不应单独判为目标单元错误的项目

以下特征也存在于当前可生成 SRAM 中，因此不能仅凭这些特征否定目标版图：

- MRW gate 形式；
- 只使用 M0 的局部信号访问；
- gate、MD、BMD、V0 恰好采用参考中的最小尺寸；
- 没有 M1–M3 图形；
- 没有显式 device marker；
- 当前脚本范围内没有完整 foundry LVS、body tap 和 well 规则。

这些内容可以作为未来流程增强项，但不是相对于当前 SRAM 参考的版图生成失败条件。
