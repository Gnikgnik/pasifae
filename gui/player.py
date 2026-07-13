# SPDX-License-Identifier: GPL-3.0-or-later
"""Player grafico (PySide6/Qt) per le avventure testuali.

È solo una *vista* sul motore: chiama Motore.esegui(stringa) -> stringa e
disegna il risultato. Look neutro, comparsa morbida del testo, storico dei
comandi e salvataggio/caricamento partita.

Uso:
    python gui/player.py [avventure/faro.json]
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
if str(RADICE) not in sys.path:
    sys.path.insert(0, str(RADICE))

# Da sorgente i dati stanno nella radice del progetto; impacchettato con
# PyInstaller stanno in una cartella temporanea (sys._MEIPASS).
RISORSE = Path(getattr(sys, "_MEIPASS", RADICE))


def _dir_salvataggi() -> str:
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else RADICE
    d = base / "salvataggi"
    d.mkdir(parents=True, exist_ok=True)
    return str(d)


# «*.sav» è l'estensione dei player da terminale; «Tutti i file» recupera i
# salvataggi nati senza estensione con le versioni precedenti.
FILTRO_SALVATAGGI = "Salvataggi (*.save *.sav *.json);;Tutti i file (*)"


def _con_estensione(percorso: str) -> str:
    """Aggiunge «.save» se l'utente non ha scelto un'estensione: senza, il
    dialogo di caricamento (che filtra per estensione) non mostrerebbe il file."""
    return percorso if Path(percorso).suffix else percorso + ".save"

from advcore import carica_mondo, Motore, salva_partita, carica_partita  # noqa: E402
from gui import tema  # noqa: E402
from gui.immagine import PannelloImmagine  # noqa: E402
from gui.mappa_player import MiniMappa  # noqa: E402

from PySide6.QtCore import QSettings, Qt, QTimer, Signal  # noqa: E402
from PySide6.QtGui import QAction, QActionGroup, QFont, QKeySequence  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QSplitter, QTextEdit, QVBoxLayout, QWidget,
)


def _impostazioni() -> QSettings:
    """Preferenze del player, ricordate tra le sessioni."""
    return QSettings("Pasifae", "Play")


# colore accento dichiarabile dall'avventura (meta["colore"]): solo #rrggbb,
# per non lasciar entrare stringhe arbitrarie nel foglio di stile
_RE_COLORE = re.compile(r"^#[0-9a-fA-F]{6}$")
_RE_TITOLO_GIOCO = re.compile(r"^== (.+) ==$")


class InputComando(QLineEdit):
    """Riga di comando con storico navigabile (frecce su/giù)."""

    fuoco = Signal(bool)     # entra/esce dal fuoco (per accendere la cornice)

    def __init__(self):
        super().__init__()
        self.storico: list[str] = []
        self._i = 0

    def ricorda(self, testo: str):
        if testo and (not self.storico or self.storico[-1] != testo):
            self.storico.append(testo)
        self._i = len(self.storico)

    def focusInEvent(self, ev):
        super().focusInEvent(ev)
        self.fuoco.emit(True)

    def focusOutEvent(self, ev):
        super().focusOutEvent(ev)
        self.fuoco.emit(False)

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Up and self.storico:
            self._i = max(0, self._i - 1)
            self.setText(self.storico[self._i])
            return
        if ev.key() == Qt.Key_Down and self.storico:
            self._i = min(len(self.storico), self._i + 1)
            self.setText(self.storico[self._i] if self._i < len(self.storico) else "")
            return
        super().keyPressEvent(ev)


class VistaTrascrizione(QTextEdit):
    """Trascrizione con colonna di lettura limitata: su finestre larghe il
    testo non si stende da bordo a bordo ma resta in una colonna centrata di
    larghezza comoda (~75 caratteri). Ctrl+rotella regola la dimensione."""

    EM_COLONNA = 42          # larghezza massima della colonna, in em
    zoom = Signal(int)       # +1/-1 da Ctrl+rotella

    def __init__(self):
        super().__init__()
        self._em = 16

    def imposta_em(self, em: int):
        self._em = em
        self._adatta_margini()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._adatta_margini()

    def wheelEvent(self, ev):
        if ev.modifiers() & Qt.ControlModifier:
            self.zoom.emit(1 if ev.angleDelta().y() > 0 else -1)
            ev.accept()
            return
        super().wheelEvent(ev)

    def _adatta_margini(self):
        margine = max(0, (self.width() - self._em * self.EM_COLONNA) // 2)
        self.setViewportMargins(margine, 0, margine, 0)


class Player(QMainWindow):
    # sotto questa larghezza la mini-mappa si nasconde: la colonna di testo
    # ha la priorità (com'è già per l'illustrazione, che collassa da sola
    # quando la stanza non ne ha una — qui però è una questione di spazio,
    # non di contenuto, quindi va decisa a ogni resize).
    LARGHEZZA_MIN_MAPPA = 900

    def __init__(self, percorso: str | None = None):
        super().__init__()
        from gui import risorse
        self.setWindowIcon(risorse.icona_app())
        self.mondo = None
        self.motore = None
        self.percorso = None
        self.tema = "scuro"
        self.animazione = True
        self.accento = None            # colore accento dell'avventura (meta)
        self._titoli_stanze: set[str] = set()
        imp = _impostazioni()
        try:
            self.dim_testo = int(imp.value("dim_testo", 16))
        except (TypeError, ValueError):
            self.dim_testo = 16
        self.dim_testo = max(10, min(28, self.dim_testo))
        try:
            self.grazie = bool(int(imp.value("grazie", 0)))
        except (TypeError, ValueError):
            self.grazie = False
        try:
            self.illustrazioni = bool(int(imp.value("illustrazioni", 1)))
        except (TypeError, ValueError):
            self.illustrazioni = True
        try:
            self.mostra_mappa = bool(int(imp.value("mappa", 1)))
        except (TypeError, ValueError):
            self.mostra_mappa = True
        self._voci: list[tuple[str, str]] = []
        # stato dell'animazione "telescrivente"
        self._anim = QTimer(self)
        self._anim.setInterval(22)
        self._anim.timeout.connect(self._anima_passo)
        self._anim_cuts: list[int] = []
        self._anim_step = 0

        self.setWindowTitle("Pasifae Play")
        self.resize(1120, 700)
        self._costruisci_menu()

        centrale = QWidget()
        radice = QVBoxLayout(centrale)
        radice.setContentsMargins(0, 0, 0, 0)
        radice.setSpacing(0)

        self.titolo = QLabel(); self.titolo.setObjectName("titolo")
        self.stato = QLabel(); self.stato.setObjectName("stato")
        self.stato.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        testa = QFrame(); testa.setObjectName("barra")
        h = QHBoxLayout(testa)
        h.setContentsMargins(24, 14, 24, 14)
        h.addWidget(self.titolo); h.addStretch(1); h.addWidget(self.stato)
        radice.addWidget(testa)

        # illustrazione a colonna, a fianco della trascrizione: molto più
        # grande della vecchia striscia, con larghezza regolabile e ricordata
        self.immagine = PannelloImmagine(riempi=True)
        self.immagine.imposta_attiva(self.illustrazioni)

        # mini-mappa a destra: si popola via via che si visitano le stanze
        self.mappa = MiniMappa(self.tema)
        self.mappa.setVisible(self.mostra_mappa)

        self.vista = VistaTrascrizione(); self.vista.setObjectName("vista")
        self.vista.setReadOnly(True); self.vista.setFrameStyle(QFrame.NoFrame)
        self.vista.imposta_em(self.dim_testo)
        self.vista.zoom.connect(self._cambia_dim)
        self._in_fondo = True
        barra = self.vista.verticalScrollBar()
        barra.valueChanged.connect(self._registra_se_in_fondo)
        barra.rangeChanged.connect(self._segui_fondo)

        riga = QFrame(); riga.setObjectName("barra_giu")
        hr = QHBoxLayout(riga)
        hr.setContentsMargins(24, 12, 24, 18); hr.setSpacing(12)
        self.cornice_input = QFrame()
        self.cornice_input.setObjectName("cornice_input")
        self.cornice_input.setProperty("fuoco", False)
        hc = QHBoxLayout(self.cornice_input)
        hc.setContentsMargins(14, 7, 14, 7); hc.setSpacing(10)
        prompt = QLabel("›"); prompt.setObjectName("prompt")
        self.input = InputComando(); self.input.setObjectName("input")
        self.input.setPlaceholderText("scrivi un comando e premi Invio…  (aiuto)")
        self.input.returnPressed.connect(self._invia)
        self.input.fuoco.connect(self._accendi_cornice)
        hc.addWidget(prompt); hc.addWidget(self.input, 1)
        hr.addWidget(self.cornice_input)

        colonna = QWidget()
        vdx = QVBoxLayout(colonna)
        vdx.setContentsMargins(0, 0, 0, 0); vdx.setSpacing(0)
        vdx.addWidget(self.vista, 1)
        vdx.addWidget(riga)

        self.spartizione = QSplitter(Qt.Horizontal)
        self.spartizione.addWidget(self.immagine)
        self.spartizione.addWidget(colonna)
        self.spartizione.addWidget(self.mappa)
        self.spartizione.setCollapsible(1, False)   # il testo non sparisce mai
        self.spartizione.setStretchFactor(0, 2)
        self.spartizione.setStretchFactor(1, 3)
        self.spartizione.setStretchFactor(2, 2)
        try:
            col = int(imp.value("colonna_immagine", 0))
        except (TypeError, ValueError):
            col = 0
        try:
            col_mappa = int(imp.value("colonna_mappa", 0))
        except (TypeError, ValueError):
            col_mappa = 0
        largo = self.width()
        col = col if 0 < col < largo else int(largo * 0.3)
        col_mappa = col_mappa if 0 < col_mappa < largo else int(largo * 0.3)
        self.spartizione.setSizes([col, largo - col - col_mappa, col_mappa])
        self.spartizione.splitterMoved.connect(self._ricorda_colonna)
        radice.addWidget(self.spartizione, 1)

        self.setCentralWidget(centrale)
        self._applica_tema()
        self._aggiorna_visibilita_mappa()

        if percorso:
            self._apri_avventura(percorso)
        else:
            self._modo_blank()
        self.input.setFocus()

    # ---------- menu ----------

    def _costruisci_menu(self):
        barra = self.menuBar()

        mf = barra.addMenu("File")
        a_apri = QAction("Apri avventura…", self); a_apri.setShortcut("Ctrl+O")
        a_apri.triggered.connect(self._apri); mf.addAction(a_apri)
        mf.addSeparator()
        a_esci = QAction("Esci", self); a_esci.triggered.connect(self.close)
        mf.addAction(a_esci)

        m = barra.addMenu("Partita")
        self._azioni_partita = []
        for testo, slot, scorc in (("Salva partita…", self._salva, "Ctrl+S"),
                                   ("Carica partita…", self._carica, "Ctrl+L")):
            a = QAction(testo, self); a.setShortcut(scorc)
            a.triggered.connect(slot); m.addAction(a)
            self._azioni_partita.append(a)
        m.addSeparator()
        a_riavvia = QAction("Riavvia", self)
        a_riavvia.triggered.connect(self._riavvia); m.addAction(a_riavvia)
        self._azioni_partita.append(a_riavvia)

        v = barra.addMenu("Visualizza")
        gruppo = QActionGroup(self)
        for etichetta, chiave in (("Tema scuro", "scuro"), ("Tema chiaro", "chiaro")):
            a = QAction(etichetta, self, checkable=True)
            a.setChecked(chiave == self.tema)
            a.triggered.connect(lambda _=False, c=chiave: self._cambia_tema(c))
            gruppo.addAction(a); v.addAction(a)
        v.addSeparator()
        a_anim = QAction("Testo animato", self, checkable=True)
        a_anim.setChecked(self.animazione)
        a_anim.triggered.connect(lambda on: setattr(self, "animazione", on))
        v.addAction(a_anim)
        a_grazie = QAction("Carattere con grazie", self, checkable=True)
        a_grazie.setChecked(self.grazie)
        a_grazie.triggered.connect(self._imposta_grazie)
        v.addAction(a_grazie)
        a_illu = QAction("Illustrazioni", self, checkable=True)
        a_illu.setChecked(self.illustrazioni)
        a_illu.triggered.connect(self._imposta_illustrazioni)
        v.addAction(a_illu)
        a_mappa = QAction("Mappa", self, checkable=True)
        a_mappa.setChecked(self.mostra_mappa)
        a_mappa.triggered.connect(self._imposta_mappa)
        v.addAction(a_mappa)
        v.addSeparator()
        a_piu = QAction("Testo più grande", self)
        a_piu.setShortcut(QKeySequence.ZoomIn)
        a_piu.triggered.connect(lambda: self._cambia_dim(+1))
        v.addAction(a_piu)
        a_meno = QAction("Testo più piccolo", self)
        a_meno.setShortcut(QKeySequence.ZoomOut)
        a_meno.triggered.connect(lambda: self._cambia_dim(-1))
        v.addAction(a_meno)
        a_norm = QAction("Dimensione normale", self)
        a_norm.setShortcut("Ctrl+0")
        a_norm.triggered.connect(self._dim_normale)
        v.addAction(a_norm)

        a = barra.addMenu("Aiuto")
        a_info = QAction("Informazioni", self)
        a_info.triggered.connect(self._informazioni); a.addAction(a_info)

    # ---------- apertura avventura ----------

    def _apri(self):
        base = str(RISORSE / "avventure")
        f, _ = QFileDialog.getOpenFileName(
            self, "Apri avventura", base, "Avventure (*.json)")
        if not f:
            return
        try:
            self._apri_avventura(f)
        except Exception as e:                       # noqa: BLE001
            QMessageBox.warning(self, "Apri avventura",
                                f"Impossibile aprire l'avventura:\n{e}")

    def _apri_avventura(self, percorso: str):
        mondo = carica_mondo(percorso)               # se fallisce, _apri lo segnala
        self.mondo = mondo
        self.motore = Motore(mondo)
        self.mappa.imposta_mondo(mondo)
        self.percorso = percorso
        self._titoli_stanze = {s.nome.upper() for s in mondo.stanze.values()}
        colore = str(mondo.meta.get("colore") or "")
        self.accento = colore if _RE_COLORE.match(colore) else None
        self._applica_tema()
        self._anim_finisci()
        self._voci.clear()
        titolo = mondo.meta.get("titolo") or "Avventura"
        self.setWindowTitle(f"{titolo} — Pasifae")
        self._abilita_gioco(True)
        self.input.setPlaceholderText("scrivi un comando e premi Invio…  (aiuto)")
        self._mostra(self.motore.avvia(), "risposta")
        self._aggiorna_stato()
        self.input.setFocus()

    def _modo_blank(self):
        self.mondo = None
        self.motore = None
        self.percorso = None
        self._titoli_stanze = set()
        self.accento = None
        self._applica_tema()
        self._anim_finisci()
        self._voci = [("risposta",
                       "Nessuna avventura aperta.\n\n"
                       "Apri un'avventura da  File ▸ Apri avventura…  (Ctrl+O) "
                       "per cominciare a giocare.")]
        self.setWindowTitle("Pasifae Play")
        self.titolo.setText("Pasifae")
        self.stato.setText("")
        self.immagine.mostra_file(None)
        self.mappa.imposta_mondo(None)
        self._abilita_gioco(False)
        self._ridisegna()

    def _abilita_gioco(self, attivo: bool):
        self.input.setEnabled(attivo)
        for a in getattr(self, "_azioni_partita", []):
            a.setEnabled(attivo)
        if not attivo:
            self.input.setPlaceholderText(
                "apri un'avventura da  File ▸ Apri avventura…")

    def _informazioni(self):
        from gui import risorse
        risorse.mostra_informazioni(self, "Pasifae Play")

    # ---------- gioco ----------

    def _invia(self):
        if self.motore is None:
            return                       # nessuna avventura aperta
        if self._anim.isActive():
            self._anim_finisci()        # un Invio durante l'animazione la completa
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
            self.input.setPlaceholderText("— fine —   (Partita ▸ Riavvia)")

    def _riavvia(self):
        self._anim_finisci()
        self._voci.clear()
        self._mostra(self.motore.riavvia(), "risposta")
        self._aggiorna_stato()
        self.input.setPlaceholderText("scrivi un comando e premi Invio…  (aiuto)")
        self.input.setFocus()

    def _salva(self):
        cartella = _dir_salvataggi()
        f, _ = QFileDialog.getSaveFileName(self, "Salva partita", cartella,
                                           FILTRO_SALVATAGGI)
        if f:
            f = _con_estensione(f)
            salva_partita(self.mondo, f)
            self.statusBar().showMessage(f"Partita salvata in {f}", 4000)

    def _carica(self):
        cartella = _dir_salvataggi()
        f, _ = QFileDialog.getOpenFileName(self, "Carica partita", cartella,
                                           FILTRO_SALVATAGGI)
        if not f:
            return
        carica_partita(self.mondo, f)
        self._anim_finisci()
        self._voci.clear()
        self._mostra("(partita caricata)\n\n" + self.motore._descrivi_stanza(), "risposta")
        self._aggiorna_stato()
        self.input.setFocus()

    # ---------- vista e animazione ----------

    def _mostra(self, testo: str, genere: str):
        self._voci.append((genere, testo))
        if genere == "risposta" and self.animazione and testo.strip():
            parti = re.findall(r"\S+\s*", testo)
            self._anim_cuts, acc = [], 0
            for p in parti:
                acc += len(p); self._anim_cuts.append(acc)
            self._anim_step = 0
            self._disegna_statico()
            self._anim.start()
        else:
            self._ridisegna()

    def _anima_passo(self):
        self._anim_step += 1
        if self._anim_step >= len(self._anim_cuts):
            self._anim_finisci()
        else:
            self._aggiorna_ultima_voce()

    def _anim_finisci(self):
        self._anim.stop()
        self._anim_cuts = []
        self._anim_step = 0
        self._ridisegna()

    def _blocco_html(self, genere: str, testo: str, p: dict) -> str:
        dim = self.dim_testo
        font = tema.FONT_TESTO_GRAZIE if self.grazie else tema.FONT_TESTO
        stile = f"font-family:{font}; font-size:{dim}px; line-height:165%; "
        if genere == "comando":
            corpo = html.escape(testo).replace("\n", "<br>")
            return (f'<div style="{stile}color:{p["muto"]}; '
                    f'margin:2px 0 14px 0;"><i>{corpo}</i></div>')
        corpo = "<br>".join(self._riga_html(r, p) for r in testo.split("\n"))
        return (f'<div style="{stile}color:{p["testo"]}; '
                f'margin:0 0 16px 0;">{corpo}</div>')

    def _riga_html(self, riga: str, p: dict) -> str:
        """Gerarchia tipografica della trascrizione, ricavata dalle
        convenzioni testuali del motore: «== titolo ==» per il gioco, il
        nome della stanza in maiuscolo come prima riga della descrizione,
        il prefisso fisso «Uscite:» per le direzioni."""
        accento = self.accento or p["accento"]
        m = _RE_TITOLO_GIOCO.match(riga)
        if m:
            return (f'<span style="font-size:{self.dim_testo + 5}px; '
                    f'font-weight:700; letter-spacing:1px; color:{accento};">'
                    f'{html.escape(m.group(1))}</span>')
        if riga in self._titoli_stanze:
            return (f'<span style="font-size:{self.dim_testo + 2}px; '
                    f'font-weight:700; letter-spacing:1px; color:{accento};">'
                    f'{html.escape(riga)}</span>')
        if riga.startswith("Uscite:"):
            return (f'<span style="color:{p["muto"]};">'
                    f'{html.escape(riga)}</span>')
        return html.escape(riga)

    def _scorri_in_fondo(self):
        barra = self.vista.verticalScrollBar()
        barra.setValue(barra.maximum())

    def _registra_se_in_fondo(self, valore: int):
        self._in_fondo = valore >= self.vista.verticalScrollBar().maximum()

    def _segui_fondo(self, _minimo: int, massimo: int):
        """Dopo setHtml()/insertHtml() la corsa della scrollbar è una stima:
        il layout vero arriva dopo e la allunga. Se la vista era in fondo ce
        la riporta, altrimenti l'ultima riga resta fuori dallo schermo."""
        if self._in_fondo:
            self.vista.verticalScrollBar().setValue(massimo)

    def _ridisegna(self):
        """Ridisegna l'intera cronologia. Costa proporzionalmente alla sua
        lunghezza: usato solo per eventi rari (nuovo messaggio non animato,
        cambio tema, fine animazione), mai per-fotogramma."""
        p = tema.PALETTE[self.tema]
        ultimo = len(self._voci) - 1
        blocchi = []
        for i, (genere, testo) in enumerate(self._voci):
            if (i == ultimo and self._anim_cuts
                    and self._anim_step < len(self._anim_cuts)):
                testo = testo[:self._anim_cuts[self._anim_step]]
            blocchi.append(self._blocco_html(genere, testo, p))
        self.vista.setHtml("".join(blocchi))
        self._scorri_in_fondo()

    def _disegna_statico(self):
        """Ridisegna tutta la cronologia tranne l'ultima voce (quella che sta
        per animarsi) e memorizza il punto in cui inizia, cosicché i singoli
        fotogrammi dell'animazione tocchino solo quella voce e non l'intero
        documento (altrimenti il ridisegno rallenta con la partita e sotto
        Linux produce un fastidioso farfallio)."""
        p = tema.PALETTE[self.tema]
        blocchi = [self._blocco_html(g, t, p) for g, t in self._voci[:-1]]
        self.vista.setHtml("".join(blocchi))
        cursore = self.vista.textCursor()
        cursore.movePosition(cursore.MoveOperation.End)
        self._anim_anchor = cursore.position()
        self._aggiorna_ultima_voce()

    def _aggiorna_ultima_voce(self):
        p = tema.PALETTE[self.tema]
        genere, testo = self._voci[-1]
        if self._anim_cuts and self._anim_step < len(self._anim_cuts):
            testo = testo[:self._anim_cuts[self._anim_step]]
        cursore = self.vista.textCursor()
        cursore.setPosition(self._anim_anchor)
        cursore.movePosition(cursore.MoveOperation.End, cursore.MoveMode.KeepAnchor)
        cursore.removeSelectedText()
        if self._anim_anchor > 0:
            # senza un nuovo blocco l'insertHtml() si fonde col precedente
            # e la voce animata appare attaccata alla riga del comando
            cursore.insertBlock()
        cursore.insertHtml(self._blocco_html(genere, testo, p))
        self._scorri_in_fondo()

    def _cambia_dim(self, delta: int):
        nuova = max(10, min(28, self.dim_testo + delta))
        if nuova == self.dim_testo:
            return
        self.dim_testo = nuova
        _impostazioni().setValue("dim_testo", nuova)
        self.vista.imposta_em(nuova)
        self._anim_finisci()        # ridisegna tutto alla nuova dimensione

    def _dim_normale(self):
        self._cambia_dim(16 - self.dim_testo)

    def _imposta_grazie(self, attivo: bool):
        self.grazie = bool(attivo)
        _impostazioni().setValue("grazie", int(self.grazie))
        self._anim_finisci()        # ridisegna col nuovo carattere

    def _imposta_illustrazioni(self, attive: bool):
        self.illustrazioni = bool(attive)
        _impostazioni().setValue("illustrazioni", int(self.illustrazioni))
        self.immagine.imposta_attiva(self.illustrazioni)

    def _imposta_mappa(self, attiva: bool):
        self.mostra_mappa = bool(attiva)
        _impostazioni().setValue("mappa", int(self.mostra_mappa))
        self._aggiorna_visibilita_mappa()

    def _aggiorna_visibilita_mappa(self):
        """Visibile solo se l'utente l'ha attivata E la finestra è abbastanza
        larga: sotto LARGHEZZA_MIN_MAPPA la colonna di lettura ha la
        priorità (vedi resizeEvent)."""
        if not hasattr(self, "mappa"):
            return
        self.mappa.setVisible(
            self.mostra_mappa and self.width() >= self.LARGHEZZA_MIN_MAPPA)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._aggiorna_visibilita_mappa()

    def _ricorda_colonna(self, *_):
        """La larghezza scelta per le colonne di illustrazione e mappa si
        conserva tra le sessioni."""
        larghezze = self.spartizione.sizes()
        _impostazioni().setValue("colonna_immagine", larghezze[0])
        _impostazioni().setValue("colonna_mappa", larghezze[2])

    def _accendi_cornice(self, acceso: bool):
        self.cornice_input.setProperty("fuoco", acceso)
        stile = self.cornice_input.style()
        stile.unpolish(self.cornice_input)
        stile.polish(self.cornice_input)

    def _aggiorna_stato(self):
        if self.mondo is None:
            self.titolo.setText("Pasifae"); self.stato.setText("")
            self.immagine.mostra_file(None)
            self.mappa.imposta_mondo(None)
            return
        self.titolo.setText(self.mondo.meta.get("titolo", "Avventura"))
        stanza = self.mondo.stanze.get(self.mondo.stanza_corrente)
        luogo = f"{stanza.nome}    ·    " if stanza else ""
        self.stato.setText(
            f"{luogo}punteggio {self.mondo.punteggio}"
            f"    ·    turni {self.mondo.mosse}")
        self._aggiorna_immagine(stanza)
        self.mappa.aggiorna()

    def _aggiorna_immagine(self, stanza):
        """Illustrazione della stanza corrente: il nome file (relativo al
        JSON dell'avventura, e quindi nei giochi compilati alla cartella
        delle risorse impacchettate) è quello sostituito a runtime
        dall'effetto di regola cambia_immagine, se presente, altrimenti
        l'illustrazione di default dichiarata dall'autore."""
        nome = (stanza.immagine_attuale or stanza.immagine) if stanza else ""
        if not nome or not self.percorso:
            self.immagine.mostra_file(None)
            return
        self.immagine.mostra_file(str(Path(self.percorso).parent / nome))

    # ---------- tema ----------

    def _cambia_tema(self, nome: str):
        self.tema = nome
        self._applica_tema()
        self.mappa.imposta_tema(nome)
        self._ridisegna()

    def _applica_tema(self):
        qss = tema.qss(self.tema)
        if self.accento:
            qss += (f'\n#prompt {{ color: {self.accento}; }}'
                    f'\n#titolo {{ color: {self.accento}; }}'
                    f'\n#cornice_input[fuoco="true"] '
                    f'{{ border: 1px solid {self.accento}; }}')
        self.setStyleSheet(qss)


def _avventura_inclusa() -> str | None:
    """Se l'eseguibile è stato compilato con un'avventura allegata
    (Pasifae Editor ▸ Compila gioco), restituisce il suo percorso."""
    p = RISORSE / "avventura.json"
    return str(p) if p.exists() else None


def main():
    percorso = sys.argv[1] if len(sys.argv) > 1 else _avventura_inclusa()
    app = QApplication(sys.argv)
    app.setApplicationName("Pasifae")
    app.setApplicationDisplayName("Pasifae Play")
    from gui import risorse
    app.setWindowIcon(risorse.icona_app())
    app.setFont(QFont("Segoe UI", 10))
    Player(percorso).show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
