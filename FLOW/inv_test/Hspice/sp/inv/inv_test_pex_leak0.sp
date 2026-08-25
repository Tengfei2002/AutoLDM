* Auto-generated inverter PEX test: leak0
.option INGOLD=2 POST=2
.hdl "../../../INPUT_MODEL/inv_test_fet_n.va"
.hdl "../../../INPUT_MODEL/inv_test_fet_p.va"
.include "../../inv_test_pex.inc"
.param VDD_VAL=0.7 VSS_VAL=0
.param VCORE='VDD_VAL-VSS_VAL'
.param CLOAD=5f TRISE=20p TFALL=20p TDELAY=500p PULSE_WIDTH=1n PERIOD=2n TSTEP=1p TSTOP=4n DC_STEP=1m LOGIC_LOW_MAX=0.2 LOGIC_HIGH_MIN=0.8
VVSS VSS 0 'VSS_VAL'
VVDD VDD VSS 'VCORE'

VA A VSS 0
CLOAD Y VSS 'CLOAD'
XDUT A Y VDD VSS INV_TEST_PEX
.tran 'TSTEP' 'TSTOP'
.measure tran IVDD_AVG AVG I(VVDD) FROM='TSTOP/2' TO='TSTOP'
.measure tran VOUT_AVG AVG V(Y) FROM='TSTOP/2' TO='TSTOP'
.print tran V(A) V(Y) I(VVDD)
.end
