* Gate 1: Fusion PMOS ID-VG, source at VDD, independent deck
.OPTION POST=2 PROBE INGOLD=2 MEASDGT=6
.TEMP 25
.HDL "../../va/fusion_ic_pmos_lvt.va"
.PARAM VDD=0.7 LCH=16n WDEV=25n NFDEV=1 VD=0
VSS s 0 DC 'VDD'
VDS d 0 DC 'VD'
VGS g 0 DC 0
VB b 0 DC 'VDD'
XMP d g s b pmos_lvt L='LCH' W='WDEV' NF='NFDEV'
.DC VGS 0 'VDD' 1m
.PRINT DC V(g) V(d) V(s) I(VDS)
.END
