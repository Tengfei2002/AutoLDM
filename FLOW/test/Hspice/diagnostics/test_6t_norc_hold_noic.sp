* Diagnostic only: no PEX RC and no .ic initial condition.
.option post=2 nomod brief
.option runlvl=5
.hdl ../../INPUT_MODEL/test_fet_n.va
.hdl ../../INPUT_MODEL/test_fet_p.va
.include test_6t_norc.inc

VVSS VSS 0 0
VVDD VDD VSS 0.7
VBL BL VSS 0.7
VBLB BLB VSS 0.7
VWL WL VSS 0

XDUT BL BLB WL VDD VSS Q QB TEST_6T_NORC

.tran 1p 5n
.probe tran v(Q) v(QB) i(VVDD)
.end
