* Gate 3B: ideal interconnect read Q=1
.OPTION POST=2 PROBE INGOLD=2 MEASDGT=6 METHOD=GEAR GSHUNT=1e-12
.TEMP 25
.INCLUDE "sram6t_ideal.inc"
.PARAM VDD=0.7
VDD_SRC vdd 0 DC 'VDD'
VSS_SRC vss 0 DC 0
VBL bl_drv 0 DC 'VDD'
VBLB blb_drv 0 DC 'VDD'
RBL bl bl_drv 10
RBLB blb blb_drv 10
VWL wl 0 PWL(0 0 0.2n 0 0.30n 'VDD' 0.80n 'VDD' 0.90n 0 1n 0)
CQ q 0 1f
CQB qb 0 1f
CBL bl 0 10f
CBLB blb 0 10f
XSRAM bl blb wl q qb vdd vss SRAM6T
.IC V(q)='VDD' V(qb)=0 V(bl)='VDD' V(blb)='VDD'
.TRAN 0.1p 1n
.PRINT TRAN V(q) V(qb) V(bl) V(blb) V(wl) I(VDD_SRC)
.MEAS TRAN R1_QMIN MIN V(q) FROM=0.30n TO=0.80n
.MEAS TRAN R1_QBMAX MAX V(qb) FROM=0.30n TO=0.80n
.END
