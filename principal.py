#!/usr/bin/env python3
"""Punto de entrada de WaveMascot.exe y WaveMascot.app (el build de PyInstaller).

Un solo ejecutable hace de todo según el primer argumento:

    WaveMascot.exe --estado listo     hook de Claude Code (igual que "mascota.py --estado listo")
    WaveMascot.exe mascota --ui ...   la ventana de la mascota (la lanza el hook)
    WaveMascot.exe ajustes            centro de ajustes
    WaveMascot.exe bandeja            ícono junto al reloj
    WaveMascot.exe celular --aviso=…  manda un aviso a Telegram (lo lanza el hook)
    WaveMascot.exe desinstalar        desinstalador

En macOS, abrir WaveMascot.app (sin argumentos) instala la primera vez y después abre los
ajustes; "WaveMascot.app/Contents/MacOS/WaveMascot instalar --silencioso" instala sin preguntar.
"""

from __future__ import annotations

import os
import sys
import traceback

import mascota as m

PROGRAMAS = ("mascota", "ajustes", "bandeja", "celular", "desinstalar") + (("instalar",) if m.MAC else ())


def main() -> int:
    argumentos = [a for a in sys.argv[1:] if not a.startswith("-psn_")]  # macOS viejo agrega -psn_...
    if m.MAC and m.CONGELADO and not argumentos:  # doble click en WaveMascot.app
        import instalador
        return instalador.abrir_app()
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
    if programa == "celular":
        import celular
        return celular.main(sys.argv[1:])
    if programa in ("desinstalar", "instalar"):
        import instalador
        return instalador.main([programa, *sys.argv[1:]])
    return m.main()


if __name__ == "__main__":
    try:
        codigo = main()
    except Exception:  # nunca un error que frene a Claude Code: se registra y se sale con 0
        m.log("[exe] error:\n" + traceback.format_exc())
        codigo = 0
    os._exit(codigo)
