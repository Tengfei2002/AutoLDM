AutoLDM minimal generated-include validation
.option INGOLD=2
.hdl "../INPUT_MODEL/inv_test_fet_n.va"
.hdl "../INPUT_MODEL/inv_test_fet_p.va"
.include "inv_test_pex.inc"

* Every external port is clamped to 0 V for a topology/VA compile smoke test.
VVALIDATE_1 VALIDATE_PORT_1 0 0 $ A
VVALIDATE_2 VALIDATE_PORT_2 0 0 $ Y
VVALIDATE_3 VALIDATE_PORT_3 0 0 $ VDD
VVALIDATE_4 VALIDATE_PORT_4 0 0 $ VSS
XVALIDATE VALIDATE_PORT_1 VALIDATE_PORT_2 VALIDATE_PORT_3 VALIDATE_PORT_4 INV_TEST_PEX
.op
.end
