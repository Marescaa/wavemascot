"""Genera las imágenes y GIFs de docs/ (las que muestra el README) a partir de la app real.

Corre en una carpeta de usuario temporal (no lee ni escribe tu ~/.wavemascot), sin sonido y sin mostrar
nada en pantalla: las ventanas se dibujan fuera de pantalla y los avisos se pintan en una imagen.

    python tools/capturas.py            # todo
    python tools/capturas.py --solo-gif # solo los GIF de la mascota (no necesita Qt)
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
(casa / ".wavemascot").mkdir()
(casa / ".wavemascot" / "config.json").write_text(json.dumps({"sonido": False, "volumen": 0}))
sys.path.insert(0, str(RAIZ))

from PIL import Image, ImageDraw  # noqa: E402

import sprites  # noqa: E402

IDIOMAS = ("en", "es", "pt")
ESTADOS = ("listo", "permiso", "pensando", "subagente", "limite", "error")
FONDO = (0x1E, 0x1B, 0x22)  # "escritorio" oscuro: se ve bien con el tema claro y el oscuro de GitHub
# Un aspecto lindo por estilo, para las galerías
ASPECTOS = {
    "clasico": {"estilo": "clasico", "cabeza": "chispa"},
    "sakura": {"estilo": "sakura"},
    "ninja": {"estilo": "ninja"},
    "robot": {"estilo": "robot"},
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
    # Los 4 estilos festejando
    grilla_gif([cuadros_de(a, "listo") for a in ASPECTOS.values()], 4, 4, DOCS / "estilos.gif")
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


def qimagen_a_pil(img):
    img = img.convertToFormat(img.Format.Format_RGB32)
    datos = bytes(img.constBits().asstring(img.sizeInBytes()))
    return Image.frombytes("RGBA", (img.width(), img.height()), datos, "raw", "BGRA").convert("RGB")


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


def qt_capturas():
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QColor, QImage, QPainter
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    import ajustes
    import idiomas
    import mascota as m
    from idiomas import t

    nombres = ["aviso", "comportamiento", "mascota", "vestuario", "sonido", "celular"]
    for idioma in IDIOMAS:
        print("Idioma", idioma)
        idiomas.usar(idioma)
        carpeta = DOCS / "capturas" / idioma
        carpeta.mkdir(parents=True, exist_ok=True)
        avisos = {}

        # --- los avisos animados: la mascota real arriba y el cartel real abajo -------------------
        botones = {"listo": ["enfocar"], "permiso": ["permitir", "denegar", "enfocar"], "pensando": [],
                   "subagente": ["enfocar"], "limite": [], "error": ["enfocar"]}
        for estado in ESTADOS:
            mensaje = ajustes.AUTOMATICO[estado]
            mensaje = t(mensaje, herramienta="Bash") if "{" in mensaje else t(mensaje)
            meta = " · ".join(x for x in ["2 min 05 s" if estado == "listo" else "", t("mi-proyecto"),
                                           t("Título del chat")] if x)
            cartel = m.Cartel()
            cartel.tema = "oscuro"
            cartel.medir(mensaje, t(ajustes.RESUMEN_EJEMPLO[estado]), meta, botones[estado])
            esc = 2
            w, h = int(cartel.ancho + 24), int(cartel.alto + 8)
            # la barra de tiempo se va vaciando, como en la pantalla
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
                cartel.pintar(p, w / 2, 4, QColor(m.ESTADOS[estado]["acento"]), 1 - i / n)
                p.end()
                tarjeta = qimagen_a_pil(fr)
                hoja = Image.new("RGB", (ancho, alto), FONDO)
                pm = sobre_fondo(cuadros[i % len(cuadros)], mascota_esc).crop(
                    tuple(v * mascota_esc for v in recorte))
                hoja.paste(pm, ((ancho - mw) // 2, 12))
                hoja.paste(tarjeta, ((ancho - tarjeta.width) // 2, 12 + mh))
                salida.append(hoja)
            guardar_gif(salida, ms, carpeta / f"aviso-{estado}.gif")
            avisos[estado] = salida

        portada(avisos["permiso"], telegram(idioma, carpeta, t, ajustes), carpeta / "portada.gif")

        # --- la ventana de ajustes, una captura por pestaña ---------------------------------------
        (casa / ".wavemascot" / "config.json").write_text(json.dumps(
            {"sonido": False, "volumen": 0, "idioma": idioma, "aspecto": {"estilo": "clasico", "cabeza": "chispa"}}))
        ajustes.aplicar_tema("oscuro")
        win = ajustes.Ajustes()
        win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        win.resize(980, 760)
        win.show()
        for i in range(win.pestanas.count()):
            win.pestanas.setCurrentIndex(i)
            win.ver_estado("permiso" if nombres[i] == "comportamiento" else "listo")
            for _ in range(40):  # deja que la vista previa entre y muestre el cartel
                app.processEvents()
                time.sleep(0.03)
            win.grab().save(str(carpeta / f"ajustes-{i + 1}-{nombres[i]}.png"))
            print("  ", (carpeta / f"ajustes-{i + 1}-{nombres[i]}.png").relative_to(RAIZ))
        win.timer_guardar.stop()  # nunca guardar, ni siquiera en la carpeta temporal
        win.close()
        win.deleteLater()
        app.processEvents()


if __name__ == "__main__":
    os.environ.setdefault("QT_SCALE_FACTOR", "2")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # nada en pantalla
    if os.name == "nt":  # sin pantalla, Qt no encuentra solo las fuentes de Windows
        os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
    gifs_mascota()
    if "--solo-gif" not in sys.argv:
        qt_capturas()
    print("listo. carpeta temporal:", casa)
