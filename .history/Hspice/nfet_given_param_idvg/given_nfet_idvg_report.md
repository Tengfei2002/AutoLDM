# 指定 NFET 参数的 Id-Vg HSPICE 仿真

## 参数

| 参数 | 数值 |
|---|---:|
| L | 1.600000000000e-08 |
| W | 3.500000000000e-08 |
| NF | 1 |
| U0 | 3.000000000000e-02 |
| XL | 1.200000000000e-08 |
| DVTSHIFT | 0.000000000000e+00 |
| DeltaWGAA | 0.000000000000e+00 |
| DeltaTGAA | 0.000000000000e+00 |
| EOT_0 | 1.100000000000e-09 |

## 仿真设置

- VA 模型：`Hspice/va/cfet_nmos_lvt.va`
- 温度：25 °C
- 扫描：`.DC Vg POI ... SWEEP Vd POI 2 0.05 0.70`
- Vg 范围：-0.12 V 到 1.42 V
- 输出电流：`Id = abs(-I(Vd))`

## 曲线

![[figures/given_nfet_idvg.png]]

![[figures/given_nfet_idvg_linear.png]]

## 输出文件

- `data/given_nfet_idvg.csv`：完整 Id-Vg 数据。
- `data/given_nfet_idvg_key_points.csv`：关键 Vg 采样点。
- `figures/given_nfet_idvg.png/.svg`：log 坐标 Id-Vg，并叠加 48nm 参考点。
- `figures/given_nfet_idvg_linear.png/.svg`：线性坐标 Id-Vg。
