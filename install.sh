#!/bin/bash
# Installs WaveMascot from source on macOS (the same thing install.ps1 does on Windows).
#
# Copies the files to the install folder, creates a Python virtual environment there with PyQt6 and
# Pillow (your Python stays untouched), adds the hooks to ~/.claude/settings.json without touching the
# ones you already have (a backup is saved first), and creates the /wavemascot command and the menu bar
# icon. To undo it: uninstall.sh.
#
#   ./install.sh
#   ./install.sh --python /opt/homebrew/bin/python3.13 --no-startup
#
# Options: --destination DIR, --claude-dir DIR, --python PATH, --no-startup (no menu bar icon at login).
set -euo pipefail

origen="$(cd "$(dirname "$0")" && pwd)"
destino="$HOME/Library/Application Support/WaveMascot"
claude_dir="$HOME/.claude"
python=""
sin_inicio=""
while [ $# -gt 0 ]; do
  case "$1" in
    --destination|--destino) destino="$2"; shift 2 ;;
    --claude-dir) claude_dir="$2"; shift 2 ;;
    --python) python="$2"; shift 2 ;;
    --no-startup|--sin-inicio) sin_inicio="--sin-inicio"; shift ;;
    -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done
archivos=(mascota.py ajustes.py bandeja.py sprites.py ventanas.py instalador.py idiomas.py celular.py uninstall.sh
          requirements.txt LICENSE)

buscar_python() {
  if [ -n "$python" ]; then echo "$python"; return; fi
  for c in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
      command -v "$c"; return
    fi
  done
  echo "Python 3.10 or newer was not found. Install it from https://www.python.org (or 'brew install python')" \
       "or pass --python <path>." >&2
  exit 1
}

echo "WaveMascot: installing from source"
py="$(buscar_python)"
"$py" -c 'import sys; sys.exit(sys.version_info < (3, 10))' || { echo "Python 3.10 or newer is required ($py)." >&2; exit 1; }
echo "  Python $("$py" -c 'import sys; print(sys.version.split()[0])') ($py)"

# Copia de archivos (si se reinstala, primero se cierran la mascota y el ícono que estén abiertos).
mkdir -p "$destino"
venv_py="$destino/venv/bin/python"
if [ "$(cd "$destino" && pwd)" != "$origen" ]; then
  if [ -f "$destino/instalador.py" ] && [ -x "$venv_py" ]; then
    "$venv_py" "$destino/instalador.py" detener --destino "$destino" >/dev/null 2>&1 || true
  fi
  for a in "${archivos[@]}"; do
    [ -f "$origen/$a" ] && cp -f "$origen/$a" "$destino/"
  done
  rm -rf "$destino/assets"
  cp -R "$origen/assets" "$destino/assets"
  chmod +x "$destino/uninstall.sh" 2>/dev/null || true
  echo "  Files copied to $destino"
fi

# Dependencias en un entorno virtual propio: no se tocan otras instalaciones de Python.
if [ ! -x "$venv_py" ]; then
  "$py" -m venv "$destino/venv"
fi
if ! "$venv_py" -c 'import PyQt6.QtMultimedia, PIL' >/dev/null 2>&1; then
  echo "  Installing PyQt6 and Pillow..."
  "$venv_py" -m pip install --disable-pip-version-check -q -r "$destino/requirements.txt"
fi

# Hooks (merge con backup), comando /wavemascot y el ícono al iniciar sesión.
"$venv_py" "$destino/instalador.py" configurar --tipo fuente --destino "$destino" --claude-dir "$claude_dir" $sin_inicio

if [ -z "$sin_inicio" ]; then
  (cd "$destino" && nohup "$venv_py" "$destino/bandeja.py" >/dev/null 2>&1 &)
fi

echo
echo "Done. Wave will show up the next time Claude Code finishes or needs something."
echo "Settings: the mascot icon in the menu bar or /wavemascot in Claude Code (the flag at the top changes the language)."
echo "Uninstall: \"$destino/uninstall.sh\""
