* Gate 4C: extracted-RC SRAM write Q=1 from Q=0
.OPTION POST=2 PROBE INGOLD=2 MEASDGT=6 METHOD=GEAR GSHUNT=1e-12
.TEMP 25
.INCLUDE "sram6t_rc.inc"
.PARAM VDD=0.7
VDD_SRC vdd 0 DC 'VDD'
VSS_SRC vss 0 DC 0
VBL bl_drv 0 DC 'VDD'
VBLB blb_drv 0 PWL(0 'VDD' 0.2n 'VDD' 0.22n 0 0.82n 0 0.90n 'VDD' 1n 'VDD')
RBL bl bl_drv 10
RBLB blb blb_drv 10
VWL wl 0 PWL(0 0 0.2n 0 0.22n 'VDD' 0.82n 'VDD' 0.90n 0 1n 0)
CQ q 0 1f
CQB qb 0 1f
CBL bl 0 10f
CBLB blb 0 10f
XSRAM bl blb wl q qb vdd vss SRAM6T_RC
.IC V(q)=0 V(qb)='VDD' V(bl)='VDD' V(blb)='VDD'
.TRAN 0.1p 1n
.PRINT TRAN V(q) V(qb) V(bl) V(blb) V(wl) I(VDD_SRC)
.MEAS TRAN W1_QFINAL FIND V(q) AT=0.95n
.MEAS TRAN W1_QBFINAL FIND V(qb) AT=0.95n
.END
