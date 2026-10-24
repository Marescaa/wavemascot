<#
.SYNOPSIS
    Installs WaveMascot from source.

.DESCRIPTION
    Copies the files to the install folder, installs PyQt6 and Pillow if they are missing, adds the
    hooks to ~/.claude/settings.json without touching the ones you already have (a backup is saved
    first), and creates the /wavemascot command and the tray icon. To undo it: uninstall.ps1.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\install.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\install.ps1 -Python C:\Python312\python.exe -NoStartup
#>
[CmdletBinding()]
param(
    # Where the program is copied.
    [Alias('Destination')][string]$Destino = (Join-Path $env:LOCALAPPDATA 'Programs\WaveMascot'),
    # Claude Code's settings folder (the one with settings.json).
    [string]$ClaudeDir = (Join-Path $env:USERPROFILE '.claude'),
    # Python interpreter to use (default: the "py" launcher or "python" on PATH).
    [string]$Python = '',
    # No tray icon when Windows starts.
    [Alias('NoStartup')][switch]$SinInicio
)

$ErrorActionPreference = 'Stop'
$Origen = $PSScriptRoot
$Archivos = 'mascota.py', 'ajustes.py', 'bandeja.py', 'sprites.py', 'ventanas.py', 'instalador.py', 'idiomas.py', 'celular.py', 'actualizacion.py', 'guia_pro.py', 'marco.py',
            'uninstall.ps1', 'requirements.txt', 'LICENSE'

function Correr([string]$exe, [string[]]$argumentos, [switch]$Callado) {
    # Los programas externos que escriben en stderr no deben cortar el script (PowerShell 5.1).
    $ErrorActionPreference = 'Continue'
    if ($Callado) { & $exe @argumentos 2>&1 | Out-Null } else { & $exe @argumentos | Out-Host }
    return $LASTEXITCODE
}

function Ejecutar([string]$exe, [string[]]$argumentos) {
    if ((Correr $exe $argumentos) -ne 0) { throw "Failed: $exe $($argumentos -join ' ')" }
}

function Buscar-Python {
    if ($Python) { return (Resolve-Path $Python).Path }
    $ErrorActionPreference = 'Continue'
    foreach ($c in @(@('py', '-3'), @('python'), @('python3'))) {
        if (-not (Get-Command $c[0] -ErrorAction SilentlyContinue)) { continue }
        $argumentos = @($c | Select-Object -Skip 1) + @('-c', 'import sys; print(sys.executable)')
        $ruta = & $c[0] @argumentos 2>$null
        # El "python" de la Microsoft Store sin instalar es un atajo que abre la tienda.
        if ($LASTEXITCODE -eq 0 -and $ruta -and (Test-Path "$ruta".Trim())) { return "$ruta".Trim() }
    }
    throw 'Python 3.10 or newer was not found. Install it from https://www.python.org (check "Add to PATH") or pass -Python <path to python.exe>.'
}

Write-Host 'WaveMascot: installing from source' -ForegroundColor Cyan
$py = Buscar-Python
$version = & $py -c 'import sys; print(sys.version_info[0], sys.version_info[1], sep=chr(46))'
if ([version]$version -lt [version]'3.10') { throw "Python 3.10 or newer is required (found $version at $py)." }
Write-Host "  Python $version ($py)"

# Dependencias: solo si faltan, así no se tocan otras instalaciones.
if ((Correr $py @('-c', 'import PyQt6.QtMultimedia, PIL') -Callado) -ne 0) {
    Write-Host '  Installing PyQt6 and Pillow...'
    $pip = @('-m', 'pip', 'install', '--disable-pip-version-check', '-q', '-r', (Join-Path $Origen 'requirements.txt'))
    if ((Correr $py $pip) -ne 0) {  # Python del sistema sin permisos de escritura: al perfil del usuario
        Ejecutar $py ($pip + '--user')
    }
}

# Copia de archivos (si se reinstala, primero se cierran la mascota y el ícono que estén abiertos).
$mismaCarpeta = (Test-Path $Destino) -and ((Resolve-Path $Destino).Path.TrimEnd('\') -eq $Origen.TrimEnd('\'))
if (-not $mismaCarpeta) {
    if (Test-Path (Join-Path $Destino 'instalador.py')) {
        Correr $py @((Join-Path $Origen 'instalador.py'), 'detener', '--destino', $Destino) | Out-Null
    }
    New-Item -ItemType Directory -Force -Path $Destino | Out-Null
    foreach ($a in $Archivos) {
        $fuente = Join-Path $Origen $a
        if (Test-Path $fuente) { Copy-Item -LiteralPath $fuente -Destination $Destino -Force }
    }
    $assets = Join-Path $Destino 'assets'
    if (Test-Path $assets) { Remove-Item -LiteralPath $assets -Recurse -Force }
    Copy-Item -LiteralPath (Join-Path $Origen 'assets') -Destination $assets -Recurse
    Write-Host "  Files copied to $Destino"
}

# Hooks (merge con backup), comando /wavemascot y accesos directos.
$argumentos = @((Join-Path $Destino 'instalador.py'), 'configurar', '--tipo', 'fuente',
                '--destino', $Destino, '--claude-dir', $ClaudeDir)
if ($SinInicio) { $argumentos += '--sin-inicio' }
Ejecutar $py $argumentos

if (-not $SinInicio) {
    $pyw = Join-Path (Split-Path $py) 'pythonw.exe'
    if (-not (Test-Path $pyw)) { $pyw = $py }
    Start-Process -FilePath $pyw -ArgumentList "`"$(Join-Path $Destino 'bandeja.py')`"" -WorkingDirectory $Destino
}

Write-Host ''
Write-Host 'Done. Wave will show up the next time Claude Code finishes or needs something.' -ForegroundColor Green
Write-Host 'Settings: the tray icon or /wavemascot in Claude Code (the flag at the top changes the language).'
Write-Host 'Uninstall: uninstall.ps1'
