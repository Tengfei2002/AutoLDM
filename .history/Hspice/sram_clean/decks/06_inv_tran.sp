* Gate 2: Fusion CMOS inverter transient, independent deck
.OPTION POST=2 PROBE INGOLD=2 MEASDGT=6 METHOD=GEAR GSHUNT=1e-12
.TEMP 25
.HDL "../../va/fusion_ic_nmos_lvt.va"
.HDL "../../va/fusion_ic_pmos_lvt.va"
.PARAM VDD=0.7 LCH=16n WN=25n WP=25n NF=1 CLOAD=1f TR=20p PER=400p
VDD_SRC vdd 0 DC 'VDD'
VIN in 0 PULSE(0 'VDD' 100p 'TR' 'TR' 'PER/2-TR' 'PER')
RLEAK out 0 1G
CLOAD out 0 'CLOAD'
XMN out in 0 0 nmos_lvt L='LCH' W='WN' NF='NF'
XMP out in vdd vdd pmos_lvt L='LCH' W='WP' NF='NF'
.TRAN 0.1p 1.3n
.PRINT TRAN V(in) V(out) I(VDD_SRC)
.MEAS TRAN INV_TPHL TRIG V(in) VAL='VDD/2' RISE=2 TARG V(out) VAL='VDD/2' FALL=2
.MEAS TRAN INV_TPLH TRIG V(in) VAL='VDD/2' FALL=2 TARG V(out) VAL='VDD/2' RISE=2
.MEAS TRAN INV_IAVG AVG I(VDD_SRC) FROM=0.9n TO=1.3n
.END
