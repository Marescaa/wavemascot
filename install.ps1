<#
.SYNOPSIS
    Instala WaveMascot desde el código fuente.

.DESCRIPTION
    Copia los archivos a la carpeta de destino, instala PyQt6 y Pillow si faltan, agrega los
    hooks a ~/.claude/settings.json sin tocar los que ya tengas (antes guarda un backup), crea
    el comando /wavemascot y el ícono junto al reloj. Para revertirlo: uninstall.ps1.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\install.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\install.ps1 -Python C:\Python312\python.exe -SinInicio
#>
[CmdletBinding()]
param(
    # Dónde se copia el programa.
    [string]$Destino = (Join-Path $env:LOCALAPPDATA 'Programs\WaveMascot'),
    # Carpeta de configuración de Claude Code (la que tiene settings.json).
    [string]$ClaudeDir = (Join-Path $env:USERPROFILE '.claude'),
    # Intérprete de Python a usar (por defecto: el lanzador "py" o "python" del PATH).
    [string]$Python = '',
    # Sin ícono junto al reloj al iniciar Windows.
    [switch]$SinInicio
)

$ErrorActionPreference = 'Stop'
$Origen = $PSScriptRoot
$Archivos = 'mascota.py', 'ajustes.py', 'bandeja.py', 'sprites.py', 'ventanas.py', 'instalador.py',
            'uninstall.ps1', 'requirements.txt', 'LICENSE'

function Correr([string]$exe, [string[]]$argumentos, [switch]$Callado) {
    # Los programas externos que escriben en stderr no deben cortar el script (PowerShell 5.1).
    $ErrorActionPreference = 'Continue'
    if ($Callado) { & $exe @argumentos 2>&1 | Out-Null } else { & $exe @argumentos | Out-Host }
    return $LASTEXITCODE
}

function Ejecutar([string]$exe, [string[]]$argumentos) {
    if ((Correr $exe $argumentos) -ne 0) { throw "Falló: $exe $($argumentos -join ' ')" }
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
    throw 'No encontré Python 3.10 o superior. Instalalo desde https://www.python.org (marcá "Add to PATH") o pasá -Python <ruta a python.exe>.'
}

Write-Host 'WaveMascot: instalación desde el código fuente' -ForegroundColor Cyan
$py = Buscar-Python
$version = & $py -c 'import sys; print(sys.version_info[0], sys.version_info[1], sep=chr(46))'
if ([version]$version -lt [version]'3.10') { throw "Hace falta Python 3.10 o superior (encontré $version en $py)." }
Write-Host "  Python $version ($py)"

# Dependencias: solo si faltan, así no se tocan otras instalaciones.
if ((Correr $py @('-c', 'import PyQt6.QtMultimedia, PIL') -Callado) -ne 0) {
    Write-Host '  Instalando PyQt6 y Pillow...'
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
    Write-Host "  Archivos copiados a $Destino"
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
Write-Host 'Listo. Wave avisa la próxima vez que Claude Code termine o necesite algo.' -ForegroundColor Green
Write-Host 'Ajustes: el ícono junto al reloj o /wavemascot en Claude Code. Desinstalar: uninstall.ps1'
