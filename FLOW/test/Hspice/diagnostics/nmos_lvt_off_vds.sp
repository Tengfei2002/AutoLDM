* Minimal diagnostic: NMOS pass-gate off-state VDS sweep.
.option INGOLD=2 POST=2
.hdl "../../INPUT_MODEL/test_fet_n.va"
VD D 0 0
VG G 0 0
VS S 0 0
VB B 0 0
XN D G S B nmos_lvt L=1.6e-8 W=3.5e-8 NF=1
.dc VD 0 0.7 1m
.print dc v(D) v(G) v(S) i(VD)
.end
