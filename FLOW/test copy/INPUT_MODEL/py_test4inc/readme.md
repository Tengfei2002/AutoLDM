# 6T SRAM PEX 统一比较流程

在 `FLOW/test` 下运行：

```powershell
py INPUT_MODEL\py_test4inc\gen_sram1_sp.py Hspice\test_pex.inc INPUT_MODEL\test_bench\sram1.txt INPUT_MODEL\test_fet_n.va INPUT_MODEL\test_fet_p.va -o Hspice\sp
py INPUT_MODEL\py_test4inc\run_sram1_sp.py Hspice\sp -o Hspice\results\sram1
```

`sram1.txt` 是所有待比较 SRAM 结构共用的测试边界。每个结构只替换自己的 PEX `.inc`；不得改变 VDD、阵列 RC、驱动、时序和判据。

## bench 参数

| 区段 | 参数 | 含义 |
|---|---|---|
| `SUPPLY` | `vdd`、`vss` | 名义电源。当前 VA 温度固定为 300 K，不进行温度扫描。 |
| `ARRAY` | `cbl`、`rbl` | 被选单元到列端的等效位线电容与电阻。 |
| `ARRAY` | `rwl`、`cwl` | WL driver 到单元 WL 端的等效电阻与负载电容。 |
| `ARRAY` | `rbl_drv` | 写入 BL/BLB 驱动电阻。 |
| `ARRAY` | `rvdd`、`rvss`、`cvdd` | 局部供电 RC。 |
| `TIMING` | `tr`、`tstep`、`tstop` | WL 边沿、最大输出步长和仿真时间。 |
| `MEASURE` | `sense_v` | 读判定阈值 `V(BLBF)-V(BLF)`。 |

这些值是结果定义的一部分。比较两个结构时必须完全相同，并在图表标题或结果表中记录。

## 生成的测试

| deck | 指标 |
|---|---|
| `smoke` | PEX/VA 编译和工作点。 |
| `hold` | 保持状态、统一测试边界下的总静态功耗。 |
| `read0`、`read1` | 两种存储状态下的读延迟、位线差分、读扰动、读通过状态和 active energy。 |
| `write0`、`write1` | 两种写入方向的写延迟、写通过状态和 active energy。 |
| `wtrip0`、`wtrip1` | DC write-trip bitline voltage 与 write-trip margin。它是写静态鲁棒性指标，不与 WSNM 混称。 |
| `hsnm`、`hsnm_qb` | 两支独立保持 VTC，后处理为 HSNM。 |
| `rsnm`、`rsnm_qb` | 两支独立读模式 VTC，后处理为 RSNM。 |

读 deck 使用 `CBL/RBL/RWL` 等效阵列边界；写 deck 使用同一 CBL/RBL 和 `RBL_DRV`。因此读写时间、功耗和扰动可用于同一条件下的结构比较，但不是未声明阵列规模的“本征单元指标”。

## 有效性规则

运行器将以下 deck 标为 `model_numerical_error`，并且不写入标量指标或科研图：

- HSPICE 返回非零；
- `.lis` 中出现 `numerical NaN` 或 `FPE`；
- 缺少预期的 `.print` 数据表。

当前 Fusion NMOS VA 在访问管的部分正常偏置下仍可能出现 NaN。因此只有 `analysis_status=ok` 的结果可以进入跨结构表格；`model_numerical_error` 是模型待修复项，不能用零值或旧图替代。

## 输出

| 路径 | 内容 |
|---|---|
| `raw/<deck>/` | 原始 HSPICE listing、波形和标准输出，用于追溯数值问题。 |
| `data/<deck>.csv` | 瞬态或 DC 原始数据。瞬态 CSV 包含单元端和列端 BL/BLB、电源电流、总驱动源功率及能量。 |
| `data/summary_metrics.csv` | 可用于结构比较的标量指标；必须筛选 `analysis_status=ok`。 |
| `figures/*.png`、`figures/*.svg` | 有效 deck 的波形、读位线差分和 HSNM/RSNM butterfly 图。 |
| `run_status.csv` | 每个 deck 的返回码、NaN/FPE 标记和输出位置。 |

## 图表与比较

建议每个结构报告：面积、提取 BL/WL/VDD/VSS RC、HSNM、RSNM、write-trip、读/写延迟、读/写 active energy、读扰动、保持功耗和 Vmin。Vmin 仅在读、写、RSNM 和 write-trip 都为有效通过结果时定义；当前 VA 有 NaN 时，Vmin 必须报告为不可判定。

不要做同一结构“有/无 RC”对照。每种结构直接使用自己的完整 PEX，在同一 `sram1.txt` 条件下比较即可；若器件尺寸或模型不同，结论应表述为整体结构性能，而不能单独归因于 RC。
