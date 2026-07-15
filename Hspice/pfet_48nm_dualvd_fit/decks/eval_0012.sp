***********************************************************************
* 48 nm PFET dual-Vd Id-Vg fitting deck: eval_0012
* CSV Vg is treated as negative gate voltage; CSV VD is treated as positive |VSD|.
***********************************************************************
.OPTION POST=2 INGOLD=2 PROBE NOMOD
.TEMP 25

.HDL "../../va/cfet_pmos_lvt.va"

.PARAM LCH = 1.600000000000e-08
.PARAM WDEV = 2.500000000000e-08
.PARAM NFDEV = 1.000000000000e+00
.PARAM EOTFIX = 7.600000000000e-10

Vd d 0 DC 0
Vg g 0 DC 0
Vs s 0 DC 0
Vb b 0 DC 0

Xmp d g s b cfet_pmos_lvt
+ L='LCH' W='WDEV' NF='NFDEV'
+ U0=1.722052989872e-01 XL=2.754983838939e-09 DVTSHIFT=2.772386381853e-01
+ DeltaWGAA=3.052178387814e-09 DeltaTGAA=1.436636127968e-10
+ EOT_0='EOTFIX'

.DC Vg POI 25 -1.31329 -1.3071 -1.21472 -1.20307 -1.11613 -1.1045 -1.01206 -1.00595 -0.90796 -0.901856 -0.803856 -0.797764 -0.710636 -0.704609 -0.600914 -0.594943 -0.501987 -0.501645 -0.402695 -0.397431 -0.298205 -0.298007 -0.198594 -0.19355 -0.099181 SWEEP Vd POI 2 -0.05 -0.70
.PRINT DC V(g) V(d) I(Vd) PAR('ABS(I(Vd))')

.END
