* ideal read transient q=1
.OPTION POST=2 PROBE INGOLD=2 MEASDGT=6 METHOD=GEAR GSHUNT=1e-12
.TEMP 25
.INCLUDE "sram6t_ideal.inc"
.PARAM VDD=0.7
VDD_SRC vdd 0 DC 'VDD'
VSS_SRC vss 0 DC 0

VBLDRV bl_drv 0 DC 'VDD'
VBLBDRV blb_drv 0 DC 'VDD'
RBL bl bl_drv 1G
RBLB blb blb_drv 1G
VWL wl 0 PWL(0 0 0.10n 0 0.20n 'VDD' 1.20n 'VDD')
CQ q 0 1f
CQB qb 0 1f
CBL bl 0 10f
CBLB blb 0 10f
XSRAM bl blb wl q qb vdd vss SRAM6T
.IC V(q)='VDD' V(qb)=0 V(bl)='VDD' V(blb)='VDD'
.TRAN 0.2p 1.2n
.PRINT TRAN V(q) V(qb) V(bl) V(blb)
.PRINT TRAN V(wl) I(VDD_SRC)
.MEAS TRAN Q_LOW_MAX MAX V(qb) FROM=0.20n TO=1.20n
.MEAS TRAN Q_HIGH_MIN MIN V(q) FROM=0.20n TO=1.20n
.END
