* ideal write trip dc
.OPTION POST=2 PROBE INGOLD=2 MEASDGT=6 METHOD=GEAR GSHUNT=1e-12
.TEMP 25
.INCLUDE "sram6t_ideal.inc"
.PARAM VDD=0.7
VDD_SRC vdd 0 DC 'VDD'
VSS_SRC vss 0 DC 0

VBLDRV bl 0 DC 'VDD'
VBLBDRV blb 0 DC 'VDD'
VWL wl 0 DC 'VDD'
CQ q 0 1f
CQB qb 0 1f
CBL bl 0 10f
CBLB blb 0 10f
XSRAM bl blb wl q qb vdd vss SRAM6T
.NODESET V(q)='VDD' V(qb)=0
.DC VBLDRV 'VDD' 0 -0.001
.PRINT DC V(bl) V(q) V(qb)
.END
