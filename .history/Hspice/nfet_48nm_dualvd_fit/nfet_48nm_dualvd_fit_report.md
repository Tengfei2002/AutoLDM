# 48 nm NFET 双 Vd 同参 Verilog-A 拟合报告

## 1. 目标与数据

本流程使用 `Hspice/.ref_iv` 中 48 nm NFET 的两条 Id-Vg 参考曲线，在同一套 Verilog-A 实例参数下同时拟合：

- VD=0.05 V：Vg=-0.104965–1.31515 V，Id(ref)=1.9337e-10–4.18826e-05
- VD=0.70 V：Vg=-0.116145–1.40754 V，Id(ref)=4.65129e-10–0.000535751

参考 CSV 的第二列 Id 已先按下式进行口径修正：

```text
Id_scaled = Id_original / 0.44893 * 3.9E-5 / 0.156
scale = 5.568796917114e-04
```

`.ref_iv/backup_before_id_scale/` 中保留了缩放前的 CSV 备份；`.ref_iv/id_scale_summary.md` 记录了全部文件的缩放前后范围。本报告中的参考曲线和拟合误差均基于缩放后的 Id。

## 2. 固定参数与优化参数

固定参数：

| 参数 | 数值 |
|---|---:|
| L | 1.600000000000e-08 |
| W | 2.500000000000e-08 |
| NF | 1 |
| EOT_0 | 7.900000000000e-10 |

优化参数：

| 参数 | 拟合值 |
|---|---:|
| U0 | 2.465126225809e-02 |
| XL | 4.677576751588e-09 |
| DVTSHIFT | 2.340310883015e-01 |
| DeltaWGAA | 2.048235619238e-09 |
| DeltaTGAA | 1.409403394487e-09 |

拟合后的 VA 文件：`cfet_nmos_lvt_48nm_dualvd_fit.va`。

## 3. 目标函数与计算方法

HSPICE 对同一个器件实例执行 `.DC Vg ... SWEEP Vd POI 2 0.05 0.70`。模型电流按参考 Vg 点插值后与 CSV 中的 Id 对比。主目标函数为两条曲线共同的 log-domain RMSE，并加入高电流区相对误差约束：

```text
log_error = log10(Id_model) - log10(Id_ref)
loss = RMSE(log_error_all)
       + 0.15 * RMSE(relative_error_high_current, VD=0.05)
       + 0.15 * RMSE(relative_error_high_current, VD=0.70)
```

采用 log-domain 的原因是 Id-Vg 曲线同时包含亚阈值区和强导通区，直接线性最小二乘会几乎只拟合大电流区。

## 4. 拟合结果

质量判定：**通过**。

该参数集满足当前质量门限，可作为后续 SRAM/电路仿真的候选模型。

| 指标 | 数值 |
|---|---:|
| loss | 0.172627 |
| log RMSE, all | 0.121531 decade |
| log RMSE, VD=0.05 V | 0.104598 decade |
| log RMSE, VD=0.70 V | 0.139844 decade |
| high-current relative RMSE, VD=0.05 V | 0.0997127 |
| high-current relative RMSE, VD=0.70 V | 0.240922 |
| max absolute log error | 0.317546 decade |

![[figures/nfet_48nm_dualvd_fit.png]]

![[figures/nfet_48nm_dualvd_log_residual.png]]

## 5. 输出文件

- `data/fit_summary.csv`：全部候选参数和误差。
- `data/best_fit_points.csv`：参考点、模型点、相对误差和 log 误差。
- `best_params.json`：最佳参数、固定参数和误差指标。
- `cfet_nmos_lvt_48nm_dualvd_fit.va`：已写入固定参数和拟合参数的 VA 文件副本。
- `figures/nfet_48nm_dualvd_fit.png/.svg`：参考曲线与拟合曲线，以及点误差。
- `figures/nfet_48nm_dualvd_log_residual.png/.svg`：log-domain 残差。
