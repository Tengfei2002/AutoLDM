***********************************************************************
* NMOS Id-Vg fitting candidate fit_c029
* W and L are fixed. Other instance parameters are swept.
***********************************************************************
.OPTION POST=2 INGOLD=2 PROBE NOMOD
.TEMP 25

.HDL "../../../va/cfet_nmos_lvt.va"

.PARAM VMAX = 1
.PARAM VG_STEP = 0.002
.PARAM LCH = 1.600000e-08
.PARAM WDEV = 2.500000e-08
.PARAM NFDEV = 1

Vd d 0 DC 0
Vg g 0 DC 0
Vs s 0 DC 0
Vb b 0 DC 0

Xmn d g s b cfet_nmos_lvt
+ L='LCH' W='WDEV' NF='NFDEV'
+ U0=2.00000000e-02 XL=1.20000000e-08 DVTSHIFT=4.00000000e-02
+ DeltaWGAA=0.00000000e+00 DeltaTGAA=0.00000000e+00
+ EOT_0=9.00000000e-10

.DC Vg 0 'VMAX' 'VG_STEP' SWEEP Vd POI 1 0.05
.PRINT DC V(g) V(d) I(Vd) PAR('-I(Vd)')

.END
