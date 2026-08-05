* SRAM 6T block-level missing RC SPICE model
* This model keeps only schematic endpoints and whole-conductor RC values.

.SUBCKT SRAM_6T_RC_BLOCK BL BLB WL Q QB VDD VSS

* ---- concentrated missing R values, Ohm ----
.PARAM R_MISS_BL   = 1
.PARAM R_MISS_BLB  = 1
.PARAM R_MISS_WL   = 1
.PARAM R_MISS_Q    = 1
.PARAM R_MISS_QB   = 1
.PARAM R_MISS_VDD  = 1
.PARAM R_MISS_VSS  = 1

* ---- concentrated missing C values, F ----
.PARAM C_MISS_BL_GND    = 1a
.PARAM C_MISS_BLB_GND   = 1a
.PARAM C_MISS_WL_GND    = 1a
.PARAM C_MISS_Q_GND     = 1a
.PARAM C_MISS_QB_GND    = 1a
.PARAM C_MISS_VDD_GND   = 1a
.PARAM C_MISS_VSS_GND   = 1a
.PARAM C_MISS_Q_QB      = 1a
.PARAM C_MISS_WL_Q      = 1a
.PARAM C_MISS_WL_QB     = 1a
.PARAM C_MISS_BL_Q      = 1a
.PARAM C_MISS_BLB_QB    = 1a

* ---- external ports to schematic endpoints ----
R_PORT_BL   BL   BL_PORT    1m
R_PORT_BLB  BLB  BLB_PORT   1m
R_PORT_WL   WL   WL_PORT    1m
R_PORT_Q    Q    Q_NODE     1m
R_PORT_QB   QB   QB_NODE    1m
R_PORT_VDD  VDD  VDD_PORT   1m
R_PORT_VSS  VSS  VSS_PORT   1m

* ---- whole-conductor resistances ----
R_BL_BLOCK   BL_PORT   PG1_BL_SD       {R_MISS_BL}
R_BLB_BLOCK  BLB_PORT  PG2_BLB_SD      {R_MISS_BLB}
R_WL_PG1     WL_PORT   PG1_WL_GATE     {R_MISS_WL}
R_WL_PG2     WL_PORT   PG2_WL_GATE     {R_MISS_WL}
R_Q_N        Q_NODE    PG1_PD1_Q_SD    {R_MISS_Q}
R_Q_P        Q_NODE    PU1_Q_SD        {R_MISS_Q}
R_Q_GATE     Q_NODE    PD2_PU2_Q_GATE  {R_MISS_Q}
R_QB_N       QB_NODE   PD2_PG2_QB_SD   {R_MISS_QB}
R_QB_P       QB_NODE   PU2_QB_SD       {R_MISS_QB}
R_QB_GATE    QB_NODE   PD1_PU1_QB_GATE {R_MISS_QB}
R_VDD_PU1    VDD_PORT  PU1_VDD_SD      {R_MISS_VDD}
R_VDD_PU2    VDD_PORT  PU2_VDD_SD      {R_MISS_VDD}
R_VSS_PD1    VSS_PORT  PD1_VSS_SD      {R_MISS_VSS}
R_VSS_PD2    VSS_PORT  PD2_VSS_SD      {R_MISS_VSS}

* ---- whole-conductor capacitance ----
C_BL_GND     BL_PORT   0 {C_MISS_BL_GND}
C_BLB_GND    BLB_PORT  0 {C_MISS_BLB_GND}
C_WL_GND     WL_PORT   0 {C_MISS_WL_GND}
C_Q_GND      Q_NODE    0 {C_MISS_Q_GND}
C_QB_GND     QB_NODE   0 {C_MISS_QB_GND}
C_VDD_GND    VDD_PORT  0 {C_MISS_VDD_GND}
C_VSS_GND    VSS_PORT  0 {C_MISS_VSS_GND}

* ---- schematic-critical coupling capacitance ----
C_Q_QB       Q_NODE    QB_NODE          {C_MISS_Q_QB}
C_WL_Q       WL_PORT   Q_NODE           {C_MISS_WL_Q}
C_WL_QB      WL_PORT   QB_NODE          {C_MISS_WL_QB}
C_BL_Q       BL_PORT   Q_NODE           {C_MISS_BL_Q}
C_BLB_QB     BLB_PORT  QB_NODE          {C_MISS_BLB_QB}

.ENDS SRAM_6T_RC_BLOCK
