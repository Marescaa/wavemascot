#!/bin/bash
# Uninstalls WaveMascot on macOS (installed with install.sh or with WaveMascot.app).
#
# Closes the mascot, removes only its hooks from ~/.claude/settings.json (with a backup first; yours
# stay as they were), and deletes the /wavemascot command, the login item and the program. Your
# settings (~/.wavemascot) are kept unless you pass --delete-settings.
#
#   ./uninstall.sh
#   ./uninstall.sh --delete-settings
#
# Options: --destination DIR (a source install folder or WaveMascot.app), --claude-dir DIR, --delete-settings.
set -euo pipefail

destino=""
opciones=(--silencioso)
while [ $# -gt 0 ]; do
  case "$1" in
    --destination|--destino) destino="$2"; shift 2 ;;
    --claude-dir) opciones+=(--claude-dir "$2"); shift 2 ;;
    --delete-settings|--borrar-config) opciones+=(--borrar-config); shift ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done
cd "$HOME"  # para poder borrar la carpeta aunque este script esté adentro

if [ -z "$destino" ]; then
  # Instalada con la app: el manifiesto de ~/.wavemascot dice dónde está.
  manifiesto="$HOME/.wavemascot/instalacion.json"
  if [ -f "$manifiesto" ]; then
    destino="$(/usr/bin/plutil -extract destino raw -o - "$manifiesto" 2>/dev/null || true)"
  fi
  [ -n "$destino" ] && [ -d "$destino" ] || destino="$HOME/Library/Application Support/WaveMascot"
fi

if [ -x "$destino/Contents/MacOS/WaveMascot" ]; then  # WaveMascot.app
  "$destino/Contents/MacOS/WaveMascot" desinstalar --destino "$destino" "${opciones[@]}"
else
  origen="$destino"
  [ -f "$origen/instalador.py" ] || origen="$(cd "$(dirname "$0")" && pwd)"
  [ -f "$origen/instalador.py" ] || { echo "instalador.py was not found in $destino or next to this script." >&2; exit 1; }
  python="$destino/venv/bin/python"
  [ -x "$python" ] || python="$(command -v python3)"
  # Se corre una copia: el original se borra junto con la carpeta del programa.
  copia="$(mktemp -d)"
  trap 'rm -rf "$copia"' EXIT
  cp "$origen/instalador.py" "$copia/"
  [ -f "$origen/idiomas.py" ] && cp "$origen/idiomas.py" "$copia/"
  # El python del entorno virtual se borra con la carpeta: se usa el del sistema que lo creó.
  base="$("$python" -c 'import sys; print(sys._base_executable)' 2>/dev/null || command -v python3)"
  "$base" "$copia/instalador.py" desinstalar --destino "$destino" "${opciones[@]}"
fi
echo "WaveMascot uninstalled."
