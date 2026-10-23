#!/bin/bash
# Construye WaveMascot.app y su instalador dist/WaveMascot-Mac-<chip>.dmg con PyInstaller (macOS).
#
#   ./build-mac.sh
#   PYTHON=/usr/local/bin/python3.14 ./build-mac.sh
#
# 1. Crea un entorno virtual en build/venv-mac con las versiones fijas de requirements-build.txt
#    (no toca tu instalación de Python).
# 2. Empaqueta la app (principal.py + módulos + assets) como build/dist-mac/WaveMascot.app, para el
#    chip de esta Mac (Apple Silicon o Intel).
# 3. La firma (ad hoc, o con MAC_FIRMA="Developer ID Application: ..." si tenés una) y arma el .dmg
#    con la app y un acceso a Aplicaciones para arrastrarla.
set -euo pipefail

raiz="$(cd "$(dirname "$0")" && pwd)"
build="$raiz/build"
dist="$raiz/dist"
version="$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$raiz/mascota.py")"
[ -n "$version" ] || { echo "No encontré __version__ en mascota.py" >&2; exit 1; }
case "$(uname -m)" in
  arm64) chip="AppleSilicon" ;;
  x86_64) chip="Intel" ;;
  *) echo "Chip desconocido: $(uname -m)" >&2; exit 1 ;;
esac

echo "Construyendo WaveMascot $version para Mac ($chip)"
venv="$build/venv-mac"
py="$venv/bin/python"
[ -x "$py" ] || "${PYTHON:-python3}" -m venv "$venv"
"$py" -m pip install --disable-pip-version-check -q -r "$raiz/requirements-build.txt"

rm -rf "$build/dist-mac" "$build/work-mac" "$build/dmg-mac" "$dist"
mkdir -p "$dist"

# 1) La app: un solo ejecutable que hace de hook, mascota, ajustes, ícono, instalador y desinstalador.
"$py" -m PyInstaller --noconfirm --clean --windowed \
  --name WaveMascot --icon "$raiz/assets/icono.icns" --osx-bundle-identifier io.github.marescaa.wavemascot \
  --distpath "$build/dist-mac" --workpath "$build/work-mac" --specpath "$build" \
  --add-data "$raiz/assets:assets" \
  --hidden-import ajustes --hidden-import bandeja --hidden-import instalador --hidden-import idiomas --hidden-import celular --hidden-import actualizacion \
  --exclude-module tkinter \
  "$raiz/principal.py"
app="$build/dist-mac/WaveMascot.app"

# Lo que PyInstaller suma por las dudas y la mascota nunca usa (lo mismo que saca build.ps1).
find "$app" \( -path '*/PyQt6/Qt6/lib/QtPdf.framework' -o -path '*/PyQt6/Qt6/plugins/imageformats/libqpdf.dylib' \
  -o -path '*/PyQt6/Qt6/plugins/tls' -o -path '*/PyQt6/Qt6/plugins/networkinformation' \
  -o -path '*/PIL/_avif*' -o -path '*/PIL/_imagingft*' \) -prune -exec rm -rf {} +
find "$app" -type l ! -exec test -e {} \; -delete  # los accesos que apuntaban a lo borrado

# Licencias: la del proyecto, las atribuciones y los textos de las bibliotecas incluidas (PyQt6 es GPL v3).
recursos="$app/Contents/Resources"
cp "$raiz/LICENSE" "$raiz/THIRD_PARTY.md" "$recursos/"
sitio="$("$py" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
for info in "$sitio"/*.dist-info; do
  nombre="$(basename "$info" | tr '[:upper:]' '[:lower:]' | sed -E 's/-[^-]+\.dist-info$//')"
  case "$nombre" in pyqt6|pyqt6_qt6|pyqt6_sip|pillow|pyinstaller) ;; *) continue ;; esac
  find "$info" -type f \( -iname 'LICEN[CS]E*' -o -iname 'COPYING*' \) | while read -r archivo; do
    mkdir -p "$recursos/licencias/$nombre"
    cp "$archivo" "$recursos/licencias/$nombre/"
  done
done
base_python="$("$py" -c 'import sys; print(sys.base_prefix)')"
for licencia in "$base_python/LICENSE.txt" "$base_python"/lib/python3*/LICENSE.txt; do
  if [ -f "$licencia" ]; then
    mkdir -p "$recursos/licencias/python"
    cp "$licencia" "$recursos/licencias/python/LICENSE.txt"
    break
  fi
done

# Info.plist: versión, sin ícono en el Dock (vive en la barra de menús; los ajustes lo muestran al
# abrirse) y la versión mínima de macOS: la más alta que piden los binarios incluidos (Python, Qt, Pillow).
"$py" - "$app/Contents/Info.plist" "$version" "$app" <<'PY'
import os, plistlib, re, subprocess, sys

ruta, version, app = sys.argv[1:]
MACH_O = {b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xca\xfe\xba\xbe"}
minimas = ["10.13"]
for carpeta, _, archivos in os.walk(app):
    for nombre in archivos:
        archivo = os.path.join(carpeta, nombre)
        if os.path.islink(archivo):
            continue
        with open(archivo, "rb") as f:
            if f.read(4) not in MACH_O:
                continue
        salida = subprocess.run(["otool", "-l", archivo], capture_output=True, text=True).stdout
        # Solo LC_BUILD_VERSION (minos) y LC_VERSION_MIN_MACOSX (version); otros comandos también dicen "version".
        for comando in salida.split("Load command")[1:]:
            if "cmd LC_BUILD_VERSION" in comando:
                minimas += re.findall(r"^\s*minos (\d+\.\d+)", comando, re.M)
            elif "cmd LC_VERSION_MIN_MACOSX" in comando:
                minimas += re.findall(r"^\s*version (\d+\.\d+)", comando, re.M)
minima = max(minimas, key=lambda v: tuple(int(x) for x in v.split(".")))
with open(ruta, "rb") as f:
    datos = plistlib.load(f)
datos.update({
    "CFBundleName": "WaveMascot", "CFBundleDisplayName": "WaveMascot",
    "CFBundleShortVersionString": version, "CFBundleVersion": version,
    "LSUIElement": True, "LSMinimumSystemVersion": minima, "NSHighResolutionCapable": True,
    "LSApplicationCategoryType": "public.app-category.developer-tools",
    "NSHumanReadableCopyright": "© 2026 Francisco Maresca. MIT; the app includes PyQt6 (GPL v3).",
})
with open(ruta, "wb") as f:
    plistlib.dump(datos, f)
print(f"macOS {minima} o más nuevo")
assert 10 <= int(minima.split(".")[0]) <= 30, f"versión mínima rara: {minima}"
PY

# 2) Firma: ad hoc (gratis; macOS pide confirmar la primera vez) o con un Developer ID.
firma="${MAC_FIRMA:--}"
codesign --force --deep --sign "$firma" "$app"
codesign --verify --deep --strict "$app"

# 3) El .dmg: la app y un acceso a Aplicaciones para arrastrarla.
staging="$build/dmg-mac"
mkdir -p "$staging"
ditto "$app" "$staging/WaveMascot.app"
ln -s /Applications "$staging/Applications"
dmg="$dist/WaveMascot-Mac-$chip.dmg"  # sin versión: el link "releases/latest/download" del README no cambia
for intento in 1 2 3; do  # hdiutil a veces falla con "Resource busy" en las máquinas de CI
  hdiutil create -volname WaveMascot -srcfolder "$staging" -ov -format UDZO -fs HFS+ "$dmg" && break
  [ "$intento" = 3 ] && exit 1
  sleep 5
done
[ "$firma" = "-" ] || codesign --force --sign "$firma" "$dmg"

hash="$(shasum -a 256 "$dmg" | cut -d' ' -f1)"
echo
echo "Listo: $dmg"
echo "SHA256: $hash"
