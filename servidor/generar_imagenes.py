#!/usr/bin/env python3
"""Genera las imágenes del bot de Telegram a partir de los sprites de Wave (necesita ffmpeg para el video).

    python servidor/generar_imagenes.py

Quedan en servidor/publico/img y se publican con el Worker (npx wrangler deploy):
  perfil.mp4       foto de perfil animada (Wave saludando), la sube /setup con setMyProfilePhoto
  perfil.jpg       la misma, quieta (por si el video no se acepta)
  saludo.gif       la manda el bot al tocar Iniciar sin código
  festejo.gif      la manda el bot al conectar una compu
  descripcion.gif  640x360 para /setdescriptionpic en BotFather (la API no permite cambiarla)
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ.parent))
import sprites  # noqa: E402
from PIL import Image  # noqa: E402

SALIDA = RAIZ / "publico" / "img"
FONDO = (0x1C, 0x15, 0x13)
ASPECTO = sprites.ASPECTO_DEFECTO


def cuadros(estado: str) -> tuple[list[Image.Image], int]:
    lista, ms = sprites.ESTADOS[estado](ASPECTO)
    return [c.convert("RGBA") for c in lista], ms


def caja_comun(lista: list[Image.Image]) -> tuple[int, int, int, int]:
    """El rectángulo que ocupa Wave en todos los cuadros (así no "salta" al recortar)."""
    cajas = [c.getbbox() for c in lista if c.getbbox()]
    return (min(c[0] for c in cajas), min(c[1] for c in cajas), max(c[2] for c in cajas), max(c[3] for c in cajas))


def lienzo(lista: list[Image.Image], ancho: int, alto: int, alto_wave: int, dy: int = 0) -> list[Image.Image]:
    """Cada cuadro recortado, agrandado sin suavizar y centrado sobre el fondo."""
    caja = caja_comun(lista)
    escala = max(1, alto_wave // (caja[3] - caja[1]))
    salida = []
    for c in lista:
        recorte = c.crop(caja)
        recorte = recorte.resize((recorte.width * escala, recorte.height * escala), Image.NEAREST)
        fondo = Image.new("RGBA", (ancho, alto), (*FONDO, 255))
        fondo.alpha_composite(recorte, ((ancho - recorte.width) // 2, (alto - recorte.height) // 2 + dy))
        salida.append(fondo.convert("RGB"))
    return salida


def guardar_gif(lista: list[Image.Image], ms: int, ruta: Path) -> None:
    planos = [c.convert("P", palette=Image.ADAPTIVE, colors=64) for c in lista]
    planos[0].save(ruta, format="GIF", save_all=True, append_images=planos[1:], duration=ms, loop=0, optimize=False)


def guardar_mp4(lista: list[Image.Image], ms: int, ruta: Path, vueltas: int = 3) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("falta ffmpeg para el video de perfil")
    with tempfile.TemporaryDirectory() as carpeta:
        n = 0
        for _ in range(vueltas):
            for c in lista:
                c.save(Path(carpeta) / f"{n:04d}.png")
                n += 1
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-framerate", f"{1000 / ms:.4f}",
                        "-i", str(Path(carpeta) / "%04d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-r", "30", "-crf", "18", "-movflags", "+faststart", "-an", str(ruta)], check=True)


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    saludo, ms_saludo = cuadros("idle_saludo")
    festejo, ms_festejo = cuadros("listo")

    # Perfil: Telegram lo recorta en círculo, así que Wave va chica y centrada.
    perfil = lienzo(saludo, 640, 640, 400)
    guardar_mp4(perfil, ms_saludo, SALIDA / "perfil.mp4")
    perfil[0].save(SALIDA / "perfil.jpg", quality=95)

    guardar_gif(lienzo(saludo, 360, 360, 260), ms_saludo, SALIDA / "saludo.gif")
    guardar_gif(lienzo(festejo, 360, 360, 260), ms_festejo, SALIDA / "festejo.gif")
    guardar_gif(lienzo(saludo, 640, 360, 260), ms_saludo, SALIDA / "descripcion.gif")
    for archivo in sorted(SALIDA.iterdir()):
        print(f"{archivo.name:16} {archivo.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
