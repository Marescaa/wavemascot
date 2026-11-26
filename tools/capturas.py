"""Genera las imágenes y GIFs de docs/ (las que muestra el README) a partir de la app real.

Corre en una carpeta de usuario temporal (no lee ni escribe tu ~/.wavemascot), sin sonido y sin mostrar
nada en pantalla: las ventanas se dibujan fuera de pantalla y los avisos se pintan en una imagen.

    python tools/capturas.py            # todo
    python tools/capturas.py --solo-gif # solo los GIF de la mascota (no necesita Qt)
    python tools/capturas.py --solo=isla,ajustes --idioma=es   # una parte, en un idioma (para probar)

La isla y Uso leen transcripts de Claude Code: no se usan los tuyos, sino medio año de sesiones
inventadas que escribe tools/datos_ejemplo.py en la carpeta temporal.
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DOCS = RAIZ / "docs"
casa = Path(tempfile.mkdtemp(prefix="wave-capturas-"))
os.environ["USERPROFILE"] = os.environ["HOME"] = str(casa)
os.environ["USERNAME"] = os.environ["USER"] = "wave-capturas"  # otro canal: no le habla a tus ajustes abiertos
os.environ.pop("CLAUDE_CONFIG_DIR", None)  # los transcripts de ejemplo, nunca los tuyos
(casa / ".wavemascot").mkdir()
(casa / ".wavemascot" / "config.json").write_text(json.dumps({"sonido": False, "volumen": 0}))
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "tools"))

from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

import datos_ejemplo  # noqa: E402
import sprites  # noqa: E402

PROYECTOS = casa / ".claude" / "projects"
ARGS = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
SOLO = set(ARGS["solo"].split(",")) if "solo" in ARGS else None  # avisos, ajustes, isla


def toca(parte: str) -> bool:
    return SOLO is None or parte in SOLO

IDIOMAS = ("en", "es", "pt")
ESTADOS = ("listo", "permiso", "pensando", "subagente", "limite", "error")
FONDO = (0x1E, 0x1B, 0x22)  # "escritorio" oscuro: se ve bien con el tema claro y el oscuro de GitHub
# Un aspecto lindo por estilo, para las galerías
ASPECTOS = {
    "clasico": {"estilo": "clasico", "cabeza": "chispa"},
    "sakura": {"estilo": "sakura"},
    "ninja": {"estilo": "ninja"},
    "robot": {"estilo": "robot"},
    "hamburguesa": {"estilo": "hamburguesa"},
}


def guardar_gif(cuadros, ms, ruta: Path) -> None:
    """Cuadros RGB opacos -> GIF liviano con paleta común."""
    paleta = cuadros[0].quantize(colors=128, method=Image.Quantize.MEDIANCUT)
    planos = [c.quantize(palette=paleta, dither=Image.Dither.NONE) for c in cuadros]
    ruta.parent.mkdir(parents=True, exist_ok=True)
    planos[0].save(ruta, save_all=True, append_images=planos[1:], duration=ms, loop=0, optimize=True)
    print("  ", ruta.relative_to(RAIZ), f"{ruta.stat().st_size // 1024} KB")


def cuadros_de(aspecto, estado):
    cuadros, ms = sprites.ESTADOS[estado](sprites.normalizar(aspecto))
    return [c.convert("RGBA") for c in cuadros], ms


def sobre_fondo(cuadro, escala, lado=None):
    lado = lado or sprites.LADO
    lienzo = Image.new("RGBA", (lado, lado), (*FONDO, 255))
    lienzo.alpha_composite(cuadro, ((lado - cuadro.width) // 2, (lado - cuadro.height) // 2))
    return lienzo.convert("RGB").resize((lado * escala, lado * escala), Image.NEAREST)


def mezclar_tiempos(listas):
    """Varias animaciones en una grilla: avanzan juntas a 10 cuadros por segundo durante 4 s."""
    paso, total = 100, 4000
    salida = []
    for t in range(0, total, paso):
        fila = []
        for cuadros, ms in listas:
            ms = ms if isinstance(ms, int) else ms[0]
            fila.append(cuadros[(t // max(ms, 1)) % len(cuadros)])
        salida.append(fila)
    return salida, paso


def funcion_estilo(aspecto, escala=3, ancho_lienzo=2):
    """Entrada (deslizándose desde la derecha), festejo y salida de un estilo, en cuadros RGB."""
    a = sprites.normalizar(aspecto)
    n = sprites.CUADROS_DESLIZ
    lado = sprites.LADO
    if a["estilo"] == "clasico":
        quieto, ms = cuadros_de(a, "idle")
        entrada = [quieto[i % len(quieto)] for i in range(n)]
        salida = [quieto[i % len(quieto)] for i in range(n)]
        paso = 65
    else:
        entrada, paso = cuadros_de(a, "entrada")
        salida, _ = cuadros_de(a, "salida")
    listo, ms_listo = cuadros_de(a, "listo")
    ms_listo = ms_listo if isinstance(ms_listo, int) else ms_listo[0]
    festejo = [listo[int(i * paso / ms_listo) % len(listo)] for i in range(int(2200 / paso))]
    ancho = lado * ancho_lienzo
    centro = (ancho - lado) // 2

    def colocar(cuadro, x):
        hoja = Image.new("RGBA", (ancho, lado), (*FONDO, 255))
        hoja.alpha_composite(cuadro, (int(x), 0)) if 0 <= x <= ancho - lado else hoja.paste(cuadro, (int(x), 0), cuadro)
        return hoja.convert("RGB").crop((0, 2, ancho, lado)).resize((ancho * escala, (lado - 2) * escala), Image.NEAREST)

    def suave(t):
        return 1 - (1 - t) ** 3

    cuadros = []
    for i, c in enumerate(entrada):
        x = ancho - (ancho - centro) * suave(min(1, (i + 1) / n)) if i < n else centro
        cuadros.append(colocar(c, x))
    cuadros += [colocar(c, centro) for c in festejo]
    final = len(salida) - n
    for i, c in enumerate(salida):
        x = centro if i < final else centro + (ancho - centro) * ((i - final + 1) / n) ** 2
        cuadros.append(colocar(c, x))
    cuadros += [colocar(Image.new("RGBA", (lado, lado)), centro)] * 6  # pausa antes de repetir
    return cuadros, paso


def grilla_gif(listas, columnas, escala, ruta, recorte=(0, 2, 56, 56)):
    tiempos, paso = mezclar_tiempos(listas)
    x0, y0, x1, y1 = recorte
    w, h = (x1 - x0) * escala, (y1 - y0) * escala
    filas = (len(listas) + columnas - 1) // columnas
    cuadros = []
    for fila in tiempos:
        hoja = Image.new("RGB", (w * columnas, h * filas), FONDO)
        for i, c in enumerate(fila):
            img = sobre_fondo(c, escala).crop((x0 * escala, y0 * escala, x1 * escala, y1 * escala))
            hoja.paste(img, ((i % columnas) * w, (i // columnas) * h))
        cuadros.append(hoja)
    guardar_gif(cuadros, paso, ruta)


def gifs_mascota():
    print("GIFs de la mascota")
    # Los 6 estados del estilo clásico
    grilla_gif([cuadros_de(ASPECTOS["clasico"], e) for e in ESTADOS], 6, 3, DOCS / "estados.gif")
    # Los estilos festejando
    grilla_gif([cuadros_de(a, "listo") for a in ASPECTOS.values()], len(ASPECTOS), 4, DOCS / "estilos.gif")
    # Cada estilo entra, festeja y se va, como en la pantalla (desliza desde el borde derecho)
    for estilo, a in ASPECTOS.items():
        guardar_gif(*funcion_estilo(a), DOCS / "estilos" / f"{estilo}.gif")
    # Vestuario: varias combinaciones quietas en una tira
    combinaciones = [
        {"cabeza": "luna", "ropa": "bufanda", "accesorio": "anteojos", "color": "celeste"},
        {"cabeza": "orejas", "ropa": "mono", "accesorio": "auriculares"},
        {"cabeza": "hoja", "ropa": "corbata", "accesorio": "lentes"},
        {"estilo": "sakura", "ropa": "remera"},
        {"estilo": "ninja", "piel": "oscura", "accesorio": "auriculares"},
        {"estilo": "robot", "ropa": "bufanda"},
    ]
    grilla_gif([cuadros_de(a, "idle") for a in combinaciones], 6, 3, DOCS / "vestuario.gif")


def qimagen_a_pil(img, alfa=False):
    img = img.convertToFormat(img.Format.Format_ARGB32 if alfa else img.Format.Format_RGB32)
    datos = bytes(img.constBits().asstring(img.sizeInBytes()))
    foto = Image.frombytes("RGBA", (img.width(), img.height()), datos, "raw", "BGRA")
    return foto if alfa else foto.convert("RGB")


def pil_a_qimagen(foto):
    from PyQt6.QtGui import QImage
    foto = foto.convert("RGBA")
    return QImage(foto.tobytes("raw", "RGBA"), foto.width, foto.height, foto.width * 4,
                  QImage.Format.Format_RGBA8888).copy()


# --- el "escritorio" detrás del vidrio ------------------------------------------------------------------------

def escritorio(ancho, alto, editor=False, liso=False):
    """Un fondo de pantalla oscuro con manchas de color suaves (y, si se pide, una ventana de código encima):
    algo que se note desenfocado detrás del vidrio. Inventado, no es una captura. liso: sin las manchas (en un GIF
    de 256 colores el degradé se vería a escalones)."""
    lado = max(ancho, alto)
    chico = Image.new("RGB", (max(2, ancho // 16), max(2, alto // 16)), (24, 21, 33))
    d = ImageDraw.Draw(chico)
    for fx, fy, fr, color in () if liso else ((0.12, 0.10, 0.30, (204, 104, 74)), (0.88, 0.18, 0.28, (104, 84, 214)),
                              (0.62, 1.00, 0.40, (34, 128, 150)), (0.30, 0.80, 0.22, (170, 64, 116))):
        cx, cy, r = fx * chico.width, fy * chico.height, fr * lado / 16
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)
    chico = chico.filter(ImageFilter.GaussianBlur(lado / 16 * 0.16))
    fondo = chico.resize((ancho, alto), Image.BICUBIC).convert("RGBA")
    if editor:  # una ventana de editor de código, con renglones de colores (sin texto de verdad)
        e = ancho / 760
        capa = Image.new("RGBA", (ancho, alto))
        d = ImageDraw.Draw(capa)
        x0, y0, x1, y1 = int(70 * e), int(26 * e), int(690 * e), alto + int(40 * e)
        d.rounded_rectangle((x0, y0, x1, y1), radius=int(10 * e), fill=(22, 24, 30, 240))
        d.rectangle((x0, y0 + int(10 * e), x1, y0 + int(30 * e)), fill=(30, 32, 40, 255))
        d.rounded_rectangle((x0, y0, x1, y0 + int(30 * e)), radius=int(10 * e), fill=(30, 32, 40, 255))
        for i, c in enumerate(((237, 106, 94), (245, 191, 79), (98, 197, 84))):
            cx, cy = x0 + int((18 + 16 * i) * e), y0 + int(15 * e)
            d.ellipse((cx - 5 * e, cy - 5 * e, cx + 5 * e, cy + 5 * e), fill=c)
        colores = [(198, 120, 221), (97, 175, 239), (229, 192, 123), (152, 195, 121), (171, 178, 191),
                   (224, 108, 117), (86, 182, 194)]
        import random
        azar = random.Random(5)
        y = y0 + int(46 * e)
        while y < alto:
            x = x0 + int((44 + 18 * azar.choice((0, 0, 1, 1, 2, 3))) * e)
            for _ in range(azar.randint(1, 5)):
                largo = int(azar.randint(18, 90) * e)
                if x + largo > x1 - 30 * e:
                    break
                d.rounded_rectangle((x, y, x + largo, y + int(7 * e)), radius=int(3 * e),
                                    fill=(*azar.choice(colores), 230))
                x += largo + int(9 * e)
            y += int(19 * e)
        fondo.alpha_composite(capa)
    return fondo


def desenfocar(foto, escala):
    return foto.filter(ImageFilter.GaussianBlur(22 * escala))


def ventana_con_sombra(foto, escala, radio=10):
    """La ventana de ajustes de vidrio como se ve en el escritorio: el fondo desenfocado detrás, las esquinas
    redondeadas y una sombra suave, sobre transparente (queda bien en el tema claro y el oscuro de GitHub)."""
    w, h = foto.size
    margen = 36 * escala
    lienzo = Image.new("RGBA", (w + 2 * margen, h + 2 * margen), (0, 0, 0, 0))
    mascara = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, w - 1, h - 1), radius=radio * escala, fill=255)
    sombra = Image.new("L", lienzo.size, 0)
    sombra.paste(Image.new("L", (w, h), 120), (margen, margen + 10 * escala), mascara)
    sombra = sombra.filter(ImageFilter.GaussianBlur(16 * escala))
    lienzo.paste(Image.new("RGBA", lienzo.size, (0, 0, 0, 255)), (0, 0), sombra)
    detras = desenfocar(escritorio(w, h), escala)
    detras.alpha_composite(foto)
    # un filo claro de un píxel, como el borde de las ventanas
    borde = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(borde).rounded_rectangle((0, 0, w - 1, h - 1), radius=radio * escala,
                                            outline=(255, 255, 255, 34), width=max(1, escala // 2))
    detras.alpha_composite(borde)
    lienzo.paste(detras, (margen, margen), mascara)
    return lienzo


def guardar_png(foto, ruta):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    foto.save(ruta, optimize=True)
    print("  ", ruta.relative_to(RAIZ), f"{ruta.stat().st_size // 1024} KB")


# Textos del bot (los mismos de servidor/worker.js)
BOT = {"en": ("✅ Allow", "❌ Deny", "✅ Allowed from Telegram", "bot"),
       "es": ("✅ Permitir", "❌ Denegar", "✅ Permitido desde Telegram", "bot"),
       "pt": ("✅ Permitir", "❌ Negar", "✅ Permitido pelo Telegram", "bot")}


def telegram(idioma, carpeta, t, ajustes):
    """Ilustración (no es una captura) del chat con @WaveNotificationBot: un aviso con el GIF real de Wave y un
    pedido de permiso que se aprueba tocando el botón. Colores y forma del tema oscuro de Telegram."""
    from PyQt6.QtCore import QRectF, Qt
    from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath

    esc, ancho = 2, 400
    fondo, burbuja, texto, gris, azul = (QColor("#0e1621"), QColor("#182533"), QColor("#f5f5f5"),
                                          QColor("#7f91a4"), QColor("#6ab2f2"))
    gif, _ = cuadros_de(ASPECTOS["clasico"], "listo")
    permitir, denegar, aprobado, _ = BOT[idioma]
    mensaje = t(ajustes.AUTOMATICO["listo"])
    resumen = t(ajustes.RESUMEN_EJEMPLO["listo"])
    meta = "2 min 05 s · " + t("mi-proyecto")
    pedido = t(ajustes.AUTOMATICO["permiso"])
    pedido = t(pedido, herramienta="Bash") if "{" in pedido else pedido
    comando = "npm install --save-dev vitest"
    total, toque = 56, 30  # cuadros; en el 30 se toca "Permitir"
    alto = 560
    cuadros = []
    for i in range(total):
        img = QImage(ancho * esc, alto * esc, QImage.Format.Format_RGB32)
        img.fill(fondo)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.scale(esc, esc)
        # barra de arriba
        p.fillRect(QRectF(0, 0, ancho, 56), QColor("#17212b"))
        avatar = sobre_fondo(gif[0], 1).crop((4, 10, 52, 58)).resize((36, 36), Image.NEAREST)
        cabeza = QImage(avatar.tobytes("raw", "RGB"), 36, 36, 36 * 3, QImage.Format.Format_RGB888)
        circulo = QPainterPath()
        circulo.addEllipse(QRectF(14, 10, 36, 36))
        p.save(); p.setClipPath(circulo); p.drawImage(QRectF(14, 10, 36, 36), cabeza); p.restore()
        p.setPen(texto); p.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        p.drawText(QRectF(60, 10, 300, 20), "WaveNotificationBot")
        p.setPen(gris); p.setFont(QFont("Segoe UI", 9))
        p.drawText(QRectF(60, 29, 300, 18), "bot")

        def caja(x, y, w, h, color=burbuja):
            camino = QPainterPath()
            camino.addRoundedRect(QRectF(x, y, w, h), 12, 12)
            p.fillPath(camino, color)

        # 1) el aviso con el GIF
        x, y, w = 12, 70, 260
        cuadro = sobre_fondo(gif[i % len(gif)], 1).crop((2, 6, 54, 54)).resize((w, int(w * 48 / 52)), Image.NEAREST)
        caja(x, y, w, cuadro.height + 74)
        q = QImage(cuadro.tobytes("raw", "RGB"), cuadro.width, cuadro.height, cuadro.width * 3,
                   QImage.Format.Format_RGB888)
        p.save()
        recorte = QPainterPath(); recorte.addRoundedRect(QRectF(x, y, w, cuadro.height), 12, 12)
        p.setClipPath(recorte); p.drawImage(QRectF(x, y, w, cuadro.height), q); p.restore()
        yy = y + cuadro.height + 8
        p.setPen(texto); p.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        p.drawText(QRectF(x + 10, yy, w - 20, 18), mensaje); yy += 20
        p.setFont(QFont("Segoe UI", 10)); p.drawText(QRectF(x + 10, yy, w - 20, 18), resumen); yy += 20
        f = QFont("Segoe UI", 9); f.setItalic(True); p.setFont(f); p.setPen(gris)
        p.drawText(QRectF(x + 10, yy, w - 20, 18), meta)
        # 2) el pedido de permiso
        y = 70 + cuadro.height + 74 + 10
        w = 300
        alto_caja = 112 if i >= toque + 3 else 92
        caja(x, y, w, alto_caja)
        p.setPen(texto); p.setFont(QFont("Segoe UI Emoji", 10, QFont.Weight.Bold))
        p.drawText(QRectF(x + 10, y + 8, w - 20, 18), "🔐 " + pedido)
        caja(x + 10, y + 32, w - 20, 26, QColor("#0f1a24"))
        p.setPen(azul); p.setFont(QFont("Consolas", 10))
        p.drawText(QRectF(x + 18, y + 32, w - 30, 26), Qt.AlignmentFlag.AlignVCenter, comando)
        f = QFont("Segoe UI", 9); f.setItalic(True); p.setFont(f); p.setPen(gris)
        p.drawText(QRectF(x + 10, y + 64, w - 20, 18), t("mi-proyecto") + " · " + t("Título del chat"))
        if i >= toque + 3:  # ya aprobado: el mensaje se edita y los botones desaparecen
            p.setPen(texto); p.setFont(QFont("Segoe UI Emoji", 10))
            p.drawText(QRectF(x + 10, y + 86, w - 20, 18), aprobado)
        else:
            by = y + alto_caja + 4
            for j, etiqueta in enumerate((permitir, denegar)):
                bx = x + j * (w / 2 + 2)
                apretado = j == 0 and toque <= i < toque + 3
                caja(bx, by, w / 2 - 2, 34, QColor("#3a5f86" if apretado else "#24394f"))
                p.setPen(texto); p.setFont(QFont("Segoe UI Emoji", 10, QFont.Weight.DemiBold))
                p.drawText(QRectF(bx, by, w / 2 - 2, 34), Qt.AlignmentFlag.AlignCenter, etiqueta)
            if toque - 6 <= i < toque + 3:  # el dedo que toca
                p.setBrush(QColor(255, 255, 255, 70 if i < toque else 120)); p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QRectF(x + w / 4 - 14, by + 3, 28, 28))
        p.end()
        cuadros.append(qimagen_a_pil(img))
    cuadros += [cuadros[-1]] * 14
    guardar_gif(cuadros, 90, carpeta / "telegram.gif")
    return cuadros


def portada(aviso, celular, ruta):
    """La imagen de arriba del README: el aviso en la compu y el mismo momento en el celular, lado a lado."""
    alto = 600
    tel = [c.resize((int(c.width * alto / c.height / 1.0), alto), Image.LANCZOS) for c in celular]
    av = aviso[0]
    escala = min(1.0, (alto - 40) / av.height)
    av = [c.resize((int(c.width * escala), int(c.height * escala)), Image.LANCZOS) for c in aviso]
    hueco = 80
    ancho = av[0].width + hueco + tel[0].width + 120
    mascara = Image.new("L", tel[0].size, 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, *[v - 1 for v in tel[0].size]), radius=26, fill=255)
    cuadros = []
    for i in range(len(tel)):
        hoja = Image.new("RGB", (ancho, alto + 40), FONDO)
        a = av[i % len(av)]
        hoja.paste(a, (60, (alto + 40 - a.height) // 2))
        hoja.paste(tel[i], (60 + a.width + hueco, 20), mascara)
        cuadros.append(hoja)
    guardar_gif(cuadros, 90, ruta)


def logo():
    """El logo del README: Wave quieta, recortada y agrandada sin suavizar (fondo transparente)."""
    cuadro = cuadros_de(ASPECTOS["clasico"], "idle")[0][0]
    cuadro = cuadro.crop(cuadro.getbbox())
    cuadro = cuadro.resize((cuadro.width * 4, cuadro.height * 4), Image.NEAREST)
    ruta = DOCS / "logo.png"
    cuadro.save(ruta, optimize=True)
    print("  ", ruta.relative_to(RAIZ))


def aviso_gif(m, estado, mensaje, resumen, meta, botones, ruta):
    """Un aviso animado: la mascota real arriba y el cartel real abajo, con la barra de tiempo vaciándose."""
    from PyQt6.QtGui import QColor, QImage, QPainter

    cartel = m.Cartel()
    cartel.tema = "oscuro"
    cartel.medir(mensaje, resumen, meta, botones)
    esc = 2
    w, h = int(cartel.ancho + 24), int(cartel.alto + 26)  # con lugar para la sombra del vidrio
    cuadros, ms = cuadros_de(ASPECTOS["clasico"], estado)
    ms = ms if isinstance(ms, int) else ms[0]
    n = max(len(cuadros), int(3000 / max(ms, 1)))
    mascota_esc = 3 * esc  # tamaño por defecto (3 px por pixel de arte) a 2x
    recorte = (0, 8, 56, 56)
    mw = (recorte[2] - recorte[0]) * mascota_esc
    mh = (recorte[3] - recorte[1]) * mascota_esc
    ancho = max(w * esc, mw) + 40
    alto = mh + h * esc + 24
    salida = []
    for i in range(n):
        fr = QImage(w * esc, h * esc, QImage.Format.Format_RGB32)
        fr.fill(QColor(*FONDO))
        p = QPainter(fr)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.scale(esc, esc)
        cartel.pintar(p, w / 2, 9, QColor(m.ESTADOS[estado]["acento"]), 1 - i / n)
        p.end()
        tarjeta = qimagen_a_pil(fr)
        hoja = Image.new("RGB", (ancho, alto), FONDO)
        pm = sobre_fondo(cuadros[i % len(cuadros)], mascota_esc).crop(tuple(v * mascota_esc for v in recorte))
        hoja.paste(pm, ((ancho - mw) // 2, 12))
        hoja.paste(tarjeta, ((ancho - tarjeta.width) // 2, 12 + mh))
        salida.append(hoja)
    guardar_gif(salida, ms, ruta)
    return salida


# Lo que "contesta el servidor" durante las capturas: nada sale a la red.
SERVIDOR = {"estado": {}}


def sin_red():
    import actualizacion
    import celular

    def pedir(metodo, ruta, llave="", datos=None, **_):
        if ruta == "/v1/estado":
            return dict(SERVIDOR["estado"])
        raise celular.ErrorCelular("sin red durante las capturas")

    celular.pedir = pedir
    actualizacion.buscar = lambda forzar=False: None


class SinVentanaDeVidrio:
    """Hace de ventana de desenfoque de la isla: la isla pinta su vidrio como si Windows desenfocara detrás, y
    el desenfoque lo pone después la captura (sobre el escritorio de mentira)."""
    def seguir(self, *a, **k): pass
    def hide(self): pass
    def deleteLater(self): pass
    def prender(self, *a): return True


def guardar_gif_color(cuadros, ms, ruta: Path, ancho=None):
    """Como guardar_gif, pero con la paleta sacada de varios cuadros (el vidrio tiene muchos tonos)."""
    if ancho:
        cuadros = [c.resize((ancho, round(c.height * ancho / c.width)), Image.LANCZOS) for c in cuadros]
    elegidos = [cuadros[round(i * (len(cuadros) - 1) / 11)] for i in range(12)]  # el brillo pasa por varios
    muestra = Image.new("RGB", (cuadros[0].width, cuadros[0].height * len(elegidos)))
    for i, cuadro in enumerate(elegidos):
        muestra.paste(cuadro, (0, i * cuadros[0].height))
    paleta = muestra.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    planos = [c.quantize(palette=paleta, dither=Image.Dither.NONE) for c in cuadros]
    ruta.parent.mkdir(parents=True, exist_ok=True)
    planos[0].save(ruta, save_all=True, append_images=planos[1:], duration=ms, loop=0, optimize=True)
    print("  ", ruta.relative_to(RAIZ), f"{ruta.stat().st_size // 1024} KB")


def isla(app, idioma, carpeta, esperar):
    """La Dynamic Island: la pastilla chica, abierta y un GIF que se estira al pasarle el mouse. Los cuadros
    se avanzan a mano (resortes, ojos, brillo), así el GIF sale parejo aunque la compu esté ocupada."""
    import animacion
    import barra as b
    from PyQt6.QtCore import QPointF, Qt
    from PyQt6.QtGui import QPainter

    datos_ejemplo.sesiones_de_ahora(PROYECTOS, time.time(), idioma)  # los títulos en este idioma
    reloj = animacion._reloj()

    class Quieto:  # el reloj de los resortes no corre solo: avanza cuando se saca cada cuadro
        def start(self, *a): pass
        def stop(self): pass

    reloj.timer.stop()
    timer_original, reloj.timer = reloj.timer, Quieto()
    barra = b.Barra(desenfocar=False)
    barra.vidrio = SinVentanaDeVidrio()
    barra.hay_pantalla_completa = lambda: False
    barra.revisar_encima = lambda: None
    barra.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    barra.mostrar()
    if not esperar(lambda: barra.lector.uso is not None and len(barra.sesiones) == 3 and len(barra.eta) == 2, 90):
        raise SystemExit(f"la isla no leyó las 3 sesiones de ejemplo (leyó {len(barra.sesiones)}): no se guarda nada")
    for timer in (barra.timer_cuadro, barra.timer_tic, barra.timer_pantalla):
        timer.stop()
    barra.lector.parar.set()

    escala = 2
    ancho_escena = 640
    alto_escena = int(b.ARRIBA + b.CABECERA + 3 * b.FILA + b.PIE + b.USO + 34)
    dx = ancho_escena / 2 - barra.width() / 2  # la isla va arriba al centro
    fondo = escritorio(ancho_escena * escala, alto_escena * escala, editor=True)
    nitido, borroso = pil_a_qimagen(fondo), pil_a_qimagen(desenfocar(fondo, escala))
    for img in (nitido, borroso):
        img.setDevicePixelRatio(escala)
    virtual = [time.monotonic()]
    barra.mirada.reloj = virtual[0]
    barra.mirada.proximo_destino = virtual[0] + 0.6
    barra.mirada.proximo_parpadeo = virtual[0] + 2.2  # que la foto de la pastilla no salga parpadeando
    inicio_real, inicio_virtual = time.time(), virtual[0]

    class Hora:  # la hora que ve la isla avanza con los cuadros: la cuenta regresiva baja de verdad en el GIF
        monotonic = staticmethod(time.monotonic)
        sleep = staticmethod(time.sleep)

        @staticmethod
        def time():
            return inicio_real + virtual[0] - inicio_virtual

    b.time = Hora

    def paso(dt):
        virtual[0] += dt
        for resorte in list(reloj.activos):
            resorte.avanzar(dt)
        barra.trabajando = any(s["trabajando"] for s in barra.sesiones)
        barra.mirada.animo = "despierta" if barra.trabajando else "tranquila"
        barra.mirada.avanzar(virtual[0])
        barra.suavizar(dt)
        barra.medir()

    def foto():
        barra.arranque = time.monotonic() - (virtual[0] - inicio_virtual + 3.0)  # el latido y el brillo avanzan
        captura = barra.grab()
        escena = nitido.copy()
        escena.setDevicePixelRatio(escala)
        p = QPainter(escena)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.translate(QPointF(dx, 0))
        p.setClipPath(barra.forma())
        p.translate(QPointF(-dx, 0))
        p.drawImage(0, 0, borroso)
        p.setClipping(False)
        p.drawPixmap(QPointF(dx, 0), captura)
        p.end()
        return qimagen_a_pil(escena)

    def quieto(segundos):
        for _ in range(int(segundos / 0.02)):
            paso(0.02)

    quieto(1.5)
    guardar_png(foto(), carpeta / "isla-chica.png")
    barra.encima = True
    barra.r_brillo.ir_a(1.0)
    barra.abrir(True)
    quieto(2.0)
    guardar_png(foto(), carpeta / "isla-abierta.png")

    # El GIF: chica un momento, el mouse llega, se estira, se queda abierta y vuelve. Sobre el escritorio liso.
    fondo = escritorio(ancho_escena * escala, alto_escena * escala, editor=True, liso=True)
    nitido, borroso = pil_a_qimagen(fondo), pil_a_qimagen(desenfocar(fondo, escala))
    for img in (nitido, borroso):
        img.setDevicePixelRatio(escala)
    barra.abrir(False)
    barra.encima = False
    barra.r_brillo.ir_a(0.0)
    quieto(2.0)
    cuadros, dt = [], 0.05  # 20 cuadros por segundo: alcanza para el resorte y el GIF pesa menos
    guion = [(1.4, None), (0.11, "encima"), (2.9, "abrir"), (0.42, "salir"), (1.3, "cerrar")]
    for duracion, accion in guion:
        if accion == "encima":
            barra.encima = True
            barra.r_brillo.ir_a(1.0)
        elif accion == "abrir":
            barra.abrir(True)
        elif accion == "salir":
            barra.encima = False
            barra.r_brillo.ir_a(0.0)
        elif accion == "cerrar":
            barra.abrir(False)
        for _ in range(round(duracion / dt)):
            paso(dt)
            cuadros.append(foto())
    guardar_gif_color(cuadros, int(dt * 1000), carpeta / "isla.gif")
    barra.apagar()
    b.time = time
    reloj.activos.clear()
    reloj.timer = timer_original  # los ajustes vuelven a animarse solos
    barra.deleteLater()
    app.processEvents()


def qt_capturas():
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    sin_red()
    import ajustes
    import idiomas
    import instalador
    import mascota as m
    import paneles
    from idiomas import t

    m.Sonidos.tocar = lambda self, *a, **k: None  # las capturas muestran el sonido prendido, pero nunca suena

    def esperar(condicion, segundos):
        fin = time.time() + segundos
        while time.time() < fin and not condicion():
            app.processEvents()
            time.sleep(0.02)
        for _ in range(30):  # que terminen los resortes
            app.processEvents()
            time.sleep(0.02)
        listo = bool(condicion())
        if not listo and segundos >= 5:  # las de 1 s son solo una pausa, no esperan nada
            print(f"   ¡ojo! pasaron {segundos} s y no estuvo listo: la captura puede salir incompleta")
        return listo

    def abrir(config, tema="oscuro", estilo="clasico"):
        base = {"sonido": True, "volumen": 70, "aspecto": {"estilo": "clasico", "cabeza": "chispa"}}
        base.update(config)
        (casa / ".wavemascot" / "config.json").write_text(json.dumps(base))
        # La ventana de vidrio: fuera de pantalla Windows no da el desenfoque, así que se pinta como si lo
        # diera y el desenfoque lo pone ventana_con_sombra (con el escritorio de mentira detrás).
        paneles.VIDRIO = True
        ajustes.aplicar_tema(tema, estilo)
        win = ajustes.Ajustes()
        paneles.VIDRIO = True
        ajustes.aplicar_tema(tema, estilo)
        win.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        win.resize(1080, 760)
        win.show()
        esperar(lambda: False, 0.4)  # las respuestas "del servidor" llegan desde otro hilo
        return win

    def cerrar(win):
        win.timer_guardar.stop()  # nunca guardar, ni siquiera en la carpeta temporal
        win.close()
        win.deleteLater()
        app.processEvents()

    def guardar(win, ruta):
        guardar_png(ventana_con_sombra(qimagen_a_pil(win.grab().toImage(), alfa=True), 2), ruta)

    nombres = list(ajustes.PAGINAS)  # avisos, mascota, celular, isla, uso, proyectos, general
    # "Abrir al iniciar Windows" como queda después de instalar (prendido), sin mirar tu carpeta de Inicio
    import bandeja
    bandeja.ACCESO_INICIO = casa / "Inicio" / "WaveMascot.lnk"
    bandeja.ACCESO_INICIO.parent.mkdir(parents=True, exist_ok=True)
    bandeja.ACCESO_INICIO.touch()
    datos_ejemplo.historia(PROYECTOS, time.time())
    for idioma in [ARGS["idioma"]] if "idioma" in ARGS else IDIOMAS:
        print("Idioma", idioma)
        idiomas.usar(idioma)
        carpeta = DOCS / "capturas" / idioma
        carpeta.mkdir(parents=True, exist_ok=True)

        if toca("isla"):
            (casa / ".wavemascot" / "config.json").write_text(json.dumps(
                {"sonido": False, "volumen": 0, "idioma": idioma, "aspecto": {"estilo": "clasico"}}))
            isla(app, idioma, carpeta, esperar)

        if toca("avisos"):
            avisos = {}
            botones = {"listo": ["enfocar"], "permiso": ["permitir", "denegar", "enfocar"], "pensando": [],
                       "subagente": ["enfocar"], "limite": [], "error": ["enfocar"]}
            for estado in ESTADOS:
                mensaje = ajustes.AUTOMATICO[estado]
                mensaje = t(mensaje, herramienta="Bash") if "{" in mensaje else t(mensaje)
                meta = " · ".join(x for x in ["2 min 05 s" if estado == "listo" else "", t("mi-proyecto"),
                                               t("Título del chat")] if x)
                avisos[estado] = aviso_gif(m, estado, mensaje, t(ajustes.RESUMEN_EJEMPLO[estado]), meta,
                                           botones[estado], carpeta / f"aviso-{estado}.gif")
            # el aviso de versión nueva (Actualizar / Ahora no)
            aviso_gif(m, "listo", t("¡Hay una versión nueva de WaveMascot!"),
                      t("Versión {version}", version=instalador.VERSION), "", ["actualizar", "ahora_no"],
                      carpeta / "aviso-actualizacion.gif")
            portada(avisos["permiso"], telegram(idioma, carpeta, t, ajustes), carpeta / "portada.gif")

        if not toca("ajustes"):
            continue
        datos_ejemplo.sesiones_de_ahora(PROYECTOS, time.time(), idioma)  # lo de hoy, para Uso
        # --- la ventana de ajustes, una captura por sección (recién instalada: Telegram sin conectar) --
        SERVIDOR["estado"] = {}
        win = abrir({"idioma": idioma})
        for i, nombre in enumerate(nombres):
            win.ir_a(i, animar=False)
            if nombre not in ajustes.SIN_VISTA:
                win.ver_estado("permiso" if nombre == "celular" else "listo")
            if nombre in ajustes.DE_DATOS:
                esperar(lambda: win.uso.informe is not None and not any(r.moviendose for r in (
                    win.uso.curva.morfo, win.uso.curva.fundido, win.uso.curva.cuenta, win.uso.dona.corre,
                    win.uso.sesiones.corre, win.uso.trabajo.corre, win.uso.cache.corre,
                    win.uso.proyectos.corre)), 90)
            else:
                esperar(lambda: False, 1.2)  # deja que la vista previa entre y muestre el cartel
            guardar(win, carpeta / f"ajustes-{i + 1}-{nombre}.png")
        cerrar(win)

        # --- Telegram conectado ---------------------------------------------------------------------
        SERVIDOR["estado"] = {"conectado": True, "nombre": "Alex"}
        win = abrir({"idioma": idioma, "celular": {"activo": True, "llave": "demo", "conectado": True,
                                                    "nombre": "Alex"}})
        win.ir_a(nombres.index("celular"), animar=False)
        win.ver_estado("permiso")
        esperar(lambda: False, 1.2)
        guardar(win, carpeta / "celular-conectado.png")
        cerrar(win)

        # --- el tema claro, con Sakura ---------------------------------------------------------------
        SERVIDOR["estado"] = {}
        win = abrir({"idioma": idioma, "tema": "claro", "aspecto": {"estilo": "sakura"}}, "claro", "sakura")
        win.ir_a(nombres.index("mascota"), animar=False)
        esperar(lambda: False, 1.2)
        guardar(win, carpeta / "ajustes-claro-sakura.png")
        cerrar(win)


if __name__ == "__main__":
    os.environ.setdefault("QT_SCALE_FACTOR", "2")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # nada en pantalla
    if os.name == "nt":  # sin pantalla, Qt no encuentra solo las fuentes de Windows
        os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
    if (SOLO is None and "idioma" not in ARGS) or (SOLO and "gif" in SOLO) or "--solo-gif" in sys.argv:
        gifs_mascota()
        logo()
    if "--solo-gif" not in sys.argv and (SOLO is None or SOLO - {"gif"}):
        if "idioma" in ARGS:
            qt_capturas()
        else:  # un proceso por idioma: Qt arranca limpio cada vez
            import subprocess
            partes = [f"--solo={','.join(sorted(SOLO - {'gif'}))}"] if SOLO else []
            for idioma in IDIOMAS:
                subprocess.run([sys.executable, "-u", __file__, f"--idioma={idioma}", *partes], check=True)
    print("listo. carpeta temporal:", casa, flush=True)
    os._exit(0)  # sin esperar a que Python desarme Qt al salir (a veces se cae ahí, ya con todo guardado)
