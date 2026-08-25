* Auto-generated SRAM1 PEX test: hold
.option INGOLD=2 POST=2
.hdl "../../../INPUT_MODEL/test_fet_n.va"
.hdl "../../../INPUT_MODEL/test_fet_p.va"
.include "../test_6t_norc.inc"
.param VDD_VAL=0.7 VSS_VAL=0
.param VCORE='VDD_VAL-VSS_VAL'
.param CBL=30f RBL=100 RWL=100 RBL_DRV=100 CWL=5f RVDD=10 RVSS=10 CVDD=10f SENSE_V=0.05 TR=20p TSTEP=1p TSTOP=5n

VVSS VSS_SRC 0 'VSS_VAL'
VVDD VDD_SRC VSS_SRC 'VCORE'
RVDD VDD_SRC VDD 'RVDD'
RVSS VSS VSS_SRC 'RVSS'
CVDD VDD VSS 'CVDD'

VBLDRV BLF VSS_SRC 'VCORE'
VBLBDRV BLBF VSS_SRC 'VCORE'
RBL0 BLF BL 'RBL'
RBLB0 BLBF BLB 'RBL'
CBL0 BLF VSS 'CBL'
CBLB0 BLBF VSS 'CBL'
VWLDRV WLDRV VSS_SRC 0
RWL0 WLDRV WL 'RWL'
CWL0 WL VSS 'CWL'
XDUT BL BLB WL VDD VSS Q QB TEST_6T_NORC
.ic V(Q)=0 V(QB)='VCORE'
* 1 ps output interval prevents timing metrics from being quantized at 10 ps.
* Do not use UIC: establish a DC operating point before the transient run.
.tran 'TSTEP' 'TSTOP'
.probe tran v(BL) v(BLB) v(WL) v(Q) v(QB) v(BLF) v(BLBF) i(VVDD) i(VBLDRV) i(VBLBDRV) i(VWLDRV)
.print tran v(BL) v(BLB) v(WL) v(Q) v(QB) v(BLF) v(BLBF) i(VVDD) i(VBLDRV) i(VBLBDRV) i(VWLDRV)
.end
