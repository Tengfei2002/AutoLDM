* Candidate RC repair validation: hold Q=1 only.
.OPTION POST=2 PROBE INGOLD=2 MEASDGT=6 METHOD=GEAR GSHUNT=1e-12
.TEMP 25
.INCLUDE "sram6t_rc_candidate.inc"
.PARAM VDD=0.7
VDD_SRC vdd 0 DC 'VDD'
VSS_SRC vss 0 DC 0
VBL bl_drv 0 DC 'VDD'
VBLB blb_drv 0 DC 'VDD'
RBL bl bl_drv 1G
RBLB blb blb_drv 1G
VWL wl 0 DC 0
CQ q 0 1f
CQB qb 0 1f
CBL bl 0 10f
CBLB blb 0 10f
XSRAM bl blb wl q qb vdd vss SRAM6T_RC_CAND
.IC V(q)='VDD' V(qb)=0 V(bl)='VDD' V(blb)='VDD'
.TRAN 0.1p 1n
.PRINT TRAN V(q) V(qb) V(bl) V(blb) V(wl) I(VDD_SRC)
.MEAS TRAN H1_QMIN MIN V(q) FROM=0.1n TO=1n
.MEAS TRAN H1_QBMAX MAX V(qb) FROM=0.1n TO=1n
.END
