# SPDX-License-Identifier: GPL-3.0-or-later
"""Mappa grafica dell'avventura per l'editor Qt.

Riusa la disposizione su griglia di advcore.mappa (_layout) e disegna stanze,
collegamenti (con senso e condizioni), personaggi e oggetti con QGraphicsView:
vettoriale, con zoom, scorrimento ed esportazione in PNG.
"""
from __future__ import annotations

import math

from advcore.mappa import _layout, _destinazione, _oggetti_in
from gui import tema

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import (
    QBrush, QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPolygonF,
)
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QGraphicsScene, QGraphicsView, QHBoxLayout, QLabel,
    QPushButton, QVBoxLayout,
)

CELL_W, CELL_H = 220, 168
BOX_W, BOX_H = 176, 112
CARD = {"nord": (0, -1), "sud": (0, 1), "est": (1, 0), "ovest": (-1, 0)}


class VistaMappa(QGraphicsView):
    """QGraphicsView con zoom alla rotellina e trascinamento per scorrere."""

    def __init__(self, scena):
        super().__init__(scena)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.TextAntialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

    def wheelEvent(self, ev):
        f = 1.15 if ev.angleDelta().y() > 0 else 1 / 1.15
        self.scale(f, f)


class FinestraMappa(QDialog):
    def __init__(self, mondo, tema_nome="scuro", parent=None):
        super().__init__(parent)
        self.mondo = mondo
        self.pal = tema.PALETTE.get(tema_nome, tema.PALETTE["scuro"])
        self.setWindowTitle("Mappa dell'avventura")
        self.setStyleSheet(tema.qss(tema_nome))
        self.resize(960, 720)

        self.scena = QGraphicsScene(self)
        self.scena.setBackgroundBrush(QColor(self.pal["bg"]))
        self.vista = VistaMappa(self.scena)

        legenda = QLabel(
            "→ senso unico    —  doppio senso    ┄ condizionata (flag)    "
            "◆ personaggio    • oggetto")
        legenda.setObjectName("stato")

        barra = QHBoxLayout()
        barra.addWidget(legenda)
        barra.addStretch(1)
        for testo, slot in (("Adatta", self._adatta), ("+", lambda: self._zoom(1.2)),
                            ("−", lambda: self._zoom(1 / 1.2)),
                            ("Esporta PNG…", self._esporta), ("Chiudi", self.accept)):
            b = QPushButton(testo)
            b.clicked.connect(slot)
            if testo in ("+", "−"):
                b.setFixedWidth(40)
            barra.addWidget(b)

        radice = QVBoxLayout(self)
        radice.setContentsMargins(12, 12, 12, 12)
        radice.addLayout(barra)
        radice.addWidget(self.vista, 1)

        self._costruisci()
        self._adatta()

    # ---------- costruzione della scena ----------

    def _posizioni(self):
        coord, isolate = _layout(self.mondo)
        if not coord and not isolate:
            return {}
        # le stanze non posizionabili vanno in una riga sotto la griglia
        maxy = max((y for _, y in coord.values()), default=-1)
        for i, sid in enumerate(isolate):
            coord[sid] = (i, maxy + 2)
        # normalizza in modo che il minimo sia (0,0)
        minx = min(x for x, _ in coord.values())
        miny = min(y for _, y in coord.values())
        return {sid: (x - minx, y - miny) for sid, (x, y) in coord.items()}

    def _centro(self, pos):
        gx, gy = pos
        return (gx * CELL_W + CELL_W / 2, gy * CELL_H + CELL_H / 2)

    def _costruisci(self):
        pos = self._posizioni()
        if not pos:
            self.scena.addText("(nessuna stanza: crea almeno una stanza)",
                               QFont(tema.FONT_TESTO.split(",")[0], 12))
            return
        self._disegna_collegamenti(pos)
        for sid, p in pos.items():
            self._disegna_stanza(sid, p)

    def _disegna_collegamenti(self, pos):
        # raccoglie tutte le uscite tra stanze posizionate
        conns = []
        for sid in pos:
            for direz, u in self.mondo.stanze[sid].uscite.items():
                dst = _destinazione(u)
                if dst in pos and dst != sid:
                    conns.append((sid, direz, dst, isinstance(u, dict) and bool(u.get("se"))))
        coppie = {(a, b) for a, _, b, _ in conns}
        fatti = set()
        for src, direz, dst, cond in conns:
            doppio = (dst, src) in coppie
            if doppio:
                chiave = tuple(sorted((src, dst)))
                if chiave in fatti:
                    continue
                fatti.add(chiave)
            self._linea(pos[src], pos[dst], direz, cond, freccia=not doppio)

    def _linea(self, pa, pb, direz, cond, freccia):
        cx, cy = self._centro(pa)
        tx, ty = self._centro(pb)
        x1, y1 = _bordo(cx, cy, BOX_W / 2, BOX_H / 2, tx, ty)
        x2, y2 = _bordo(tx, ty, BOX_W / 2, BOX_H / 2, cx, cy)
        colore = QColor(self.pal["accento"]) if not cond else QColor(self.pal["muto"])
        pen = QPen(colore, 2)
        if cond:
            pen.setStyle(Qt.DashLine)
        adiacente = (abs(pa[0] - pb[0]) + abs(pa[1] - pb[1]) == 1) and direz in CARD

        if adiacente:
            self.scena.addLine(x1, y1, x2, y2, pen)
            ax, ay = x1, y1                         # origine per l'orientamento freccia
            lx, ly = (x1 + x2) / 2, (y1 + y2) / 2   # punto dell'etichetta
        else:
            # curva che aggira i riquadri intermedi
            dx, dy = x2 - x1, y2 - y1
            L = math.hypot(dx, dy) or 1
            nx, ny = -dy / L, dx / L
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            off = 46
            ctrlx, ctrly = mx + nx * off, my + ny * off
            path = QPainterPath(QPointF(x1, y1))
            path.quadTo(QPointF(ctrlx, ctrly), QPointF(x2, y2))
            item = self.scena.addPath(path, pen)
            item.setZValue(0)
            ax, ay = ctrlx, ctrly
            lx, ly = ctrlx, ctrly
        if freccia:
            self._freccia(ax, ay, x2, y2, colore)
        if direz not in CARD:
            etichetta = {"giu": "giù"}.get(direz, direz)
            txt = self.scena.addSimpleText(etichetta,
                                           QFont(tema.FONT_TESTO.split(",")[0], 8))
            txt.setBrush(QBrush(QColor(self.pal["muto"])))
            txt.setPos(lx - txt.boundingRect().width() / 2, ly - 8)
            txt.setZValue(3)

    def _freccia(self, x1, y1, x2, y2, colore):
        ang = math.atan2(y2 - y1, x2 - x1)
        s = 10
        p1 = QPointF(x2, y2)
        p2 = QPointF(x2 - s * math.cos(ang - 0.4), y2 - s * math.sin(ang - 0.4))
        p3 = QPointF(x2 - s * math.cos(ang + 0.4), y2 - s * math.sin(ang + 0.4))
        self.scena.addPolygon(QPolygonF([p1, p2, p3]),
                              QPen(colore, 1), QBrush(colore))

    def _disegna_stanza(self, sid, pos):
        gx, gy = pos
        bx = gx * CELL_W + (CELL_W - BOX_W) / 2
        by = gy * CELL_H + (CELL_H - BOX_H) / 2
        stanza = self.mondo.stanze[sid]
        iniziale = (self.mondo.meta.get("stanza_iniziale") == sid)
        buia = bool(getattr(stanza, "buia", False))

        fondo = QColor(self.pal["barra"] if not buia else self.pal["ombra"])
        bordo = QColor(self.pal["accento"] if iniziale else self.pal["bordo"])
        rett = self.scena.addRect(bx, by, BOX_W, BOX_H, QPen(bordo, 2 if iniziale else 1),
                                  QBrush(fondo))
        rett.setZValue(1)

        f_tit = QFont(tema.FONT_TESTO.split(",")[0], 10)
        f_tit.setBold(True)
        titolo = self.scena.addSimpleText(_taglia(stanza.nome or sid, 22), f_tit)
        titolo.setBrush(QBrush(QColor(self.pal["testo"])))
        titolo.setPos(bx + 10, by + 8)
        titolo.setZValue(2)

        f_id = QFont(tema.FONT_TESTO.split(",")[0], 7)
        sub = self.scena.addSimpleText(
            sid + ("  ·  iniziale" if iniziale else "") + ("  ·  buia" if buia else ""),
            f_id)
        sub.setBrush(QBrush(QColor(self.pal["muto"])))
        sub.setPos(bx + 10, by + 26)
        sub.setZValue(2)

        # oggetti e personaggi nella stanza
        oggetti = _oggetti_in(self.mondo, sid)
        png = [o for o in oggetti if o.props.get("png")]
        altri = [o for o in oggetti if not o.props.get("png")]
        righe = ([("◆", o, True) for o in png] + [("•", o, False) for o in altri])
        f_o = QFont(tema.FONT_TESTO.split(",")[0], 8)
        y = by + 44
        mostrati = righe[:4]
        for marca, o, e_png in mostrati:
            scen = o.props.get("scenario")
            col = (self.pal["accento"] if e_png
                   else self.pal["muto"] if scen else self.pal["testo"])
            it = self.scena.addSimpleText(f"{marca} {_taglia(o.nome or o.id, 24)}", f_o)
            it.setBrush(QBrush(QColor(col)))
            it.setPos(bx + 12, y)
            it.setZValue(2)
            y += 15
        if len(righe) > 4:
            piu = self.scena.addSimpleText(f"  +{len(righe) - 4} altri", f_o)
            piu.setBrush(QBrush(QColor(self.pal["muto"])))
            piu.setPos(bx + 12, y)
            piu.setZValue(2)

    # ---------- comandi ----------

    def _adatta(self):
        r = self.scena.itemsBoundingRect().adjusted(-40, -40, 40, 40)
        self.scena.setSceneRect(r)
        self.vista.fitInView(r, Qt.KeepAspectRatio)

    def _zoom(self, f):
        self.vista.scale(f, f)

    def _esporta(self):
        percorso, _ = QFileDialog.getSaveFileName(
            self, "Esporta mappa", "mappa.png", "Immagini (*.png)")
        if not percorso:
            return
        self.esporta(percorso)

    def esporta(self, percorso):
        r = self.scena.itemsBoundingRect().adjusted(-40, -40, 40, 40)
        img = QImage(int(r.width()) * 2, int(r.height()) * 2,
                     QImage.Format_ARGB32)
        img.fill(QColor(self.pal["bg"]))
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        self.scena.render(p, QRectF(img.rect()), r)
        p.end()
        img.save(percorso)


def _bordo(cx, cy, hw, hh, tx, ty):
    """Punto sul bordo del riquadro (centro cx,cy; semi-lati hw,hh) in direzione
    del punto (tx,ty)."""
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0:
        return cx, cy
    sx = hw / abs(dx) if dx else float("inf")
    sy = hh / abs(dy) if dy else float("inf")
    s = min(sx, sy)
    return cx + dx * s, cy + dy * s


def _taglia(testo, n):
    testo = testo or ""
    return testo if len(testo) <= n else testo[:n - 1] + "…"
