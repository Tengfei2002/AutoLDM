$FLOWRoot = "C:\Users\Tengfei\Desktop\Project_DTCO\AutoLDM\FLOW"
$ProjectRoot = "C:\Users\Tengfei\Desktop\Project_DTCO\AutoLDM\FLOW\test"
$SDELocation = "$ProjectRoot\SDE\"
$INPUTLocation = "$ProjectRoot\INPUT_MODEL\"
$OUTPUTLocation = "$ProjectRoot\OUTPUT\"

$RemoteHost  = "tfzhang@10.129.166.83"
$RemoteDir   = "/home/SOI/tfz/test_RC/test_base"

Set-Location "$ProjectRoot"
$env:NAME = "test"

cd C:\Users\Tengfei\Desktop\Project_DTCO\AutoLDM\FLOW\test\.
echo $env:NAME


python "$ProjectRoot\gen_sde.py" `
  "$INPUTLocation\${env:NAME}_gds.txt" `
  "$INPUTLocation\${env:NAME}_params.txt" `
  "$INPUTLocation\${env:NAME}_stacked.txt" `
  -o "$SDELocation\${env:NAME}_sde.cmd"


python "$ProjectRoot\gds2txt.py" "$INPUTLocation\${env:NAME}.gds"

python "$ProjectRoot\txt2gds.py" "$INPUTLocation\${env:NAME}_gds.txt"

python "$ProjectRoot\gen_drc_report.py" `
  "$INPUTLocation\${env:NAME}_gds.txt" `
  "$INPUTLocation\test_params.txt" `
  "$INPUTLocation\test_stacked.txt" `
  "$INPUTLocation\${env:NAME}_design_rules.txt" `
  -o "$OUTPUTLocation\${env:NAME}_drc_report.txt"


python "$ProjectRoot\gen_rc_Matrix.py" `
  "$INPUTLocation\test_pin.txt" `
  "$SDELocation\test_c_cMatrix.spi" `
  "$SDELocation\test_r_cMatrix.spi" `
  -o "$ProjectRoot\Hspice\test_pin_spice.txt" `
  --strict-contact-face

(after process @win, no password need when trying to enter ssh)
ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\id_ed25519" -C "tfzhang@windows"
Get-Content "$env:USERPROFILE\.ssh\id_ed25519.pub" | ssh tfzhang@10.129.166.83 "umask 077; mkdir -p ~/.ssh; cat >> ~/.ssh/authorized_keys; chmod 700 ~/.ssh; chmod 600 ~/.ssh/authorized_keys"

ssh tfzhang@10.129.166.83
tftfZhanG
cd /home/SOI/tfz/test_RC/test_base
chmod +x cleanup_obsolete_swb_files.sh
./cleanup_obsolete_swb_files.sh --target /home/SOI/tfz/test_RC/test_base --execute



scp "$SDELocation\${env:NAME}_c_sde.cmd" "${RemoteHost}:${RemoteDir}/c_dvs.cmd"
scp "$SDELocation\${env:NAME}_r_sde.cmd" "${RemoteHost}:${RemoteDir}/r_dvs.cmd"

scp "${RemoteHost}:${RemoteDir}/test_c_cMatrix.spi" "$SDELocation/${env:NAME}_c_cMatrix.spi"
scp "${RemoteHost}:${RemoteDir}/test_r_cMatrix.spi" "$SDELocation/${env:NAME}_r_cMatrix.spi"