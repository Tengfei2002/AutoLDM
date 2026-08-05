* ideal read noise-source RSNM q1
.OPTION POST=2 PROBE INGOLD=2 MEASDGT=6 METHOD=GEAR GSHUNT=1e-12
.TEMP 25
.INCLUDE "sram6t_ideal.inc"
.PARAM VDD=0.7
VDD_SRC vdd 0 DC 'VDD'
VSS_SRC vss 0 DC 0

VNOISE vn 0 DC 0
VBL bl 0 DC 'VDD'
VBLB blb 0 DC 'VDD'
VWL wl 0 DC 'VDD'
EGQB gqb 0 VOL='V(qb)+V(vn)'
EGQ gq 0 VOL='V(q)-V(vn)'
CQ q 0 1f
CQB qb 0 1f
CBL bl 0 10f
CBLB blb 0 10f

XPG1 bl wl q vss nmos_lvt L='LCH' W='WPG' NF='NF'
XPG2 blb wl qb vss nmos_lvt L='LCH' W='WPG' NF='NF'
XPD1 q gqb vss vss nmos_lvt L='LCH' W='WPD' NF='NF'
XPD2 qb gq vss vss nmos_lvt L='LCH' W='WPD' NF='NF'
XPU1 q gqb vdd vdd pmos_lvt L='LCH' W='WPU' NF='NF'
XPU2 qb gq vdd vdd pmos_lvt L='LCH' W='WPU' NF='NF'

.NODESET V(q)='VDD' V(qb)=0 V(bl)='VDD' V(blb)='VDD'
.DC VNOISE 0 0.5 0.001
.PRINT DC V(q) V(qb) V(gq) V(gqb) V(vn)
.END
