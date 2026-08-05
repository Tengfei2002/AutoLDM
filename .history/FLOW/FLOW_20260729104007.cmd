
$ProjectRoot = "C:\Users\Tengfei\Desktop\Project_DTCO\AutoLDM"
$RemoteHost  = "tfzhang@10.129.166.83"
$RemoteDir   = "/home/SOI/tfz/test_RC/test_base"

Set-Location "$ProjectRoot\FLOW\test"
$env:NAME = "test"

cd C:\Users\Tengfei\Desktop\Project_DTCO\AutoLDM\FLOW\test\.
echo $env:NAME


python .\gen_sde.py `
  .\INPUT_MODEL\${env:NAME}_gds.txt `
  .\INPUT_MODEL\${env:NAME}_params.txt `
  .\INPUT_MODEL\${env:NAME}_stacked.txt `
  -o .\SDE\${env:NAME}_sde.cmd


python .\INPUT_MODEL\txt_gds_trans\gds2txt.py .\INPUT_MODEL\${env:NAME}.gds

python .\INPUT_MODEL\txt_gds_trans\txt2gds.py .\INPUT_MODEL\${env:NAME}_gds.txt

python .\gen_drc_report.py `
  ".\INPUT_MODEL\${env:NAME}_gds.txt" `
  ".\INPUT_MODEL\test_params.txt" `
  ".\INPUT_MODEL\test_stacked.txt" `
  ".\INPUT_MODEL\${env:NAME}_design_rules.txt" `
  -o ".\OUTPUT\${env:NAME}_drc_report.txt"


(after process @win, no password need when trying to enter ssh)
ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\id_ed25519" -C "tfzhang@windows"
Get-Content "$env:USERPROFILE\.ssh\id_ed25519.pub" | ssh tfzhang@10.129.166.83 "umask 077; mkdir -p ~/.ssh; cat >> ~/.ssh/authorized_keys; chmod 700 ~/.ssh; chmod 600 ~/.ssh/authorized_keys"

ssh tfzhang@10.129.166.83
tftfZhanG
cd /home/SOI/tfz/test_RC/test_base
chmod +x cleanup_obsolete_swb_files.sh
./cleanup_obsolete_swb_files.sh --target /home/SOI/tfz/test_RC/test_base --execute



scp "C:\Users\Tengfei\Desktop\Project_DTCO\AutoLDM\FLOW\test\SDE\test_c_sde.cmd" tfzhang@10.129.166.83:/home/SOI/tfz/test_RC/test_base/
scp "C:\Users\Tengfei\Desktop\Project_DTCO\AutoLDM\FLOW\test\SDE\test_r_sde.cmd" tfzhang@10.129.166.83:/home/SOI/tfz/test_RC/test_base/
scp tfzhang@10.129.166.83:/home/SOI/tfz/test_RC/test_base/gtree.dat "C:\Users\Tengfei\Desktop\Project_DTCO\AutoLDM\"