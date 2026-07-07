@echo off
echo processing GDSII data_set

cd C:\Users\Tengfei\Desktop\Project_DTCO\AutoLDM\LD
%python gen_layout.py ./gds/test.gds%
python gen_layout.py ./gds/XNOR2x1.gds
python gds_show.py ./gds/XNOR2x1_gds.txt

