* Auto-generated SRAM1 PEX test: write1
.option INGOLD=2 POST=2
.hdl "../../INPUT_MODEL/test_fet_n.va"
.hdl "../../INPUT_MODEL/test_fet_p.va"
.include "../test_pex.inc"
.param VDD_VAL=0.7 VSS_VAL=0
.param VCORE='VDD_VAL-VSS_VAL' TR=20p TSTOP=10n

VVSS VSS 0 'VSS_VAL'
VVDD VDD VSS 'VCORE'

VBL BL VSS 'VCORE'
VBLB BLB VSS 0
VWL WL VSS PULSE(0 'VCORE' 1n 'TR' 'TR' 2n 'TSTOP')
XDUT BL BLB WL VDD VSS Q QB TEST_PEX
.ic V(Q)=0 V(QB)='VCORE'
.tran 10p 'TSTOP' UIC
.probe tran v(BL) v(BLB) v(WL) v(Q) v(QB) i(VVDD)
.end