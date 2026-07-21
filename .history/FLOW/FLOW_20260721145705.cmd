
cd C:\Users\Tengfei\Desktop\Project_DTCO\AutoLDM\.
set NAME = test


python .\gen_sde.py `
  .\INPUT_MODEL\${env:NAME}gds.txt `
  .\INPUT_MODEL\${env:NAME}params.txt `
  .\INPUT_MODEL\${env:NAME}stacked.txt `
  -o .\SDE\${env:NAME}sde.cmd


python .\INPUT_MODEL\txt_gds_trans\gds2txt.py .\INPUT_MODEL\${env:NAME}gds.gds

python .\INPUT_MODEL\txt_gds_trans\txt2gds.py 