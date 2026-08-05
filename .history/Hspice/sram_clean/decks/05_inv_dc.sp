* Gate 2: Fusion CMOS inverter DC transfer, independent deck
.OPTION POST=2 PROBE INGOLD=2 MEASDGT=6
.TEMP 25
.HDL "../../va/fusion_ic_nmos_lvt.va"
.HDL "../../va/fusion_ic_pmos_lvt.va"
.PARAM VDD=0.7 LCH=16n WN=25n WP=25n NF=1
VDD_SRC vdd 0 DC 'VDD'
VIN in 0 DC 0
RLEAK out 0 1G
XMN out in 0 0 nmos_lvt L='LCH' W='WN' NF='NF'
XMP out in vdd vdd pmos_lvt L='LCH' W='WP' NF='NF'
.DC VIN 0 'VDD' 1m
.PRINT DC V(in) V(out) I(VDD_SRC)
.END
