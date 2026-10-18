#!/usr/bin/env python3
"""Punto de entrada de WaveMascot.exe (el build de PyInstaller).

Un solo ejecutable hace de todo según el primer argumento:

    WaveMascot.exe --estado listo     hook de Claude Code (igual que "mascota.py --estado listo")
    WaveMascot.exe mascota --ui ...   la ventana de la mascota (la lanza el hook)
    WaveMascot.exe ajustes            centro de ajustes
    WaveMascot.exe bandeja            ícono junto al reloj
    WaveMascot.exe desinstalar        desinstalador
"""

from __future__ import annotations

import os
import sys
import traceback

import mascota as m

PROGRAMAS = ("mascota", "ajustes", "bandeja", "desinstalar")


def main() -> int:
    programa = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in PROGRAMAS else "mascota"
    if len(sys.argv) > 1 and sys.argv[1] == programa:
        del sys.argv[1]  # cada módulo ve sus argumentos como si lo hubieran llamado directo
    if programa == "ajustes":
        if "--ventana" not in sys.argv[1:]:
            m.lanzar_desacoplado(["ajustes.py", "--ventana"])  # el /wavemascot no tiene que esperar
            return 0
        import ajustes
        return ajustes.ejecutar_ventana()
    if programa == "bandeja":
        import bandeja
        return bandeja.main()
    if programa == "desinstalar":
        import instalador
        return instalador.main(["desinstalar", *sys.argv[1:]])
    return m.main()


if __name__ == "__main__":
    try:
        codigo = main()
    except Exception:  # nunca un error que frene a Claude Code: se registra y se sale con 0
        m.log("[exe] error:\n" + traceback.format_exc())
        codigo = 0
    os._exit(codigo)
