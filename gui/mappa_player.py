# SPDX-License-Identifier: GPL-3.0-or-later
"""Mini-mappa del Pasifae Player: si popola via via che il giocatore esplora.

Sola lettura (nessun drag, nessun menu): un riquadro per ogni stanza già
visitata, una linea per ogni collegamento fra due stanze visitate. Dalle
stanze visitate, le uscite cardinali (nord/sud/est/ovest) verso una stanza
non ancora vista sono un breve trattino verso il bordo — indicano che di là
si può andare, senza svelarne il nome o il contenuto; le uscite non
cardinali (su/giù/dentro/fuori...) verso l'ignoto compaiono come una piccola
etichetta sotto il titolo.

I riquadri non hanno una dimensione fissa: si adattano allo spazio del
pannello, calcolata dalla griglia automatica (`advcore.mappa._layout`, via
`gui.mappa._posizioni_griglia`) ristretta alle sole stanze visitate — non
alle posizioni disegnate a mano nell'editor, che sono libere (non a griglia)
e quindi incompatibili con celle uniformi. Sotto una soglia minima di
leggibilità i riquadri smettono di restringersi e compare lo scorrimento.
"""
from __future__ import annotations

from advcore.engine import ETICHETTA_DIR
from advcore.mappa import uscite_visibili
from gui import tema
from gui.mappa import CARD, _bordo, _posizioni_griglia, _taglia

from PySide6.QtCore import QRectF
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsRectItem, QGraphicsScene, QGraphicsSimpleTextItem, QGraphicsView,
    QSizePolicy, QVBoxLayout, QWidget,
)

# dimensioni del riquadro: si scala fra questi limiti per riempire il
# pannello disponibile senza diventare né illeggibile né spropositato
_BOX_MIN_W, _BOX_MIN_H = 130, 84
_BOX_MAX_W, _BOX_MAX_H = 220, 132
_GAP = 18            # spazio fra le celle della griglia
_STUB_FRAZ = 0.17    # lunghezza del trattino, proporzionale alla larghezza


class MiniMappa(QWidget):
    """Mappa read-only nel player: si aggiorna con `aggiorna()` dopo ogni
    comando (chiamata da Player._aggiorna_stato, come l'illustrazione)."""

    def __init__(self, tema_nome: str = "scuro", parent=None):
        super().__init__(parent)
        self.mondo = None
        self.pal = tema.PALETTE.get(tema_nome, tema.PALETTE["scuro"])
        self.nodi: dict[str, QGraphicsRectItem] = {}
        self._box_w, self._box_h = _BOX_MAX_W, _BOX_MAX_H
        # in uno splitter la dimensione la decide il contenitore (come per
        # PannelloImmagine): senza, il minimo del QGraphicsView costringe la
        # colonna di lettura a restringersi anche su finestre strette
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.setMinimumSize(1, 1)

        self.scena = QGraphicsScene(self)
        self.scena.setBackgroundBrush(QColor(self.pal["bg"]))
        self.vista = QGraphicsView(self.scena)
        self.vista.setRenderHint(QPainter.Antialiasing)
        self.vista.setRenderHint(QPainter.TextAntialiasing)
        self.vista.setDragMode(QGraphicsView.ScrollHandDrag)
        self.vista.setInteractive(False)      # sola lettura

        radice = QVBoxLayout(self)
        radice.setContentsMargins(0, 0, 0, 0)
        radice.addWidget(self.vista, 1)

    def showEvent(self, ev):
        super().showEvent(ev)
        self.aggiorna()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self.aggiorna()

    # ---------- API per il player ----------

    def imposta_tema(self, tema_nome: str):
        self.pal = tema.PALETTE.get(tema_nome, tema.PALETTE["scuro"])
        self.scena.setBackgroundBrush(QColor(self.pal["bg"]))
        self.aggiorna()

    def imposta_mondo(self, mondo):
        """Nuova avventura aperta (o None per svuotare): riparte da zero."""
        self.mondo = mondo
        self.aggiorna()

    def aggiorna(self):
        """Ridisegna le stanze visitate e le uscite note, ricalcolando la
        dimensione dei riquadri sullo spazio disponibile in quel momento.
        Costo trascurabile (poche stanze, nessuna persistenza di item fra
        una chiamata e l'altra): più semplice e robusto che aggiornare la
        scena in place."""
        self.scena.clear()
        self.nodi = {}
        if self.mondo is None:
            self.scena.setSceneRect(QRectF(0, 0, 10, 10))
            return

        visitate = {sid for sid, s in self.mondo.stanze.items() if s.visitata}
        griglia = _posizioni_griglia(self.mondo)
        coord = {sid: griglia[sid] for sid in visitate if sid in griglia}
        if not coord:
            self.scena.setSceneRect(QRectF(0, 0, 10, 10))
            return

        minx = min(x for x, _ in coord.values())
        maxx = max(x for x, _ in coord.values())
        miny = min(y for _, y in coord.values())
        maxy = max(y for _, y in coord.values())
        cols, rows = maxx - minx + 1, maxy - miny + 1

        largo = max(self.vista.viewport().width(), 200)
        alto = max(self.vista.viewport().height(), 150)
        cellw = min(_BOX_MAX_W + _GAP, max(_BOX_MIN_W + _GAP, largo / cols))
        cellh = min(_BOX_MAX_H + _GAP, max(_BOX_MIN_H + _GAP, alto / rows))
        self._box_w, self._box_h = cellw - _GAP, cellh - _GAP

        extra = self._etichette_extra(visitate)
        for sid, (gx, gy) in coord.items():
            nodo = self._crea_nodo(sid, sid == self.mondo.stanza_corrente,
                                   extra.get(sid, []))
            self.scena.addItem(nodo)
            nodo.setPos((gx - minx) * cellw, (gy - miny) * cellh)
            self.nodi[sid] = nodo

        self._disegna_collegamenti(visitate)
        self.scena.setSceneRect(0, 0, cols * cellw, rows * cellh)

    # ---------- costruzione ----------

    def _etichette_extra(self, visitate):
        """Direzioni non cardinali verso una stanza non ancora visitata, per
        ogni stanza visitata: mostrate come testo, non come trattino (non
        hanno un verso sulla griglia)."""
        extra: dict[str, list[str]] = {}
        for sid in visitate:
            for direz, dst in uscite_visibili(self.mondo, self.mondo.stanze[sid]):
                if direz in CARD or dst not in self.mondo.stanze or dst in visitate:
                    continue
                extra.setdefault(sid, []).append(ETICHETTA_DIR.get(direz, direz))
        return extra

    def _crea_nodo(self, sid, corrente, extra):
        stanza = self.mondo.stanze[sid]
        nodo = QGraphicsRectItem(0, 0, self._box_w, self._box_h)
        bordo = QColor(self.pal["accento"] if corrente else self.pal["bordo"])
        nodo.setPen(QPen(bordo, 2 if corrente else 1))
        nodo.setBrush(QBrush(QColor(self.pal["barra"])))

        chars = max(8, int(self._box_w / 9))
        f_tit = QFont(tema.FONT_TESTO.split(",")[0], 10)
        f_tit.setBold(True)
        titolo = QGraphicsSimpleTextItem(_taglia(stanza.nome or sid, chars), nodo)
        titolo.setFont(f_tit)
        titolo.setBrush(QBrush(QColor(self.pal["testo"])))
        titolo.setPos(10, 8)

        if extra:
            f_e = QFont(tema.FONT_TESTO.split(",")[0], 8)
            et = QGraphicsSimpleTextItem(
                _taglia("altre uscite: " + ", ".join(extra), chars + 8), nodo)
            et.setFont(f_e)
            et.setBrush(QBrush(QColor(self.pal["muto"])))
            et.setPos(10, self._box_h - 20)
        return nodo

    def _centro(self, sid):
        p = self.nodi[sid].pos()
        return (p.x() + self._box_w / 2, p.y() + self._box_h / 2)

    def _disegna_collegamenti(self, visitate):
        fatti = set()
        for sid in visitate:
            for direz, dst in uscite_visibili(self.mondo, self.mondo.stanze[sid]):
                if dst == sid or dst not in self.mondo.stanze:
                    continue
                if dst in visitate:
                    chiave = tuple(sorted((sid, dst)))
                    if chiave in fatti:
                        continue
                    fatti.add(chiave)
                    self._linea_piena(sid, dst)
                elif direz in CARD:
                    self._trattino(sid, direz)

    def _linea_piena(self, src, dst):
        cx, cy = self._centro(src)
        tx, ty = self._centro(dst)
        x1, y1 = _bordo(cx, cy, self._box_w / 2, self._box_h / 2, tx, ty)
        x2, y2 = _bordo(tx, ty, self._box_w / 2, self._box_h / 2, cx, cy)
        self.scena.addLine(x1, y1, x2, y2, QPen(QColor(self.pal["accento"]), 2))

    def _trattino(self, sid, direz):
        cx, cy = self._centro(sid)
        dx, dy = CARD[direz]
        x1, y1 = _bordo(cx, cy, self._box_w / 2, self._box_h / 2, cx + dx, cy + dy)
        stub = self._box_w * _STUB_FRAZ
        x2, y2 = x1 + dx * stub, y1 + dy * stub
        self.scena.addLine(x1, y1, x2, y2, QPen(QColor(self.pal["muto"]), 2))
