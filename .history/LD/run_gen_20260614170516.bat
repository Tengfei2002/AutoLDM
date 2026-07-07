@echo off
echo processing GDSII data_set

cd C:\Users\Tengfei\Desktop\Project_DTCO\AutoLDM\LD
% python gen_layout.py ./gds/test1.gds
% python gds_show.py ./gds/test1_gds.txt

python gen_arch.py ./gds/test1_gds.txt ./rules/cfet_arch.txt ./rules/layer_rule_1.txt