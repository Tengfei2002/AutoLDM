* Diagnostic only: read0 with a finite-resistance, smooth-release state initializer.
.option INGOLD=2 POST=2
.hdl "../../INPUT_MODEL/test_fet_n.va"
.hdl "../../INPUT_MODEL/test_fet_p.va"
.include "test_6t_norc.inc"
.param VDD_VAL=0.7 VSS_VAL=0
.param VCORE='VDD_VAL-VSS_VAL'
.param CBL=30f RBL=100 RWL=100 CWL=5f TR=20p TSTEP=1p TSTOP=5n

VVSS VSS_SRC 0 'VSS_VAL'
VVDD VDD_SRC VSS_SRC 'VCORE'
RVDD VDD_SRC VDD 10
RVSS VSS VSS_SRC 10
CVDD VDD VSS 10f

VBLDRV BLPRE VSS_SRC 'VCORE'
VBLBDRV BLBPRE VSS_SRC 'VCORE'
RPREBL BLPRE BLF 1G
RPREBLB BLBPRE BLBF 1G
RBL0 BLF BL 'RBL'
RBLB0 BLBF BLB 'RBL'
CBL0 BLF VSS 'CBL'
CBLB0 BLBF VSS 'CBL'
VWLDRV WLDRV VSS_SRC PULSE(0 'VCORE' 1n 'TR' 'TR' 2n 'TSTOP')
RWL0 WLDRV WL 'RWL'
CWL0 WL VSS 'CWL'

* The 20 kohm paths set a deterministic state, then both move to mid-supply at 0.55 ns.
* They are only a simulator initialization aid and are inactive before the 1 ns read pulse.
VQINIT QINIT VSS_SRC PWL(0 0 0.5n 0 0.55n 'VCORE/2')
VQBINIT QBINIT VSS_SRC PWL(0 'VCORE' 0.5n 'VCORE' 0.55n 'VCORE/2')
RQINIT QINIT Q 20k
RQBINIT QBINIT QB 20k

XDUT BL BLB WL VDD VSS Q QB TEST_6T_NORC
.tran 'TSTEP' 'TSTOP'
.probe tran v(BL) v(BLB) v(WL) v(Q) v(QB) v(BLF) v(BLBF) i(VVDD)
.print tran v(BL) v(BLB) v(WL) v(Q) v(QB) v(BLF) v(BLBF) i(VVDD)
.end
