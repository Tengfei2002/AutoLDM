* Gate 1: Fusion NMOS ID-VD, independent deck
.OPTION POST=2 PROBE INGOLD=2 MEASDGT=6
.TEMP 25
.HDL "../../va/fusion_ic_nmos_lvt.va"
.PARAM VDD=0.7 LCH=16n WDEV=25n NFDEV=1 VG=0.7
VDS d 0 DC 0
VGS g 0 DC 'VG'
VS s 0 0
VB b 0 0
XMN d g s b nmos_lvt L='LCH' W='WDEV' NF='NFDEV'
.DC VDS 0 'VDD' 1m
.PRINT DC V(d) V(g) I(VDS)
.END
