# SPDX-License-Identifier: GPL-3.0-or-later
"""Pannello dell'illustrazione di stanza, condiviso da player e anteprima.

Un'etichetta che mostra l'immagine della stanza corrente (stile Magnetic
Scrolls) e collassa quando la stanza non ne ha una. Due modalità: striscia
sopra la trascrizione (tetto in altezza) oppure colonna a fianco, dove
l'immagine riempie tutta l'altezza disponibile.
Volutamente NON inline nel QTextEdit: le immagini nel documento si
intreccerebbero con l'animazione telescrivente e con lo scorrimento pigro
del layout, zone già delicate.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy


class PannelloImmagine(QLabel):
    """Mostra un'immagine adattata allo spazio del pannello: in modalità
    striscia si adatta alla larghezza con un tetto in altezza; in modalità
    colonna (`riempi=True`) sfrutta tutta l'area che il layout le concede.
    Nascosto quando non c'è nulla da mostrare o l'utente lo ha spento."""

    ALTEZZA_MAX = 240

    def __init__(self, riempi: bool = False):
        super().__init__()
        self.setObjectName("illustrazione")
        self._riempi = bool(riempi)
        if self._riempi:
            # in uno splitter la dimensione la decide il contenitore: la
            # pixmap non deve gonfiare il sizeHint e allargare la colonna
            self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
            self.setMinimumSize(1, 1)
            self.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
            self.setContentsMargins(26, 14, 12, 18)
        else:
            self.setAlignment(Qt.AlignCenter)
            self.setContentsMargins(26, 14, 26, 0)   # come il padding della vista
        self._sorgente: QPixmap | None = None
        self._percorso: str | None = None
        self._attiva = True
        self.hide()

    def imposta_attiva(self, attiva: bool):
        """Interruttore dell'utente (Visualizza ▸ Illustrazioni)."""
        self._attiva = bool(attiva)
        self._aggiorna_visibilita()

    def mostra_file(self, percorso: str | None):
        """Carica e mostra l'immagine; None, file mancante o illeggibile
        collassano il pannello senza errori."""
        if percorso == self._percorso:
            return
        self._percorso = percorso
        self._sorgente = None
        if percorso and Path(percorso).is_file():
            pm = QPixmap(percorso)
            if not pm.isNull():
                self._sorgente = pm
        self._riscala()
        self._aggiorna_visibilita()

    def _aggiorna_visibilita(self):
        self.setVisible(self._attiva and self._sorgente is not None)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._riscala()

    def _riscala(self):
        if self._sorgente is None:
            self.clear()
            return
        r = self.contentsRect()
        tetto = r.height() if self._riempi else self.ALTEZZA_MAX
        self.setPixmap(self._sorgente.scaled(
            max(1, r.width()), max(1, tetto),
            Qt.KeepAspectRatio, Qt.SmoothTransformation))
