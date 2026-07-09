***********************************************************************
* Single Verilog-A NMOS Id-Vd sweep family for cfet_nmos_lvt.va.
* Outputs are intended to be plotted by plot_hspice_results.py.
*
* PLOT_FAMILY single_va
* PLOT_DEVICE nmos
* PLOT_KIND idvd
* PLOT_VARIANTS L16_W25 L16_W15 L16_W35 L24_W25
* PLOT_CURVES VGS=0.35 VGS=0.50 VGS=0.70
***********************************************************************
.OPTION POST=2 INGOLD=2 PROBE NOMOD
.TEMP 25

.HDL "../va/cfet_nmos_lvt.va"

.PARAM VMAX = 0.7
.PARAM VD_STEP = 0.002
.PARAM LCH = 16n
.PARAM WDEV = 25n
.PARAM NFDEV = 1

Vd d 0 DC 0
Vg g 0 DC 0
Vs s 0 DC 0
Vb b 0 DC 0

Xmn d g s b cfet_nmos_lvt L='LCH' W='WDEV' NF='NFDEV'

.DC Vd 0 'VMAX' 'VD_STEP' SWEEP Vg POI 3 0.35 0.50 0.70
.PRINT DC V(g) V(d) I(Vd) PAR('-I(Vd)')

.ALTER L16_W15
.PARAM LCH=16n WDEV=15n

.ALTER L16_W35
.PARAM LCH=16n WDEV=35n

.ALTER L24_W25
.PARAM LCH=24n WDEV=25n

.END
