"""Captura cada pestaña de los ajustes con la plataforma real de macOS (temporal, rama mac).

    python pruebas_mac/capturas_ajustes.py CARPETA
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
salida = Path(sys.argv[1])

import ajustes  # noqa: E402
import idiomas  # noqa: E402
import mascota as m  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv[:1])
app.setStyle("Fusion")
for idioma, tema in (("es", "oscuro"), ("en", "claro"), ("pt", "acento")):
    config = m.cargar_config()
    config.update(idioma=idioma, tema=tema)
    m.guardar_config(config)
    idiomas.usar(idioma)
    ajustes.aplicar_tema(tema)
    ventana = ajustes.Ajustes()
    ventana.resize(940, 760)
    ventana.show()
    for i in range(ventana.pestanas.count()):
        ventana.pestanas.setCurrentIndex(i)
        for _ in range(20):
            app.processEvents()
        ventana.grab().save(str(salida / f"ajustes-{idioma}-{i + 1}.png"))
    print(idioma, tema, "fuente:", app.font().family(), app.font().pointSizeF(), "dpr:", ventana.devicePixelRatioF())
    ventana.close()
config = m.cargar_config()
config.update(idioma="es", tema="oscuro")
m.guardar_config(config)
