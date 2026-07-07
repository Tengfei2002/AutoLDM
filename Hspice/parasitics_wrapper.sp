* ===================================================================
* Subcircuit 1: CFET Inverter Wrapper
* ===================================================================
.SUBCKT CFET_INV IN OUT VDD VSS

    * --- 1. Device Model Instantiation (Epi Layer) ---
    Xmp1 NPDrain_Epi NPGate_Epi_P PSource_Epi VDD pmos_lvt L=16n W=200n NF=1
    Xmn1 NPDrain_Epi NPGate_Epi_N NSource_Epi VSS nmos_lvt L=16n W=100n NF=1

    * --- 2. Connection Epi-Inner (Contact Resistance) ---
    R_con_d_p  NPDrain_Epi   NPDrain_Inner_P 0.001
    R_con_d_n  NPDrain_Epi   NPDrain_Inner_N 0.001
    R_con_g_p  NPGate_Epi_P  NPGate_Inner_P  0.001
    R_con_g_n  NPGate_Epi_N  NPGate_Inner_N  0.001
    R_con_s_p  PSource_Epi   PSource_Inner   0.001
    R_con_s_n  NSource_Epi   NSource_Inner   0.001

    * --- 3. Connection Inner-Outer (RC Matrix) ---

    * [Gate Path] T-Network: Outer feeds both Inners
    R_0_1  NPGate_Outer    NPGate_Inner_N  6.3444e+00 
    R_0_2  NPGate_Outer    NPGate_Inner_P  3.2252e+02 
    R_1_2  NPGate_Inner_N  NPGate_Inner_P  4.4958e+00 

    * [Drain Path] Daisy Chain: Inner_N -> Inner_P -> Outer
    * (Implies NMOS output goes through PMOS contact area)
    R_3_4      NPDrain_Inner_N NPDrain_Inner_P 3.8110e+01
    R_out_lnk  NPDrain_Inner_P NPDrain_Outer   0.001

    * [Source Path] Direct connection
    R_5_6  PSource_Outer   PSource_Inner   1.5227e+00 
    R_7_8  NSource_Outer   NSource_Inner   7.1327e-01 

    * --- 4. External Ports to Outer Layer ---
    R_ext_in   IN   NPGate_Outer   0.001
    R_ext_out  OUT  NPDrain_Outer  0.001
    R_ext_vdd  VDD  PSource_Outer  0.001
    R_ext_vss  VSS  NSource_Outer  0.001

    * --- 5. CFET Parasitic Capacitance Matrix ---
    C_0_1  NPDrain_Epi    NPDrain_Outer  4.9460e-17 
    C_0_2  NPDrain_Epi    NPGate_Outer   4.6636e-17 
    C_0_3  NPDrain_Epi    PSource_Epi    6.3458e-19 
    C_0_4  NPDrain_Epi    NSource_Epi    1.3420e-19 
    C_0_5  NPDrain_Epi    Tungsten_31    5.8159e-20 
    C_1_2  NPDrain_Outer  NPGate_Outer   9.5887e-18 
    C_1_3  NPDrain_Outer  PSource_Epi    1.1905e-20 
    C_1_4  NPDrain_Outer  NSource_Epi    1.0560e-20 
    C_1_5  NPDrain_Outer  Tungsten_31    6.9939e-21 
    C_2_3  NPGate_Outer   PSource_Epi    8.8637e-18 
    C_2_4  NPGate_Outer   NSource_Epi    1.4693e-17 
    C_2_5  NPGate_Outer   Tungsten_31    1.3242e-17 
    C_3_4  PSource_Epi    NSource_Epi    2.3683e-22 
    C_3_5  PSource_Epi    Tungsten_31    8.8707e-18 
    C_4_5  NSource_Epi    Tungsten_31    1.2179e-17 

    * Floating Metal Handling
    R_float_fix Tungsten_31 0 1G

.ENDS CFET_INV


* ===================================================================
* Subcircuit 2: S2FET Inverter Wrapper
* ===================================================================
.SUBCKT S2FET_INV IN OUT VDD VSS

    * --- 1. Device Model Instantiation (Epi Layer) ---
    Xmp1 NPDrain_Epi NPGate_Epi_P PSource_Epi VDD pmos_lvt L=16n W=200n NF=1
    Xmn1 NPDrain_Epi NPGate_Epi_N NSource_Epi VSS nmos_lvt L=16n W=100n NF=1

    * --- 2. Connection Epi-Inner (Contact Resistance) ---
    R_s2_c_dp NPDrain_Epi   NPDrain_Inner_P 0.001
    R_s2_c_dn NPDrain_Epi   NPDrain_Inner_N 0.001
    R_s2_c_gp NPGate_Epi_P  NPGate_Inner_P  0.001
    R_s2_c_gn NPGate_Epi_N  NPGate_Inner_N  0.001
    R_s2_c_sp PSource_Epi   PSource_Inner   0.001
    R_s2_c_sn NSource_Epi   NSource_Inner   0.001

    * --- 3. Connection Inner-Outer (RC Matrix) ---

    * [Gate Path] T-Network
    R_s2_0_1 NPGate_Outer    NPGate_Inner_N  1.0925e+01 
    R_s2_0_2 NPGate_Outer    NPGate_Inner_P  8.9182e+01 
    R_s2_1_2 NPGate_Inner_N  NPGate_Inner_P  4.5928e+00 

    * [Drain Path] Delta Network: Outer connects to BOTH Inners
    R_s2_3_4 NPDrain_Outer   NPDrain_Inner_N 6.8662e+00 
    R_s2_3_5 NPDrain_Outer   NPDrain_Inner_P 7.3826e+01
    R_s2_4_5 NPDrain_Inner_N NPDrain_Inner_P 7.8889e+00 

    * [Source Path] Direct connection
    R_s2_6_7 PSource_Outer   PSource_Inner   1.0709e+00 
    R_s2_8_9 NSource_Outer   NSource_Inner   1.1231e+01 

    * --- 4. External Ports to Outer Layer ---
    R_ext_s2_in  IN   NPGate_Outer   0.001
    R_ext_s2_out OUT  NPDrain_Outer  0.001
    R_ext_s2_vdd VDD  PSource_Outer  0.001
    R_ext_s2_vss VSS  NSource_Outer  0.001

    * --- 5. S2FET Parasitic Capacitance Matrix ---
    C_s2_0_1 NPDrain_Outer NPDrain_Epi   2.1301e-20 
    C_s2_0_2 NPDrain_Outer PSource_Epi   1.1385e-17 
    C_s2_0_3 NPDrain_Outer NSource_Epi   9.3538e-18 
    C_s2_0_4 NPDrain_Outer NPGate_Outer  2.5489e-17 
    C_s2_0_5 NPDrain_Outer Tungsten_46   1.0030e-19 
    C_s2_1_2 NPDrain_Epi   PSource_Epi   1.7774e-19 
    C_s2_1_3 NPDrain_Epi   NSource_Epi   3.1528e-19 
    C_s2_1_4 NPDrain_Epi   NPGate_Outer  2.3581e-17 
    C_s2_1_5 NPDrain_Epi   Tungsten_46   2.7083e-17 
    C_s2_2_3 PSource_Epi   NSource_Epi   2.4287e-19 
    C_s2_2_4 PSource_Epi   NPGate_Outer  1.1698e-17 
    C_s2_2_5 PSource_Epi   Tungsten_46   5.0800e-20 
    C_s2_3_4 NSource_Epi   NPGate_Outer  1.1107e-17 
    C_s2_3_5 NSource_Epi   Tungsten_46   1.6185e-20 
    C_s2_4_5 NPGate_Outer  Tungsten_46   2.4474e-17 

    * Floating Metal Handling
    R_float_s1 Tungsten_46 0 1G

.ENDS S2FET_INV


.SUBCKT IDEAL_INV IN OUT VDD VSS

    Xmp1 NPDrain_Epi NPGate_Epi_P PSource_Epi VDD pmos_lvt L=16n W=200n NF=1
    Xmn1 NPDrain_Epi NPGate_Epi_N NSource_Epi VSS nmos_lvt L=16n W=100n NF=1

    R_id_c_dp NPDrain_Epi   NPDrain_Inner_P 1u
    R_id_c_dn NPDrain_Epi   NPDrain_Inner_N 1u
    R_id_c_gp NPGate_Epi_P  NPGate_Inner_P  1u
    R_id_c_gn NPGate_Epi_N  NPGate_Inner_N  1u
    R_id_c_sp PSource_Epi   PSource_Inner   1u
    R_id_c_sn NSource_Epi   NSource_Inner   1u

    R_id_g1 NPGate_Outer NPGate_Inner_N 1u
    R_id_g2 NPGate_Outer NPGate_Inner_P 1u

    R_id_d1 NPDrain_Outer NPDrain_Inner_N 1u
    R_id_d2 NPDrain_Outer NPDrain_Inner_P 1u

    R_id_s1 PSource_Outer PSource_Inner 1u
    R_id_s2 NSource_Outer NSource_Inner 1u

    R_id_ext_i IN  NPGate_Outer  1u
    R_id_ext_o OUT NPDrain_Outer 1u
    R_id_ext_v VDD PSource_Outer 1u
    R_id_ext_g VSS NSource_Outer 1u

    C_id_01 NPDrain_Outer NPDrain_Epi  1z
    C_id_02 NPDrain_Outer PSource_Epi  1z
    C_id_03 NPDrain_Outer NSource_Epi  1z
    C_id_04 NPDrain_Outer NPGate_Outer 1z
    C_id_12 NPDrain_Epi   PSource_Epi  1z
    C_id_13 NPDrain_Epi   NSource_Epi  1z
    C_id_14 NPDrain_Epi   NPGate_Outer 1z
    C_id_23 PSource_Epi   NSource_Epi  1z
    C_id_24 PSource_Epi   NPGate_Outer 1z
    C_id_34 NSource_Epi   NPGate_Outer 1z

    R_float_id Tungsten_Dummy 0 1G
    C_dummy    NPDrain_Outer Tungsten_Dummy 1z

.ENDS IDEAL_INV