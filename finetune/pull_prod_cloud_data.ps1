# Pull production cloud_data (Windows PowerShell).
# Usage: .\finetune\pull_prod_cloud_data.ps1
param(
  [string]$HostName = "root@194.226.187.101",
  [string]$Key = "",
  [string]$RemoteDir = "/opt/niteos-cloud/cloud_data"
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not $Key) { $Key = Join-Path $Root "deploy\niteos_deploy_key" }
$OutTar = Join-Path $Root "finetune\data\prod_cloud_data.tar.gz"
New-Item -ItemType Directory -Force -Path (Split-Path $OutTar) | Out-Null
$parent = Split-Path $RemoteDir -Parent
$base = Split-Path $RemoteDir -Leaf
Write-Host "Archiving $RemoteDir on $HostName ..."
& ssh -i $Key -o StrictHostKeyChecking=no $HostName "tar czf - -C $parent $base" | Set-Content -Encoding Byte -Path $OutTar
# Set-Content -Encoding Byte is awkward on some PS versions � use .NET
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = "ssh"
$psi.Arguments = "-i `"$Key`" -o StrictHostKeyChecking=no $HostName `"tar czf - -C $parent $base`""
$psi.RedirectStandardOutput = $true
$psi.UseShellExecute = $false
$p = [System.Diagnostics.Process]::Start($psi)
$fs = [System.IO.File]::Create($OutTar)
$p.StandardOutput.BaseStream.CopyTo($fs)
$fs.Close()
$p.WaitForExit()
if ($p.ExitCode -ne 0) { throw "ssh/tar failed with exit $($p.ExitCode)" }
Write-Host "Saved $OutTar"
Write-Host "Export with: python -m finetune.export_dataset --from-prod-tarball `"$OutTar`""
