***********************************************************************
* Single NMOS output I-V sweep for cfet_nmos_lvt.va
* Run from this directory, or use ../run_iv.ps1
***********************************************************************
.OPTION POST=2 INGOLD=2 PROBE NOMOD
.TEMP 25

.hdl "../../va/cfet_nmos_lvt.va"

.PARAM LCH = 16n
.PARAM WN   = 35n
.PARAM NFN  = 1
.PARAM VMAX = 0.7
.PARAM VG_STEP = 0.05
.PARAM VD_STEP = 0.005

* Bias convention:
*   NMOS source/body are grounded.
*   VGS is swept by Vg, VDS is swept by Vd.
Vd d 0 DC 0
Vg g 0 DC 0
Vs s 0 DC 0
Vb b 0 DC 0

Xmn d g s b cfet_nmos_lvt L='LCH' W='WN' NF='NFN'

* Primary output curve: Ids vs Vds at multiple Vgs values.
.DC Vd 0 'VMAX' 'VD_STEP' Vg 0 'VMAX' 'VG_STEP'

* HSPICE current through a voltage source is defined into its positive
* terminal. For this drain supply, conventional NMOS Id is -I(Vd).
.PRINT DC V(g) V(d) I(Vd) PAR('-I(Vd)')

.END
