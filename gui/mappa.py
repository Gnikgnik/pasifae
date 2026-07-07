# SPDX-License-Identifier: GPL-3.0-or-later
"""Mappa grafica dell'avventura per l'editor Qt.

Le stanze sono riquadri trascinabili: la disposizione scelta dall'autore vive
in meta["editor"]["mappa"] (il motore la ignora; storage la conserva com'è).
In mancanza di posizioni salvate si usa la griglia di advcore.mappa (_layout).
I collegamenti (con senso e condizioni) seguono i nodi in tempo reale.
Vettoriale, con zoom, scorrimento ed esportazione in PNG.
"""
from __future__ import annotations

import math

from advcore.mappa import _layout, _destinazione, _oggetti_in
from advcore.model import Stanza
from advcore.parser import DIREZIONI_CANONICHE
from gui import tema

from PySide6.QtCore import Qt, QLineF, QPointF, QRectF, QTimer
from PySide6.QtGui import (
    QBrush, QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPolygonF,
)
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QGraphicsItem, QGraphicsRectItem, QGraphicsScene, QGraphicsSimpleTextItem,
    QGraphicsView, QHBoxLayout, QInputDialog, QLabel, QMenu, QMessageBox,
    QPushButton, QVBoxLayout,
)

CELL_W, CELL_H = 220, 168
BOX_W, BOX_H = 176, 112
CARD = {"nord": (0, -1), "sud": (0, 1), "est": (1, 0), "ovest": (-1, 0)}
OPPOSTE = {"nord": "sud", "sud": "nord", "est": "ovest", "ovest": "est",
           "su": "giu", "giu": "su", "dentro": "fuori", "fuori": "dentro"}


class VistaMappa(QGraphicsView):
    """QGraphicsView con zoom alla rotellina e trascinamento per scorrere."""

    def __init__(self, scena, finestra=None):
        super().__init__(scena)
        self._finestra = finestra
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.TextAntialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

    def wheelEvent(self, ev):
        f = 1.15 if ev.angleDelta().y() > 0 else 1 / 1.15
        self.scale(f, f)

    def contextMenuEvent(self, ev):
        """Clic destro sul vuoto: menu del canvas (nuova stanza). Sui nodi
        non fa nulla: lì il tasto destro trascina un collegamento o apre il
        menu delle uscite al rilascio."""
        if self._finestra is None:
            return
        it = self.itemAt(ev.pos())
        while it is not None and not isinstance(it, NodoStanza):
            it = it.parentItem()
        if it is not None:
            return
        self._finestra._menu_canvas(ev.globalPos(), self.mapToScene(ev.pos()))


class NodoStanza(QGraphicsRectItem):
    """Riquadro di stanza trascinabile. Mentre si muove avvisa la finestra,
    che aggiorna i collegamenti e registra la posizione nei metadati."""

    def __init__(self, sid, finestra):
        super().__init__(0, 0, BOX_W, BOX_H)
        self.sid = sid
        self._finestra = finestra
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemSendsScenePositionChanges)
        self.setCursor(Qt.OpenHandCursor)
        self.setZValue(1)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemScenePositionHasChanged:
            self._finestra._nodo_spostato(self.sid)
        return super().itemChange(change, value)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.RightButton:
            self._finestra._inizia_collegamento(self.sid, ev.scenePos())
            ev.accept()
            return
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self._finestra._collegamento_da:
            self._finestra._muovi_collegamento(ev.scenePos())
            return
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.RightButton and self._finestra._collegamento_da:
            self._finestra._chiudi_collegamento(ev.scenePos(), ev.screenPos())
            return
        super().mouseReleaseEvent(ev)
        self._finestra._fine_trascinamento(self.sid)

    def mouseDoubleClickEvent(self, ev):
        self._finestra._apri_stanza(self.sid)
        ev.accept()


class FinestraMappa(QDialog):
    def __init__(self, mondo, tema_nome="scuro", parent=None, su_modifica=None,
                 vai_a=None):
        super().__init__(parent)
        self.mondo = mondo
        self.su_modifica = su_modifica
        self._vai_a = vai_a
        self.pal = tema.PALETTE.get(tema_nome, tema.PALETTE["scuro"])
        self.setWindowTitle("Mappa dell'avventura")
        self.setStyleSheet(tema.qss(tema_nome))
        self.resize(960, 720)

        self.nodi: dict[str, NodoStanza] = {}
        self._item_collegamenti = []
        self._spostati = set()
        self._pronta = False
        self._collegamento_da = None    # sid sorgente del right-drag in corso
        self._collegamento_press = None
        self._linea_tmp = None

        self.scena = QGraphicsScene(self)
        self.scena.setBackgroundBrush(QColor(self.pal["bg"]))
        self.vista = VistaMappa(self.scena, self)

        legenda = QLabel(
            "trascina i riquadri · doppio clic apre la stanza · tasto destro "
            "e trascina = nuova uscita · destro su stanza = uscite · destro "
            "sul vuoto = nuova stanza\n"
            "→ senso unico    —  doppio senso    ┄ condizionata (flag)    "
            "◆ personaggio    • oggetto")
        legenda.setObjectName("stato")

        barra = QHBoxLayout()
        barra.addWidget(legenda)
        barra.addStretch(1)
        for testo, slot in (("Riordina", self._riordina),
                            ("Adatta", self._adatta), ("+", lambda: self._zoom(1.2)),
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
        self._pronta = True
        self._adatta()

    # ---------- costruzione della scena ----------

    def _posizioni_griglia(self):
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

    def _posizioni_pixel(self):
        """Angolo alto-sinistro di ogni riquadro: prima le posizioni salvate
        dall'autore (meta["editor"]["mappa"]), per le altre stanze la griglia
        automatica."""
        griglia = self._posizioni_griglia()
        salvate = self.mondo.meta.get("editor", {}).get("mappa", {})
        pos = {}
        for sid, (gx, gy) in griglia.items():
            p = salvate.get(sid)
            if (isinstance(p, (list, tuple)) and len(p) == 2
                    and all(isinstance(v, (int, float)) for v in p)):
                pos[sid] = (float(p[0]), float(p[1]))
            else:
                pos[sid] = (gx * CELL_W + (CELL_W - BOX_W) / 2,
                            gy * CELL_H + (CELL_H - BOX_H) / 2)
        return pos

    def _costruisci(self):
        pos = self._posizioni_pixel()
        if not pos:
            self.scena.addText("(nessuna stanza: crea almeno una stanza)",
                               QFont(tema.FONT_TESTO.split(",")[0], 12))
            return
        for sid, (px, py) in pos.items():
            nodo = self._crea_nodo(sid)
            self.scena.addItem(nodo)
            nodo.setPos(px, py)
            self.nodi[sid] = nodo
        self._ridisegna_collegamenti()

    def _crea_nodo(self, sid):
        """Il riquadro della stanza con titolo, sottotitolo e contenuto come
        figli: si muove tutto insieme."""
        stanza = self.mondo.stanze[sid]
        iniziale = (self.mondo.meta.get("stanza_iniziale") == sid)
        buia = bool(getattr(stanza, "buia", False))

        nodo = NodoStanza(sid, self)
        fondo = QColor(self.pal["barra"] if not buia else self.pal["ombra"])
        bordo = QColor(self.pal["accento"] if iniziale else self.pal["bordo"])
        nodo.setPen(QPen(bordo, 2 if iniziale else 1))
        nodo.setBrush(QBrush(fondo))

        f_tit = QFont(tema.FONT_TESTO.split(",")[0], 10)
        f_tit.setBold(True)
        titolo = QGraphicsSimpleTextItem(_taglia(stanza.nome or sid, 22), nodo)
        titolo.setFont(f_tit)
        titolo.setBrush(QBrush(QColor(self.pal["testo"])))
        titolo.setPos(10, 8)

        f_id = QFont(tema.FONT_TESTO.split(",")[0], 7)
        sub = QGraphicsSimpleTextItem(
            sid + ("  ·  iniziale" if iniziale else "") + ("  ·  buia" if buia else ""),
            nodo)
        sub.setFont(f_id)
        sub.setBrush(QBrush(QColor(self.pal["muto"])))
        sub.setPos(10, 26)

        # oggetti e personaggi nella stanza
        oggetti = _oggetti_in(self.mondo, sid)
        png = [o for o in oggetti if o.props.get("png")]
        altri = [o for o in oggetti if not o.props.get("png")]
        righe = ([("◆", o, True) for o in png] + [("•", o, False) for o in altri])
        f_o = QFont(tema.FONT_TESTO.split(",")[0], 8)
        y = 44
        for marca, o, e_png in righe[:4]:
            scen = o.props.get("scenario")
            col = (self.pal["accento"] if e_png
                   else self.pal["muto"] if scen else self.pal["testo"])
            it = QGraphicsSimpleTextItem(f"{marca} {_taglia(o.nome or o.id, 24)}",
                                         nodo)
            it.setFont(f_o)
            it.setBrush(QBrush(QColor(col)))
            it.setPos(12, y)
            y += 15
        if len(righe) > 4:
            piu = QGraphicsSimpleTextItem(f"  +{len(righe) - 4} altri", nodo)
            piu.setFont(f_o)
            piu.setBrush(QBrush(QColor(self.pal["muto"])))
            piu.setPos(12, y)
        return nodo

    # ---------- collegamenti ----------

    def _centro(self, sid):
        p = self.nodi[sid].pos()
        return (p.x() + BOX_W / 2, p.y() + BOX_H / 2)

    def _ridisegna_collegamenti(self):
        for it in self._item_collegamenti:
            self.scena.removeItem(it)
        self._item_collegamenti = []
        conns = []
        for sid in self.nodi:
            for direz, u in self.mondo.stanze[sid].uscite.items():
                dst = _destinazione(u)
                if dst in self.nodi and dst != sid:
                    conns.append((sid, direz, dst,
                                  isinstance(u, dict) and bool(u.get("se"))))
        coppie = {(a, b) for a, _, b, _ in conns}
        fatti = set()
        for src, direz, dst, cond in conns:
            doppio = (dst, src) in coppie
            if doppio:
                chiave = tuple(sorted((src, dst)))
                if chiave in fatti:
                    continue
                fatti.add(chiave)
            self._linea(src, dst, direz, cond, freccia=not doppio)

    def _linea(self, src, dst, direz, cond, freccia):
        cx, cy = self._centro(src)
        tx, ty = self._centro(dst)
        x1, y1 = _bordo(cx, cy, BOX_W / 2, BOX_H / 2, tx, ty)
        x2, y2 = _bordo(tx, ty, BOX_W / 2, BOX_H / 2, cx, cy)
        colore = QColor(self.pal["accento"]) if not cond else QColor(self.pal["muto"])
        pen = QPen(colore, 2)
        if cond:
            pen.setStyle(Qt.DashLine)

        if not self._attraversa_nodi(x1, y1, x2, y2, {src, dst}):
            it = self.scena.addLine(x1, y1, x2, y2, pen)
            it.setZValue(0)
            self._item_collegamenti.append(it)
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
            it = self.scena.addPath(path, pen)
            it.setZValue(0)
            self._item_collegamenti.append(it)
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
            self._item_collegamenti.append(txt)

    def _attraversa_nodi(self, x1, y1, x2, y2, esclusi):
        """Vero se il segmento passa sopra il riquadro di un'altra stanza."""
        linea = QLineF(x1, y1, x2, y2)
        for sid, nodo in self.nodi.items():
            if sid in esclusi:
                continue
            p = nodo.pos()
            r = QRectF(p.x(), p.y(), BOX_W, BOX_H).adjusted(-6, -6, 6, 6)
            if _interseca(linea, r):
                return True
        return False

    def _freccia(self, x1, y1, x2, y2, colore):
        ang = math.atan2(y2 - y1, x2 - x1)
        s = 10
        p1 = QPointF(x2, y2)
        p2 = QPointF(x2 - s * math.cos(ang - 0.4), y2 - s * math.sin(ang - 0.4))
        p3 = QPointF(x2 - s * math.cos(ang + 0.4), y2 - s * math.sin(ang + 0.4))
        it = self.scena.addPolygon(QPolygonF([p1, p2, p3]),
                                   QPen(colore, 1), QBrush(colore))
        self._item_collegamenti.append(it)

    # ---------- trascinamento ----------

    def _nodo_spostato(self, sid):
        """Chiamato dal nodo a ogni variazione di posizione: registra la
        posizione nei metadati dell'editor e fa seguire i collegamenti."""
        if not self._pronta:
            return
        p = self.nodi[sid].pos()
        (self.mondo.meta.setdefault("editor", {})
             .setdefault("mappa", {}))[sid] = [round(p.x()), round(p.y())]
        self._spostati.add(sid)
        self._ridisegna_collegamenti()

    def _fine_trascinamento(self, sid):
        """Al rilascio del mouse: se il nodo si è davvero mosso, una sola
        segnalazione di modifica all'editor."""
        if sid not in self._spostati:
            return
        self._spostati.discard(sid)
        if self.su_modifica:
            self.su_modifica()

    def _apri_stanza(self, sid):
        """Doppio clic su un riquadro: salta alla stanza nell'editor e chiude
        la mappa (che è modale) per lasciare il posto."""
        if self._vai_a:
            self._vai_a("Stanze", sid)
            self.accept()

    # ---------- uscite dal trascinamento col tasto destro ----------

    def _inizia_collegamento(self, sid, punto):
        self._collegamento_da = sid
        self._collegamento_press = punto
        cx, cy = self._centro(sid)
        pen = QPen(QColor(self.pal["accento"]), 2, Qt.DashLine)
        self._linea_tmp = self.scena.addLine(cx, cy, punto.x(), punto.y(), pen)
        self._linea_tmp.setZValue(4)

    def _muovi_collegamento(self, punto):
        if self._linea_tmp is not None:
            ln = self._linea_tmp.line()
            self._linea_tmp.setLine(ln.x1(), ln.y1(), punto.x(), punto.y())

    def _chiudi_collegamento(self, punto, punto_schermo):
        src = self._collegamento_da
        press = self._collegamento_press
        self._collegamento_da = None
        self._collegamento_press = None
        if self._linea_tmp is not None:
            self.scena.removeItem(self._linea_tmp)
            self._linea_tmp = None
        dst = self._nodo_a(punto)
        # menu e dialoghi vanno aperti DOPO che il gestore dell'evento è
        # tornato e il grab del mouse è stato rilasciato: su Wayland un
        # popup dentro il gestore fallisce il grab e può andare in crash.
        if dst is None or dst == src:
            # clic destro fermo sulla stanza: menu delle sue uscite
            if press is not None and (punto - press).manhattanLength() < 8:
                QTimer.singleShot(0, lambda: self._menu_stanza(src,
                                                               punto_schermo))
            return
        QTimer.singleShot(0, lambda: self._proponi_uscita(src, dst))

    def _proponi_uscita(self, src, dst):
        scelta = self._chiedi_uscita(src, dst)
        if scelta:
            direz, ritorno = scelta
            self._crea_uscita(src, dst, direz, ritorno)

    def _nodo_a(self, punto):
        """L'id della stanza il cui riquadro contiene il punto di scena."""
        for it in self.scena.items(punto):
            while it is not None and not isinstance(it, NodoStanza):
                it = it.parentItem()
            if it is not None:
                return it.sid
        return None

    def _chiedi_uscita(self, src, dst):
        """Dialogo per la nuova uscita src → dst: direzione (solo quelle
        libere) e ritorno opzionale. Ritorna (direzione, ritorno) o None."""
        libere = [d for d in DIREZIONI_CANONICHE
                  if d not in self.mondo.stanze[src].uscite]
        if not libere:
            QMessageBox.information(
                self, "Nessuna direzione libera",
                f"«{self.mondo.stanze[src].nome}» ha già un'uscita in ogni "
                "direzione.")
            return None
        dlg = QDialog(self)
        dlg.setWindowTitle("Nuova uscita")
        dlg.setStyleSheet(self.styleSheet())
        form = QFormLayout(dlg)
        form.addRow(QLabel(f"Da «{self.mondo.stanze[src].nome}» "
                           f"a «{self.mondo.stanze[dst].nome}»"))
        cb = QComboBox()
        for d in libere:
            cb.addItem({"giu": "giù"}.get(d, d), d)
        form.addRow("Direzione:", cb)
        chk = QCheckBox("crea anche il ritorno (direzione opposta)")
        chk.setChecked(True)
        form.addRow(chk)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        form.addRow(bb)
        if dlg.exec() != QDialog.Accepted:
            return None
        return cb.currentData(), chk.isChecked()

    def _crea_uscita(self, src, dst, direz, ritorno):
        uscite = self.mondo.stanze[src].uscite
        if direz in uscite:
            QMessageBox.information(
                self, "Direzione occupata",
                f"«{self.mondo.stanze[src].nome}» ha già un'uscita verso "
                f"{direz}. Eliminala prima (clic destro sulla stanza).")
            return
        uscite[direz] = dst
        opp = OPPOSTE.get(direz)
        if ritorno and opp and opp not in self.mondo.stanze[dst].uscite:
            self.mondo.stanze[dst].uscite[opp] = src
        self._ridisegna_collegamenti()
        if self.su_modifica:
            self.su_modifica()

    def _elimina_uscita(self, sid, direz):
        self.mondo.stanze[sid].uscite.pop(direz, None)
        self._ridisegna_collegamenti()
        if self.su_modifica:
            self.su_modifica()

    def _menu_stanza(self, sid, punto_schermo):
        """Clic destro fermo su una stanza: le sue uscite, da eliminare."""
        stanza = self.mondo.stanze[sid]
        menu = QMenu(self)
        menu.setStyleSheet(self.styleSheet())
        if stanza.uscite:
            for direz, u in sorted(stanza.uscite.items()):
                dst = _destinazione(u)
                nome = (self.mondo.stanze[dst].nome
                        if dst in self.mondo.stanze else dst)
                az = menu.addAction(
                    f"Elimina uscita {'giù' if direz == 'giu' else direz} "
                    f"→ {nome}")
                az.setData(direz)
        else:
            az = menu.addAction("(nessuna uscita)")
            az.setEnabled(False)
            az.setData(None)
        scelto = menu.exec(punto_schermo.toPoint()
                           if hasattr(punto_schermo, "toPoint")
                           else punto_schermo)
        if scelto and scelto.data():
            self._elimina_uscita(sid, scelto.data())

    # ---------- nuova stanza dal canvas ----------

    def _menu_canvas(self, punto_schermo, punto_scena):
        menu = QMenu(self)
        menu.setStyleSheet(self.styleSheet())
        az = menu.addAction("Nuova stanza qui…")
        if menu.exec(punto_schermo) == az:
            self._chiedi_stanza(punto_scena)

    def _chiedi_stanza(self, punto):
        sid, ok = QInputDialog.getText(self, "Nuova stanza",
                                       "Identificatore (id) univoco:")
        sid = sid.strip()
        if not (ok and sid):
            return
        if sid in self.mondo.stanze:
            QMessageBox.information(self, "Nuova stanza",
                                    "Esiste già una stanza con questo id.")
            return
        nome, ok = QInputDialog.getText(
            self, "Nuova stanza", "Nome della stanza (mostrato al giocatore):",
            text=sid)
        nome = nome.strip()
        self._crea_stanza(sid, nome if (ok and nome) else sid, punto)

    def _crea_stanza(self, sid, nome, punto):
        """Crea la stanza e il suo riquadro con l'angolo nel punto di scena."""
        if not sid or sid in self.mondo.stanze:
            QMessageBox.information(self, "Nuova stanza",
                                    "Esiste già una stanza con questo id.")
            return
        self.mondo.stanze[sid] = Stanza(id=sid, nome=nome or sid, desc="",
                                        uscite={})
        nodo = self._crea_nodo(sid)
        self.scena.addItem(nodo)
        self.nodi[sid] = nodo
        nodo.setPos(punto.x(), punto.y())   # _nodo_spostato registra in meta
        self._spostati.discard(sid)
        if self.su_modifica:
            self.su_modifica()

    def _riordina(self):
        """Dimentica le posizioni manuali e torna al layout automatico."""
        salvate = self.mondo.meta.get("editor", {}).get("mappa")
        if salvate:
            self.mondo.meta["editor"].pop("mappa", None)
            if self.su_modifica:
                self.su_modifica()
        self._pronta = False
        self.scena.clear()
        self.nodi = {}
        self._item_collegamenti = []
        self._spostati = set()
        self._costruisci()
        self._pronta = True
        self._adatta()

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


def _interseca(linea: QLineF, r: QRectF) -> bool:
    """Vero se il segmento tocca il rettangolo."""
    if r.contains(linea.p1()) or r.contains(linea.p2()):
        return True
    lati = (QLineF(r.topLeft(), r.topRight()),
            QLineF(r.topRight(), r.bottomRight()),
            QLineF(r.bottomRight(), r.bottomLeft()),
            QLineF(r.bottomLeft(), r.topLeft()))
    for lato in lati:
        tipo, _ = linea.intersects(lato)
        if tipo == QLineF.IntersectionType.BoundedIntersection:
            return True
    return False


def _taglia(testo, n):
    testo = testo or ""
    return testo if len(testo) <= n else testo[:n - 1] + "…"
