<#
.SYNOPSIS
    Uninstalls WaveMascot (installed with install.ps1 or with the .exe installer).

.DESCRIPTION
    Closes the mascot, removes only its hooks from ~/.claude/settings.json (with a backup first;
    yours stay as they were), and deletes the /wavemascot command, the shortcuts and the program
    folder. Your settings (~/.wavemascot) are kept unless you pass -DeleteSettings.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
#>
[CmdletBinding()]
param(
    [Alias('Destination')][string]$Destino = (Join-Path $env:LOCALAPPDATA 'Programs\WaveMascot'),
    # Default: the one used when installing.
    [string]$ClaudeDir = '',
    [string]$Python = '',
    # Also delete the settings and the log (~/.wavemascot).
    [Alias('DeleteSettings')][switch]$BorrarConfig
)

$ErrorActionPreference = 'Stop'
Set-Location $env:USERPROFILE  # para poder borrar la carpeta aunque este script esté adentro

$opciones = @('--destino', $Destino, '--silencioso')
if ($ClaudeDir) { $opciones += @('--claude-dir', $ClaudeDir) }
if ($BorrarConfig) { $opciones += '--borrar-config' }

$exe = Join-Path $Destino 'WaveMascot.exe'
if (Test-Path $exe) {  # instalada con el .exe
    $p = Start-Process -FilePath $exe -ArgumentList (@('desinstalar') + ($opciones | ForEach-Object { "`"$_`"" })) -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw "The uninstaller failed ($($p.ExitCode))." }
}
else {
    if (-not $Python) {
        foreach ($c in 'py', 'python', 'python3') {
            if (Get-Command $c -ErrorAction SilentlyContinue) { $Python = $c; break }
        }
    }
    if (-not $Python) { throw 'Python was not found. Pass -Python <path to python.exe>.' }
    $origen = $Destino
    if (-not (Test-Path (Join-Path $origen 'instalador.py'))) { $origen = $PSScriptRoot }
    if (-not (Test-Path (Join-Path $origen 'instalador.py'))) { throw "instalador.py was not found in $Destino or next to this script." }
    # Se corre una copia: el original se borra junto con la carpeta del programa.
    $copia = Join-Path $env:TEMP "wavemascot-uninstall-$PID"
    New-Item -ItemType Directory -Force -Path $copia | Out-Null
    foreach ($a in 'instalador.py', 'idiomas.py') {
        if (Test-Path (Join-Path $origen $a)) { Copy-Item -LiteralPath (Join-Path $origen $a) -Destination $copia -Force }
    }
    try {
        & $Python (Join-Path $copia 'instalador.py') desinstalar @opciones
        if ($LASTEXITCODE -ne 0) { throw "The uninstaller failed ($LASTEXITCODE)." }
    }
    finally { Remove-Item -LiteralPath $copia -Recurse -Force -ErrorAction SilentlyContinue }
}
Write-Host 'WaveMascot uninstalled.' -ForegroundColor Green
