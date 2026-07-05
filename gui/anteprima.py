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
from pathlib import Path

from advcore import Motore
from advcore.model import INVENTARIO
from gui import analisi, regole, tema
from gui.immagine import PannelloImmagine
from gui.player import InputComando

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPushButton, QSplitter, QTextEdit,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)


class FinestraGioco(QDialog):
    def __init__(self, mondo, tema_nome="scuro", parent=None, partenza=None,
                 percorso=None):
        super().__init__(parent)
        self.tema = tema_nome
        self.mondo = copy.deepcopy(mondo)      # si gioca su una copia
        self.percorso = percorso               # JSON: base delle illustrazioni
        self.partenza = dict(partenza or {})
        self._applica_partenza()
        # il motore fotografa QUESTO stato come iniziale: anche «Riavvia»
        # torna al punto di prova scelto, non all'inizio dell'avventura
        self.motore = Motore(self.mondo)
        self._voci: list[tuple[str, str]] = []

        self.setWindowTitle("Prova dell'avventura")
        self.setStyleSheet(tema.qss(tema_nome))
        self.resize(1060, 640)

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

        testo_avviso = "Anteprima — i progressi di questa prova non vengono salvati."
        if self.partenza.get("stanza"):
            nome = self.mondo.stanze[self.mondo.stanza_corrente].nome
            testo_avviso = (f"Anteprima dal punto scelto («{nome}») — "
                            "i progressi non vengono salvati.")
        avviso = QLabel(testo_avviso)
        avviso.setObjectName("campetto")
        avviso.setContentsMargins(22, 6, 0, 0)
        radice.addWidget(avviso)

        # illustrazione a colonna, a fianco della trascrizione: come nel player
        self.immagine = PannelloImmagine(riempi=True)

        self.vista = QTextEdit(); self.vista.setObjectName("vista")
        self.vista.setReadOnly(True); self.vista.setFrameStyle(QFrame.NoFrame)

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

        colonna = QWidget()
        vdx = QVBoxLayout(colonna)
        vdx.setContentsMargins(0, 0, 0, 0); vdx.setSpacing(0)
        vdx.addWidget(self.vista, 1)
        vdx.addWidget(riga)

        self.spartizione = QSplitter(Qt.Horizontal)
        self.spartizione.addWidget(self.immagine)
        self.spartizione.addWidget(colonna)
        self.spartizione.setCollapsible(1, False)   # il testo non sparisce mai
        self.spartizione.setStretchFactor(0, 2)
        self.spartizione.setStretchFactor(1, 3)
        largo = self.width()
        self.spartizione.setSizes([int(largo * 0.44),
                                   largo - int(largo * 0.44)])
        radice.addWidget(self.spartizione, 1)

        self._mostra(self.motore.avvia(), "risposta")
        self._aggiorna_stato()
        self.input.setFocus()

    def _applica_partenza(self):
        """Prepara la copia del mondo al punto di prova scelto (stanza,
        inventario, flag). Va fatto PRIMA di creare il motore."""
        p = self.partenza
        if p.get("stanza") in self.mondo.stanze:
            self.mondo.stanza_corrente = p["stanza"]
        for oid in p.get("inventario") or []:
            if oid in self.mondo.oggetti:
                self.mondo.oggetti[oid].posizione = INVENTARIO
        self.mondo.flags.update(p.get("flags") or {})

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
        stanza = self.mondo.stanze.get(self.mondo.stanza_corrente)
        if stanza is None or not getattr(stanza, "immagine", "") or not self.percorso:
            self.immagine.mostra_file(None)
        else:
            self.immagine.mostra_file(
                str(Path(self.percorso).parent / stanza.immagine))


class DialogoProvaDa(QDialog):
    """Scelta del punto di prova per le avventure lunghe: stanza di partenza,
    oggetti già nell'inventario e flag preimpostati. Il risultato
    (`partenza()`) si passa a FinestraGioco."""

    def __init__(self, mondo, tema_nome="scuro", parent=None, stanza=None):
        super().__init__(parent)
        self.setWindowTitle("Prova da…")
        self.setStyleSheet(tema.qss(tema_nome))
        self.resize(500, 580)
        v = QVBoxLayout(self)
        v.setContentsMargins(18, 16, 18, 14)
        v.setSpacing(8)

        v.addWidget(self._etichetta("PARTI DALLA STANZA"))
        self.cb_stanza = QComboBox()
        for sid, s in mondo.stanze.items():
            self.cb_stanza.addItem(f"{s.nome}  ({sid})", sid)
        if stanza is not None:
            i = self.cb_stanza.findData(stanza)
            if i >= 0:
                self.cb_stanza.setCurrentIndex(i)
        v.addWidget(self.cb_stanza)

        v.addWidget(self._etichetta("GIÀ NELL'INVENTARIO"))
        self.lista_oggetti = QListWidget()
        for oid, o in mondo.oggetti.items():
            it = QListWidgetItem(f"{o.nome}  ({oid})")
            it.setData(Qt.UserRole, oid)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Unchecked)
            self.lista_oggetti.addItem(it)
        v.addWidget(self.lista_oggetti, 1)

        v.addWidget(self._etichetta("FLAG DA IMPOSTARE (spunta e scrivi il valore)"))
        self.albero_flag = QTreeWidget()
        self.albero_flag.setHeaderLabels(["flag", "valore"])
        self.albero_flag.setRootIsDecorated(False)
        for nome in analisi.flag_noti(mondo):
            iniziale = mondo.flags.get(nome)
            testo = (str(iniziale)
                     if iniziale not in (None, True, False) else "vero")
            it = QTreeWidgetItem([nome, testo])
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEditable)
            it.setCheckState(0, Qt.Unchecked)
            self.albero_flag.addTopLevelItem(it)
        self.albero_flag.setColumnWidth(0, 240)
        v.addWidget(self.albero_flag, 1)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def _etichetta(self, testo: str) -> QLabel:
        e = QLabel(testo)
        e.setObjectName("sezione")
        return e

    def partenza(self) -> dict:
        """Il punto di prova scelto, nel formato atteso da FinestraGioco."""
        inventario = [self.lista_oggetti.item(i).data(Qt.UserRole)
                      for i in range(self.lista_oggetti.count())
                      if self.lista_oggetti.item(i).checkState() == Qt.Checked]
        flags = {}
        for i in range(self.albero_flag.topLevelItemCount()):
            it = self.albero_flag.topLevelItem(i)
            if it.checkState(0) == Qt.Checked:
                flags[it.text(0)] = regole.val_da_testo(it.text(1))
        return {"stanza": self.cb_stanza.currentData(),
                "inventario": inventario, "flags": flags}
