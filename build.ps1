<#
.SYNOPSIS
    Construye el instalador dist\WaveMascot-Setup.exe con PyInstaller.

.DESCRIPTION
    1. Crea un entorno virtual en build\venv con las versiones fijas de requirements-build.txt
       (no toca tu instalación de Python).
    2. Empaqueta la app (principal.py + módulos + assets) como build\dist\WaveMascot\WaveMascot.exe.
    3. La comprime en build\app.zip y arma el instalador de un solo archivo a partir de instalador.py.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\build.ps1
#>
[CmdletBinding()]
param(
    # Python con el que se crea el entorno virtual del build.
    [string]$Python = 'python'
)

$ErrorActionPreference = 'Stop'
$raiz = $PSScriptRoot
$build = Join-Path $raiz 'build'
$dist = Join-Path $raiz 'dist'
$version = (Select-String -Path (Join-Path $raiz 'mascota.py') -Pattern '^__version__ = "(.+)"').Matches[0].Groups[1].Value
if (-not $version) { throw 'No encontré __version__ en mascota.py' }

function Ejecutar([string]$exe, [string[]]$argumentos) {
    $ErrorActionPreference = 'Continue'  # PyInstaller escribe su progreso en stderr
    & $exe @argumentos 2>&1 | ForEach-Object { "$_" } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "Falló: $exe $($argumentos -join ' ')" }
}

Write-Host "Construyendo WaveMascot $version" -ForegroundColor Cyan
$venv = Join-Path $build 'venv'
$py = Join-Path $venv 'Scripts\python.exe'
if (-not (Test-Path $py)) { Ejecutar $Python @('-m', 'venv', $venv) }
Ejecutar $py @('-m', 'pip', 'install', '--disable-pip-version-check', '-q', '-r', (Join-Path $raiz 'requirements-build.txt'))

foreach ($d in (Join-Path $build 'dist'), (Join-Path $build 'work'), $dist) {
    if (Test-Path $d) { Remove-Item -LiteralPath $d -Recurse -Force }
}
$icono = Join-Path $raiz 'assets\icono.ico'
$comunes = @('--noconfirm', '--clean', '--windowed', '--icon', $icono,
             '--workpath', (Join-Path $build 'work'), '--specpath', $build)

# 1) La app: un solo WaveMascot.exe que hace de hook, mascota, ajustes, ícono y desinstalador.
Ejecutar $py (@('-m', 'PyInstaller') + $comunes + @(
    '--name', 'WaveMascot', '--distpath', (Join-Path $build 'dist'),
    '--add-data', "$(Join-Path $raiz 'assets');assets",
    '--hidden-import', 'ajustes', '--hidden-import', 'bandeja', '--hidden-import', 'instalador', '--hidden-import', 'idiomas', '--hidden-import', 'celular', '--hidden-import', 'actualizacion', '--hidden-import', 'guia_pro',
    '--exclude-module', 'tkinter',
    (Join-Path $raiz 'principal.py')))

# Lo que PyInstaller suma por las dudas y la mascota nunca usa (no dibuja con OpenGL, no abre PDF,
# no lee AVIF ni dibuja texto con Pillow): ~45 MB menos. libssl y libcrypto se quedan: los avisos a
# Telegram (celular.py) van por HTTPS.
$interno = Join-Path $build 'dist\WaveMascot\_internal'
$sobran = 'PyQt6\Qt6\bin\opengl32sw.dll', 'PyQt6\Qt6\bin\Qt6Pdf.dll', 'PyQt6\Qt6\plugins\imageformats\qpdf.dll',
          'PyQt6\Qt6\plugins\tls', 'PyQt6\Qt6\plugins\networkinformation',
          'PIL\_avif*.pyd', 'PIL\_imagingft*.pyd'
foreach ($s in $sobran) { Remove-Item -Path (Join-Path $interno $s) -Recurse -Force -ErrorAction SilentlyContinue }

# Licencias: la del proyecto, las atribuciones y los textos de las bibliotecas incluidas (PyQt6 es GPL v3).
$carpetaApp = Join-Path $build 'dist\WaveMascot'
Copy-Item -LiteralPath (Join-Path $raiz 'LICENSE'), (Join-Path $raiz 'THIRD_PARTY.md') -Destination $carpetaApp
$licencias = Join-Path $carpetaApp 'licencias'
New-Item -ItemType Directory -Force -Path $licencias | Out-Null
$sitio = Join-Path $venv 'Lib\site-packages'
Get-ChildItem $sitio -Directory -Filter '*.dist-info' |
    Where-Object { $_.Name -match '^(pyqt6|pyqt6_qt6|pyqt6_sip|pillow|pyinstaller)-' } | ForEach-Object {
        $destinoLicencia = Join-Path $licencias ($_.Name -replace '-[^-]+\.dist-info$', '')
        Get-ChildItem $_.FullName -Recurse -File | Where-Object { $_.Name -match '^(LICEN[CS]E|COPYING)' } | ForEach-Object {
            New-Item -ItemType Directory -Force -Path $destinoLicencia | Out-Null
            Copy-Item -LiteralPath $_.FullName -Destination $destinoLicencia
        }
    }
$basePython = & $py -c 'import sys; print(sys.base_prefix)'
$licenciaPython = Join-Path $basePython 'LICENSE.txt'
if (Test-Path $licenciaPython) {
    New-Item -ItemType Directory -Force -Path (Join-Path $licencias 'python') | Out-Null
    Copy-Item -LiteralPath $licenciaPython -Destination (Join-Path $licencias 'python')
}

# 2) La app comprimida, que viaja dentro del instalador.
$app = Join-Path $build 'app.zip'
Ejecutar $py @('-c', 'import shutil, sys; shutil.make_archive(sys.argv[1], ''zip'', sys.argv[2])',
               ($app -replace '\.zip$', ''), (Join-Path $build 'dist\WaveMascot'))

# 3) El instalador: un .exe que desempaqueta app.zip y configura hooks, /wavemascot y accesos.
$setup = 'WaveMascot-Setup'  # sin versión: el link "releases/latest/download" del README no cambia
Ejecutar $py (@('-m', 'PyInstaller') + $comunes + @(
    '--onefile', '--name', $setup, '--distpath', $dist,
    '--add-data', "$app;.", '--exclude-module', 'tkinter',
    (Join-Path $raiz 'instalador.py')))

$exe = Join-Path $dist "$setup.exe"
$hash = (Get-FileHash -Algorithm SHA256 $exe).Hash.ToLower()
"$hash  $setup.exe" | Out-File -Encoding ascii (Join-Path $dist 'SHA256SUMS.txt')
Write-Host ''
Write-Host "Listo: $exe" -ForegroundColor Green
Write-Host "SHA256: $hash"
