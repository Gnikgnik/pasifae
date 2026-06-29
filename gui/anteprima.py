# SPDX-License-Identifier: GPL-3.0-or-later
"""Anteprima giocabile dell'avventura dentro l'editor.

Fa girare il motore su una COPIA in memoria del mondo corrente (comprese le
modifiche non salvate): si gioca davvero, ma i progressi della prova non
alterano i dati in modifica. Testo immediato (niente animazione) per provare in
fretta, con storico dei comandi.
"""
from __future__ import annotations

import copy
import html

from advcore import Motore
from gui import tema
from gui.player import InputComando

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout,
)


class FinestraGioco(QDialog):
    def __init__(self, mondo, tema_nome="scuro", parent=None):
        super().__init__(parent)
        self.tema = tema_nome
        self.mondo = copy.deepcopy(mondo)      # si gioca su una copia
        self.motore = Motore(self.mondo)
        self._voci: list[tuple[str, str]] = []

        self.setWindowTitle("Prova dell'avventura")
        self.setStyleSheet(tema.qss(tema_nome))
        self.resize(820, 620)

        radice = QVBoxLayout(self)
        radice.setContentsMargins(0, 0, 0, 0)
        radice.setSpacing(0)

        # intestazione: titolo, avviso, punteggio/turni
        self.titolo = QLabel(); self.titolo.setObjectName("titolo")
        self.stato = QLabel(); self.stato.setObjectName("stato")
        self.stato.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        testa = QFrame(); testa.setObjectName("barra")
        h = QHBoxLayout(testa)
        h.setContentsMargins(20, 12, 20, 12)
        h.addWidget(self.titolo); h.addStretch(1); h.addWidget(self.stato)
        radice.addWidget(testa)

        avviso = QLabel("Anteprima — i progressi di questa prova non vengono salvati.")
        avviso.setObjectName("campetto")
        avviso.setContentsMargins(22, 6, 0, 0)
        radice.addWidget(avviso)

        self.vista = QTextEdit(); self.vista.setObjectName("vista")
        self.vista.setReadOnly(True); self.vista.setFrameStyle(QFrame.NoFrame)
        radice.addWidget(self.vista, 1)

        riga = QFrame(); riga.setObjectName("barra_giu")
        hr = QHBoxLayout(riga)
        hr.setContentsMargins(22, 12, 18, 16); hr.setSpacing(10)
        prompt = QLabel("›"); prompt.setObjectName("prompt")
        self.input = InputComando(); self.input.setObjectName("input")
        self.input.setPlaceholderText("scrivi un comando e premi Invio…  (aiuto)")
        self.input.returnPressed.connect(self._invia)
        b_riavvia = QPushButton("Riavvia"); b_riavvia.clicked.connect(self._riavvia)
        b_chiudi = QPushButton("Chiudi"); b_chiudi.clicked.connect(self.accept)
        # In un QDialog i pulsanti sono "predefiniti": Invio attiverebbe loro invece
        # di inviare il comando. Lo disattiviamo, così Invio resta alla riga.
        for b in (b_riavvia, b_chiudi):
            b.setAutoDefault(False)
            b.setDefault(False)
        hr.addWidget(prompt); hr.addWidget(self.input, 1)
        hr.addWidget(b_riavvia); hr.addWidget(b_chiudi)
        radice.addWidget(riga)

        self._mostra(self.motore.avvia(), "risposta")
        self._aggiorna_stato()
        self.input.setFocus()

    def _invia(self):
        testo = self.input.text().strip()
        if not testo:
            return
        self.input.ricorda(testo)
        self.input.clear()
        self._mostra("› " + testo, "comando")
        risposta = self.motore.esegui(testo)
        if risposta:
            self._mostra(risposta, "risposta")
        self._aggiorna_stato()
        if self.mondo.finita:
            self.input.setPlaceholderText("— fine —   (Riavvia per rigiocare)")

    def _riavvia(self):
        self._voci.clear()
        self._mostra(self.motore.riavvia(), "risposta")
        self._aggiorna_stato()
        self.input.setPlaceholderText("scrivi un comando e premi Invio…  (aiuto)")
        self.input.setFocus()

    def _mostra(self, testo, genere):
        self._voci.append((genere, testo))
        p = tema.PALETTE[self.tema]
        blocchi = []
        for gen, txt in self._voci:
            corpo = html.escape(txt).replace("\n", "<br>")
            if gen == "comando":
                blocchi.append(f'<div style="color:{p["muto"]}; '
                               f'margin:2px 0 14px 0;"><i>{corpo}</i></div>')
            else:
                blocchi.append(f'<div style="color:{p["testo"]}; '
                               f'margin:0 0 16px 0;">{corpo}</div>')
        self.vista.setHtml(
            f'<div style="font-family:{tema.FONT_TESTO}; font-size:16px; '
            f'line-height:165%;">' + "".join(blocchi) + "</div>")
        barra = self.vista.verticalScrollBar()
        barra.setValue(barra.maximum())

    def _aggiorna_stato(self):
        self.titolo.setText(self.mondo.meta.get("titolo") or "Anteprima")
        self.stato.setText(
            f"punteggio {self.mondo.punteggio}    ·    turni {self.mondo.mosse}")
