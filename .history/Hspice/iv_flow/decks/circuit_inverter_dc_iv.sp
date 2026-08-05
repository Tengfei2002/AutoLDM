***********************************************************************
* Inverter-level DC I-V / voltage-transfer sweep using parasitic wrappers
* Compares CFET_INV, S2FET_INV, and IDEAL_INV from parasitics_wrapper.sp.
* Run from this directory, or use ../run_iv.ps1
***********************************************************************
.OPTION POST=2 INGOLD=2 PROBE NOMOD
.TEMP 25

.hdl "../../va/cfet_nmos_lvt.va"
.hdl "../../va/cfet_pmos_lvt.va"
.INCLUDE "../../parasitics_wrapper.sp"

.PARAM VDD_VAL = 0.7
.PARAM VIN_STEP = 0.001

Vvdd_c     vdd_c 0 DC 'VDD_VAL'
Vvdd_s     vdd_s 0 DC 'VDD_VAL'
Vvdd_ideal vdd_i 0 DC 'VDD_VAL'
Vvss       vss   0 DC 0
Vin        in    0 DC 0

Xinv_cfet  in out_c vdd_c vss CFET_INV
Xinv_s2fet in out_s vdd_s vss S2FET_INV
Xinv_ideal in out_i vdd_i vss IDEAL_INV

* DC voltage transfer and static supply current.
.DC Vin 0 'VDD_VAL' 'VIN_STEP'

.PRINT DC V(in) V(out_c) V(out_s) V(out_i)
.PRINT DC I(Vvdd_c) I(Vvdd_s) I(Vvdd_ideal)
.PRINT DC PAR('-I(Vvdd_c)') PAR('-I(Vvdd_s)') PAR('-I(Vvdd_ideal)')

.MEAS DC CFET_VM  FIND V(in) WHEN V(out_c)='VDD_VAL/2'
.MEAS DC S2FET_VM FIND V(in) WHEN V(out_s)='VDD_VAL/2'
.MEAS DC IDEAL_VM FIND V(in) WHEN V(out_i)='VDD_VAL/2'

.END
