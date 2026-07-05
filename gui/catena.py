# SPDX-License-Identifier: GPL-3.0-or-later
"""Finestra «Concatenazione dei puzzle» (Strumenti dell'editor).

Mostra ad albero, a ritroso dai finali, la catena dei passi dell'avventura:
ogni passo (regola, dialogo, esito di scontro, uscita condizionata) elenca i
requisiti, e sotto ogni requisito compaiono i passi che lo producono. La
derivazione dei passi è in analisi.catena_puzzle (pura, senza Qt); qui c'è
solo la vista.
"""
from __future__ import annotations

from advcore.model import INVENTARIO, SCARTATO
from gui import tema
from gui.analisi import catena_puzzle, stanze_libere

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QLabel, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
)

_FINALI = {"vittoria": "🏁 Vittoria", "sconfitta": "☠ Sconfitta"}


class FinestraCatena(QDialog):
    def __init__(self, mondo, tema_nome="scuro", parent=None, vai_a=None):
        super().__init__(parent)
        self.mondo = mondo
        self._vai_a = vai_a
        self.setWindowTitle("Concatenazione dei puzzle")
        self.setStyleSheet(tema.qss(tema_nome))
        self.resize(760, 580)

        self._passi = catena_puzzle(mondo)
        self._produttori: dict[tuple, list] = {}
        for p in self._passi:
            for ris in p["produce"]:
                self._produttori.setdefault(ris, []).append(p)
        self._libere = stanze_libere(mondo)

        v = QVBoxLayout(self)
        v.setContentsMargins(18, 16, 18, 14)
        v.setSpacing(8)
        v.addWidget(QLabel("A ritroso dai finali: sotto ogni passo i suoi "
                           "requisiti, sotto ogni requisito chi lo produce "
                           "(doppio clic per andare all'elemento)."))
        self.albero = QTreeWidget()
        self.albero.setHeaderHidden(True)
        self.albero.itemDoubleClicked.connect(self._doppio_clic)
        v.addWidget(self.albero, 1)
        b = QPushButton("Chiudi")
        b.setAutoDefault(False)
        b.clicked.connect(self.accept)
        v.addWidget(b)

        self._popola()
        self.albero.expandAll()

    # ---------- costruzione dell'albero ----------

    def _popola(self):
        finali = [(esito, p) for esito in _FINALI
                  for p in self._produttori.get(("fine", esito), [])]
        if finali:
            for esito, p in finali:
                radice = QTreeWidgetItem([f"{_FINALI[esito]}  ←  {p['titolo']}"])
                radice.setData(0, Qt.UserRole, (p["categoria"], p["chiave"]))
                self.albero.addTopLevelItem(radice)
                self._aggiungi_requisiti(radice, p, antenati=(id(p),))
        elif self._passi:
            # nessun finale definito: si mostrano tutti i passi in piano
            for p in self._passi:
                it = self._item_passo(p)
                self.albero.addTopLevelItem(it)
                self._aggiungi_requisiti(it, p, antenati=(id(p),))
        else:
            self.albero.addTopLevelItem(QTreeWidgetItem(
                ["Nessun passo concatenato: l'avventura non ha regole, "
                 "dialoghi o uscite condizionate che producano progressi."]))

    def _item_passo(self, p) -> QTreeWidgetItem:
        it = QTreeWidgetItem([p["titolo"]])
        it.setData(0, Qt.UserRole, (p["categoria"], p["chiave"]))
        return it

    def _aggiungi_requisiti(self, item, passo, antenati):
        for genere, rid in passo["richiede"]:
            figlio = QTreeWidgetItem([self._testo_risorsa(genere, rid)])
            item.addChild(figlio)
            self._espandi_risorsa(figlio, genere, rid, antenati)

    def _espandi_risorsa(self, figlio, genere, rid, antenati):
        """Sotto un requisito: i passi che lo producono e, per gli oggetti
        in stanze non liberamente raggiungibili, il requisito della stanza."""
        for prod in self._produttori.get((genere, rid), []):
            if id(prod) in antenati:
                figlio.addChild(QTreeWidgetItem(
                    [f"… {prod['titolo']} (già nella catena sopra)"]))
                continue
            it_p = self._item_passo(prod)
            figlio.addChild(it_p)
            self._aggiungi_requisiti(it_p, prod, antenati + (id(prod),))
        if genere == "oggetto":
            o = self.mondo.oggetti.get(rid)
            if o is not None and o.posizione in self.mondo.stanze \
                    and o.posizione not in self._libere:
                sotto = QTreeWidgetItem(
                    [self._testo_risorsa("stanza", o.posizione)])
                figlio.addChild(sotto)
                self._espandi_risorsa(sotto, "stanza", o.posizione, antenati)

    def _testo_risorsa(self, genere, rid) -> str:
        """Etichetta del requisito, con lo stato di partenza quando aiuta."""
        prodotto = (genere, rid) in self._produttori
        if genere == "flag":
            base = f"serve il flag «{rid}»"
            if self.mondo.flags.get(rid):
                return base + "  —  già vero all'inizio"
            return base if prodotto else base + "  —  ⚠ niente lo imposta"
        if genere == "oggetto":
            base = f"serve «{rid}»"
            o = self.mondo.oggetti.get(rid)
            if o is None:
                return base + "  —  ⚠ oggetto inesistente"
            if o.posizione == INVENTARIO:
                return base + "  —  già nell'inventario"
            if o.posizione in self.mondo.stanze:
                return base + f"  —  si trova in «{o.posizione}»"
            if o.posizione in self.mondo.oggetti:
                return base + f"  —  dentro «{o.posizione}»"
            if o.posizione == SCARTATO or not o.posizione:
                return base if prodotto else base + "  —  ⚠ fuori dal gioco"
            return base
        if genere == "stanza":
            base = f"raggiungere «{rid}»"
            if rid in self._libere:
                return base + "  —  raggiungibile liberamente"
            return base if prodotto else base + "  —  ⚠ nessun accesso noto"
        if genere == "timer":
            base = f"scade il timer «{rid}»"
            return base if prodotto else base + "  —  ⚠ mai avviato"
        return f"{genere} «{rid}»"

    # ---------- navigazione ----------

    def _doppio_clic(self, item, _col):
        dati = item.data(0, Qt.UserRole)
        if dati and self._vai_a:
            self._vai_a(dati[0], dati[1])
            self.accept()
