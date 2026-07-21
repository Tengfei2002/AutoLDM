
cd C:\Users\Tengfei\Desktop\Project_DTCO\AutoLDM\.
set NAME = test


python .\gen_sde.py `
  .\INPUT_MODEL\$test$_gds.txt `
  .\INPUT_MODEL\test_params.txt `
  .\INPUT_MODEL\test_stacked.txt `
  -o .\SDE\test_sde.cmd

python gds2txt.py xxx.gds
python txt2gds.py xxx.txt
python .\INPUT_MODEL\txt_gds_trans\gds2txt.py .\INPUT_MODEL\test_gds.gds

python .\INPUT_MODEL\txt_gds_trans\txt2gds.py 