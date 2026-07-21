
cd C:\Users\Tengfei\Desktop\Project_DTCO\AutoLDM\FLOW\test\.
$env:NAME = "test"
echo $env:NAME


python .\gen_sde.py `
  .\INPUT_MODEL\${env:NAME}_gds.txt `
  .\INPUT_MODEL\${env:NAME}_params.txt `
  .\INPUT_MODEL\${env:NAME}_stacked.txt `
  -o .\SDE\${env:NAME}_sde.cmd


python .\INPUT_MODEL\txt_gds_trans\gds2txt.py .\INPUT_MODEL\${env:NAME}.gds

python .\INPUT_MODEL\txt_gds_trans\txt2gds.py .\INPUT_MODEL\${env:NAME}_gds.txt

.\OUTPUT\