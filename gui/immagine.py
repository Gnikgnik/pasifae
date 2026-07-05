# SPDX-License-Identifier: GPL-3.0-or-later
"""Pannello dell'illustrazione di stanza, condiviso da player e anteprima.

Un'etichetta sopra la trascrizione che mostra l'immagine della stanza
corrente (stile Magnetic Scrolls) e collassa quando la stanza non ne ha una.
Volutamente NON inline nel QTextEdit: le immagini nel documento si
intreccerebbero con l'animazione telescrivente e con lo scorrimento pigro
del layout, zone già delicate.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel


class PannelloImmagine(QLabel):
    """Mostra un'immagine adattata alla larghezza, con un tetto in altezza.
    Nascosto quando non c'è nulla da mostrare o l'utente lo ha spento."""

    ALTEZZA_MAX = 240

    def __init__(self):
        super().__init__()
        self.setObjectName("illustrazione")
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
        self.setPixmap(self._sorgente.scaled(
            max(1, self.contentsRect().width()), self.ALTEZZA_MAX,
            Qt.KeepAspectRatio, Qt.SmoothTransformation))
