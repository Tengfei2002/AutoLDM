* Shared topology only; no analysis, no sources, no ALTER.
.HDL "../../va/fusion_ic_nmos_lvt.va"
.HDL "../../va/fusion_ic_pmos_lvt.va"
.PARAM LCH=16n WPG=25n WPD=25n WPU=25n NF=1
.SUBCKT SRAM6T BL BLB WL Q QB VDD VSS
XPG1 BL WL Q VSS nmos_lvt L='LCH' W='WPG' NF='NF'
XPG2 BLB WL QB VSS nmos_lvt L='LCH' W='WPG' NF='NF'
XPD1 Q QB VSS VSS nmos_lvt L='LCH' W='WPD' NF='NF'
XPD2 QB Q VSS VSS nmos_lvt L='LCH' W='WPD' NF='NF'
XPU1 Q QB VDD VDD pmos_lvt L='LCH' W='WPU' NF='NF'
XPU2 QB Q VDD VDD pmos_lvt L='LCH' W='WPU' NF='NF'
.ENDS SRAM6T
