* Gate 1: Fusion NMOS ID-VG, independent deck
.OPTION POST=2 PROBE INGOLD=2 MEASDGT=6
.TEMP 25
.HDL "../../va/fusion_ic_nmos_lvt.va"
.PARAM VDD=0.7 LCH=16n WDEV=25n NFDEV=1 VD=0.7
VDS d 0 DC 'VD'
VGS g 0 DC 0
VS s 0 0
VB b 0 0
XMN d g s b nmos_lvt L='LCH' W='WDEV' NF='NFDEV'
.DC VGS 0 'VDD' 1m
.PRINT DC V(g) V(d) V(s) I(VDS)
.END
