"""Dibujo de la mascota en pixel art: estilo, color, cabeza, ropa y accesorio.

mascota.py y ajustes.py lo usan para generar (y guardar en caché) los GIF del aspecto
elegido. Ejecutado directamente regenera los sonidos y el ícono:

    python sprites.py

Cada cuadro se dibuja en una grilla de 56x56 "píxeles de arte" y se guarda escalado
x4 (sin suavizado) como GIF animado con fondo transparente. Pillow se importa recién
al dibujar, así importar este módulo (por ejemplo desde el hook) es instantáneo.
"""

import io
import math
import os
import random
import struct
import wave
from pathlib import Path

VERSION = 2  # subirla cuando cambie el dibujo, para invalidar la caché
CACHE = Path.home() / ".wavemascot" / "cache"
LADO = 56
ESCALA = 4  # debe coincidir con PIXEL_ASSET en mascota.py
SUELO = 52  # fila donde apoyan los pies
CX = LADO // 2

PALETA = [
    (255, 0, 255),    # transparente
    (43, 26, 20),     # contorno
    (217, 119, 87),   # cuerpo (lo reemplaza el color elegido)
    (180, 89, 60),    # sombra del cuerpo
    (242, 165, 132),  # brillo del cuerpo
    (250, 243, 230),  # crema
    (240, 138, 138),  # rubor / lengua
    (255, 209, 102),  # chispa / oro
    (255, 255, 255),  # blanco
    (91, 192, 248),   # azul
    (123, 211, 137),  # verde
    (180, 140, 242),  # violeta
    (229, 72, 77),    # rojo
    (168, 176, 186),  # nube
    (107, 116, 128),  # nube oscura
    (201, 169, 79),   # chispa apagada
    (67, 160, 71),    # hoja
    (150, 146, 84),   # hoja marchita
    (176, 46, 56),    # rojo oscuro
    (60, 110, 196),   # azul de la ropa
    (38, 70, 138),    # azul oscuro
    (204, 150, 40),   # oro oscuro
    (54, 48, 60),     # sombrero oscuro
    (240, 204, 170),  # piel (la cara del ninja; la reemplaza el tono elegido)
    (94, 234, 255),   # luz de los ojos del robot
    (255, 150, 40),   # fuego de los cohetes
]
(TRANSP, CONT, CUERPO, SOMBRA, BRILLO, CREMA, RUBOR, CHISPA, BLANCO, AZUL, VERDE, VIOLETA,
 ROJO, NUBE, NUBE_OSC, CHISPA_OFF, HOJA, HOJA_OFF, ROJO_OSC, AZUL_ROPA, AZUL_OSC, ORO_OSC,
 OSCURO, PIEL, LED, FUEGO) = range(len(PALETA))

# Opciones del vestuario: id -> nombre visible.
COLORES = {  # nombre, cuerpo, sombra, brillo
    "terracota": ("Terracota", (217, 119, 87), (180, 89, 60), (242, 165, 132)),
    "menta": ("Menta", (122, 201, 160), (76, 156, 118), (184, 234, 206)),
    "lavanda": ("Lavanda", (142, 128, 232), (103, 88, 196), (190, 180, 255)),
    "naranja": ("Naranja", (240, 162, 92), (201, 120, 52), (255, 207, 152)),
    "rosa": ("Rosa", (240, 138, 178), (202, 96, 140), (255, 196, 220)),
    "celeste": ("Celeste", (104, 186, 238), (62, 140, 200), (176, 224, 255)),
    "amarillo": ("Amarillo", (242, 200, 84), (206, 158, 40), (255, 232, 158)),
    "grafito": ("Grafito", (138, 140, 152), (100, 102, 114), (190, 192, 202)),
    "sombra": ("Sombra", (58, 60, 72), (36, 38, 46), (90, 94, 108)),
    "acero": ("Acero", (150, 160, 174), (106, 116, 130), (198, 206, 216)),
    "carmesi": ("Carmesí", (200, 62, 70), (152, 38, 48), (236, 116, 118)),
    "bosque": ("Bosque", (96, 142, 100), (64, 104, 72), (146, 188, 146)),
    "noche": ("Noche", (72, 92, 148), (50, 64, 112), (118, 140, 196)),
}
# Orden de las muestras en ajustes: por tono, y los neutros aparte (None = salto de línea).
ORDEN_COLORES = ["carmesi", "terracota", "naranja", "amarillo", "bosque", "menta", "celeste", "noche", "lavanda",
                 "rosa", None, "grafito", "acero", "sombra"]
# Estilos: cambian la cara de la mascota y cómo aparece, festeja y se va. Cada uno guarda su color.
ESTILOS = {"clasico": "Clásico", "sakura": "Sakura", "ninja": "Ninja", "robot": "Robot"}
COLOR_SUGERIDO = {"clasico": "terracota", "sakura": "rosa", "ninja": "sombra", "robot": "acero"}
PIELES = {"clara": ("Clara", (240, 204, 170)), "triguena": ("Trigueña", (222, 176, 134)),
          "morena": ("Morena", (176, 124, 88)), "oscura": ("Oscura", (118, 80, 56))}
# Colores propios de cada estilo: contorno, borde claro de afuera (CREMA) y rubor.
PALETA_ESTILO = {
    "clasico": {},
    "sakura": {CONT: (74, 30, 56), CREMA: (255, 236, 244), RUBOR: (255, 128, 166)},
    "ninja": {CONT: (6, 6, 8), CREMA: (118, 122, 138)},
    "robot": {CONT: (18, 22, 30), CREMA: (214, 224, 234)},
}
CON_ENTRADA = ("sakura", "ninja", "robot")  # el Clásico entra y sale solo deslizándose
CUADROS_DESLIZ = 8  # cuadros de la entrada (los primeros) y de la salida (los últimos) que van deslizándose
CABEZAS = {"chispa": "Chispa", "hoja": "Brote", "luna": "Luna", "orejas": "Orejas",
           "gorro": "Gorro", "galera": "Galera", "corona": "Corona", "gorra": "Gorra", "nada": "Nada"}
ROPAS = {"nada": "Nada", "remera": "Remera", "bufanda": "Bufanda", "mono": "Moño", "corbata": "Corbata",
         "capa": "Capa"}
ACCESORIOS = {"nada": "Nada", "anteojos": "Anteojos", "lentes": "Lentes de sol", "auriculares": "Auriculares",
              "flor": "Flor"}
OPCIONES = {"color": COLORES, "cabeza": CABEZAS, "ropa": ROPAS, "accesorio": ACCESORIOS}
ASPECTO_DEFECTO = {"color": "terracota", "cabeza": "chispa", "ropa": "nada", "accesorio": "nada",
                   "estilo": "clasico", "piel": "clara"}
# Los skins de la versión anterior, para traducir configuraciones viejas.
PRESETS = {
    "clasico": ASPECTO_DEFECTO,
    "menta": {**ASPECTO_DEFECTO, "color": "menta", "cabeza": "hoja"},
    "noche": {**ASPECTO_DEFECTO, "color": "lavanda", "cabeza": "luna"},
    "michi": {**ASPECTO_DEFECTO, "color": "naranja", "cabeza": "orejas"},
}

FORMAS_CHISPA = {
    "mas": [(0, 0), (1, 0), (2, 0), (-1, 0), (-2, 0), (0, 1), (0, 2), (0, -1), (0, -2)],
    "chica": [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)],
}
LUNA = [(x, y) for x in range(-2, 3) for y in range(-2, 3)
        if x * x + y * y <= 5 and (x - 1) ** 2 + (y + 1) ** 2 > 2]
LUNA_CHICA = [(-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1)]
HOJA_IZQ = [(-4, -2), (-3, -2), (-4, -1), (-3, -1), (-2, -1), (-3, 0), (-2, 0), (-1, 0)]
HOJAS = HOJA_IZQ + [(-x, y - 1) for x, y in HOJA_IZQ]
HOJAS_CAIDAS = [(s * x, y) for s in (-1, 1) for x, y in [(1, 1), (2, 1), (2, 2), (3, 2), (3, 3)]]
ANILLO = [(x, y) for x in range(-3, 4) for y in range(-3, 4) if 2.3 <= math.hypot(x, y) <= 3.4]
ALA_MONO = [(-4, -1), (-3, -1), (-4, 0), (-3, 0), (-2, 0), (-4, 1), (-3, 1)]
NUDO_MONO = [(0, -1), (0, 0), (0, 1), (-1, 0), (1, 0)]
FLOR = [(0, 0), (0, -1), (0, -2), (1, 0), (2, 0), (0, 1), (0, 2), (-1, 0), (-2, 0),
        (1, -1), (-1, -1), (1, 1), (-1, 1)]
# Cuánto subir la nube del estado triste para que no tape cada sombrero.
ALTO_SOMBRERO = {"galera": 4, "gorro": 3, "corona": 2}


def normalizar(aspecto) -> dict:
    """Completa el aspecto con los valores por defecto y descarta opciones desconocidas.

    "colores" guarda el color de cada estilo; "color" es siempre el del estilo elegido."""
    aspecto = aspecto if isinstance(aspecto, dict) else {}
    a = {clave: aspecto.get(clave) if aspecto.get(clave) in opciones else ASPECTO_DEFECTO[clave]
         for clave, opciones in OPCIONES.items()}
    estilo = aspecto.get("estilo") if aspecto.get("estilo") in ESTILOS else "clasico"
    guardados = aspecto.get("colores") if isinstance(aspecto.get("colores"), dict) else {}
    colores = {e: guardados[e] if guardados.get(e) in COLORES else COLOR_SUGERIDO[e] for e in ESTILOS}
    if aspecto.get("color") in COLORES:
        colores[estilo] = aspecto["color"]
    a.update(estilo=estilo, color=colores[estilo], colores=colores,
             piel=aspecto.get("piel") if aspecto.get("piel") in PIELES else "clara")
    return a


def con_estilo(aspecto, estilo: str) -> dict:
    """El aspecto con otro estilo (y el color que ese estilo tiene guardado)."""
    a = normalizar(aspecto)
    return {**a, "estilo": estilo, "color": a["colores"][estilo]}


def lienzo(aspecto, lado=LADO) -> "Lienzo":
    return Lienzo(aspecto["color"], lado, aspecto.get("estilo", "clasico"), aspecto.get("piel", "clara"))


class Lienzo:
    def __init__(self, color="terracota", lado=LADO, estilo="clasico", piel="clara"):
        from PIL import Image, ImageDraw

        self.img = Image.new("P", (lado, lado), TRANSP)
        _, cuerpo, sombra, brillo = COLORES.get(color, COLORES["terracota"])
        colores = {**PALETA_ESTILO.get(estilo, {}), CUERPO: cuerpo, SOMBRA: sombra, BRILLO: brillo,
                   PIEL: PIELES.get(piel, PIELES["clara"])[1]}
        plana = [c for i, rgb in enumerate(PALETA) for c in colores.get(i, rgb)]
        self.img.putpalette(plana + [0] * (768 - len(plana)))
        self.img.info["transparency"] = TRANSP
        self.d = ImageDraw.Draw(self.img)

    def px(self, x, y, color, detras=False):
        if 0 <= x < self.img.width and 0 <= y < self.img.height:
            if detras and self.img.getpixel((x, y)) != TRANSP:
                return
            self.img.putpixel((x, y), color)

    def pxs(self, puntos, color, detras=False):
        for x, y in puntos:
            self.px(x, y, color, detras)

    def borde_exterior(self, color):
        """Contorno claro de 1 px alrededor de todo lo dibujado (estilo sticker),
        para que la mascota se lea también sobre fondos oscuros."""
        from PIL import Image, ImageChops, ImageFilter

        indices = Image.frombytes("L", self.img.size, self.img.tobytes())
        lleno = indices.point(lambda i: 0 if i == TRANSP else 255)
        borde = ImageChops.subtract(lleno.filter(ImageFilter.MaxFilter(3)), lleno)
        self.img.paste(color, mask=borde)

    def elipse(self, caja, color):
        self.d.ellipse(caja, fill=color)

    def figura(self, puntos, color, contorno=CONT):
        """Pinta un grupo de píxeles con un contorno de 1 px alrededor."""
        dentro = set(puntos)
        if contorno is not None:
            borde = {(x + dx, y + dy) for x, y in dentro
                     for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))} - dentro
            self.pxs(borde, contorno)
        self.pxs(dentro, color)


def espejo(puntos, cx):
    return [(2 * cx - x, y) for x, y in puntos]


def rect(x0, y0, x1, y1):
    return [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]


class Cuerpo:
    """Geometría del cuerpo en un cuadro, para ubicar ropa y accesorios."""

    def __init__(self, dy, ancho, alto, dx=0):
        self.cx = CX + dx
        self.abajo = SUELO - 2 + dy
        self.arriba = self.abajo - alto + 1
        self.alto, self.mitad = alto, ancho // 2
        self.izq, self.der = self.cx - self.mitad, self.cx + self.mitad
        self.centro_y = (self.arriba + self.abajo) / 2
        self.ey = self.arriba + alto * 9 // 20           # fila de los ojos
        self.hombro_y = self.arriba + alto * 11 // 20
        self.ex = self.cx - (5 + (ancho - 25) // 4)       # centro del ojo izquierdo

    def adentro(self, x, y, margen=1.0) -> bool:
        rx, ry = self.mitad - margen, self.alto / 2 - margen
        return ((x - self.cx) / rx) ** 2 + ((y - self.centro_y) / ry) ** 2 <= 1

    def media_ancho(self, y) -> float:
        t = (y - self.centro_y) / (self.alto / 2)
        return self.mitad * math.sqrt(max(0.0, 1 - t * t))


# --- partes de la mascota ---------------------------------------------------

def ojo(tipo, c, e):
    """Píxeles (oscuros, blancos) del ojo izquierdo con centro (c, e)."""
    if tipo == "abierto":
        return rect(c - 1, e - 1, c, e + 1), [(c - 1, e - 1)]
    if tipo == "grande":
        return rect(c - 1, e - 2, c + 1, e + 1), [(c - 1, e - 2), (c - 1, e - 1)]
    if tipo == "feliz":
        return [(c - 2, e + 1), (c - 1, e), (c, e - 1), (c + 1, e), (c + 2, e + 1)], []
    if tipo == "triste":
        ceja = [(c - 2, e - 2), (c - 1, e - 3), (c, e - 3), (c + 1, e - 4)]
        return rect(c - 1, e, c, e + 1) + ceja, [(c - 1, e)]
    if tipo == "cerrado":
        return [(c - 1, e + 1), (c, e + 1), (c + 1, e + 1)], []
    raise ValueError(tipo)


def boca(tipo, m, y):
    """Píxeles (oscuros, rosados) de la boca centrada en x=m."""
    if tipo == "sonrisa":
        return [(m - 2, y), (m + 2, y), (m - 1, y + 1), (m, y + 1), (m + 1, y + 1)], []
    if tipo == "abierta":
        oscuro = rect(m - 2, y, m + 2, y) + [(m - 2, y + 1), (m + 2, y + 1)] + rect(m - 1, y + 2, m + 1, y + 2)
        return oscuro, rect(m - 1, y + 1, m + 1, y + 1)
    if tipo == "o":
        return [p for p in rect(m - 1, y, m + 1, y + 2) if p != (m, y + 1)], [(m, y + 1)]
    if tipo == "triste":
        return [(m - 2, y + 1), (m - 1, y), (m, y), (m + 1, y), (m + 2, y + 1)], []
    if tipo == "gato":
        return [(m - 2, y), (m - 1, y + 1), (m, y), (m + 1, y + 1), (m + 2, y)], [(m, y - 1)]
    if tipo == "plana":
        return [(m - 1, y + 1), (m, y + 1), (m + 1, y + 1)], []
    raise ValueError(tipo)


def mano(pose, lado, c):
    alto = c.abajo - c.arriba
    return {
        "abajo": (c.cx + lado * (c.mitad + 1), c.abajo - 3),
        "lado": (c.cx + lado * (c.mitad + 4), c.arriba + alto * 2 // 5),
        "arriba": (c.cx + lado * (c.mitad + 2), c.arriba - 3),
        "ola1": (c.cx + lado * (c.mitad + 5), c.arriba),
        "ola2": (c.cx + lado * (c.mitad + 2), c.arriba - 5),
    }[pose]


def brazo(lz, hombro, punta):
    hx, hy = punta
    lz.d.line([hombro, punta], fill=CONT, width=4)
    lz.elipse((hx - 2, hy - 2, hx + 2, hy + 2), CONT)
    lz.d.line([hombro, punta], fill=CUERPO, width=2)
    lz.elipse((hx - 1, hy - 1, hx + 1, hy + 1), CUERPO)


def orejas(lz, c, caidas, inclinacion):
    cx, arriba = c.cx, c.arriba
    for lado in (-1, 1):
        if caidas:
            punta = [(cx + lado * 9, arriba + 5), (cx + lado * 13, arriba + 1), (cx + lado * 4, arriba + 2)]
            dentro = [(cx + lado * 9, arriba + 3), (cx + lado * 11, arriba + 2), (cx + lado * 7, arriba + 2)]
        else:
            punta = [(cx + lado * 10, arriba + 5), (cx + lado * 8 + inclinacion, arriba - 4),
                     (cx + lado * 3, arriba + 1)]
            dentro = [(cx + lado * 8, arriba + 2), (cx + lado * 8 + inclinacion, arriba - 1),
                      (cx + lado * 6, arriba + 1)]
        lz.d.polygon(punta, fill=CUERPO, outline=CONT)
        lz.d.polygon(dentro, fill=RUBOR)


def antena(lz, tipo, c, inclinacion, chispa, color_chispa):
    """Chispa, brote o luna sobre la cabeza; inclinacion == "caida" en el estado triste."""
    cx, arriba = c.cx, c.arriba
    caida = inclinacion == "caida"
    if tipo == "hoja":
        if caida:
            lz.pxs([(cx, arriba - 1)], CONT)
            lz.figura([(cx + x, arriba - 2 + y) for x, y in HOJAS_CAIDAS], HOJA_OFF)
        else:
            lz.pxs([(cx, arriba - 1), (cx + inclinacion, arriba - 2)], CONT)
            lz.figura([(cx + inclinacion + x, arriba - 3 + y) for x, y in HOJAS], HOJA)
    elif caida:
        lz.pxs([(cx, arriba - 1), (cx - 1, arriba - 2), (cx - 2, arriba - 2)], CONT)
        forma = FORMAS_CHISPA["chica"] if tipo == "chispa" else LUNA_CHICA
        lz.figura([(cx - 4 + x, arriba - 2 + y) for x, y in forma], CHISPA_OFF)
    else:
        lz.pxs([(cx, arriba - 1), (cx + inclinacion, arriba - 2)], CONT)
        forma = FORMAS_CHISPA[chispa] if tipo == "chispa" else LUNA
        lz.figura([(cx + inclinacion + x, arriba - 5 + y) for x, y in forma], color_chispa)


def sombrero(lz, tipo, c):
    cx, a = c.cx, c.arriba
    d = lz.d
    if tipo == "gorro":
        d.chord((cx - 9, a - 6, cx + 9, a + 8), 180, 360, fill=ROJO, outline=CONT)
        d.rectangle((cx - 10, a + 1, cx + 10, a + 4), fill=ROJO_OSC, outline=CONT)
        lz.pxs([(x, y) for x in range(cx - 8, cx + 9, 2) for y in (a + 2, a + 3)], ROJO)
        lz.figura(rect(cx - 1, a - 8, cx + 1, a - 6) + [(cx, a - 9), (cx, a - 5)], CREMA)
    elif tipo == "galera":
        d.rectangle((cx - 6, a - 9, cx + 6, a + 1), fill=OSCURO, outline=CONT)
        d.rectangle((cx - 10, a + 1, cx + 10, a + 3), fill=OSCURO, outline=CONT)
        lz.pxs(rect(cx - 5, a - 2, cx + 5, a), ROJO)
        lz.pxs([(cx - 4, y) for y in range(a - 8, a - 3)], NUBE_OSC)
    elif tipo == "corona":
        for x0, alto in ((cx - 7, 6), (cx - 2, 7), (cx + 4, 6)):
            ancho = 3 if alto == 6 else 4
            punta = x0 + (0 if x0 < cx - 3 else ancho if x0 > cx + 3 else ancho // 2)
            d.polygon([(x0, a), (punta, a - alto), (x0 + ancho, a)], fill=CHISPA, outline=CONT)
        d.rectangle((cx - 7, a - 1, cx + 7, a + 2), fill=CHISPA, outline=CONT)
        lz.pxs([(x, a + 1) for x in range(cx - 6, cx + 7)], ORO_OSC)
        lz.pxs([(cx, a)], ROJO)
        lz.pxs([(cx - 4, a), (cx + 4, a)], AZUL)
    elif tipo == "gorra":
        d.chord((cx - 9, a - 5, cx + 9, a + 9), 180, 360, fill=AZUL_ROPA, outline=CONT)
        d.polygon([(cx + 4, a + 1), (cx + 15, a + 2), (cx + 14, a + 4), (cx + 4, a + 3)], fill=AZUL_OSC, outline=CONT)
        lz.pxs([(cx, a - 5)], CREMA)
        lz.pxs([(cx - 3, a - 1), (cx - 2, a - 2), (cx - 2, a)], CHISPA)


def capa(lz, c, en_aire):
    """Va detrás del cuerpo: solo asoman los costados (y flamea al saltar)."""
    vuelo = 4 if en_aire else 1
    hombro = c.arriba + c.alto // 3
    puntos = [(c.izq + 3, hombro), (c.der - 3, hombro), (c.der + 2 + vuelo, c.abajo + 1 - vuelo),
              (c.cx, c.abajo + 2), (c.izq - 2 - vuelo, c.abajo + 1 - vuelo)]
    lz.d.polygon(puntos, fill=ROJO, outline=CONT)
    lz.d.line([(c.izq + 4, hombro + 2), (c.izq - vuelo, c.abajo - vuelo)], fill=ROJO_OSC)
    lz.d.line([(c.der - 4, hombro + 2), (c.der + vuelo, c.abajo - vuelo)], fill=ROJO_OSC)


def remera(lz, c):
    """Pinta de azul el cuerpo debajo de la cara (cuello en U) y el arranque de los brazos."""
    for x in range(c.izq, c.der + 1):
        inicio = c.ey + 7 - min(4, max(0, abs(x - c.cx) - 3))
        for y in range(inicio, c.abajo + 1):
            if not c.adentro(x, y, margen=0.5):
                continue
            actual = lz.img.getpixel((x, y))
            if actual in (CUERPO, BRILLO):
                lz.px(x, y, AZUL_OSC if y == inicio else AZUL_ROPA)
            elif actual == SOMBRA:
                lz.px(x, y, AZUL_OSC)
    for lado in (-1, 1):  # mangas cortas
        hx = c.cx + lado * (c.mitad - 2)
        for x in range(hx - 4, hx + 5):
            for y in range(c.hombro_y - 4, c.hombro_y + 5):
                if math.hypot(x - hx, y - c.hombro_y) <= 3.6 and not c.adentro(x, y, margen=0):
                    if 0 <= x < LADO and 0 <= y < LADO and lz.img.getpixel((x, y)) == CUERPO:
                        lz.px(x, y, AZUL_ROPA)


def bufanda(lz, c):
    y0 = min(c.ey + 6, c.abajo - 4)
    for fila, color in ((y0, CONT), (y0 + 1, ROJO), (y0 + 2, ROJO), (y0 + 3, CONT)):
        mitad = round(c.media_ancho(min(fila, c.abajo - 1))) + 1
        for x in range(c.cx - mitad, c.cx + mitad + 1):
            rayada = color == ROJO and (x - c.cx) % 4 == 0
            lz.px(x, fila, CREMA if rayada else color)
    lz.figura(rect(c.cx - 8, y0 + 3, c.cx - 6, y0 + 6), ROJO)
    lz.pxs([(c.cx - 8, y0 + 7), (c.cx - 6, y0 + 7)], CREMA)


def mono(lz, c):
    y = min(c.ey + 8, c.abajo - 3)
    lz.figura([(c.cx + x, y + yy) for x, yy in ALA_MONO + espejo(ALA_MONO, 0)], ROJO)
    lz.pxs([(c.cx + x, y + yy) for x, yy in NUDO_MONO], ROJO_OSC)


def corbata(lz, c):
    y = min(c.ey + 7, c.abajo - 5)
    hoja = rect(c.cx - 1, y, c.cx + 1, y + 1) + rect(c.cx - 1, y + 2, c.cx + 1, c.abajo - 1)
    hoja += [(c.cx, c.abajo)]
    lz.figura(hoja, AZUL_ROPA)
    lz.pxs([(c.cx - 1, y), (c.cx, y + 1)] + [(c.cx + 1, yy) for yy in range(y + 3, c.abajo - 1, 2)], AZUL_OSC)


def accesorio(lz, tipo, c):
    cx, ex, ey = c.cx, c.ex, c.ey
    if tipo == "anteojos":
        aro = [(ex + x, ey + y) for x, y in ANILLO]
        lz.pxs(aro + espejo(aro, cx), CONT)
        lz.pxs([(x, ey - 1) for x in range(ex + 3, 2 * cx - ex - 2)], CONT)
        patilla = [(ex - 4, ey - 1), (ex - 5, ey - 1)]
        lz.pxs(patilla + espejo(patilla, cx), CONT)
    elif tipo == "lentes":
        vidrio = [p for p in rect(ex - 3, ey - 2, ex + 2, ey + 2) if p not in ((ex - 3, ey + 2), (ex + 2, ey + 2))]
        lz.figura(vidrio, OSCURO)
        lz.figura(espejo(vidrio, cx), OSCURO)
        lz.pxs([(x, ey - 1) for x in range(ex + 3, 2 * cx - ex - 2)], CONT)
        brillo = [(ex - 2, ey - 1), (ex - 1, ey - 2)]
        lz.pxs(brillo + espejo(brillo, cx), BLANCO)
    elif tipo == "auriculares":
        alto_extra = c.alto / 2 + 2
        lz.d.arc((c.izq - 1, c.centro_y - alto_extra, c.der + 1, c.centro_y + alto_extra),
                 180, 360, fill=CONT, width=2)
        for lado in (-1, 1):
            x0 = c.izq - 1 if lado < 0 else c.der - 2
            lz.d.rounded_rectangle((x0, ey - 3, x0 + 3, ey + 3), radius=1, fill=OSCURO, outline=CONT)
            lz.px(x0 + (2 if lado < 0 else 1), ey, ROJO)
    elif tipo == "flor":
        x, y = cx + 8, c.arriba + 2
        lz.figura([(x + 2, y + 2), (x + 3, y + 3), (x + 2, y + 3)], HOJA)
        lz.figura([(x + dx, y + dy) for dx, dy in FLOR], RUBOR)
        lz.px(x, y, CHISPA)


# --- caras y detalles de cada estilo ------------------------------------------

FLOR_SAKURA = [(-1, -2), (1, -2), (-2, -1), (-1, -1), (0, -1), (1, -1), (2, -1), (-1, 0), (1, 0),
               (-2, 1), (-1, 1), (1, 1), (2, 1), (-1, 2), (1, 2)]
CORAZON = [(1, 0), (3, 0), (0, 1), (1, 1), (2, 1), (3, 1), (4, 1), (1, 2), (2, 2), (3, 2), (2, 3)]
HEBILLA = [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)]


def espejo_x(puntos, cx):
    """Espejo para figuras de ancho par centradas entre cx - 1 y cx."""
    return [(2 * cx - 1 - x, y) for x, y in puntos]


def ojo_sakura(tipo, c, e):
    """Sakura: ojos grandes, brillantes y con pestañas."""
    if tipo in ("abierto", "grande"):
        return rect(c - 1, e - 2, c + 1, e + 1) + [(c - 2, e - 2), (c - 3, e - 3)], [(c - 1, e - 2), (c - 1, e - 1), (c + 1, e + 1)]
    if tipo == "feliz":
        return ojo(tipo, c, e)[0] + [(c - 3, e)], []
    return ojo(tipo, c, e)


def antena_sakura(lz, tipo, c, inclinacion, chispa, color_chispa):
    """En Sakura la chispa de la antena es una flor de cerezo."""
    if tipo != "chispa":
        antena(lz, tipo, c, inclinacion, chispa, color_chispa)
        return
    cx, arriba = c.cx, c.arriba
    if inclinacion == "caida":
        lz.pxs([(cx, arriba - 1), (cx - 1, arriba - 2), (cx - 2, arriba - 2)], CONT)
        lz.figura([(cx - 4 + x, arriba - 2 + y) for x, y in FORMAS_CHISPA["chica"]], RUBOR)
        lz.px(cx - 4, arriba - 2, CHISPA_OFF)
        return
    lz.pxs([(cx, arriba - 1), (cx + inclinacion, arriba - 2)], CONT)
    x0, y0 = cx + inclinacion, arriba - 5
    lz.figura([(x0 + x, y0 + y) for x, y in FLOR_SAKURA] + [(x0, y0)], RUBOR)
    lz.px(x0, y0, CHISPA if color_chispa == CHISPA else BLANCO)
    if chispa == "mas":  # destello de la flor
        lz.px(x0 - 1, y0 - 1, CREMA)


def detalles_sakura(lz, c, aspecto):
    """Brillo del cuerpo con forma de corazón y hebilla de flor al costado de la cabeza."""
    x0, y0 = c.izq + 3, c.arriba + 3
    for x in range(x0, x0 + 7):
        for y in range(y0 - 1, y0 + 4):
            if lz.img.getpixel((x, y)) == BRILLO:
                lz.px(x, y, CUERPO)
    for a, b in CORAZON:  # solo sobre el cuerpo, nunca encima de una prenda
        if lz.img.getpixel((x0 + a, y0 + b)) in (CUERPO, BRILLO):
            lz.px(x0 + a, y0 + b, BRILLO)
    if aspecto.get("accesorio") != "flor":
        hx, hy = c.der - 3, c.arriba + 3
        lz.figura([(hx + a, hy + b) for a, b in HEBILLA], BLANCO)
        lz.px(hx, hy, RUBOR)


def cara_ninja(lz, c, tipo, mirada, fase):
    """Máscara con una franja de piel donde se ven los ojos (con cejas decididas) y vincha roja."""
    y0, y1 = c.ey - 2, c.ey + 3
    for y in range(y0, y1 + 1):
        lz.pxs([(x, y) for x in range(c.izq, c.der + 1) if c.adentro(x, y, 2.0)], PIEL)
    for y in (y0 - 1, y1 + 1):
        lz.pxs([(x, y) for x in range(c.izq, c.der + 1) if c.adentro(x, y, 2.0)], CONT)
    mx, my = mirada
    for lado in (-1, 1):
        cx = (c.ex + mx) if lado < 0 else (2 * c.cx - c.ex + mx)
        e = c.ey + my

        def pon(pts, color):
            lz.pxs(pts if lado < 0 else espejo_x(pts, cx), color)
        if tipo == "feliz":
            pon([(cx - 2, e + 1), (cx - 1, e), (cx, e), (cx + 1, e + 1)], CONT)
        elif tipo == "cerrado":
            pon([(cx - 2, e + 1), (cx - 1, e + 1), (cx, e + 1), (cx + 1, e + 1)], CONT)
        elif tipo == "triste":
            pon(rect(cx - 1, e, cx, e + 1), CONT)
            pon([(cx - 2, e - 1), (cx - 1, e - 2), (cx, e - 2), (cx + 1, e - 2)], CONT)
            lz.px(cx - 1 if lado < 0 else cx, e, BLANCO)
        else:
            alto = 3 if tipo == "grande" else 2
            pon(rect(cx - 1, e, cx, e + alto - 1), CONT)
            lz.px(cx - 1 if lado < 0 else cx, e, BLANCO)
            pon([(cx - 2, e - 1), (cx - 1, e - 2), (cx, e - 2), (cx + 1, e - 2)] if tipo == "grande" else
                [(cx - 2, e - 2), (cx - 1, e - 2), (cx, e - 1), (cx + 1, e - 1)], CONT)
    vincha(lz, c, fase)


def vincha(lz, c, fase):
    y = c.ey - 5
    for yy, color in ((y, ROJO), (y + 1, ROJO_OSC)):
        lz.pxs([(x, yy) for x in range(c.izq, c.der + 1) if c.adentro(x, yy, 0.6)], color)
    ola = math.sin(fase * 1.3)
    nx = c.der - 1
    colas = [(nx + 1 + i, y + dy0 + round(i * 0.45 + ola * (i / 3.5)) - (1 if k == 0 else 0))
             for k, dy0 in enumerate((0, 2)) for i in range(1, 8)]
    lz.figura(colas, ROJO)
    lz.figura(rect(nx - 1, y - 1, nx + 1, y + 1), ROJO)
    lz.px(nx, y, ROJO_OSC)


def cara_robot(lz, c, tipo, boca_tipo, mirada):
    """Visor con ojos de luz, boca de parlante y tornillos a los costados."""
    x0, x1 = c.ex - 4, 2 * c.cx - c.ex + 4
    y0, y1 = c.ey - 2, c.ey + 2
    lz.figura([p for p in rect(x0, y0, x1, y1) if p not in ((x0, y0), (x1, y0), (x0, y1), (x1, y1))], OSCURO)
    lz.pxs([(x0 + 1, y0), (x0 + 2, y0)], NUBE_OSC)  # reflejo del vidrio
    mx, my = mirada
    for lado in (-1, 1):
        cx = (c.ex + mx) if lado < 0 else (2 * c.cx - c.ex + mx)
        e = c.ey + my

        def pon(pts, color):
            lz.pxs(pts if lado < 0 else espejo_x(pts, cx), color)
        if tipo == "feliz":
            pon([(cx - 2, e + 1), (cx - 1, e), (cx, e), (cx + 1, e + 1)], LED)
        elif tipo == "cerrado":
            pon([(cx - 1, e + 1), (cx, e + 1)], NUBE_OSC)
        elif tipo == "triste":
            pon([(cx - 1, e + 1), (cx, e + 1), (cx - 2, e), (cx + 1, e - 1)], LED)
        elif tipo == "grande":
            pon(rect(cx - 1, e - 1, cx, e + 1), LED)
        elif tipo != "apagado":
            pon(rect(cx - 1, e - 1, cx, e), LED)
    m, y = c.cx, c.ey + 5
    if boca_tipo == "abierta":
        lz.figura(rect(m - 1, y, m + 1, y), LED)
    elif boca_tipo == "o":
        lz.figura([(m, y)], LED)
    elif boca_tipo == "triste":
        lz.pxs([(m - 3, y + 1)] + [(x, y) for x in range(m - 2, m + 3)] + [(m + 3, y + 1)], CONT)
    elif boca_tipo == "plana":
        lz.pxs([(x, y) for x in range(m - 2, m + 3)], CONT)
    else:  # sonrisa: rejilla de parlante
        lz.pxs([(m - 3, y - 1)] + [(x, y) for x in range(m - 2, m + 3)] + [(m + 3, y - 1)], CONT)
        lz.pxs([(m - 1, y + 1), (m + 1, y + 1)], CONT)
    for lado in (-1, 1):  # tornillos
        x = c.izq + 2 if lado < 0 else c.der - 2
        yy = round(c.centro_y + 4)
        if c.adentro(x, yy, 1.0):
            lz.px(x, yy, NUBE)
            lz.px(x + 1 if lado < 0 else x - 1, yy + 1, CONT)


def mascota(lz, aspecto, *, dy=0, ancho=25, alto=21, ojos="abierto", boca_tipo="sonrisa",
            brazos=("abajo", "abajo"), inclinacion=0, chispa="mas", color_chispa=CHISPA,
            rubor=True, lagrima=None, en_aire=False, mirada=(0, 0), dx=0, pies=None, fase=0):
    """Dibuja la mascota con su estilo y su vestuario, y devuelve su geometría para ubicar efectos.

    mirada (-1..1, -1..1) corre los ojos un pixel hacia donde mira.
    pies (izq, der): altura de cada pie respecto del suelo (negativo = levantado), para caminar.
    fase: cuadro de la animación, para lo que se mueve solo (las colas de la vincha del ninja)."""
    c = Cuerpo(dy, ancho, alto, dx)
    cabeza, ropa = aspecto["cabeza"], aspecto["ropa"]
    estilo = aspecto.get("estilo", "clasico")
    cara_propia = estilo in ("ninja", "robot")  # máscara o visor en vez de ojos y boca
    if cara_propia:
        rubor = False

    def adornos_cabeza():
        if cabeza in ("chispa", "hoja", "luna"):
            (antena_sakura if estilo == "sakura" else antena)(lz, cabeza, c, inclinacion, chispa, color_chispa)
        elif cabeza in ("gorro", "galera", "corona", "gorra"):
            sombrero(lz, cabeza, c)

    if ropa == "capa":
        capa(lz, c, en_aire)
    for i, lado in enumerate((-1, 1)):  # pies
        x0, x1 = sorted((c.cx + lado * 4, c.cx + lado * 9))
        y = c.abajo if pies is None else SUELO - 2 + pies[i]
        lz.elipse((x0, y - 2, x1, y + 2), CONT)
        lz.elipse((x0 + 1, y - 1, x1 - 1, y + 1), SOMBRA)
    for lado, pose in zip((-1, 1), brazos):
        brazo(lz, (c.cx + lado * (c.mitad - 2), c.hombro_y), mano(pose, lado, c))
    if cabeza == "orejas":
        orejas(lz, c, inclinacion == "caida", 0 if inclinacion == "caida" else inclinacion)

    lz.elipse((c.izq, c.arriba, c.der, c.abajo), CONT)  # cuerpo con sombra abajo a la derecha
    lz.elipse((c.izq + 1, c.arriba + 1, c.der - 1, c.abajo - 1), SOMBRA)
    lz.elipse((c.izq + 1, c.arriba + 1, c.der - 2, c.abajo - 3), CUERPO)
    lz.elipse((c.izq + 4, c.arriba + 3, c.izq + 8, c.arriba + 5), BRILLO)

    if ropa == "remera":
        remera(lz, c)
    elif ropa == "bufanda":
        bufanda(lz, c)
    if estilo == "clasico":  # en los otros estilos los sombreros van después de la cara
        adornos_cabeza()

    mx, my = mirada
    if not cara_propia:
        forma_ojo = ojo_sakura if estilo == "sakura" else ojo
        oscuro, blanco = forma_ojo(ojos, c.ex + mx, c.ey + my)
        oscuro_der, blanco_der = forma_ojo(ojos, c.ex - mx, c.ey + my)  # el espejo invierte x: se compensa
        lz.pxs(oscuro + espejo(oscuro_der, c.cx), CONT)
        lz.pxs(blanco + espejo(blanco_der, c.cx), BLANCO)
        if cabeza == "orejas" and boca_tipo == "sonrisa":
            boca_tipo = "gato"
        oscuro, rosa = boca(boca_tipo, c.cx, c.ey + 4)
        lz.pxs(oscuro, CONT)
        lz.pxs(rosa, RUBOR)
    if rubor:
        mejilla = [(c.ex - 3, c.ey + 2), (c.ex - 2, c.ey + 2)]
        lz.pxs(mejilla + espejo(mejilla, c.cx), RUBOR)
    if cabeza == "orejas":  # bigotes
        bigote = [(c.ex - 5, c.ey + 3), (c.ex - 6, c.ey + 3), (c.ex - 7, c.ey + 2),
                  (c.ex - 5, c.ey + 5), (c.ex - 6, c.ey + 6)]
        lz.pxs(bigote + espejo(bigote, c.cx), CONT)
    if lagrima is not None:
        y = c.ey + 2 + lagrima
        lz.figura([(c.ex - 1, y), (c.ex - 1, y + 1)], AZUL, contorno=None)
    if estilo == "ninja":
        cara_ninja(lz, c, ojos, mirada, fase)
    elif estilo == "robot":
        cara_robot(lz, c, ojos, boca_tipo, mirada)
    elif estilo == "sakura":
        detalles_sakura(lz, c, aspecto)
    if estilo != "clasico":
        adornos_cabeza()

    if ropa == "mono":
        mono(lz, c)
    elif ropa == "corbata":
        corbata(lz, c)
    accesorio(lz, aspecto["accesorio"], c)
    return c


# --- efectos -----------------------------------------------------------------

def confeti(lz, f, total):
    azar = random.Random(7)
    colores = [VERDE, VIOLETA, CHISPA, AZUL, ROJO, CREMA]
    for i in range(18):
        x0 = azar.randrange(2, LADO - 2)
        y = (azar.randrange(0, 50) + f * 5) % 50
        x = x0 + round(1.5 * math.sin(2 * math.pi * f / total + i))
        color = colores[i % len(colores)]
        lz.pxs([(x, y), (x + 1, y)] if (f + i) % 2 else [(x, y), (x, y + 1)], color, detras=True)


def destellos(lz, f):
    for i, (x, y) in enumerate([(7, 20), (48, 13), (50, 36), (5, 40)]):
        fase = (f + i * 3) % 6
        if fase < 2:
            lz.pxs([(x, y)], BLANCO, detras=True)
        elif fase < 4:
            lz.pxs([(x, y), (x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)], CHISPA, detras=True)


def burbuja(lz, f, cx, arriba):
    """Globo de diálogo con un "!" arriba a la izquierda."""
    x0, y0 = cx - 22, arriba - 21 + (f // 2) % 2
    lz.d.rounded_rectangle((x0, y0, x0 + 11, y0 + 12), radius=3, fill=CREMA, outline=CONT)
    lz.pxs([(x0 + 8, y0 + 13), (x0 + 9, y0 + 14), (x0 + 10, y0 + 15)], CONT)  # colita
    lz.pxs([(x0 + 7, y0 + 12), (x0 + 8, y0 + 12), (x0 + 9, y0 + 13), (x0 + 8, y0 + 13)], CREMA)
    lz.pxs([(x0 + 7, y0 + 13)], CONT)
    color = ROJO if f % 4 < 2 else CONT
    lz.pxs(rect(x0 + 5, y0 + 2, x0 + 6, y0 + 7) + rect(x0 + 5, y0 + 9, x0 + 6, y0 + 10), color)


def lineas_ola(lz, f, cx, arriba):
    x, y = cx + 20, arriba - 4
    if f % 2:
        lz.pxs([(x, y), (x + 1, y - 1), (x, y + 4), (x + 1, y + 5)], CONT)


def nube(lz, cx, arriba):
    cy = arriba - 13
    bultos = [(cx - 5, cy + 1, 4), (cx, cy - 1, 5), (cx + 5, cy + 1, 4)]
    for borde, color in ((1, CONT), (0, NUBE)):
        for x, y, r in bultos:
            lz.elipse((x - r - borde, y - r - borde, x + r + borde, y + r + borde), color)
        lz.d.rectangle((cx - 8 - borde, cy + 1, cx + 8 + borde, cy + 4 + borde), fill=color)
    lz.pxs([(x, cy + 4) for x in range(cx - 6, cx + 7)], NUBE_OSC)


def lluvia(lz, f, cx, arriba):
    cy = arriba - 13
    for i, x in enumerate((cx - 5, cx, cx + 5)):
        y = cy + 7 + (f + i * 4) % 10
        if y + 1 < arriba - 1:
            lz.pxs([(x, y), (x, y + 1)], AZUL, detras=True)


def pensamiento(lz, f, cx, arriba):
    """Globo de pensamiento arriba a la derecha, con puntos que van apareciendo."""
    lz.figura([(cx + 9, arriba - 2)], CREMA)
    lz.figura([(cx + 11, arriba - 5), (cx + 12, arriba - 5), (cx + 11, arriba - 6), (cx + 12, arriba - 6)], CREMA)
    lz.d.rounded_rectangle((cx + 10, arriba - 20, cx + 26, arriba - 9), radius=5, fill=CREMA, outline=CONT)
    for i in range((f // 2) % 4):
        lz.pxs(rect(cx + 13 + i * 4, arriba - 15, cx + 14 + i * 4, arriba - 14), CONT)


Z_CHICA = [(0, 0), (1, 0), (2, 0), (1, 1), (0, 2), (1, 2), (2, 2)]
Z_GRANDE = [(0, 0), (1, 0), (2, 0), (3, 0), (2, 1), (1, 2), (0, 3), (1, 3), (2, 3), (3, 3)]


def zetas(lz, f, total, cx, arriba):
    """"Zzz" que suben desde la cabeza mientras duerme."""
    for i, forma in enumerate((Z_CHICA, Z_GRANDE, Z_GRANDE)):
        fase = (f + i * total // 3) % total
        x, y = cx + 7 + i * 3 + fase // 3, arriba - 3 - i * 5 - fase
        if y > 1:
            lz.pxs([(x + a, y + b) for a, b in forma], CONT)


def ayudante(lz, f, x0, dy):
    """Mini mascota (el subagente) con un tilde que aparece arriba."""
    suelo = SUELO + dy
    lz.elipse((x0, suelo - 9, x0 + 10, suelo), CONT)
    lz.elipse((x0 + 1, suelo - 8, x0 + 9, suelo - 1), CUERPO)
    lz.pxs([(x0 + 3, suelo - 5), (x0 + 7, suelo - 5), (x0 + 4, suelo - 3), (x0 + 5, suelo - 3), (x0 + 6, suelo - 3)],
           CONT)
    lz.pxs([(x0 + 5, suelo - 10), (x0 + 5, suelo - 11)], CONT)
    lz.figura([(x0 + 5, suelo - 13), (x0 + 4, suelo - 13), (x0 + 6, suelo - 13), (x0 + 5, suelo - 12),
               (x0 + 5, suelo - 14)], CHISPA)
    if f >= 2:  # tilde de "terminado"
        tilde = [(0, 2), (1, 3), (2, 2), (3, 1), (4, 0)]
        lz.figura([(x0 + 6 + a, suelo - 22 + b) for a, b in tilde], VERDE)


# --- estados -----------------------------------------------------------------

def cuadros_listo(aspecto):
    if aspecto.get("estilo") in LISTO_ESTILO:
        return LISTO_ESTILO[aspecto["estilo"]](aspecto)
    salto = [(0, 27, 19), (-4, 23, 25), (-8, 25, 23), (-10, 25, 21), (-10, 25, 21),
             (-8, 25, 22), (-4, 25, 23), (0, 29, 18), (0, 27, 19), (0, 25, 21)]
    cuadros = []
    for f, (dy, ancho, alto) in enumerate(salto):
        lz = lienzo(aspecto)
        en_aire = dy < 0
        mascota(lz, aspecto, dy=dy, ancho=ancho, alto=alto, ojos="feliz", en_aire=en_aire,
                boca_tipo="abierta" if en_aire else "sonrisa",
                brazos=("arriba", "arriba") if en_aire else ("lado", "lado"),
                inclinacion=(0, 1, 0, -1)[f % 4],
                chispa="mas" if f % 2 == 0 else "chica",
                color_chispa=CHISPA if f % 4 < 2 else BLANCO)
        lz.borde_exterior(CREMA)
        confeti(lz, f, len(salto))
        destellos(lz, f)
        cuadros.append(lz.img)
    return cuadros, 90


def cuadros_permiso(aspecto):
    saltitos = [0, -1, -3, -1, 0, -1, -3, -1]
    cuadros = []
    for f, dy in enumerate(saltitos):
        lz = lienzo(aspecto)
        ancho, alto = (27, 20) if dy == 0 else (25, 21)
        c = mascota(lz, aspecto, dy=dy, ancho=ancho, alto=alto, ojos="grande", boca_tipo="o",
                    brazos=("abajo", "ola1" if f % 2 == 0 else "ola2"),
                    inclinacion=(1, -1)[f % 2], chispa="mas",
                    color_chispa=BLANCO if f % 2 else CHISPA)
        burbuja(lz, f, CX, SUELO - 2 - 21 + 1)
        lineas_ola(lz, f, c.cx, c.arriba)
        lz.borde_exterior(CREMA)
        cuadros.append(lz.img)
    return cuadros, 120


def cuadros_error(aspecto):
    respiro = [21, 21, 21, 20, 20, 19, 19, 20, 20, 21]
    tope = SUELO - 2 - 21 + 1 - ALTO_SOMBRERO.get(aspecto["cabeza"], 0)
    cuadros = []
    for f, alto in enumerate(respiro):
        lz = lienzo(aspecto)
        mascota(lz, aspecto, ancho=27, alto=alto, ojos="triste", boca_tipo="triste",
                brazos=("abajo", "abajo"), inclinacion="caida", rubor=False,
                lagrima=f if f < 6 else None)
        nube(lz, CX, tope)
        lz.borde_exterior(CREMA)
        lluvia(lz, f, CX, tope)
        cuadros.append(lz.img)
    return cuadros, 150


def cuadros_pensando(aspecto, mirada=(1, -1)):
    respiro = [21, 21, 20, 20, 21, 21, 20, 20]
    cuadros = []
    for f, alto in enumerate(respiro):
        lz = lienzo(aspecto)
        c = mascota(lz, aspecto, alto=alto, boca_tipo="plana", mirada=mirada, inclinacion=(0, 1, 0, -1)[f // 2 % 4],
                    chispa="mas" if f % 4 < 2 else "chica")
        pensamiento(lz, f, c.cx, SUELO - 2 - 21 + 1)
        lz.borde_exterior(CREMA)
        cuadros.append(lz.img)
    return cuadros, 170


def cuadros_subagente(aspecto):
    saltos = [0, -2, -4, -2, 0, -2, -4, -2]
    cuadros = []
    for f, dy in enumerate(saltos):
        lz = lienzo(aspecto)
        mascota(lz, aspecto, dx=-6, ojos="feliz" if f % 4 < 2 else "abierto", mirada=(1, 0),
                inclinacion=(0, 1)[f % 2])
        ayudante(lz, f, CX + 9, dy)
        lz.borde_exterior(CREMA)
        cuadros.append(lz.img)
    return cuadros, 110


def cuadros_limite(aspecto):
    respiro = [21, 21, 20, 20, 19, 19, 20, 20, 21, 21]
    cuadros = []
    for f, alto in enumerate(respiro):
        lz = lienzo(aspecto)
        c = mascota(lz, aspecto, ancho=27, alto=alto, ojos="cerrado", boca_tipo="o" if 3 <= f <= 6 else "plana",
                    inclinacion="caida", rubor=False)
        zetas(lz, f, len(respiro), c.cx, SUELO - 2 - 21 + 1)
        lz.borde_exterior(CREMA)
        cuadros.append(lz.img)
    return cuadros, 180


# Reposo del modo compañera: un ciclo base que acepta mirada y "extras" que se intercalan al azar.

def cuadros_idle(aspecto, mirada=(0, 0)):
    respiro = [21] * 4 + [20] * 4 + [21] * 4 + [20] * 4
    cuadros = []
    for f, alto in enumerate(respiro):
        lz = lienzo(aspecto)
        mascota(lz, aspecto, alto=alto, mirada=mirada, ojos="cerrado" if f == 13 else "abierto",
                inclinacion=(0, 0, 1, 0, 0, 0, -1, 0)[f // 2])
        lz.borde_exterior(CREMA)
        cuadros.append(lz.img)
    return cuadros, 200


def cuadros_idle_mirar(aspecto):
    miradas = [(0, 0), (-1, 0), (-1, 0), (-1, 0), (0, 0), (1, 0), (1, 0), (1, 0), (0, 0), (0, -1), (0, -1), (0, 0)]
    cuadros = []
    for mirada in miradas:
        lz = lienzo(aspecto)
        mascota(lz, aspecto, mirada=mirada, inclinacion=mirada[0])
        lz.borde_exterior(CREMA)
        cuadros.append(lz.img)
    return cuadros, 180


def cuadros_idle_saltito(aspecto):
    salto = [(0, 27, 19), (-3, 24, 23), (-5, 25, 21), (-3, 25, 22), (0, 27, 19), (0, 25, 21)]
    cuadros = []
    for f, (dy, ancho, alto) in enumerate(salto):
        lz = lienzo(aspecto)
        mascota(lz, aspecto, dy=dy, ancho=ancho, alto=alto, ojos="feliz", en_aire=dy < 0,
                brazos=("arriba", "arriba") if dy < 0 else ("abajo", "abajo"))
        lz.borde_exterior(CREMA)
        cuadros.append(lz.img)
    return cuadros, 90


def cuadros_idle_bostezo(aspecto):
    pasos = [(21, "abajo", "sonrisa", "abierto"), (22, "lado", "plana", "cerrado"), (23, "arriba", "o", "cerrado"),
             (23, "arriba", "abierta", "cerrado"), (23, "arriba", "abierta", "cerrado"),
             (23, "arriba", "abierta", "cerrado"), (22, "lado", "o", "cerrado"), (21, "abajo", "plana", "cerrado"),
             (21, "abajo", "sonrisa", "abierto")]
    cuadros = []
    for alto, brazos, boca_tipo, ojos in pasos:
        lz = lienzo(aspecto)
        mascota(lz, aspecto, ancho=23 if alto == 23 else 25, alto=alto, brazos=(brazos, brazos),
                boca_tipo=boca_tipo, ojos=ojos)
        lz.borde_exterior(CREMA)
        cuadros.append(lz.img)
    return cuadros, 160


def cuadros_idle_saludo(aspecto):
    cuadros = []
    for f in range(8):
        lz = lienzo(aspecto)
        mascota(lz, aspecto, ojos="feliz", brazos=("abajo", "ola1" if f % 2 == 0 else "ola2"),
                inclinacion=(1, -1)[f % 2])
        lz.borde_exterior(CREMA)
        cuadros.append(lz.img)
    return cuadros, 130


def cuadros_caminar(aspecto):
    """Ciclo de pasos mirando a la derecha (para la izquierda se dibuja en espejo)."""
    pasos = [((0, -2), -1), ((0, -1), 0), ((0, 0), 0), ((-2, 0), -1), ((-1, 0), 0), ((0, 0), 0)]
    cuadros = []
    for f, (pies, dy) in enumerate(pasos):
        lz = lienzo(aspecto)
        mascota(lz, aspecto, dy=dy, pies=pies, mirada=(1, 0), inclinacion=(-1, 0, 0, -1, 0, 0)[f],
                brazos=("lado", "abajo") if f < 3 else ("abajo", "lado"))
        lz.borde_exterior(CREMA)
        cuadros.append(lz.img)
    return cuadros, 110


# --- efectos y animaciones de los estilos ------------------------------------
# Entradas: los primeros CUADROS_DESLIZ cuadros se ven mientras la ventana se desliza desde el costado y
# el resto ya quieta. Salidas: al revés, los últimos CUADROS_DESLIZ son el deslizamiento hacia afuera.
# Están dibujadas llegando desde la derecha; en las esquinas izquierdas mascota.py las espeja.

def mascara(img):
    """Máscara (L) de lo dibujado en una imagen de la paleta."""
    return indices(img).point(lambda i: 0 if i == TRANSP else 255)


def indices(img):
    """Los índices de la paleta de una imagen, como imagen L."""
    from PIL import Image

    return Image.frombytes("L", img.size, img.tobytes())


def pegar(lz, img, detras=False):
    """Pega lo dibujado en img sobre el lienzo; detras = solo donde el lienzo está vacío."""
    from PIL import ImageChops

    m = mascara(img)
    if detras:
        m = ImageChops.multiply(m, indices(lz.img).point(lambda i: 255 if i == TRANSP else 0))
    lz.img.paste(img, (0, 0), m)


def transformar(img, rot=0, cy=40):
    """La mascota ya dibujada, inclinada rot grados alrededor de (CX, cy), sin suavizar."""
    from PIL import Image

    out = img.rotate(rot, resample=Image.NEAREST, center=(CX, cy), fillcolor=TRANSP)
    out.info["transparency"] = TRANSP
    return out


def cuadro_estilo(aspecto, despues=None, inclinar=None, **kw):
    """Un cuadro: la mascota (inclinada si hace falta), su borde claro y los efectos de despues(lz, c)."""
    lz = lienzo(aspecto)
    c = mascota(lz, aspecto, **kw)
    if inclinar:
        img = transformar(lz.img, *inclinar)
        lz = lienzo(aspecto)
        pegar(lz, img)
    lz.borde_exterior(CREMA)
    if despues:
        despues(lz, c)
    return lz.img


def vacio(aspecto, efecto):
    lz = lienzo(aspecto)
    efecto(lz)
    return lz.img


def humo(lz, t, cx=28, cy=42, detras=False):
    """Bomba de humo: t va de 0 (estalla) a 1 (se disipó)."""
    capa = Lienzo()
    azar = random.Random(3)
    for i in range(9):
        ang = i / 9 * 2 * math.pi + azar.random() * 0.5
        dist = 4 + 13 * t
        r = max(0, round((3 + azar.random() * 3) * (1.2 - t) + 2 * t * (1 - t) * 4))
        x, y = cx + math.cos(ang) * dist, cy + math.sin(ang) * dist * 0.65 - 6 * t
        if r <= 0:
            continue
        capa.elipse((x - r - 1, y - r - 1, x + r + 1, y + r + 1), NUBE_OSC)
        capa.elipse((x - r, y - r, x + r, y + r), NUBE)
        if r > 2:
            capa.px(round(x - r / 2), round(y - r / 2), BLANCO)
    if t < 0.35:
        r = round(9 * (0.35 - t) / 0.35) + 2
        capa.elipse((cx - r, cy - r, cx + r, cy + r), NUBE)
        capa.elipse((cx - r // 2, cy - r // 2, cx + r // 2, cy + r // 2), BLANCO)
    pegar(lz, capa.img, detras)


def nube_rodante(lz, f, lado, cx=28, cy=41):
    """El ninja escondido en una nube de humo que rueda; lado: hacia dónde quedan las líneas de velocidad."""
    capa = Lienzo()
    bultos = []
    for k in range(7):
        ang = k / 7 * 2 * math.pi - lado * f * 0.55
        bultos.append((cx + math.cos(ang) * 9, cy + math.sin(ang) * 8, 4 + k % 2))
    capa.elipse((cx - 10, cy - 9, cx + 10, cy + 9), NUBE_OSC)
    for x, y, r in bultos:
        capa.elipse((x - r - 1, y - r - 1, x + r + 1, y + r + 1), NUBE_OSC)
    capa.elipse((cx - 9, cy - 8, cx + 9, cy + 8), NUBE)
    for x, y, r in bultos:
        capa.elipse((x - r, y - r, x + r, y + r), NUBE)
        capa.px(round(x - 1), round(y - r + 1), BLANCO)
    for k, yy in enumerate((cy - 6, cy, cy + 6)):  # líneas de velocidad
        x0 = cx + lado * (15 + (f + k) % 3 * 2)
        capa.pxs([(x0 + lado * i, yy) for i in range(5 - k % 2)], NUBE)
    capa.pxs([(cx - 2, cy - 1), (cx - 1, cy - 1)], ROJO)  # se asoma un poquito la vincha
    pegar(lz, capa.img)


def shuriken(lz, x, y, f):
    forma = ([(0, 0), (1, 0), (2, 0), (-1, 0), (-2, 0), (0, 1), (0, 2), (0, -1), (0, -2)] if f % 2 == 0 else
             [(0, 0), (1, 1), (2, 2), (-1, -1), (-2, -2), (1, -1), (2, -2), (-1, 1), (-2, 2)])
    lz.figura([(x + a, y + b) for a, b in forma], NUBE)
    lz.px(x, y, CONT)


def corazones(lz, f):
    for i, x0 in enumerate((6, 45, 12, 40)):
        y = 30 - ((f * 3 + i * 9) % 30)
        x = x0 + round(math.sin(f / 2 + i) * 1.5)
        lz.figura([(x + a, y + b) for a, b in CORAZON], RUBOR)


def petalos(lz, f, n=10, semilla=5):
    azar = random.Random(semilla)
    for i in range(n):
        x0, v = azar.randrange(0, 56), 2 + azar.random() * 2
        y = round((azar.randrange(0, 56) + f * v) % 60 - 4)
        x = round(x0 + math.sin(f / 2 + i) * 3)
        lz.pxs([(x, y), (x + 1, y), (x, y + 1)] if (f + i) % 3 else [(x, y), (x + 1, y + 1)],
               RUBOR if i % 2 else CREMA, detras=True)


def estela_petalos(lz, f, lado):
    """Ráfaga de pétalos detrás de Sakura mientras llega flotando (lado: hacia dónde queda la estela)."""
    azar = random.Random(11)
    for i in range(16):
        x = CX + lado * (10 + azar.randrange(0, 18)) + lado * ((f * 2 + i) % 5)
        y = 18 + azar.randrange(0, 32) + (f + i) % 3
        lz.pxs([(x, y), (x + 1, y), (x, y + 1)] if (f + i) % 3 else [(x, y), (x + 1, y + 1)],
               RUBOR if i % 2 else CREMA, detras=True)


def tilde(lz, x, y, color):
    puntos = [(0, 3), (1, 4), (2, 5), (3, 4), (4, 3), (5, 2), (6, 1), (7, 0)]
    lz.figura([(x + a, y + b) for a, b in puntos] + [(x + a, y + b + 1) for a, b in puntos], color)


def fuego(lz, c, f, largo):
    """Llamas de los cohetes hacia abajo, bajo los pies del robot."""
    for lado in (-1, 1):
        x = c.cx + lado * 6
        largo_pie = largo + (f + (lado > 0)) % 2
        for i in range(largo_pie):
            color = CHISPA if i < max(1, largo_pie // 3) else FUEGO if i < largo_pie - 1 else ROJO
            lz.px(x, c.abajo + 2 + i, color)
            if i < largo_pie - 1:
                lz.px(x - 1, c.abajo + 2 + i, color)


def fuego_lado(lz, c, f, lado, largo=11):
    """Cohetes de los pies empujando hacia atrás mientras vuela (lado: hacia dónde sale el fuego)."""
    for pie in (-1, 1):
        x0, y0 = c.cx + pie * 6 + lado * 2, c.abajo
        largo_pie = largo + (f + (pie > 0)) % 3 - 1 - (2 if pie == -lado else 0)
        for i in range(largo_pie):
            grosor = 3 if i < largo_pie * 0.45 else 2 if i < largo_pie - 2 else 1
            color = BLANCO if i < 2 else CHISPA if i < largo_pie * 0.45 else FUEGO if i < largo_pie - 2 else ROJO
            borde = {CHISPA: FUEGO, FUEGO: ROJO}.get(color, color)
            x, yc = x0 + lado * i, y0 + i // 4
            for k in range(grosor):
                lz.px(x, yc - grosor // 2 + k, color if k == grosor // 2 or i < 2 else borde)
    azar = random.Random(f)
    for _ in range(4):  # chispas sueltas
        lz.px(c.cx + lado * (12 + largo + azar.randrange(0, 6)), c.abajo + azar.randrange(-2, 4), CHISPA)


def polvo(lz, t):
    """Polvo que levanta el robot al aterrizar."""
    for lado in (-1, 1):
        for k in range(3):
            x = CX + lado * (12 + t * 6 + k * 3)
            r = max(0, round(2 - t * 2 + (k == 1)))
            if r:
                lz.elipse((x - r, SUELO - 1 - k - r, x + r, SUELO - 1 - k + r), NUBE)


def cuerpo_en(dy=0, ancho=25, alto=21):
    return Cuerpo(dy, ancho, alto)


def cuadros_entrada(aspecto):
    estilo, cs, ms = aspecto.get("estilo"), [], 65
    if estilo == "ninja":
        for i in range(CUADROS_DESLIZ):  # llega rodando escondido en una nube de humo
            cs.append(vacio(aspecto, lambda lz, i=i: nube_rodante(lz, i, 1)))
        for i, (t, detras) in enumerate([(.08, False), (.2, False), (.38, True), (.58, True), (.8, True), (1, True)]):
            cs.append(cuadro_estilo(aspecto, ancho=26, alto=20, brazos=("lado", "abajo"), fase=i,
                                    ojos="feliz" if i == 3 else "abierto",  # la nube estalla y queda en guardia
                                    despues=lambda lz, c, t=t, detras=detras: humo(lz, t, 28, 42, detras)))
    elif estilo == "robot":
        for i in range(CUADROS_DESLIZ):  # vuela con los cohetes de los pies
            dy = -5 + (0, -1, 0, 1)[i % 4]
            cs.append(cuadro_estilo(aspecto, dy=dy, brazos=("lado", "lado"), en_aire=True, inclinar=(6, 44 + dy),
                                    despues=lambda lz, c, dy=dy, i=i: fuego_lado(lz, cuerpo_en(dy), i, 1)))
        for i, (dy, largo) in enumerate([(-3, 3), (-1, 2)]):  # baja
            cs.append(cuadro_estilo(aspecto, dy=dy, brazos=("lado", "lado"), en_aire=True,
                                    despues=lambda lz, c, i=i, largo=largo: fuego(lz, c, i, largo)))
        cs.append(cuadro_estilo(aspecto, ancho=30, alto=17, ojos="cerrado", despues=lambda lz, c: polvo(lz, 0)))
        cs.append(cuadro_estilo(aspecto, ancho=27, alto=19, ojos="apagado", despues=lambda lz, c: polvo(lz, 0.5)))
        cs.append(cuadro_estilo(aspecto, ojos="apagado", despues=lambda lz, c: polvo(lz, 1)))
        for ojos in ("abierto", "apagado", "feliz", "feliz"):  # se le prenden los ojos
            cs.append(cuadro_estilo(aspecto, ojos=ojos))
    elif estilo == "sakura":
        ms = 70
        for i in range(CUADROS_DESLIZ):  # llega flotando en una ráfaga de pétalos
            dy = -7 + (0, -1, -1, 0)[i % 4]
            cs.append(cuadro_estilo(aspecto, dy=dy, en_aire=True, ojos="feliz", brazos=("lado", "lado"),
                                    despues=lambda lz, c, i=i: estela_petalos(lz, i, 1)))
        for f, (dy, ancho, alto, brazos) in enumerate([(-4, 25, 21, ("lado", "lado")), (-1, 25, 21, ("lado", "lado")),
                                                      (0, 28, 19, ("abajo", "abajo")), (0, 25, 21, ("abajo", "ola1")),
                                                      (0, 25, 21, ("abajo", "ola2"))]):
            cs.append(cuadro_estilo(aspecto, dy=dy, ancho=ancho, alto=alto, ojos="feliz", brazos=brazos, en_aire=dy < 0,
                                    despues=lambda lz, c, f=f: petalos(lz, 8 + f, 8)))
    else:
        raise ValueError(f"el estilo {estilo!r} no tiene entrada propia")
    return cs, ms


def cuadros_salida(aspecto):
    estilo, cs, ms = aspecto.get("estilo"), [], 65
    if estilo == "ninja":
        cs.append(cuadro_estilo(aspecto, ancho=26, alto=20, brazos=("lado", "abajo")))
        cs.append(cuadro_estilo(aspecto, ancho=29, alto=18, brazos=("abajo", "abajo"), fase=1))
        cs.append(cuadro_estilo(aspecto, ancho=29, alto=18, brazos=("abajo", "abajo"), fase=2,
                                despues=lambda lz, c: humo(lz, .06, 28, 42)))
        for i in range(CUADROS_DESLIZ):  # se envuelve en humo y se va rodando
            cs.append(vacio(aspecto, lambda lz, i=i: nube_rodante(lz, i, -1)))
    elif estilo == "robot":
        cs.append(cuadro_estilo(aspecto, ojos="feliz", brazos=("abajo", "ola1")))
        cs.append(cuadro_estilo(aspecto, ancho=29, alto=18, despues=lambda lz, c: fuego(lz, c, 0, 1)))
        cs.append(cuadro_estilo(aspecto, ancho=29, alto=18, despues=lambda lz, c: fuego(lz, c, 1, 3)))
        cs.append(cuadro_estilo(aspecto, dy=-3, brazos=("lado", "lado"), en_aire=True,
                                despues=lambda lz, c: fuego(lz, c, 0, 4)))
        for i in range(CUADROS_DESLIZ):  # despega y sale volando
            dy = -5 + (0, -1, 0, 1)[i % 4]
            cs.append(cuadro_estilo(aspecto, dy=dy, brazos=("lado", "lado"), en_aire=True, inclinar=(-6, 44 + dy),
                                    despues=lambda lz, c, dy=dy, i=i: fuego_lado(lz, cuerpo_en(dy), i, -1)))
    elif estilo == "sakura":
        ms = 70
        cs.append(cuadro_estilo(aspecto, ojos="feliz", brazos=("abajo", "ola1")))
        cs.append(cuadro_estilo(aspecto, ojos="feliz", brazos=("abajo", "ola2")))
        cs.append(cuadro_estilo(aspecto, ancho=28, alto=19, ojos="feliz", brazos=("abajo", "abajo")))
        cs.append(cuadro_estilo(aspecto, dy=-4, en_aire=True, ojos="feliz", brazos=("lado", "lado"),
                                despues=lambda lz, c: petalos(lz, 3, 6)))
        for i in range(CUADROS_DESLIZ):  # se va flotando
            dy = -7 + (0, -1, -1, 0)[i % 4]
            cs.append(cuadro_estilo(aspecto, dy=dy, en_aire=True, ojos="feliz", brazos=("lado", "lado"),
                                    despues=lambda lz, c, i=i: estela_petalos(lz, i, -1)))
    else:
        raise ValueError(f"el estilo {estilo!r} no tiene salida propia")
    return cs, ms


def cuadros_listo_ninja(aspecto):
    """Se agacha, salta, tira un shuriken y vuelve a la guardia."""
    pasos = [(0, 26, 20, "abierto", ("lado", "abajo")), (0, 30, 17, "abierto", ("abajo", "abajo")),
             (-5, 24, 23, "feliz", ("arriba", "lado")), (-8, 25, 21, "feliz", ("arriba", "lado")),
             (-5, 25, 21, "feliz", ("abajo", "lado")), (0, 30, 17, "abierto", ("abajo", "abajo")),
             (0, 26, 20, "abierto", ("abajo", "lado")), (0, 26, 20, "abierto", ("abajo", "lado")),
             (0, 26, 20, "feliz", ("abajo", "abajo")), (0, 26, 20, "feliz", ("abajo", "abajo")),
             (0, 26, 20, "abierto", ("lado", "abajo")), (0, 26, 20, "abierto", ("lado", "abajo"))]
    cs = [cuadro_estilo(aspecto, dy=dy, ancho=ancho, alto=alto, ojos=ojos, brazos=brazos, en_aire=dy < 0, fase=i,
                        despues=lambda lz, c, i=i: shuriken(lz, 42 + (i - 6) * 4, 30 - (i - 6) * 2, i) if 6 <= i <= 10 else None)
          for i, (dy, ancho, alto, ojos, brazos) in enumerate(pasos)]
    return cs, 80


def cuadros_listo_sakura(aspecto):
    """Salta con corazones y pétalos."""
    salto = [(0, 27, 19), (-4, 23, 25), (-8, 25, 23), (-10, 25, 21), (-8, 25, 22), (-4, 25, 23), (0, 29, 18),
             (0, 27, 19), (0, 25, 21), (0, 25, 21)]
    cs = [cuadro_estilo(aspecto, dy=dy, ancho=ancho, alto=alto, ojos="feliz", en_aire=dy < 0,
                        boca_tipo="abierta" if dy < 0 else "sonrisa",
                        brazos=("arriba", "arriba") if dy < 0 else ("lado", "lado"),
                        despues=lambda lz, c, f=f: (corazones(lz, f), petalos(lz, f, 6)))
          for f, (dy, ancho, alto) in enumerate(salto)]
    return cs, 90


def cuadros_listo_robot(aspecto):
    """Salta con un empujoncito de los cohetes y aparece un tilde de luz."""
    pasos = [(0, 25, 21, "abierto", ("abajo", "abajo"), 0), (0, 29, 18, "abierto", ("lado", "lado"), 0),
             (-3, 24, 23, "feliz", ("arriba", "arriba"), 3), (-7, 25, 21, "feliz", ("arriba", "arriba"), 4),
             (-9, 25, 21, "feliz", ("arriba", "arriba"), 3), (-6, 25, 21, "feliz", ("arriba", "arriba"), 2),
             (-2, 25, 22, "feliz", ("lado", "lado"), 1), (0, 29, 18, "feliz", ("lado", "lado"), 0),
             (0, 26, 20, "feliz", ("abajo", "lado"), 0), (0, 25, 21, "feliz", ("abajo", "ola1"), 0),
             (0, 25, 21, "feliz", ("abajo", "ola2"), 0), (0, 25, 21, "abierto", ("abajo", "ola1"), 0)]

    def efectos(lz, c, f, largo):
        if largo:
            fuego(lz, c, f, largo)
        if f >= 2:
            tilde(lz, 41, max(3, 13 - f * 2), LED)
    cs = [cuadro_estilo(aspecto, dy=dy, ancho=ancho, alto=alto, ojos=ojos, brazos=brazos, en_aire=dy < 0,
                        despues=lambda lz, c, f=f, largo=largo: efectos(lz, c, f, largo))
          for f, (dy, ancho, alto, ojos, brazos, largo) in enumerate(pasos)]
    return cs, 85


LISTO_ESTILO = {"ninja": cuadros_listo_ninja, "sakura": cuadros_listo_sakura, "robot": cuadros_listo_robot}


def tiene_entrada(aspecto) -> bool:
    """Si el estilo aparece y se va con una animación propia (el Clásico solo se desliza)."""
    return normalizar(aspecto)["estilo"] in CON_ENTRADA


ESTADOS = {"listo": cuadros_listo, "permiso": cuadros_permiso, "error": cuadros_error, "caminar": cuadros_caminar,
           "pensando": cuadros_pensando, "subagente": cuadros_subagente, "limite": cuadros_limite,
           "idle": cuadros_idle, "idle_mirar": cuadros_idle_mirar, "idle_saltito": cuadros_idle_saltito,
           "idle_bostezo": cuadros_idle_bostezo, "idle_saludo": cuadros_idle_saludo,
           "entrada": cuadros_entrada, "salida": cuadros_salida}
IDLE_EXTRAS = ("idle_mirar", "idle_saltito", "idle_bostezo", "idle_saludo")
CON_MIRADA = ("idle",)  # estados cuyos ojos pueden seguir al cursor


def guardar_gif(cuadros, ms, ruta):
    from PIL import Image

    grandes = [c.resize((LADO * ESCALA, LADO * ESCALA), Image.NEAREST) for c in cuadros]
    grandes[0].save(ruta, format="GIF", save_all=True, append_images=grandes[1:], duration=ms, loop=0,
                    transparency=TRANSP, disposal=2, optimize=False)


def carpeta_cache(a) -> str:
    return f"v{VERSION}-{a['estilo']}-{a['color']}-{a['piel']}-{a['cabeza']}-{a['ropa']}-{a['accesorio']}"


def gif(aspecto, estado, mirada=None) -> Path:
    """Ruta del GIF de ese aspecto y estado; lo dibuja la primera vez que se pide."""
    a = normalizar(aspecto)
    nombre = estado if mirada is None else f"{estado}_m{mirada[0] + 1}{mirada[1] + 1}"
    ruta = CACHE / carpeta_cache(a) / f"{nombre}.gif"
    if not ruta.is_file():
        ruta.parent.mkdir(parents=True, exist_ok=True)
        cuadros, ms = ESTADOS[estado](a) if mirada is None else ESTADOS[estado](a, mirada)
        temporal = ruta.with_name(f"{nombre}.{os.getpid()}.tmp")
        guardar_gif(cuadros, ms, temporal)
        os.replace(temporal, ruta)  # atómico: dos avisos a la vez no se pisan
    return ruta


def gif_celular(aspecto, estado, fondo=(0x1C, 0x15, 0x13), escala=6) -> Path:
    """GIF para mandar al celular (Telegram): sobre un fondo de color, porque Telegram lo pasa a video y
    pierde la transparencia, y más grande para que se vea bien en el chat. Queda en caché como gif()."""
    from PIL import Image

    a = normalizar(aspecto)
    color = "%02x%02x%02x" % tuple(fondo)
    ruta = (CACHE / carpeta_cache(a)
            / f"celular-{estado}-{color}-{escala}.gif")
    if not ruta.is_file():
        ruta.parent.mkdir(parents=True, exist_ok=True)
        cuadros, ms = ESTADOS[estado](a)
        lado = LADO * escala
        planos = []
        for cuadro in cuadros:
            lienzo = Image.new("RGBA", (LADO, LADO), (*fondo, 255))
            lienzo.alpha_composite(cuadro.convert("RGBA"))
            planos.append(lienzo.convert("RGB").resize((lado, lado), Image.NEAREST)
                          .convert("P", palette=Image.ADAPTIVE, colors=64))
        temporal = ruta.with_name(f"{ruta.stem}.{os.getpid()}.tmp")
        planos[0].save(temporal, format="GIF", save_all=True, append_images=planos[1:], duration=ms, loop=0,
                       optimize=False)
        os.replace(temporal, ruta)
    return ruta


def miniatura(aspecto, recorte=(4, 14, 52, 56), escala=2) -> bytes:
    """PNG de la mascota quieta (para la galería de ajustes), recortado y ampliado."""
    from PIL import Image

    a = normalizar(aspecto)
    lz = lienzo(a)
    mascota(lz, a)
    lz.borde_exterior(CREMA)
    img = lz.img.crop(recorte).convert("RGBA")
    img = img.resize((img.width * escala, img.height * escala), Image.NEAREST)
    salida = io.BytesIO()
    img.save(salida, "PNG")
    return salida.getvalue()


def icono_bandeja(color="terracota", escala=1):
    """La mascota en 16x16 para el ícono junto al reloj (y el .ico del acceso directo)."""
    from PIL import Image

    lz = Lienzo(color, lado=16)
    lz.elipse((1, 5, 13, 15), CONT)
    lz.elipse((2, 6, 12, 14), CUERPO)
    lz.pxs([(3, 8), (4, 7)], BRILLO)
    lz.pxs([(5, 9), (5, 10), (9, 9), (9, 10), (6, 12), (7, 13), (8, 12)], CONT)
    lz.pxs([(7, 4), (7, 3)], CONT)
    lz.pxs([(7, 0), (6, 1), (7, 1), (8, 1), (7, 2)], CHISPA)
    img = lz.img.convert("RGBA")
    return img.resize((16 * escala, 16 * escala), Image.NEAREST)


def icono_app(lado: int):
    """El ícono de WaveMascot.app (macOS): la misma mascota, con el margen de los íconos de Mac
    (el dibujo ocupa ~81 % del lado) y agrandada sin suavizar."""
    from PIL import Image

    escala = max(1, round(lado * 0.8125 / 16))
    mascota = icono_bandeja(escala=escala)
    lienzo = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    lienzo.paste(mascota, ((lado - mascota.width) // 2, (lado - mascota.height) // 2))
    return lienzo


# --- sonidos -------------------------------------------------------------------

TASA = 22050


def nota(muestras, inicio, frec, dur, vol=1.0, frec_fin=None):
    """Suma una nota suave: seno con un poco de armónicos y caída rápida."""
    i0, n, fase = int(inicio * TASA), int(dur * TASA), 0.0
    for i in range(min(n, len(muestras) - i0)):
        f = frec if frec_fin is None else frec + (frec_fin - frec) * i / n
        fase += 2 * math.pi * f / TASA
        envolvente = min(1.0, i / (0.004 * TASA)) * (1 - i / n) ** 2.2
        muestras[i0 + i] += vol * envolvente * (math.sin(fase) + 0.3 * math.sin(2 * fase)
                                                 + 0.12 * math.sin(3 * fase))


def sonido_arpegio():
    m = [0.0] * int(0.6 * TASA)
    for k, (frec, t) in enumerate([(1046.5, 0), (1318.5, 0.07), (1568.0, 0.14), (2093.0, 0.21)]):
        nota(m, t, frec, 0.35 if k == 3 else 0.16, vol=1.0 if k == 3 else 0.8)
    return m


def sonido_doble():
    m = [0.0] * int(0.5 * TASA)
    nota(m, 0, 880.0, 0.2)
    nota(m, 0.13, 1318.5, 0.32)
    return m


def sonido_triste():
    m = [0.0] * int(0.75 * TASA)
    nota(m, 0, 784.0, 0.18, 0.9)
    nota(m, 0.15, 659.3, 0.18, 0.9)
    nota(m, 0.30, 523.3, 0.4, 1.0, frec_fin=494.0)
    return m


def sonido_pop():
    m = [0.0] * int(0.18 * TASA)
    nota(m, 0, 520.0, 0.16, frec_fin=1250.0)
    return m


def sonido_campana():
    m = [0.0] * int(1.0 * TASA)
    nota(m, 0, 1567.98, 0.9)
    nota(m, 0, 3135.96, 0.5, vol=0.25)
    return m


def sonido_burbuja():
    m = [0.0] * int(0.45 * TASA)
    for i, frec in enumerate((700.0, 950.0, 1250.0)):
        nota(m, i * 0.09, frec, 0.12, frec_fin=frec * 1.6)
    return m


def sonido_suave():
    m = [0.0] * int(0.7 * TASA)
    nota(m, 0, 659.25, 0.6, vol=0.8)
    nota(m, 0.12, 987.77, 0.55, vol=0.6)
    return m


def sonido_grave():
    m = [0.0] * int(0.8 * TASA)
    nota(m, 0, 330.0, 0.35)
    nota(m, 0.28, 247.0, 0.5, frec_fin=220.0)
    return m


# Sonidos para elegir en ajustes: id -> (nombre visible, generador).
SONIDOS = {"arpegio": ("Arpegio", sonido_arpegio), "doble": ("Doble tono", sonido_doble),
           "pop": ("Pop", sonido_pop), "campana": ("Campanita", sonido_campana),
           "burbuja": ("Burbujas", sonido_burbuja), "suave": ("Suave", sonido_suave),
           "triste": ("Triste", sonido_triste), "grave": ("Grave", sonido_grave)}


def guardar_wav(muestras, ruta):
    pico = max(abs(x) for x in muestras) or 1.0
    datos = b"".join(struct.pack("<h", int(32767 * 0.6 * x / pico)) for x in muestras)
    with wave.open(str(ruta), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TASA)
        w.writeframes(datos)


def main():
    assets = Path(__file__).resolve().parent / "assets"
    (assets / "sonidos").mkdir(parents=True, exist_ok=True)
    for viejo in (assets / "sonidos").glob("*.wav"):  # se regeneran todos
        viejo.unlink()
    for clave, (_, generar) in SONIDOS.items():
        guardar_wav(generar(), assets / "sonidos" / f"{clave}.wav")
    icono_bandeja(escala=3).save(assets / "icono.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    icono_app(1024).save(assets / "icono.icns", append_images=[icono_app(n) for n in (32, 64, 128, 256, 512)])
    print("assets/sonidos/*.wav, assets/icono.ico y assets/icono.icns regenerados")
    for estado in ESTADOS:
        print(gif(ASPECTO_DEFECTO, estado))


if __name__ == "__main__":
    main()
