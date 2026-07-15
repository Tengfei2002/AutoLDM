# 48 nm NMOS/PFET Verilog-A IV 校准汇总

## 1. 数据口径

`Hspice/.ref_iv` 中 CSV 第二列 Id 已按下式缩放：

```text
Id_scaled = Id_original / 0.44893 * 3.9E-5 / 0.156
scale = 5.568796917114e-04
```

缩放前数据备份在：

```text
Hspice/.ref_iv/backup_before_id_scale
```

缩放记录：

```text
Hspice/.ref_iv/id_scale_summary.md
```

## 2. NMOS 校准结果

参考曲线：

- `Hspice/.ref_iv/nfet_idvg_0_05V_48nm.csv`
- `Hspice/.ref_iv/nfet_idvg_0_70V_48nm.csv`

固定参数：

| 参数 | 数值 |
|---|---:|
| L | 1.600000000000e-08 |
| W | 2.500000000000e-08 |
| NF | 1 |
| EOT_0 | 7.900000000000e-10 |

校准参数：

| 参数 | 数值 |
|---|---:|
| U0 | 2.465126225809e-02 |
| XL | 4.677576751588e-09 |
| DVTSHIFT | 2.340310883015e-01 |
| DeltaWGAA | 2.048235619238e-09 |
| DeltaTGAA | 1.409403394487e-09 |

拟合质量：

| 指标 | 数值 |
|---|---:|
| loss | 0.172627 |
| log RMSE, all | 0.121531 decade |
| log RMSE, VD=0.05 V | 0.104598 decade |
| log RMSE, VD=0.70 V | 0.139844 decade |
| high-current relative RMSE, VD=0.05 V | 0.099713 |
| high-current relative RMSE, VD=0.70 V | 0.240922 |
| max absolute log error | 0.317546 decade |

![[nfet_48nm_dualvd_fit/figures/nfet_48nm_dualvd_fit.png]]

## 3. PFET 校准结果

参考曲线：

- `Hspice/.ref_iv/pfet_idvg_0_05V_48nm.csv`
- `Hspice/.ref_iv/pfet_idvg_0_70V_48nm.csv`

PFET 中 CSV 的负 `Vg` 直接作为 gate 电压；CSV 的 `VD=0.05/0.70 V` 按 `|VSD|` 解释，HSPICE 中使用 `Vd=-0.05/-0.70 V`，并以 `abs(I(Vd))` 与参考 Id 对比。

固定参数：

| 参数 | 数值 |
|---|---:|
| L | 1.600000000000e-08 |
| W | 2.500000000000e-08 |
| NF | 1 |
| EOT_0 | 7.600000000000e-10 |

校准参数：

| 参数 | 数值 |
|---|---:|
| U0 | 4.593370855865e-02 |
| XL | 2.724361157963e-08 |
| DVTSHIFT | 3.953451585888e-01 |
| DeltaWGAA | 6.394033645387e-09 |
| DeltaTGAA | -3.582191512312e-10 |

拟合质量：

| 指标 | 数值 |
|---|---:|
| loss | 0.290201 |
| log RMSE, all | 0.198310 decade |
| log RMSE, VD=0.05 V | 0.178595 decade |
| log RMSE, VD=0.70 V | 0.217662 decade |
| high-current relative RMSE, VD=0.05 V | 0.156282 |
| high-current relative RMSE, VD=0.70 V | 0.456323 |
| max absolute log error | 0.493820 decade |

PFET 的拟合精度低于 NMOS，主要误差来自低 `|Vg|` 端和 `|VSD|=0.70 V` 曲线。当前结果已完成 IV 校准闭环；若后续需要进一步降低 PFET 残差，应扩大可调参数集合或单独处理低电流端权重。

![[pfet_48nm_dualvd_fit/figures/pfet_48nm_dualvd_fit.png]]

## 4. 已覆盖的 VA 文件

已将校准后的 VA 副本覆盖到：

```text
Hspice/va/cfet_nmos_lvt.va
Hspice/va/cfet_pmos_lvt.va
```

覆盖前原文件已备份到：

```text
Hspice/va/backup_before_iv_calibration_20260713_192742
```

## 5. 详细输出目录

NMOS：

```text
Hspice/nfet_48nm_dualvd_fit
```

PFET：

```text
Hspice/pfet_48nm_dualvd_fit
```
