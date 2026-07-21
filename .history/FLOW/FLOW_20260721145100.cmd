
cd C:\Users\Tengfei\Desktop\Project_DTCO\AutoLDM\.


python .\gen_sde.py `
  .\INPUT_MODEL\test_gds.txt `
  .\INPUT_MODEL\test_params.txt `
  .\INPUT_MODEL\test_stacked.txt `
  -o .\SDE\test_sde.cmd


python .\INPUT_MODEL\txt_gds_trans\