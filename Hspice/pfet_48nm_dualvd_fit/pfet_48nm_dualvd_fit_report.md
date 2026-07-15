# 48 nm PFET 双 Vd 同参 Verilog-A 拟合报告

## 数据与电压方向

参考文件：

- `Hspice/.ref_iv/pfet_idvg_0_05V_48nm.csv`
- `Hspice/.ref_iv/pfet_idvg_0_70V_48nm.csv`

参考 Id 已按 `.ref_iv/id_scale_summary.md` 中记录的公式缩放：

```text
Id_scaled = Id_original / 0.44893 * 3.9E-5 / 0.156
scale = 5.568796917114e-04
```

PFET 仿真中将 CSV 的负 `Vg` 直接作为 gate 电压；将 CSV 中的 `VD=0.05/0.70 V` 解释为 `|VSD|`，HSPICE 中分别使用 `Vd=-0.05/-0.70 V`，并用 `abs(I(Vd))` 与参考 Id 对比。

## 固定参数

| 参数 | 数值 |
|---|---:|
| L | 1.600000000000e-08 |
| W | 2.500000000000e-08 |
| NF | 1 |
| EOT_0 | 7.600000000000e-10 |

## 最佳可调参数

| 参数 | 拟合值 |
|---|---:|
| U0 | 4.593370855865e-02 |
| XL | 2.724361157963e-08 |
| DVTSHIFT | 3.953451585888e-01 |
| DeltaWGAA | 6.394033645387e-09 |
| DeltaTGAA | -3.582191512312e-10 |

## 拟合质量

| 指标 | 数值 |
|---|---:|
| loss | 0.290201 |
| log RMSE, all | 0.19831 decade |
| log RMSE, VD=0.05 V | 0.178595 decade |
| log RMSE, VD=0.70 V | 0.217662 decade |
| high-current relative RMSE, VD=0.05 V | 0.156282 |
| high-current relative RMSE, VD=0.70 V | 0.456323 |
| max absolute log error | 0.49382 decade |

![[figures/pfet_48nm_dualvd_fit.png]]

拟合后的 VA 文件副本：`cfet_pmos_lvt_48nm_dualvd_fit.va`。
