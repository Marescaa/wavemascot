"""Una ventana en pantalla completa durante N segundos (temporal, rama mac)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ventanas  # noqa: E402
from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication, QLabel  # noqa: E402

app = QApplication(sys.argv[:1])
ventana = QLabel("Video en pantalla completa")
ventana.setStyleSheet("background: #203040; color: white; font-size: 40px;")
ventana.showFullScreen()
ventanas.activar_esta_app()
QTimer.singleShot(int(sys.argv[1]) * 1000, app.quit)
app.exec()
