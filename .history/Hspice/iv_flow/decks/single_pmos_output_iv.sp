***********************************************************************
* Single PMOS output I-V sweep for cfet_pmos_lvt.va
* Run from this directory, or use ../run_iv.ps1
***********************************************************************
.OPTION POST=2 INGOLD=2 PROBE NOMOD
.TEMP 25

.hdl "../../va/cfet_pmos_lvt.va"

.PARAM LCH = 16n
.PARAM WP   = 35n
.PARAM NFP  = 1
.PARAM VMAX = 0.7
.PARAM VG_STEP = 0.05
.PARAM VD_STEP = 0.005

* Bias convention:
*   PMOS source/body are grounded.
*   VSG and VSD are swept by applying negative gate/drain voltages.
Vd d 0 DC 0
Vg g 0 DC 0
Vs s 0 DC 0
Vb b 0 DC 0

Xmp d g s b cfet_pmos_lvt L='LCH' W='WP' NF='NFP'

* Primary output curve: |Id| vs VSD at multiple VSG values.
.DC Vd 0 '-VMAX' '-VD_STEP' Vg 0 '-VMAX' '-VG_STEP'

* Columns include signed terminal current and positive-magnitude current.
.PRINT DC V(g) V(d) I(Vd) PAR('ABS(I(Vd))')

.END
