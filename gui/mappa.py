# SPDX-License-Identifier: GPL-3.0-or-later
"""Mappa grafica dell'avventura: il piano di lavoro al centro dell'editor.

PannelloMappa è un widget riusabile: le stanze sono riquadri trascinabili, la
disposizione scelta dall'autore vive in meta["editor"]["mappa"] (il motore la
ignora; storage la conserva com'è). In mancanza di posizioni salvate si usa la
griglia di advcore.mappa (_layout). I collegamenti (con senso e condizioni)
seguono i nodi in tempo reale. Vettoriale, con zoom, scorrimento ed
esportazione in PNG.
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
    QPushButton, QVBoxLayout, QWidget,
)

CELL_W, CELL_H = 220, 168
BOX_W, BOX_H = 176, 112
CARD = {"nord": (0, -1), "sud": (0, 1), "est": (1, 0), "ovest": (-1, 0)}
OPPOSTE = {"nord": "sud", "sud": "nord", "est": "ovest", "ovest": "est",
           "su": "giu", "giu": "su", "dentro": "fuori", "fuori": "dentro"}


def _posizioni_griglia(mondo):
    """Coordinate di griglia per ogni stanza (BFS di advcore.mappa._layout,
    le isolate in una riga sotto), normalizzate a partire da (0, 0)."""
    coord, isolate = _layout(mondo)
    if not coord and not isolate:
        return {}
    maxy = max((y for _, y in coord.values()), default=-1)
    for i, sid in enumerate(isolate):
        coord[sid] = (i, maxy + 2)
    minx = min(x for x, _ in coord.values())
    miny = min(y for _, y in coord.values())
    return {sid: (x - minx, y - miny) for sid, (x, y) in coord.items()}


def _posizioni_pixel(mondo):
    """Angolo alto-sinistro di ogni riquadro: prima le posizioni salvate
    dall'autore (meta["editor"]["mappa"]), per le altre stanze la griglia
    automatica. Condivisa fra l'editor (PannelloMappa) e la mini-mappa del
    player (gui/mappa_player.py)."""
    griglia = _posizioni_griglia(mondo)
    salvate = mondo.meta.get("editor", {}).get("mappa", {})
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


class VistaMappa(QGraphicsView):
    """QGraphicsView con zoom alla rotellina e trascinamento per scorrere."""

    def __init__(self, scena, pannello=None):
        super().__init__(scena)
        self._pannello = pannello
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
        if self._pannello is None:
            return
        # su Linux questo evento scatta alla PRESSIONE del destro, subito
        # dopo il press che può aver avviato un collegamento: in quel caso
        # niente menu (e c'è la linea provvisoria sotto il cursore, che
        # farebbe sembrare vuoto il punto)
        if self._pannello._collegamento_da:
            ev.accept()
            return
        # un nodo può stare sotto item non-nodo (linee, etichette):
        # cerca un NodoStanza fra TUTTI gli item nel punto
        for it in self.items(ev.pos()):
            while it is not None and not isinstance(it, NodoStanza):
                it = it.parentItem()
            if it is not None:
                ev.accept()
                return
        self._pannello._menu_canvas(ev.globalPos(), self.mapToScene(ev.pos()))


class NodoStanza(QGraphicsRectItem):
    """Riquadro di stanza trascinabile. Mentre si muove avvisa il pannello,
    che aggiorna i collegamenti e registra la posizione nei metadati."""

    def __init__(self, sid, pannello):
        super().__init__(0, 0, BOX_W, BOX_H)
        self.sid = sid
        self._pannello = pannello
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemSendsScenePositionChanges)
        self.setCursor(Qt.OpenHandCursor)
        self.setZValue(1)

    def itemChange(self, change, value):
        if (change == QGraphicsItem.ItemScenePositionHasChanged
                and self._pannello is not None):
            self._pannello._nodo_spostato(self.sid)
        return super().itemChange(change, value)

    def mousePressEvent(self, ev):
        if self._pannello is not None and ev.button() == Qt.RightButton:
            self._pannello._inizia_collegamento(self.sid, ev.scenePos())
            ev.accept()
            return
        super().mousePressEvent(ev)
        if self._pannello is not None and ev.button() == Qt.LeftButton:
            self._pannello._nodo_scelto(self.sid)

    def mouseMoveEvent(self, ev):
        if self._pannello is not None and self._pannello._collegamento_da:
            self._pannello._muovi_collegamento(ev.scenePos())
            return
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if (self._pannello is not None and ev.button() == Qt.RightButton
                and self._pannello._collegamento_da):
            self._pannello._chiudi_collegamento(ev.scenePos(), ev.screenPos())
            return
        super().mouseReleaseEvent(ev)
        if self._pannello is not None:
            self._pannello._fine_trascinamento(self.sid)

    def mouseDoubleClickEvent(self, ev):
        if self._pannello is not None:
            self._pannello._apri_stanza(self.sid)
        ev.accept()


class PannelloMappa(QWidget):
    """La mappa come piano di lavoro: widget riusabile con vista, comandi e
    tutti i gesti (trascinare le stanze, creare uscite col tasto destro,
    nuova stanza dal canvas)."""

    def __init__(self, mondo, tema_nome="scuro", parent=None, su_modifica=None,
                 vai_a=None, su_selezione=None):
        super().__init__(parent)
        self.mondo = mondo
        self.su_modifica = su_modifica
        self._vai_a = vai_a
        self._su_selezione = su_selezione
        self.pal = tema.PALETTE.get(tema_nome, tema.PALETTE["scuro"])

        self.nodi: dict[str, NodoStanza] = {}
        self._collegamenti = []
        self._spostati = set()
        self._pronta = False
        self._adattata = False
        self._collegamento_da = None    # sid sorgente del right-drag in corso
        self._collegamento_press = None
        self._linea_tmp = None

        self.scena = QGraphicsScene(self)
        self.scena.setBackgroundBrush(QColor(self.pal["bg"]))
        self.vista = VistaMappa(self.scena, self)

        barra = QHBoxLayout()
        barra.addStretch(1)
        for testo, slot in (("Riordina", self._riordina),
                            ("Adatta", self.adatta), ("+", lambda: self._zoom(1.2)),
                            ("−", lambda: self._zoom(1 / 1.2)),
                            ("Esporta PNG…", self.esporta_png)):
            b = QPushButton(testo)
            b.clicked.connect(slot)
            if testo in ("+", "−"):
                b.setFixedWidth(40)
            barra.addWidget(b)

        legenda = QLabel(
            "clic seleziona · trascina i riquadri · tasto destro e trascina "
            "= nuova uscita · destro su stanza = uscite · destro sul vuoto "
            "= nuova stanza\n"
            "→ senso unico    —  doppio senso    ┄ condizionata (flag)    "
            "◆ personaggio    • oggetto")
        legenda.setObjectName("stato")
        legenda.setWordWrap(True)

        radice = QVBoxLayout(self)
        radice.setContentsMargins(0, 0, 0, 0)
        radice.addLayout(barra)
        radice.addWidget(self.vista, 1)
        radice.addWidget(legenda)

        self._costruisci()
        self._pronta = True

    def showEvent(self, ev):
        super().showEvent(ev)
        # il primo fitInView utile si può fare solo quando la vista ha
        # la sua dimensione reale
        if not self._adattata:
            self._adattata = True
            self.adatta()

    # ---------- costruzione della scena ----------

    def _posizioni_griglia(self):
        return _posizioni_griglia(self.mondo)

    def _posizioni_pixel(self):
        return _posizioni_pixel(self.mondo)

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

    # ---------- aggiornamento dall'esterno (editor) ----------

    def aggiorna(self):
        """Ricostruisce la scena dal mondo conservando zoom e scorrimento.
        Da chiamare solo FUORI dai gestori di eventi della scena (l'editor
        la differisce con QTimer.singleShot). Se c'è un gesto in corso non
        fa nulla: sarà il gesto stesso, al termine, a segnalare la modifica
        che rimette in coda l'aggiornamento."""
        if not self._pronta or self._collegamento_da or self._spostati:
            return
        scelte = [sid for sid, n in self.nodi.items() if n.isSelected()]
        self._pronta = False
        self._scollega_item()
        self.scena.clear()
        self._costruisci()
        self._pronta = True
        for sid in scelte:
            if sid in self.nodi:
                self.nodi[sid].setSelected(True)

    def imposta_mondo(self, mondo):
        """Cambia l'avventura mostrata (nuovo/apri/chiudi nell'editor)."""
        self.mondo = mondo
        self.aggiorna()
        self.adatta()

    def imposta_tema(self, tema_nome):
        self.pal = tema.PALETTE.get(tema_nome, tema.PALETTE["scuro"])
        self.scena.setBackgroundBrush(QColor(self.pal["bg"]))
        self.aggiorna()

    def evidenzia(self, sid):
        """Seleziona (e rende visibile) il riquadro della stanza: chiamata
        dall'editor quando la selezione cambia nelle liste. Se il riquadro è
        già selezionato — ad esempio perché il clic è partito proprio da lì —
        non fa nulla, per non far saltare la vista durante il gesto."""
        nodo = self.nodi.get(sid)
        if nodo is None or nodo.isSelected():
            return
        self.scena.clearSelection()
        nodo.setSelected(True)
        self.vista.ensureVisible(nodo, 40, 40)

    def scollega(self):
        """Da chiamare prima che la finestra che ospita il pannello venga
        distrutta: lascia andare i wrapper Python degli item (un wrapper
        sopravvissuto a un item distrutto manda in crash il GC)."""
        self._pronta = False
        self._scollega_item()

    # ---------- collegamenti ----------

    def _centro(self, sid):
        p = self.nodi[sid].pos()
        return (p.x() + BOX_W / 2, p.y() + BOX_H / 2)

    def _ridisegna_collegamenti(self):
        """Ricostruisce gli item dei collegamenti. Da chiamare solo FUORI
        dai gestori di eventi della scena (creazione/eliminazione di uscite,
        riordino): rimuovere item durante itemChange è pericoloso. Durante
        il trascinamento si usa _traccia_collegamenti, che aggiorna solo
        la geometria degli item esistenti."""
        vecchi = self._collegamenti
        self._collegamenti = []
        for e in vecchi:
            for it in (e["linea"], e["freccia"], e["testo"]):
                if it is not None:
                    self.scena.removeItem(it)
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
            self._collegamenti.append(
                self._nuovo_collegamento(src, dst, direz, cond,
                                         freccia=not doppio))
        self._traccia_collegamenti()

    def _nuovo_collegamento(self, src, dst, direz, cond, freccia):
        """Crea gli item (vuoti) di un collegamento; la geometria la mette
        _traccia."""
        colore = (QColor(self.pal["accento"]) if not cond
                  else QColor(self.pal["muto"]))
        pen = QPen(colore, 2)
        if cond:
            pen.setStyle(Qt.DashLine)
        linea = self.scena.addPath(QPainterPath(), pen)
        linea.setZValue(0)
        fr = None
        if freccia:
            fr = self.scena.addPolygon(QPolygonF(), QPen(colore, 1),
                                       QBrush(colore))
            fr.setZValue(0)
        testo = None
        if direz not in CARD:
            etichetta = {"giu": "giù"}.get(direz, direz)
            testo = self.scena.addSimpleText(
                etichetta, QFont(tema.FONT_TESTO.split(",")[0], 8))
            testo.setBrush(QBrush(QColor(self.pal["muto"])))
            testo.setZValue(3)
        return {"src": src, "dst": dst, "linea": linea, "freccia": fr,
                "testo": testo}

    def _traccia_collegamenti(self):
        for e in self._collegamenti:
            self._traccia(e)

    def _traccia(self, e):
        """Aggiorna la geometria degli item di un collegamento in base alla
        posizione attuale dei nodi (nessun item creato o distrutto: sicuro
        anche dentro itemChange)."""
        cx, cy = self._centro(e["src"])
        tx, ty = self._centro(e["dst"])
        x1, y1 = _bordo(cx, cy, BOX_W / 2, BOX_H / 2, tx, ty)
        x2, y2 = _bordo(tx, ty, BOX_W / 2, BOX_H / 2, cx, cy)

        if not self._attraversa_nodi(x1, y1, x2, y2, {e["src"], e["dst"]}):
            path = QPainterPath(QPointF(x1, y1))
            path.lineTo(QPointF(x2, y2))
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
            ax, ay = ctrlx, ctrly
            lx, ly = ctrlx, ctrly
        e["linea"].setPath(path)
        if e["freccia"] is not None:
            e["freccia"].setPolygon(_punta(ax, ay, x2, y2))
        if e["testo"] is not None:
            e["testo"].setPos(lx - e["testo"].boundingRect().width() / 2,
                              ly - 8)

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

    # ---------- trascinamento e selezione ----------

    def _nodo_spostato(self, sid):
        """Chiamato dal nodo a ogni variazione di posizione: registra la
        posizione nei metadati dell'editor e fa seguire i collegamenti."""
        if not self._pronta:
            return
        p = self.nodi[sid].pos()
        (self.mondo.meta.setdefault("editor", {})
             .setdefault("mappa", {}))[sid] = [round(p.x()), round(p.y())]
        self._spostati.add(sid)
        self._traccia_collegamenti()

    def _fine_trascinamento(self, sid):
        """Al rilascio del mouse: se il nodo si è davvero mosso, una sola
        segnalazione di modifica all'editor."""
        if sid not in self._spostati:
            return
        self._spostati.discard(sid)
        if self.su_modifica:
            self.su_modifica()

    def _nodo_scelto(self, sid):
        """Clic su un riquadro: avvisa chi ospita il pannello (l'editor
        seleziona la stanza nel pannello di dettaglio)."""
        if self._su_selezione:
            self._su_selezione(sid)

    def _apri_stanza(self, sid):
        """Doppio clic su un riquadro: salta alla stanza nell'editor."""
        if self._vai_a:
            self._vai_a("Stanze", sid)

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
            # i dialoghi si aprono a menu ormai chiuso (grab Wayland)
            QTimer.singleShot(0, lambda: self._chiedi_stanza(punto_scena))

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
        # lascia andare i wrapper Python PRIMA che clear() distrugga il C++:
        # un wrapper sopravvissuto a un item distrutto manda in crash il GC.
        self._scollega_item()
        self.scena.clear()
        self._costruisci()
        self._pronta = True
        self.adatta()

    def _scollega_item(self):
        """Azzera ogni riferimento Python agli item della scena (e i loro
        riferimenti a questo pannello)."""
        for n in self.nodi.values():
            n._pannello = None
        self.nodi = {}
        self._collegamenti = []
        self._linea_tmp = None
        self._spostati = set()
        self._collegamento_da = None
        self._collegamento_press = None

    # ---------- comandi ----------

    def adatta(self):
        r = self.scena.itemsBoundingRect().adjusted(-40, -40, 40, 40)
        self.scena.setSceneRect(r)
        self.vista.fitInView(r, Qt.KeepAspectRatio)

    def _zoom(self, f):
        self.vista.scale(f, f)

    def esporta_png(self):
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


def _punta(x1, y1, x2, y2):
    """La punta di freccia (triangolo) in (x2,y2), orientata da (x1,y1)."""
    ang = math.atan2(y2 - y1, x2 - x1)
    s = 10
    return QPolygonF([
        QPointF(x2, y2),
        QPointF(x2 - s * math.cos(ang - 0.4), y2 - s * math.sin(ang - 0.4)),
        QPointF(x2 - s * math.cos(ang + 0.4), y2 - s * math.sin(ang + 0.4)),
    ])


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
