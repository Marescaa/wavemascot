#!/usr/bin/env python3
"""Ícono de la mascota junto al reloj (en macOS, en la barra de menús).

Click: abre los ajustes. Click derecho: probar un aviso, silenciar los avisos un rato,
elegir si arranca con Windows o salir. Lo abre el acceso directo de la carpeta Inicio
de Windows. En macOS el click abre el menú (como todos los íconos de la barra), arranca
al iniciar sesión con un LaunchAgent y el menú suma "Desinstalar".

Uso:  pythonw bandeja.py
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path

DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DIR))
import idiomas  # noqa: E402
import mascota as m  # noqa: E402
import sprites  # noqa: E402
import ventanas  # noqa: E402
from idiomas import t  # noqa: E402

from PyQt6.QtCore import QFileSystemWatcher, QSize, QTimer, pyqtSignal  # noqa: E402
from PyQt6.QtGui import QIcon, QPixmap  # noqa: E402
from PyQt6.QtNetwork import QLocalServer, QLocalSocket  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon  # noqa: E402

ACCESO_INICIO = (Path(os.environ.get("APPDATA", Path.home())) / "Microsoft" / "Windows" / "Start Menu"
                 / "Programs" / "Startup" / "WaveMascot.lnk")
if m.MAC:  # macOS: un LaunchAgent que abre el ícono al iniciar sesión
    import instalador  # noqa: E402
    ACCESO_INICIO = instalador.acceso_inicio()
CANAL_BANDEJA = m.CANAL + "-bandeja"
INDEFINIDO = 4_102_444_800  # 1/1/2100: "hasta que lo reactive"


def inicio_automatico() -> bool:
    return ACCESO_INICIO.exists()


def activar_inicio_automatico(activar: bool) -> None:
    """Crea o borra el acceso directo de la carpeta Inicio que abre este ícono."""
    if not activar:
        ACCESO_INICIO.unlink(missing_ok=True)
        return
    if m.MAC:
        app = m.bundle_app()
        partes = ([str(app / "Contents" / "MacOS" / "WaveMascot"), "bandeja"] if app
                  else [sys.executable, str(DIR / "bandeja.py")])
        instalador.crear_agente_inicio(ACCESO_INICIO, partes)
        return
    exe = Path(sys.executable).with_name("pythonw.exe")
    ACCESO_INICIO.parent.mkdir(parents=True, exist_ok=True)
    script = ("$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:ACCESO); "
              "$s.TargetPath = $env:OBJETIVO; $s.Arguments = $env:ARGUMENTOS; "
              "$s.WorkingDirectory = $env:CARPETA; $s.IconLocation = $env:ICONO; "
              "$s.Description = $env:DESCRIPCION; $s.Save()")
    if m.CONGELADO:  # instalada con el .exe: el ícono es "WaveMascot.exe bandeja"
        objetivo, argumentos, carpeta = sys.executable, "bandeja", str(Path(sys.executable).parent)
    else:
        objetivo, argumentos, carpeta = str(exe if exe.exists() else sys.executable), f'"{DIR / "bandeja.py"}"', str(DIR)
    entorno = {**os.environ, "ACCESO": str(ACCESO_INICIO),
               "OBJETIVO": objetivo, "ARGUMENTOS": argumentos, "CARPETA": carpeta,
               "ICONO": str(m.ASSETS / "icono.ico"), "DESCRIPCION": "WaveMascot (ícono junto al reloj)"}
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], env=entorno,
                   check=True, timeout=30, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)


def lanzar() -> None:
    m.lanzar_desacoplado([str(DIR / "bandeja.py")])  # si ya hay una, la nueva se cierra sola


def abrir_compania() -> None:
    m.lanzar_desacoplado([str(DIR / "mascota.py"), "--compania"])  # si ya está abierta, no se duplica


def icono_mascota(color: str, grande: bool = False) -> QIcon:
    """grande: también en tamaños de Dock (macOS), sin suavizar el pixel art."""
    icono = QIcon()
    for escala in (1, 2, 3) + ((8, 16, 32) if grande else ()):
        pixmap = QPixmap()
        pixmap.loadFromData(png(sprites.icono_bandeja(color, escala)))
        icono.addPixmap(pixmap)
    return icono


def png(imagen) -> bytes:
    from io import BytesIO

    salida = BytesIO()
    imagen.save(salida, "PNG")
    return salida.getvalue()


class Bandeja(QSystemTrayIcon):
    version_nueva = pyqtSignal(object)  # lo que encontró la búsqueda de actualizaciones (o None)

    def __init__(self):
        super().__init__()
        menu = QMenu()
        self.accion_actualizar = menu.addAction("")
        self.accion_actualizar.triggered.connect(self.actualizar_app)
        self.accion_actualizar.setVisible(False)
        self.separador_actualizar = menu.addSeparator()
        self.separador_actualizar.setVisible(False)
        self.accion_ajustes = menu.addAction("")
        self.accion_ajustes.triggered.connect(self.abrir_ajustes)
        menu.setDefaultAction(self.accion_ajustes)
        self.accion_probar = menu.addAction("")
        self.accion_probar.triggered.connect(self.probar)
        menu.addSeparator()
        self.accion_hora = menu.addAction("")
        self.accion_hora.triggered.connect(lambda: self.silenciar(time.time() + 3600))
        self.accion_siempre = menu.addAction("")
        self.accion_siempre.triggered.connect(lambda: self.silenciar(INDEFINIDO))
        self.accion_reactivar = menu.addAction("")
        self.accion_reactivar.triggered.connect(lambda: self.silenciar(0))
        menu.addSeparator()
        self.accion_compania = menu.addAction("")
        self.accion_compania.setCheckable(True)
        self.accion_compania.toggled.connect(self.cambiar_modo)
        self.accion_inicio = menu.addAction("")
        self.accion_inicio.setCheckable(True)
        self.accion_inicio.toggled.connect(self.cambiar_inicio)
        menu.addSeparator()
        self.accion_desinstalar = None
        if m.MAC:  # en macOS no hay menú Inicio: se desinstala desde acá
            self.accion_desinstalar = menu.addAction("")
            self.accion_desinstalar.triggered.connect(self.desinstalar)
        self.accion_salir = menu.addAction("")
        self.accion_salir.triggered.connect(QApplication.quit)
        menu.aboutToShow.connect(self.actualizar)
        self.menu = menu
        self.setContextMenu(menu)
        self.activated.connect(self.al_activar)

        m.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.vigia = QFileSystemWatcher([str(m.CONFIG_DIR)])  # config.json se reemplaza al guardar
        self.vigia.directoryChanged.connect(lambda _: QTimer.singleShot(200, self.actualizar))
        self.reloj = QTimer(self, interval=30_000, timeout=self.actualizar)  # vence el silencio
        self.reloj.start()
        self.color = None
        self.nueva = None
        self.actualizar()
        # Versiones nuevas: un rato después de arrancar (no compite con el inicio de Windows) y cada 3 horas.
        self.version_nueva.connect(self.al_encontrar_version)
        self.timer_version = QTimer(self, interval=3 * 3600 * 1000, timeout=self.buscar_version)
        self.timer_version.start()
        QTimer.singleShot(90_000, self.buscar_version)

    def buscar_version(self) -> None:
        def buscar():
            import actualizacion
            try:
                info = actualizacion.revisar_y_avisar()
            except actualizacion.ErrorActualizacion as e:
                m.log(f"[bandeja] {e}")
                info = self.nueva  # sin conexión: queda lo que ya se sabía
            try:
                self.version_nueva.emit(info)
            except RuntimeError:
                pass
        threading.Thread(target=buscar, daemon=True).start()

    def al_encontrar_version(self, info) -> None:
        self.nueva = info
        self.actualizar()

    def actualizar_app(self) -> None:
        if os.name == "nt":
            ctypes.windll.user32.AllowSetForegroundWindow(-1)
        m.lanzar_desacoplado([str(DIR / "ajustes.py"), "--actualizar"])

    def actualizar(self) -> None:
        config = m.cargar_config()
        idiomas.usar(config["idioma"])  # los textos siguen al idioma de los ajustes
        for accion, texto in ((self.accion_ajustes, "Abrir ajustes"), (self.accion_probar, "Probar aviso"),
                              (self.accion_hora, "Silenciar por 1 hora"),
                              (self.accion_siempre, "Silenciar hasta que los reactive"),
                              (self.accion_compania, "Modo compañera (fija en pantalla)"),
                              (self.accion_inicio, "Abrir al iniciar Windows"), (self.accion_salir, "Salir")):
            accion.setText(t(texto))
        if m.MAC:
            self.accion_inicio.setText(t("Abrir al iniciar sesión"))
            self.accion_desinstalar.setText(t("Desinstalar {nombre}…", nombre="WaveMascot"))
        hay_nueva = bool(self.nueva)
        self.accion_actualizar.setVisible(hay_nueva)
        self.separador_actualizar.setVisible(hay_nueva)
        if hay_nueva:
            self.accion_actualizar.setText(t("⬆ Actualizar a la versión {version}…", version=self.nueva["version"]))
        silenciada = m.silenciada(config)
        if config["aspecto"]["color"] != self.color:
            self.color = config["aspecto"]["color"]
            self.icono_normal = icono_mascota(self.color)
            self.icono_gris = QIcon(self.icono_normal.pixmap(QSize(32, 32), QIcon.Mode.Disabled))
        self.setIcon(self.icono_gris if silenciada else self.icono_normal)
        if not silenciada:
            estado = t("avisos activos")
        elif config["silenciado_hasta"] >= INDEFINIDO:
            estado = t("avisos silenciados")
        else:
            estado = t("silenciada hasta las {hora}",
                       hora=f"{datetime.fromtimestamp(config['silenciado_hasta']):%H:%M}")
        self.setToolTip(f"WaveMascot: {estado}" + (f"\n{t('Hay una versión nueva')}" if hay_nueva else ""))
        self.accion_hora.setVisible(not silenciada)
        self.accion_siempre.setVisible(not silenciada)
        self.accion_reactivar.setVisible(silenciada)
        self.accion_reactivar.setText(t("Reactivar avisos ({estado})", estado=estado))
        for accion, marcada in ((self.accion_inicio, inicio_automatico()),
                                (self.accion_compania, config["modo"] == "compania")):
            accion.blockSignals(True)
            accion.setChecked(marcada)
            accion.blockSignals(False)

    def al_activar(self, motivo) -> None:
        if m.MAC:  # en la barra de menús el click ya abre el menú, que empieza con "Abrir ajustes"
            return
        if motivo in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.abrir_ajustes()

    def abrir_ajustes(self) -> None:
        if os.name == "nt":  # el click es nuestro: dejamos que la ventana de ajustes tome el foco
            ctypes.windll.user32.AllowSetForegroundWindow(-1)
        m.lanzar_desacoplado([str(DIR / "ajustes.py")])

    def probar(self) -> None:
        m.lanzar_desacoplado([str(DIR / "mascota.py"), "--estado=listo", "--forzar",
                              "--detalle=" + t("Prueba desde el ícono")])

    def silenciar(self, hasta: float) -> None:
        config = m.cargar_config()
        config["silenciado_hasta"] = hasta
        m.guardar_config(config)
        m.log(f"[bandeja] silenciado_hasta={hasta:.0f}")
        self.actualizar()

    def cambiar_modo(self, compania: bool) -> None:
        """La compañera se va sola al ver modo "aviso" en la config; al activarla hay que abrirla."""
        config = m.cargar_config()
        config["modo"] = "compania" if compania else "aviso"
        m.guardar_config(config)
        if compania:
            abrir_compania()
        self.actualizar()

    def cambiar_inicio(self, activar: bool) -> None:
        try:
            activar_inicio_automatico(activar)
        except (OSError, subprocess.SubprocessError) as e:
            m.log(f"[bandeja] no se pudo cambiar el inicio automático: {e}")
        self.actualizar()

    def desinstalar(self) -> None:
        """macOS: el desinstalador pregunta antes; si se confirma, cierra también este ícono."""
        if m.CONGELADO:
            m.lanzar_desacoplado(["desinstalar"], suelto=True)
        else:
            m.lanzar_desacoplado([str(DIR / "instalador.py"), "desinstalar", "--dialogos"], suelto=True)


def main() -> int:
    # Un error se registra en el log; no cierra el ícono (PyQt6 aborta ante errores no atrapados).
    sys.excepthook = lambda tipo, valor, tb: m.log("[bandeja] error:\n" + "".join(
        traceback.format_exception(tipo, valor, tb)))
    if m.MAC:  # solo el ícono de la barra de menús, sin ícono en el Dock
        os.environ["QT_MAC_DISABLE_FOREGROUND_APPLICATION_TRANSFORM"] = "1"
    app = QApplication(sys.argv[:1])
    app.setQuitOnLastWindowClosed(False)
    ventanas.app_de_fondo()
    s = QLocalSocket()
    s.connectToServer(CANAL_BANDEJA)
    if s.waitForConnected(300):
        return 0  # ya hay un ícono
    servidor = QLocalServer()
    m.escuchar(servidor, CANAL_BANDEJA)
    # macOS: abrir WaveMascot.app con el ícono ya corriendo le avisa a este proceso (se abren los ajustes).
    ventanas.al_reabrir(m.reabrir_app)
    for _ in range(30):  # al iniciar Windows la barra de tareas puede tardar en estar lista
        if QSystemTrayIcon.isSystemTrayAvailable():
            break
        time.sleep(1)
    bandeja = Bandeja()
    bandeja.show()
    m.log("[bandeja] ícono junto al reloj activo")
    if m.cargar_config()["modo"] == "compania":  # al iniciar Windows, la compañera vuelve a su lugar
        abrir_compania()
    codigo = app.exec()
    servidor.close()
    return codigo


if __name__ == "__main__":
    try:
        codigo = main()
    except Exception:
        m.log("[bandeja] error:\n" + traceback.format_exc())
        codigo = 1
    os._exit(codigo)
