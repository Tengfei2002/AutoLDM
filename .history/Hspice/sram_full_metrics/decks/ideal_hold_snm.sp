* ideal hold butterfly dc
.OPTION POST=2 PROBE INGOLD=2 MEASDGT=6 METHOD=GEAR GSHUNT=1e-12
.TEMP 25
.INCLUDE "sram6t_ideal.inc"
.PARAM VDD=0.7
VDD_SRC vdd 0 DC 'VDD'
VSS_SRC vss 0 DC 0

VBL bl 0 DC 'VDD'
VBLB blb 0 DC 'VDD'
VWL wl 0 DC 0
VQ q 0 DC 0
CQB qb 0 1f
CBL bl 0 10f
CBLB blb 0 10f
XSRAM bl blb wl q qb vdd vss SRAM6T
.DC VQ 0 'VDD' 0.001
.PRINT DC V(q) V(qb)
.END
