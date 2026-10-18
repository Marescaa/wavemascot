<#
.SYNOPSIS
    Desinstala WaveMascot (instalada con install.ps1 o con el instalador .exe).

.DESCRIPTION
    Cierra la mascota, quita solo sus hooks de ~/.claude/settings.json (con backup previo; los
    tuyos quedan como estaban), borra el comando /wavemascot, los accesos directos y la carpeta del
    programa. Tu configuración (~/.wavemascot) se conserva salvo que pases -BorrarConfig.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
#>
[CmdletBinding()]
param(
    [string]$Destino = (Join-Path $env:LOCALAPPDATA 'Programs\WaveMascot'),
    # Por defecto, la que se usó al instalar.
    [string]$ClaudeDir = '',
    [string]$Python = '',
    # Borra también la configuración y el registro (~/.wavemascot).
    [switch]$BorrarConfig
)

$ErrorActionPreference = 'Stop'
Set-Location $env:USERPROFILE  # para poder borrar la carpeta aunque este script esté adentro

$opciones = @('--destino', $Destino, '--silencioso')
if ($ClaudeDir) { $opciones += @('--claude-dir', $ClaudeDir) }
if ($BorrarConfig) { $opciones += '--borrar-config' }

$exe = Join-Path $Destino 'WaveMascot.exe'
if (Test-Path $exe) {  # instalada con el .exe
    $p = Start-Process -FilePath $exe -ArgumentList (@('desinstalar') + ($opciones | ForEach-Object { "`"$_`"" })) -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw "El desinstalador terminó con error ($($p.ExitCode))." }
}
else {
    if (-not $Python) {
        foreach ($c in 'py', 'python', 'python3') {
            if (Get-Command $c -ErrorAction SilentlyContinue) { $Python = $c; break }
        }
    }
    if (-not $Python) { throw 'No encontré Python. Pasá -Python <ruta a python.exe>.' }
    $script = Join-Path $Destino 'instalador.py'
    if (-not (Test-Path $script)) { $script = Join-Path $PSScriptRoot 'instalador.py' }
    if (-not (Test-Path $script)) { throw "No encontré instalador.py ni en $Destino ni junto a este script." }
    $copia = Join-Path $env:TEMP "mascota-desinstalador-$PID.py"  # el original se borra con la carpeta
    Copy-Item -LiteralPath $script -Destination $copia -Force
    try {
        & $Python $copia desinstalar @opciones
        if ($LASTEXITCODE -ne 0) { throw "El desinstalador terminó con error ($LASTEXITCODE)." }
    }
    finally { Remove-Item -LiteralPath $copia -Force -ErrorAction SilentlyContinue }
}
Write-Host 'WaveMascot desinstalada.' -ForegroundColor Green
