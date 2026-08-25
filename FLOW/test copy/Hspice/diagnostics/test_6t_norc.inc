* Diagnostic reference: same 6T topology and device sizes, no extracted R/C.
.subckt TEST_6T_NORC BL BLB WL VDD VSS Q QB
XN1 BL  WL Q  VSS nmos_lvt L=1.6e-8 W=3.5e-8 NF=1
XN2 BLB WL QB VSS nmos_lvt L=1.6e-8 W=3.5e-8 NF=1
XN3 Q  QB VSS VSS nmos_lvt L=1.6e-8 W=3.5e-8 NF=1
XN4 QB Q  VSS VSS nmos_lvt L=1.6e-8 W=3.5e-8 NF=1
XP1 Q  QB VDD VDD pmos_lvt L=1.6e-8 W=3.5e-8 NF=1
XP2 QB Q  VDD VDD pmos_lvt L=1.6e-8 W=3.5e-8 NF=1
.ends TEST_6T_NORC
