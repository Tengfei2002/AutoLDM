***********************************************************************
* CFET vs S2FET vs Near-Ideal (Topologically Consistent) Testbench
* 文件名: compare_perf.sp
***********************************************************************
.OPTION POST INGOLD=2 PROBE
.TEMP 25

* --- 1. Include Files ---
.hdl "va/fusion_ic_nmos_lvt.va"
.hdl "va/fusion_ic_pmos_lvt.va"
.INCLUDE "parasitics_wrapper.sp"

* --- 2. Parameters ---
.PARAM VDD_VAL = 0.7
.PARAM C_LOAD  = 1.0f  
.PARAM T_PER   = 200p
.PARAM T_RISE  = 10p

* --- 3. Voltage Sources ---
Vvdd_c     vdd_c 0 DC 'VDD_VAL'
Vvdd_s     vdd_s 0 DC 'VDD_VAL'
Vvdd_ideal vdd_i 0 DC 'VDD_VAL'
Vvss       vss   0 DC 0

* --- 4. Input Stimulus ---
Vin in_node 0 PULSE(0 'VDD_VAL' 20p 'T_RISE' 'T_RISE' 'T_PER/2-T_RISE' 'T_PER')

* --- 5. Circuit Instantiation ---
* (1) CFET Structure
Xinv_cfet  in_node out_c vdd_c vss CFET_INV
Cload_c    out_c   0     'C_LOAD'

* (2) S2FET Structure
Xinv_s2fet in_node out_s vdd_s vss S2FET_INV
Cload_s    out_s   0     'C_LOAD'

* (3) Near-Ideal Structure (Reference)
* Uses 1u Ohm resistors and 1zF capacitors
Xinv_ideal in_node out_i vdd_i vss IDEAL_INV
Cload_i    out_i   0     'C_LOAD'

* --- 6. Analysis ---
.TRAN 0.1p '5*T_PER'

* --- 7. Measurements ---

* [Delay Measurements]
* Ideal (Reference)
.MEAS TRAN Ideal_TpHL TRIG v(in_node) VAL='VDD_VAL*0.5' RISE=3 TARG v(out_i) VAL='VDD_VAL*0.5' FALL=3
.MEAS TRAN Ideal_TpLH TRIG v(in_node) VAL='VDD_VAL*0.5' FALL=3 TARG v(out_i) VAL='VDD_VAL*0.5' RISE=3
.MEAS TRAN Ideal_Delay PARAM='(Ideal_TpHL + Ideal_TpLH)/2'

* CFET
.MEAS TRAN CFET_TpHL TRIG v(in_node) VAL='VDD_VAL*0.5' RISE=3 TARG v(out_c) VAL='VDD_VAL*0.5' FALL=3
.MEAS TRAN CFET_TpLH TRIG v(in_node) VAL='VDD_VAL*0.5' FALL=3 TARG v(out_c) VAL='VDD_VAL*0.5' RISE=3
.MEAS TRAN CFET_Delay PARAM='(CFET_TpHL + CFET_TpLH)/2'

* S2FET
.MEAS TRAN S2FET_TpHL TRIG v(in_node) VAL='VDD_VAL*0.5' RISE=3 TARG v(out_s) VAL='VDD_VAL*0.5' FALL=3
.MEAS TRAN S2FET_TpLH TRIG v(in_node) VAL='VDD_VAL*0.5' FALL=3 TARG v(out_s) VAL='VDD_VAL*0.5' RISE=3
.MEAS TRAN S2FET_Delay PARAM='(S2FET_TpHL + S2FET_TpLH)/2'

* [RC Impact Analysis]
* Represents pure interconnect penalty
.MEAS TRAN CFET_Penalty_Pct  PARAM='(CFET_Delay - Ideal_Delay)/Ideal_Delay * 100'
.MEAS TRAN S2FET_Penalty_Pct PARAM='(S2FET_Delay - Ideal_Delay)/Ideal_Delay * 100'

* [Power & Energy]
* Ideal
.MEAS TRAN Ideal_Iavg AVG I(Vvdd_ideal) FROM='2*T_PER' TO='4*T_PER'
.MEAS TRAN Ideal_Pwr  PARAM='Ideal_Iavg * VDD_VAL'
.MEAS TRAN Ideal_PDP  PARAM='Ideal_Pwr * Ideal_Delay'

* CFET
.MEAS TRAN CFET_Iavg AVG I(Vvdd_c) FROM='2*T_PER' TO='4*T_PER'
.MEAS TRAN CFET_Pwr  PARAM='CFET_Iavg * VDD_VAL'
.MEAS TRAN CFET_PDP  PARAM='CFET_Pwr * CFET_Delay'

* S2FET
.MEAS TRAN S2FET_Iavg AVG I(Vvdd_s) FROM='2*T_PER' TO='4*T_PER'
.MEAS TRAN S2FET_Pwr  PARAM='S2FET_Iavg * VDD_VAL'
.MEAS TRAN S2FET_PDP  PARAM='S2FET_Pwr * S2FET_Delay'

* [Energy Overhead]
.MEAS TRAN CFET_Energy_Overhead_Pct PARAM='(CFET_PDP - Ideal_PDP)/Ideal_PDP * 100'
.MEAS TRAN S2FET_Energy_Overhead_Pct PARAM='(S2FET_PDP - Ideal_PDP)/Ideal_PDP * 100'

.END
