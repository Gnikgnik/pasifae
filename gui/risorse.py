# SPDX-License-Identifier: GPL-3.0-or-later
"""Accesso alle risorse grafiche di Pasifae (icona e loghi)."""
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap

_DIR = os.path.join(os.path.dirname(__file__), "assets")

NOME = "Pasifae"
TAGLINE = "Suite per interactive fiction"


def percorso(nome: str) -> str:
    return os.path.join(_DIR, nome)


def icona_app() -> QIcon:
    """Icona dell'applicazione (per finestre, barra delle applicazioni)."""
    ic = QIcon()
    for sz in (16, 32, 48, 64, 128, 256, 512):
        p = percorso(f"pasifae_{sz}.png")
        if os.path.exists(p):
            ic.addFile(p)
    return ic


def pixmap(nome: str, larghezza: int | None = None) -> QPixmap:
    pix = QPixmap(percorso(nome))
    if larghezza and not pix.isNull():
        pix = pix.scaledToWidth(larghezza, Qt.SmoothTransformation)
    return pix


def mostra_informazioni(parent, componente: str) -> None:
    """Dialogo «Informazioni» con il logo Pasifae, condiviso da editor e player.

    `componente` è l'etichetta della parte di suite (es. "Pasifae Editor").
    """
    from PySide6.QtWidgets import QMessageBox
    from gui import __version__ as v_gui
    import advcore
    dlg = QMessageBox(parent)
    dlg.setWindowTitle("Informazioni")
    pix = pixmap("pasifae_wordmark.png", larghezza=320)
    if not pix.isNull():
        dlg.setIconPixmap(pix)
    dlg.setTextFormat(Qt.RichText)
    dlg.setText(
        f"<b>Pasifae</b> — suite per avventure testuali<br>"
        f"<i>crea avventure testuali, senza codice</i><br><br>"
        f"{componente} · interfaccia {v_gui}<br>"
        f"motore advcore {advcore.__version__}<br>"
        f"interfaccia PySide6 / Qt<br><br>"
        f"Software libero · licenza GPL-3.0-or-later")
    dlg.exec()
