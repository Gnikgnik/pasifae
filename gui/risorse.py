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


def _righe_splash(componente: str) -> tuple[str, str]:
    """Le due righe di testo del piede dello splash (versioni dei pacchetti,
    poi autore e licenza): estratte a parte così sono verificabili senza
    dover leggere i pixel disegnati da `costruisci_splash`."""
    from gui import __version__ as v_gui
    import advcore
    riga1 = f"{componente} · interfaccia {v_gui} · motore advcore {advcore.__version__}"
    riga2 = "Vito Antonio Raimondi · Software libero, licenza GPL-3.0-or-later"
    return riga1, riga2


def costruisci_splash(componente: str) -> "QPixmap":
    """Immagine dello splash d'avvio: la copertina Pasifae (logo, nome,
    tagline) più un piede con le versioni dei pacchetti, l'autore e la
    licenza — pura composizione, senza aprire alcuna finestra (testabile
    senza mostrare nulla a schermo)."""
    from PySide6.QtGui import QColor, QFont, QPainter, QPixmap

    base = pixmap("pasifae_cover.png", larghezza=560)
    piede = 64
    tela = QPixmap(base.width(), base.height() + piede)
    tela.fill(QColor("#1b1e24"))          # bg del tema scuro: continua l'immagine
    p = QPainter(tela)
    if not base.isNull():
        p.drawPixmap(0, 0, base)
    riga1_zona = tela.rect().adjusted(0, base.height() + 6, 0, -32)
    riga2_zona = tela.rect().adjusted(0, base.height() + 30, 0, -8)
    riga1_testo, riga2_testo = _righe_splash(componente)
    p.setFont(QFont("Segoe UI", 10))
    p.setPen(QColor("#d9dce3"))
    p.drawText(riga1_zona, Qt.AlignHCenter | Qt.AlignTop, riga1_testo)
    p.setFont(QFont("Segoe UI", 9))
    p.setPen(QColor("#888e9a"))
    p.drawText(riga2_zona, Qt.AlignHCenter | Qt.AlignTop, riga2_testo)
    p.end()
    return tela


def mostra_splash(app, componente: str, durata_ms: int = 1200):
    """Mostra lo splash d'avvio per almeno `durata_ms` (si può chiudere
    prima con un clic: comportamento di default di QSplashScreen) e lo
    ritorna, ancora visibile: il chiamante lo chiude con
    `splash.finish(finestra_principale)` non appena questa è pronta."""
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QSplashScreen
    splash = QSplashScreen(costruisci_splash(componente))
    splash.show()
    app.processEvents()
    attesa = QEventLoop()
    QTimer.singleShot(durata_ms, attesa.quit)
    attesa.exec()
    return splash


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
