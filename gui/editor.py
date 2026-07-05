# SPDX-License-Identifier: GPL-3.0-or-later
"""Editor grafico (PySide6/Qt) per le avventure testuali — primo incremento.

Naviga l'avventura per categorie e ne modifica stanze e metadati, salvando sul
file .json. Le altre categorie sono per ora in sola lettura (modifica in arrivo).
Condivide il tema con il player.

Uso:
    python gui/editor.py [avventure/faro.json]
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path
import copy

RADICE = Path(__file__).resolve().parent.parent
if str(RADICE) not in sys.path:
    sys.path.insert(0, str(RADICE))

# Da sorgente i dati stanno nella radice; impacchettato stanno in sys._MEIPASS.
RISORSE = Path(getattr(sys, "_MEIPASS", RADICE))


def _dir_default() -> str:
    if getattr(sys, "frozen", False):
        return str(Path(sys.executable).parent)
    return str(RADICE / "avventure")


def copia_immagine_accanto(sorgente: str, percorso_json: str | None) -> str:
    """Copia l'illustrazione scelta accanto al JSON dell'avventura e
    restituisce il nome file da scrivere nel campo `immagine` della stanza.
    Tenere le immagini accanto al JSON le rende portabili: l'avventura si
    sposta copiando la sua cartella, e la compilazione le impacchetta.
    Se il file è già nella cartella giusta non copia nulla."""
    if not percorso_json:
        raise ValueError("Salva prima l'avventura: l'immagine va copiata "
                         "accanto al suo file JSON.")
    src = Path(sorgente)
    dest = Path(percorso_json).resolve().parent / src.name
    if src.resolve() != dest:
        shutil.copy2(src, dest)
    return src.name

from advcore import carica_mondo, salva_mondo, Oggetto, Verbo, Stanza, Regola  # noqa: E402
from advcore.model import Mondo  # noqa: E402
from advcore.validazione import valida  # noqa: E402
from gui import tema  # noqa: E402
from gui import regole as R  # noqa: E402
from gui.editor_riassunti import riassunto  # noqa: E402

from PySide6.QtCore import Qt, QTimer, QThread, Signal  # noqa: E402
from PySide6.QtGui import QAction, QActionGroup, QFont, QPixmap  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication, QCheckBox, QComboBox, QCompleter, QDialog, QDialogButtonBox,
    QDockWidget, QFileDialog, QFormLayout, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox,
    QPlainTextEdit, QProgressDialog, QPushButton, QScrollArea, QSpinBox,
    QSplitter, QVBoxLayout, QWidget,
)

CATEGORIE = ["Stanze", "Oggetti", "Verbi", "Regole", "Flag iniziali", "Metadati"]

SUGG_TESTO = ("Testo dinamico:\n"
              "• {flag} inserisce il valore di un flag (o {punteggio}, {mosse}, {stanza}).\n"
              "• [flag: testo] mostra il testo solo se il flag è vero;\n"
              "  [flag: se vero | se falso] sceglie tra due varianti;\n"
              "  [prima_volta: ...] vale solo alla prima visita della stanza.")


def combo_cerca(voci, valore=None, ordina=True):
    """QComboBox editabile con ricerca incrementale «contiene» (non sensibile alle
    maiuscole): il menu mostra l'intera lista (ordinata), ma digitando si filtra.
    Regge senza problemi liste molto lunghe di oggetti, stanze, ecc."""
    voci = sorted(voci, key=str.lower) if ordina else list(voci)
    cb = QComboBox()
    cb.setEditable(True)
    cb.setInsertPolicy(QComboBox.NoInsert)
    cb.addItems(voci)
    comp = QCompleter(voci, cb)
    comp.setCaseSensitivity(Qt.CaseInsensitive)
    comp.setFilterMode(Qt.MatchContains)
    comp.setCompletionMode(QCompleter.PopupCompletion)
    cb.setCompleter(comp)
    if valore:
        if cb.findText(valore) < 0:
            cb.addItem(valore)
        cb.setCurrentText(valore)
    elif voci:
        cb.setCurrentIndex(0)
    return cb


class DialogoVoce(QDialog):
    """Sceglie il tipo di condizione/effetto e ne compila i parametri."""

    def __init__(self, parent, mondo, tipi, tema_nome, voce=None, consenti_non=False):
        super().__init__(parent)
        self.opz = R.opzioni(mondo)
        self.setWindowTitle("Modifica voce" if voce else "Aggiungi voce")
        self.setStyleSheet(tema.qss(tema_nome))
        self.setMinimumWidth(440)
        v = QVBoxLayout(self)
        self.cb_tipo = QComboBox()
        for label, key in tipi:
            self.cb_tipo.addItem(label, key)
        self.cb_tipo.currentIndexChanged.connect(self._rifai_campi)
        v.addWidget(self.cb_tipo)
        self.area = QWidget()
        self.form = QFormLayout(self.area)
        v.addWidget(self.area)
        self._chk_non = None
        if consenti_non:
            self._chk_non = QCheckBox("la condizione NON deve valere  (NON)")
            v.addWidget(self._chk_non)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)
        self._campi = {}
        self._rifai_campi()
        if voce:
            interno = voce
            if isinstance(voce, dict) and "non" in voce and self._chk_non is not None:
                self._chk_non.setChecked(True)
                interno = voce["non"]
            tipo, valori = R.da_dict(interno)
            idx = self.cb_tipo.findData(tipo)
            if idx >= 0:
                self.cb_tipo.setCurrentIndex(idx)   # rigenera i campi per il tipo
                self._imposta_valori(valori)

    def _imposta_valori(self, valori):
        for pid, val in valori.items():
            if pid not in self._campi:
                continue
            w, kind = self._campi[pid]
            if kind == "intero":
                try:
                    w.setValue(int(val))
                except (TypeError, ValueError):
                    pass
            elif kind == "valore":
                w.setCurrentText("vero" if val is True
                                 else "falso" if val is False else str(val))
            elif isinstance(w, QComboBox):
                w.setCurrentText("" if val is None else str(val))
            elif isinstance(w, QPlainTextEdit):
                w.setPlainText("" if val is None else str(val))
            else:
                w.setText("" if val is None else str(val))

    def _rifai_campi(self):
        while self.form.rowCount():
            self.form.removeRow(0)
        self._campi = {}
        key = self.cb_tipo.currentData()
        for pid, etichetta, kind in R.CAMPI[key]:
            w = self._widget(kind)
            self._campi[pid] = (w, kind)
            self.form.addRow(etichetta, w)

    def _widget(self, kind):
        if kind == "valore":
            cb = QComboBox(); cb.setEditable(True); cb.addItems(["vero", "falso"])
            return cb
        if kind in ("flag", "luogo", "timer", "oggetto", "stanza", "png",
                    "verbo", "contenitore"):
            return combo_cerca(self.opz[kind])
        if kind == "intero":
            s = QSpinBox(); s.setRange(-9999, 9999); return s
        if kind == "testo_lungo":
            t = QPlainTextEdit(); t.setMinimumHeight(70)
            t.setToolTip(SUGG_TESTO); return t
        return QLineEdit()

    def valore(self) -> dict:
        key = self.cb_tipo.currentData()
        vals = {}
        for pid, (w, kind) in self._campi.items():
            if kind == "intero":
                vals[pid] = w.value()
            elif kind == "valore":
                vals[pid] = R.val_da_testo(w.currentText())
            elif isinstance(w, QComboBox):
                vals[pid] = w.currentText().strip()
            elif isinstance(w, QPlainTextEdit):
                vals[pid] = w.toPlainText()
            else:
                vals[pid] = w.text().strip()
        val = R.ASSEMBLA[key](vals)
        if self._chk_non is not None and self._chk_non.isChecked():
            return {"non": val}
        return val


def lista_voci_widget(owner, mondo, tema_nome, titolo, lista, tipi, riass, on_change=None):
    """Widget riutilizzabile: una lista di condizioni/effetti con + aggiungi /
    rimuovi. Opera direttamente sulla `lista` passata."""
    box = QWidget()
    v = QVBoxLayout(box)
    v.setContentsMargins(0, 10, 0, 0)
    if titolo:
        lab = QLabel(titolo)
        lab.setObjectName("sezione")
        v.addWidget(lab)
    lw = QListWidget()
    lw.setMaximumHeight(120)
    for voce in lista:
        lw.addItem(riass(voce))
    v.addWidget(lw)
    riga = QHBoxLayout()
    b_add = QPushButton("+ aggiungi")
    b_mod = QPushButton("modifica")
    b_del = QPushButton("rimuovi")
    riga.addWidget(b_add)
    riga.addWidget(b_mod)
    riga.addWidget(b_del)
    riga.addStretch(1)
    v.addLayout(riga)

    negabile = (tipi is R.TIPI_CONDIZIONE)

    def aggiungi():
        d = DialogoVoce(owner, mondo, tipi, tema_nome, consenti_non=negabile)
        if d.exec():
            lista.append(d.valore())
            lw.addItem(riass(lista[-1]))
            if on_change:
                on_change()

    def modifica():
        r = lw.currentRow()
        if r < 0:
            return
        d = DialogoVoce(owner, mondo, tipi, tema_nome, voce=lista[r],
                        consenti_non=negabile)
        if d.exec():
            lista[r] = d.valore()
            lw.item(r).setText(riass(lista[r]))
            if on_change:
                on_change()

    def rimuovi():
        r = lw.currentRow()
        if r >= 0:
            lista.pop(r)
            lw.takeItem(r)
            if on_change:
                on_change()
    b_add.clicked.connect(aggiungi)
    b_mod.clicked.connect(modifica)
    b_del.clicked.connect(rimuovi)
    lw.itemDoubleClicked.connect(lambda _: modifica())
    return box


class DialogoBattuta(QDialog):
    """Modifica una battuta di dialogo: etichetta, testo, «una volta», più le
    liste SE (condizioni di comparsa) e ALLORA (effetti alla scelta)."""

    def __init__(self, parent, mondo, tema_nome, battuta=None):
        super().__init__(parent)
        self.setWindowTitle("Battuta di dialogo")
        self.setStyleSheet(tema.qss(tema_nome))
        self.setMinimumWidth(540)
        b = battuta or {}
        self._se = [copy.deepcopy(c) for c in b.get("se", [])]
        self._allora = [copy.deepcopy(e) for e in b.get("allora", [])]
        v = QVBoxLayout(self)
        form = QFormLayout()
        v.addLayout(form)
        self.e_et = QLineEdit(b.get("etichetta", ""))
        form.addRow("etichetta (voce di menu)", self.e_et)
        self.e_testo = QPlainTextEdit(b.get("testo", ""))
        self.e_testo.setMinimumHeight(90)
        form.addRow("testo (cosa dice)", self.e_testo)
        self.c_una = QCheckBox("disponibile una sola volta")
        self.c_una.setChecked(bool(b.get("una_volta")))
        form.addRow("", self.c_una)
        v.addWidget(lista_voci_widget(
            self, mondo, tema_nome, "SE — condizioni (la battuta compare se…)",
            self._se, R.TIPI_CONDIZIONE, R.riassunto_condizione))
        v.addWidget(lista_voci_widget(
            self, mondo, tema_nome, "ALLORA — effetti alla scelta",
            self._allora, R.TIPI_EFFETTO, R.riassunto_effetto))
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def battuta(self) -> dict:
        b = {"etichetta": self.e_et.text().strip(), "testo": self.e_testo.toPlainText()}
        if self.c_una.isChecked():
            b["una_volta"] = True
        if self._se:
            b["se"] = self._se
        if self._allora:
            b["allora"] = self._allora
        return b


class DialogoUscita(QDialog):
    """Crea/modifica un'uscita: direzione, stanza di destinazione e, in opzione,
    un flag che la tiene chiusa finché non è vero, con messaggio di blocco."""

    DIREZIONI = ["nord", "sud", "est", "ovest", "su", "giu", "dentro", "fuori"]

    def __init__(self, parent, mondo, tema_nome, direzione=None, valore=None):
        super().__init__(parent)
        self.setWindowTitle("Uscita")
        self.setStyleSheet(tema.qss(tema_nome))
        self.setMinimumWidth(460)
        v = QVBoxLayout(self)
        form = QFormLayout()
        v.addLayout(form)
        self.cb_dir = QComboBox(); self.cb_dir.setEditable(True)
        self.cb_dir.addItems(self.DIREZIONI)
        if direzione:
            self.cb_dir.setCurrentText(direzione)
        form.addRow("direzione", self.cb_dir)
        self.cb_dest = QComboBox()
        self.cb_dest.addItems(list(mondo.stanze.keys()))
        dest = valore.get("to") if isinstance(valore, dict) else valore
        if dest and dest in mondo.stanze:
            self.cb_dest.setCurrentText(dest)
        form.addRow("destinazione (stanza)", self.cb_dest)
        self.cb_flag = QComboBox(); self.cb_flag.setEditable(True)
        self.cb_flag.addItems([""] + sorted(mondo.flags.keys()))
        se = valore.get("se") if isinstance(valore, dict) else ""
        self.cb_flag.setCurrentText(se or "")
        form.addRow("aperta solo se flag (facolt.)", self.cb_flag)
        self.e_bloc = QLineEdit(
            valore.get("bloccata", "") if isinstance(valore, dict) else "")
        form.addRow("messaggio se bloccata", self.e_bloc)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def uscita(self):
        d = self.cb_dir.currentText().strip()
        dest = self.cb_dest.currentText().strip()
        flag = self.cb_flag.currentText().strip()
        bloc = self.e_bloc.text().strip()
        if flag or bloc:
            val = {"to": dest}
            if flag:
                val["se"] = flag
            if bloc:
                val["bloccata"] = bloc
            return d, val
        return d, dest


class DialogoTimer(QDialog):
    """Gestisce i nomi dei timer dell'avventura: quelli dichiarati (riusabili
    dalle tendine) e quelli già usati nelle regole, con il conteggio degli usi."""

    def __init__(self, parent, mondo, tema_nome):
        super().__init__(parent)
        self.mondo = mondo
        self._cambiato = False
        self.setWindowTitle("Gestione timer")
        self.setStyleSheet(tema.qss(tema_nome))
        self.setMinimumWidth(440)
        v = QVBoxLayout(self)
        intro = QLabel("I timer dichiarati qui compaiono nelle tendine quando crei "
                       "regole ed effetti. Quelli già usati nell'avventura sono "
                       "elencati con il numero di utilizzi.")
        intro.setObjectName("campetto")
        intro.setWordWrap(True)
        v.addWidget(intro)
        self.lista = QListWidget()
        v.addWidget(self.lista)
        riga = QHBoxLayout()
        b_add = QPushButton("+ Aggiungi")
        b_del = QPushButton("Rimuovi")
        b_chiudi = QPushButton("Chiudi")
        for b in (b_add, b_del, b_chiudi):
            b.setAutoDefault(False)
        riga.addWidget(b_add)
        riga.addWidget(b_del)
        riga.addStretch(1)
        riga.addWidget(b_chiudi)
        v.addLayout(riga)
        b_add.clicked.connect(self._aggiungi)
        b_del.clicked.connect(self._rimuovi)
        b_chiudi.clicked.connect(self._chiudi)
        self._refill()

    def _refill(self, sel=-1):
        self.lista.clear()
        dichiarati = list(self.mondo.meta.get("timer", []) or [])
        rif = R.riferimenti_timer(self.mondo)
        nomi = sorted(set(dichiarati) | set(rif))
        for nome in nomi:
            usi = rif.get(nome, 0)
            parti = []
            parti.append("dichiarato" if nome in dichiarati else "non dichiarato")
            parti.append(f"{usi} usi" if usi else "non ancora usato")
            it = QListWidgetItem(f"{nome}    ·    {'  ·  '.join(parti)}")
            it.setData(Qt.UserRole, nome)
            self.lista.addItem(it)
        if 0 <= sel < self.lista.count():
            self.lista.setCurrentRow(sel)

    def _aggiungi(self):
        nome, ok = QInputDialog.getText(self, "Nuovo timer", "Nome del timer:")
        nome = nome.strip()
        if not (ok and nome):
            return
        dichiarati = self.mondo.meta.setdefault("timer", [])
        if nome in dichiarati:
            return
        dichiarati.append(nome)
        self._cambiato = True
        self._refill(self.lista.count())

    def _rimuovi(self):
        it = self.lista.currentItem()
        if it is None:
            return
        nome = it.data(Qt.UserRole)
        dichiarati = self.mondo.meta.get("timer", []) or []
        if nome not in dichiarati:
            QMessageBox.information(
                self, "Timer in uso",
                "Questo timer non è dichiarato: è solo usato nelle regole. "
                "Per toglierlo, rimuovi gli effetti/inneschi che lo usano.")
            return
        usi = R.riferimenti_timer(self.mondo).get(nome, 0)
        if usi and QMessageBox.question(
                self, "Timer in uso",
                f"«{nome}» è ancora usato in {usi} punti. Rimuovere solo la "
                f"dichiarazione? (gli usi restano)") != QMessageBox.StandardButton.Yes:
            return
        dichiarati.remove(nome)
        self._cambiato = True
        self._refill()

    def _chiudi(self):
        self.accept() if self._cambiato else self.reject()


class _CompilaWorker(QThread):
    """Esegue la compilazione PyInstaller in un thread, senza bloccare la GUI."""
    fatto = Signal(str)        # percorso dell'eseguibile prodotto
    errore = Signal(str)       # messaggio d'errore
    avanzamento = Signal(str)  # riga di log

    def __init__(self, mondo, cartella):
        super().__init__()
        self._mondo = mondo
        self._cartella = cartella

    def run(self):
        from gui import compila
        try:
            percorso = compila.compila(
                self._mondo, self._cartella, log=self.avanzamento.emit)
            self.fatto.emit(percorso)
        except Exception as e:                       # noqa: BLE001
            self.errore.emit(str(e))


class Editor(QMainWindow):
    def __init__(self, percorso=None):
        super().__init__()
        from gui import risorse
        self.setWindowIcon(risorse.icona_app())
        self.tema = "scuro"
        self.modificato = False
        if percorso:
            self.percorso = percorso
            self.mondo = carica_mondo(percorso)
        else:
            self.percorso = None
            self.mondo = Mondo()        # ambiente vuoto: nessuna avventura caricata

        self.resize(1040, 680)
        self._costruisci_menu()

        # tre pannelli: categorie | elementi | dettaglio
        self.lista_cat = QListWidget()
        self.lista_cat.addItems(CATEGORIE)
        self.lista_cat.currentRowChanged.connect(self._scegli_categoria)

        self.lista_el = QListWidget()
        self.lista_el.currentRowChanged.connect(self._scegli_elemento)
        self.lista_el.setContextMenuPolicy(Qt.CustomContextMenu)
        self.lista_el.customContextMenuRequested.connect(self._menu_elementi)
        self.filtro_el = QLineEdit()
        self.filtro_el.setPlaceholderText("filtra per nome o id…")
        self.filtro_el.setClearButtonEnabled(True)
        self.filtro_el.textChanged.connect(self._filtra_elementi)
        self.btn_nuovo = QPushButton("+ Nuovo")
        self.btn_nuovo.clicked.connect(self._nuovo)
        self.btn_duplica = QPushButton("Duplica")
        self.btn_duplica.clicked.connect(self._duplica)
        self.btn_elimina = QPushButton("Elimina")
        self.btn_elimina.clicked.connect(self._elimina)

        self.dettaglio = QScrollArea()
        self.dettaglio.setWidgetResizable(True)
        self.dettaglio.setFrameShape(QScrollArea.NoFrame)

        sx = self._colonna("CATEGORIE", self.lista_cat)
        cx = self._colonna("ELEMENTI", self.lista_el,
                            [self.btn_nuovo, self.btn_duplica, self.btn_elimina],
                            filtro=self.filtro_el)
        split = QSplitter()
        split.addWidget(sx)
        split.addWidget(cx)
        split.addWidget(self.dettaglio)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 0)
        split.setStretchFactor(2, 1)
        split.setSizes([200, 260, 580])
        self.setCentralWidget(split)

        self.lista_problemi = QListWidget()
        self.lista_problemi.itemDoubleClicked.connect(self._vai_da_problema)
        self.dock_problemi = QDockWidget("Problemi", self)
        self.dock_problemi.setObjectName("dock_problemi")
        self.dock_problemi.setWidget(self.lista_problemi)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_problemi)
        self.dock_problemi.hide()
        self.dock_problemi.visibilityChanged.connect(self._su_visibilita_problemi)

        self._applica_tema()
        self._aggiorna_titolo()
        self.lista_cat.setCurrentRow(0)

    def _colonna(self, etichetta, widget, bottoni=None, filtro=None):
        c = QWidget()
        v = QVBoxLayout(c)
        v.setContentsMargins(12, 12, 12, 12)
        lab = QLabel(etichetta)
        lab.setObjectName("sezione")
        v.addWidget(lab)
        if filtro is not None:
            v.addWidget(filtro)
        v.addWidget(widget, 1)
        if bottoni:
            riga = QHBoxLayout()
            for b in bottoni:
                riga.addWidget(b)
            v.addLayout(riga)
        return c

    # ---------- menu ----------

    def _costruisci_menu(self):
        barra = self.menuBar()
        m_file = barra.addMenu("File")
        for testo, slot, scorc in (("Nuovo", self._nuova_avventura, "Ctrl+N"),
                                   ("Apri…", self._apri, "Ctrl+O"),
                                   ("Salva", self._salva, "Ctrl+S"),
                                   ("Salva con nome…", self._salva_con_nome, "Ctrl+Shift+S"),
                                   ("Chiudi", self._chiudi_avventura, "Ctrl+W")):
            a = QAction(testo, self)
            a.setShortcut(scorc)
            a.triggered.connect(slot)
            m_file.addAction(a)
        m_file.addSeparator()
        a_ver = QAction("Verifica riferimenti", self)
        a_ver.triggered.connect(self._verifica)
        m_file.addAction(a_ver)
        m_file.addSeparator()
        a_esci = QAction("Esci", self)
        a_esci.triggered.connect(self.close)
        m_file.addAction(a_esci)

        m_vista = barra.addMenu("Visualizza")
        gruppo = QActionGroup(self)
        for etichetta, chiave in (("Tema scuro", "scuro"), ("Tema chiaro", "chiaro")):
            a = QAction(etichetta, self, checkable=True)
            a.setChecked(chiave == self.tema)
            a.triggered.connect(lambda _=False, c=chiave: self._cambia_tema(c))
            gruppo.addAction(a)
            m_vista.addAction(a)

        m_str = barra.addMenu("Strumenti")
        a_prova = QAction("Prova l'avventura…", self)
        a_prova.setShortcut("Ctrl+P")
        a_prova.triggered.connect(self._prova)
        m_str.addAction(a_prova)
        a_prova_da = QAction("Prova da…", self)
        a_prova_da.setShortcut("Ctrl+Shift+P")
        a_prova_da.triggered.connect(lambda: self._prova_da())
        m_str.addAction(a_prova_da)
        a_mappa = QAction("Mappa dell'avventura…", self)
        a_mappa.setShortcut("Ctrl+M")
        a_mappa.triggered.connect(self._apri_mappa)
        m_str.addAction(a_mappa)
        m_str.addSeparator()
        a_timer = QAction("Gestione timer…", self)
        a_timer.triggered.connect(self._gestione_timer)
        m_str.addAction(a_timer)
        m_str.addSeparator()
        a_prob = QAction("Pannello problemi", self, checkable=True)
        a_prob.setShortcut("Ctrl+J")
        a_prob.toggled.connect(lambda on: self.dock_problemi.setVisible(on))
        self.act_problemi = a_prob
        m_str.addAction(a_prob)
        a_usi = QAction("Dove è usato…", self)
        a_usi.triggered.connect(self._dove_usato)
        m_str.addAction(a_usi)
        m_str.addSeparator()
        a_compila = QAction("Compila gioco autonomo… (PyInstaller)", self)
        a_compila.triggered.connect(self._compila_gioco)
        m_str.addAction(a_compila)

        m_aiuto = barra.addMenu("Aiuto")
        a_info = QAction("Informazioni…", self)
        a_info.triggered.connect(self._informazioni)
        m_aiuto.addAction(a_info)

    def _prova(self):
        if not self.mondo.stanze:
            self.statusBar().showMessage(
                "Crea almeno una stanza per provare l'avventura.", 4000)
            return
        from gui.anteprima import FinestraGioco
        FinestraGioco(self.mondo, self.tema, self).exec()

    def _prova_da(self, stanza=None):
        """Prova dell'avventura da un punto scelto (stanza, inventario, flag):
        per le avventure lunghe non si può ricominciare sempre dall'inizio."""
        if not self.mondo.stanze:
            self.statusBar().showMessage(
                "Crea almeno una stanza per provare l'avventura.", 4000)
            return
        if stanza is None and CATEGORIE[self.lista_cat.currentRow()] == "Stanze":
            it = self.lista_el.currentItem()
            if it is not None:
                stanza = it.data(Qt.UserRole)
        from gui.anteprima import FinestraGioco, DialogoProvaDa
        d = DialogoProvaDa(self.mondo, self.tema, self, stanza=stanza)
        if d.exec():
            FinestraGioco(self.mondo, self.tema, self,
                          partenza=d.partenza()).exec()

    def _menu_elementi(self, pos):
        """Menu contestuale sulla lista degli elementi: sulle stanze offre
        la prova dell'avventura a partire da lì."""
        it = self.lista_el.itemAt(pos)
        if it is None or CATEGORIE[self.lista_cat.currentRow()] != "Stanze":
            return
        menu = QMenu(self)
        a_prova = menu.addAction("Prova da questa stanza…")
        if menu.exec(self.lista_el.mapToGlobal(pos)) == a_prova:
            self._prova_da(stanza=it.data(Qt.UserRole))

    def _apri_mappa(self):
        from gui.mappa import FinestraMappa
        FinestraMappa(self.mondo, self.tema, self).exec()

    def _gestione_timer(self):
        dlg = DialogoTimer(self, self.mondo, self.tema)
        if dlg.exec():
            self._segna_modifica()

    def _informazioni(self):
        from gui import risorse
        risorse.mostra_informazioni(self, "Pasifae Editor")

    def _su_visibilita_problemi(self, vis):
        if hasattr(self, "act_problemi"):
            self.act_problemi.blockSignals(True)
            self.act_problemi.setChecked(vis)
            self.act_problemi.blockSignals(False)
        if vis:
            self._aggiorna_problemi()

    def _vai_a(self, categoria, chiave):
        if categoria not in CATEGORIE:
            return
        ci = CATEGORIE.index(categoria)
        if self.lista_cat.currentRow() != ci:
            self.lista_cat.setCurrentRow(ci)
        else:
            self._scegli_categoria(ci)
        if chiave is None:
            return
        for i in range(self.lista_el.count()):
            if self.lista_el.item(i).data(Qt.UserRole) == chiave:
                self.lista_el.setCurrentRow(i)
                self.lista_el.scrollToItem(self.lista_el.item(i))
                break

    def _vai_da_problema(self, item):
        dati = item.data(Qt.UserRole)
        if dati:
            self._vai_a(dati[0], dati[1])

    def _aggiorna_problemi(self):
        if not hasattr(self, "lista_problemi"):
            return
        from gui.analisi import analizza_problemi
        self.lista_problemi.clear()
        probs = analizza_problemi(self.mondo)
        if not probs:
            self.lista_problemi.addItem(QListWidgetItem("Nessun problema rilevato ✓"))
            return
        for p in probs:
            it = QListWidgetItem(("● " if p["grave"] else "○ ") + p["testo"])
            it.setData(Qt.UserRole, (p["categoria"], p["chiave"]))
            self.lista_problemi.addItem(it)

    def _dove_usato(self):
        cat = CATEGORIE[self.lista_cat.currentRow()]
        it = self.lista_el.currentItem()
        mapa = {"Flag iniziali": "flag", "Oggetti": "oggetto", "Stanze": "stanza"}
        if cat not in mapa or it is None:
            self.statusBar().showMessage(
                "Seleziona prima un flag, un oggetto o una stanza.", 4000)
            return
        from gui.analisi import usi_di
        genere, chiave = mapa[cat], it.data(Qt.UserRole)
        usi = usi_di(self.mondo, genere, chiave)
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Usi di «{chiave}»")
        dlg.setStyleSheet(tema.qss(self.tema))
        dlg.resize(540, 380)
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel(f"«{chiave}» è usato in {len(usi)} punti (doppio clic per andarci):"
                           if usi else f"«{chiave}» non risulta usato da nessuna parte."))
        lw = QListWidget()
        v.addWidget(lw)
        for u in usi:
            item = QListWidgetItem(u["testo"])
            item.setData(Qt.UserRole, (u["categoria"], u["chiave"]))
            lw.addItem(item)

        def vai(item):
            dati = item.data(Qt.UserRole)
            if dati:
                self._vai_a(dati[0], dati[1])
                dlg.accept()
        lw.itemDoubleClicked.connect(vai)
        b = QPushButton("Chiudi")
        b.setAutoDefault(False)
        b.clicked.connect(dlg.accept)
        v.addWidget(b)
        dlg.exec()

    # ---------- compilazione gioco autonomo ----------

    def _compila_gioco(self):
        from gui import compila
        if not self.mondo.stanze or not self.mondo.meta.get("stanza_iniziale"):
            QMessageBox.warning(
                self, "Compila gioco",
                "Prima di compilare, definisci almeno una stanza e imposta la "
                "stanza iniziale (in Metadati).")
            return
        if not compila.disponibile():
            QMessageBox.information(
                self, "Compila gioco",
                "PyInstaller non è installato in questo ambiente.\n\n"
                "Installalo con:\n    pip install pyinstaller\n\n"
                "poi riprova.")
            return
        cartella = QFileDialog.getExistingDirectory(
            self, "Dove salvare l'eseguibile del gioco")
        if not cartella:
            return

        self._dlg_compila = QProgressDialog(
            "Preparazione…", None, 0, 0, self)
        self._dlg_compila.setWindowTitle("Compilazione del gioco")
        self._dlg_compila.setWindowModality(Qt.WindowModal)
        self._dlg_compila.setMinimumDuration(0)
        self._dlg_compila.setCancelButton(None)
        self._dlg_compila.setMinimumWidth(440)

        self._worker_compila = _CompilaWorker(
            copy.deepcopy(self.mondo), cartella)
        self._worker_compila.avanzamento.connect(
            self._dlg_compila.setLabelText)
        self._worker_compila.fatto.connect(self._compila_finita)
        self._worker_compila.errore.connect(self._compila_errore)
        self._worker_compila.finished.connect(self._dlg_compila.reset)
        self._dlg_compila.show()
        self._worker_compila.start()

    def _compila_finita(self, percorso):
        QMessageBox.information(
            self, "Compilazione completata",
            f"Eseguibile del gioco creato:\n\n{percorso}\n\n"
            "Avvialo per giocare l'avventura: si aprirà direttamente, "
            "senza bisogno di Pasifae.")

    def _compila_errore(self, messaggio):
        QMessageBox.warning(self, "Compilazione non riuscita", messaggio)

    # ---------- navigazione ----------

    def _filtra_elementi(self, testo):
        testo = testo.strip().lower()
        for i in range(self.lista_el.count()):
            it = self.lista_el.item(i)
            it.setHidden(bool(testo) and testo not in it.text().lower())

    def _scegli_categoria(self, riga):
        if riga < 0:
            return
        cat = CATEGORIE[riga]
        modificabile = cat in ("Stanze", "Oggetti", "Verbi", "Regole", "Flag iniziali")
        self.btn_nuovo.setEnabled(modificabile)
        self.btn_elimina.setEnabled(modificabile)
        self.btn_duplica.setEnabled(cat in ("Stanze", "Oggetti", "Regole"))
        self.filtro_el.blockSignals(True)
        self.filtro_el.clear()
        self.filtro_el.blockSignals(False)
        self.lista_el.blockSignals(True)
        self.lista_el.clear()
        if cat == "Stanze":
            for sid, s in self.mondo.stanze.items():
                self._voce(f"{s.nome}   ·   {sid}", sid)
        elif cat == "Oggetti":
            for oid, o in self.mondo.oggetti.items():
                self._voce(f"{o.nome}   ·   {oid}", oid)
        elif cat == "Verbi":
            for vid in self.mondo.verbi:
                self._voce(vid, vid)
        elif cat == "Regole":
            for i, r in enumerate(self.mondo.regole):
                self._voce(f"[{i}] {r.id or '(senza id)'} — {R.quando_breve(r.quando)}", i)
        elif cat == "Flag iniziali":
            for k, v in self.mondo.flags.items():
                self._voce(f"{k} = {v}", k)
        elif cat == "Metadati":
            self._voce("Metadati dell'avventura", "__meta__")
        self.lista_el.blockSignals(False)
        if self.lista_el.count():
            self.lista_el.setCurrentRow(0)
        else:
            self._mostra_dettaglio(QLabel("(nessun elemento)"))

    def _voce(self, testo, chiave):
        it = QListWidgetItem(testo)
        it.setData(Qt.UserRole, chiave)
        self.lista_el.addItem(it)

    def _scegli_elemento(self, riga):
        if riga < 0:
            return
        cat = CATEGORIE[self.lista_cat.currentRow()]
        chiave = self.lista_el.item(riga).data(Qt.UserRole)
        if cat == "Stanze":
            self._form_stanza(chiave)
        elif cat == "Oggetti":
            self._form_oggetto(chiave)
        elif cat == "Verbi":
            self._form_verbo(chiave)
        elif cat == "Flag iniziali":
            self._form_flag(chiave)
        elif cat == "Regole":
            self._form_regola(chiave)
        elif cat == "Metadati":
            self._form_meta()
        else:
            self._scheda_sola_lettura(cat, chiave)

    # ---------- dettaglio: form modificabili ----------

    def _form_stanza(self, sid):
        s = self.mondo.stanze[sid]
        cont, form = self._form_base(f"Stanza · {sid}")
        lab_id = QLabel(sid)
        lab_id.setStyleSheet("font-family: 'DejaVu Sans Mono', Consolas, monospace;")
        e_nome = QLineEdit(s.nome)
        e_desc = QPlainTextEdit(s.desc)
        e_desc.setToolTip(SUGG_TESTO)
        e_desc.setMinimumHeight(150)
        c_buia = QCheckBox("stanza buia (serve una luce)")
        c_buia.setChecked(bool(getattr(s, "buia", False)))
        form.addRow(self._campetto("id (interno, fisso)"), lab_id)
        form.addRow(self._campetto("nome (mostrato)"), e_nome)
        form.addRow(self._campetto("descrizione"), e_desc)
        form.addRow("", c_buia)
        e_img, box_img = self._immagine_widget(getattr(s, "immagine", ""))
        form.addRow(self._campetto("illustrazione"), box_img)
        uscite_lav = copy.deepcopy(s.uscite)
        form.addRow(self._uscite_widget(uscite_lav))

        def applica():
            s.nome = e_nome.text().strip()
            s.desc = e_desc.toPlainText()
            s.buia = c_buia.isChecked()
            s.immagine = e_img.text().strip()
            s.uscite = uscite_lav
            self._segna_modifica()
            self._aggiorna_voce_corrente(f"{s.nome}   ·   {sid}")
            self.statusBar().showMessage(f"Stanza «{sid}» aggiornata.", 3000)
        self._aggiungi_applica(cont, applica)
        self._mostra_dettaglio(cont)

    def _immagine_widget(self, nome_attuale: str):
        """Campo illustrazione della stanza: nome file (relativo al JSON),
        Sfoglia… che copia l'immagine accanto al JSON, Togli, e miniatura."""
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        riga = QHBoxLayout()
        e_img = QLineEdit(nome_attuale)
        e_img.setObjectName("campo_immagine")
        e_img.setReadOnly(True)
        e_img.setPlaceholderText("(nessuna illustrazione)")
        b_sfoglia = QPushButton("Sfoglia…")
        b_sfoglia.setObjectName("sfoglia_immagine")
        b_togli = QPushButton("Togli")
        b_togli.setObjectName("togli_immagine")
        riga.addWidget(e_img, 1); riga.addWidget(b_sfoglia); riga.addWidget(b_togli)
        v.addLayout(riga)
        miniatura = QLabel()
        miniatura.setObjectName("miniatura_immagine")
        v.addWidget(miniatura)

        def aggiorna_miniatura():
            pm = QPixmap()
            nome = e_img.text().strip()
            if nome and self.percorso:
                pm = QPixmap(str(Path(self.percorso).parent / nome))
            if pm.isNull():
                miniatura.clear(); miniatura.hide()
            else:
                miniatura.setPixmap(pm.scaledToHeight(
                    90, Qt.SmoothTransformation))
                miniatura.show()

        def sfoglia():
            f, _ = QFileDialog.getOpenFileName(
                self, "Scegli illustrazione", _dir_default(),
                "Immagini (*.png *.jpg *.jpeg *.gif *.bmp *.webp)")
            if not f:
                return
            try:
                e_img.setText(copia_immagine_accanto(f, self.percorso))
            except (ValueError, OSError) as err:
                QMessageBox.warning(self, "Illustrazione", str(err))
                return
            aggiorna_miniatura()

        def togli():
            e_img.clear()               # il file accanto al JSON non si tocca
            aggiorna_miniatura()

        b_sfoglia.clicked.connect(sfoglia)
        b_togli.clicked.connect(togli)
        aggiorna_miniatura()
        return e_img, box

    def _uscite_widget(self, uscite):
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 10, 0, 0)
        lab = QLabel("USCITE (collegamenti ad altre stanze)")
        lab.setObjectName("sezione")
        v.addWidget(lab)
        lw = QListWidget()
        lw.setMaximumHeight(130)

        def riass(d, val):
            if isinstance(val, dict):
                dest = val.get("to", "?")
                extra = f"  ·  se «{val['se']}»" if val.get("se") else ""
                return f"{d}  →  {dest}{extra}"
            return f"{d}  →  {val}"

        def refill(sel=-1):
            lw.clear()
            for d, val in uscite.items():
                lw.addItem(riass(d, val))
            if 0 <= sel < lw.count():
                lw.setCurrentRow(sel)
        refill()
        v.addWidget(lw)
        riga = QHBoxLayout()
        b_add = QPushButton("+ aggiungi")
        b_mod = QPushButton("modifica")
        b_del = QPushButton("rimuovi")
        for b in (b_add, b_mod, b_del):
            riga.addWidget(b)
        riga.addStretch(1)
        v.addLayout(riga)

        def chiavi():
            return list(uscite.keys())

        def aggiungi():
            d = DialogoUscita(self, self.mondo, self.tema)
            if d.exec():
                dire, val = d.uscita()
                if dire:
                    uscite[dire] = val
                    refill(chiavi().index(dire))
                    self._segna_modifica()

        def modifica():
            r = lw.currentRow()
            if r < 0:
                return
            dire_old = chiavi()[r]
            d = DialogoUscita(self, self.mondo, self.tema, dire_old, uscite[dire_old])
            if d.exec():
                dire, val = d.uscita()
                if dire:
                    if dire != dire_old:
                        del uscite[dire_old]
                    uscite[dire] = val
                    refill(chiavi().index(dire))
                    self._segna_modifica()

        def rimuovi():
            r = lw.currentRow()
            if r >= 0:
                del uscite[chiavi()[r]]
                refill(min(r, len(uscite) - 1))
                self._segna_modifica()
        b_add.clicked.connect(aggiungi)
        b_mod.clicked.connect(modifica)
        b_del.clicked.connect(rimuovi)
        return box

    def _form_meta(self):
        meta = self.mondo.meta
        cont, form = self._form_base("Metadati dell'avventura")
        campi = {}
        for chiave, etichetta in (("titolo", "titolo"), ("autore", "autore"),
                                  ("versione", "versione del gioco"),
                                  ("stanza_iniziale", "stanza iniziale"),
                                  ("colore", "colore accento (es. #7fa8d8)")):
            e = QLineEdit(str(meta.get(chiave, "")))
            campi[chiave] = e
            form.addRow(self._campetto(etichetta), e)
        e_intro = QPlainTextEdit(str(meta.get("intro", "")))
        e_intro.setMinimumHeight(120)
        campi["intro"] = e_intro
        form.addRow(self._campetto("intro"), e_intro)

        def applica():
            for k, w in campi.items():
                meta[k] = w.toPlainText() if isinstance(w, QPlainTextEdit) else w.text()
            self._segna_modifica()
            self.statusBar().showMessage("Metadati aggiornati.", 3000)
        self._aggiungi_applica(cont, applica)
        self._mostra_dettaglio(cont)

    # ---------- helper di campo ----------

    def _opz_luoghi(self, escludi=None):
        contenitori = [oid for oid, o in self.mondo.oggetti.items()
                       if o.props.get("contenitore") and oid != escludi]
        return list(self.mondo.stanze.keys()) + ["inventario"] + contenitori

    def _combo(self, opzioni, valore):
        return combo_cerca(opzioni, str(valore) if valore else None)

    def _aggiorna_voce_corrente(self, testo):
        it = self.lista_el.currentItem()
        if it is not None:
            it.setText(testo)

    # ---------- form: OGGETTO ----------

    def _form_oggetto(self, oid):
        o = self.mondo.oggetti[oid]
        props = o.props
        cont, form = self._form_base(f"Oggetto · {oid}")
        e_nome = QLineEdit(o.nome)
        e_sost = QLineEdit(", ".join(o.nomi))
        e_agg = QLineEdit(", ".join(o.aggettivi or []))
        cb_pos = self._combo(self._opz_luoghi(escludi=oid), o.posizione)
        e_desc = QPlainTextEdit(props.get("desc", ""))
        e_desc.setToolTip(SUGG_TESTO)
        e_desc.setMinimumHeight(100)
        e_fras = QLineEdit(props.get("in_stanza", ""))
        form.addRow(self._campetto("nome"), e_nome)
        form.addRow(self._campetto("sostantivi (csv)"), e_sost)
        form.addRow(self._campetto("aggettivi (csv)"), e_agg)
        form.addRow(self._campetto("posizione"), cb_pos)
        form.addRow(self._campetto("descrizione"), e_desc)
        form.addRow(self._campetto("frase in stanza"), e_fras)

        spunte = {}
        for chiave, etichetta in (
                ("prendibile", "prendibile"),
                ("scenario", "scenario (non elencato)"),
                ("contenitore", "contenitore"), ("aperto", "aperto"),
                ("indossabile", "indossabile"), ("png", "personaggio (png)")):
            cb = QCheckBox(etichetta)
            cb.setChecked(bool(props.get(chiave)))
            spunte[chiave] = cb
            form.addRow("", cb)

        luce = props.get("luce")
        c_luce = QCheckBox("è una sorgente di luce (sempre)")
        c_luce.setChecked(luce is True)
        e_luce_flag = QLineEdit(luce if isinstance(luce, str) else "")
        form.addRow(self._campetto("luce"), c_luce)
        form.addRow(self._campetto("luce solo se flag"), e_luce_flag)

        c_comb = QCheckBox("combattente (affrontabile in scontro)")
        c_comb.setChecked(bool(props.get("combattente")))
        s_hp = QSpinBox(); s_hp.setMaximum(9999); s_hp.setValue(int(props.get("hp", 10)))
        s_att = QSpinBox(); s_att.setMaximum(999); s_att.setValue(int(props.get("attacco", 3)))
        s_dif = QSpinBox(); s_dif.setMaximum(999); s_dif.setValue(int(props.get("difesa", 1)))
        c_fuga = QCheckBox("il giocatore può fuggire")
        c_fuga.setChecked(props.get("fuga", True))
        e_intro = QLineEdit(props.get("intro_scontro", ""))
        form.addRow(self._campetto("combattimento"), c_comb)
        form.addRow(self._campetto("PF (hp)"), s_hp)
        form.addRow(self._campetto("attacco"), s_att)
        form.addRow(self._campetto("difesa"), s_dif)
        form.addRow("", c_fuga)
        form.addRow(self._campetto("intro scontro"), e_intro)

        # --- dialogo a livelli (per i png) ---
        s_stato = QSpinBox(); s_stato.setRange(0, 99)
        s_stato.setValue(int(props.get("stato_iniziale", 0)))
        e_saluto = QPlainTextEdit(props.get("saluto", ""))
        e_saluto.setMinimumHeight(64)
        form.addRow(self._campetto("stato iniziale conversazione"), s_stato)
        form.addRow(self._campetto("saluto"), e_saluto)
        dialogo_lav = [copy.deepcopy(b) for b in props.get("dialogo", [])]
        form.addRow(self._battute_widget(dialogo_lav))

        # --- esito alla sconfitta (per i combattenti) ---
        sconfitto_lav = [copy.deepcopy(e) for e in props.get("sconfitto", [])]
        form.addRow(lista_voci_widget(
            self, self.mondo, self.tema, "ESITO ALLA SCONFITTA — effetti",
            sconfitto_lav, R.TIPI_EFFETTO, R.riassunto_effetto, self._segna_modifica))

        def applica():
            o.nome = e_nome.text().strip()
            o.nomi = [s.strip() for s in e_sost.text().split(",") if s.strip()]
            o.aggettivi = [s.strip() for s in e_agg.text().split(",") if s.strip()]
            o.posizione = cb_pos.currentText()
            props["desc"] = e_desc.toPlainText()
            if e_fras.text().strip():
                props["in_stanza"] = e_fras.text().strip()
            else:
                props.pop("in_stanza", None)
            for chiave, cb in spunte.items():
                props[chiave] = cb.isChecked()
            if e_luce_flag.text().strip():
                props["luce"] = e_luce_flag.text().strip()
            elif c_luce.isChecked():
                props["luce"] = True
            else:
                props.pop("luce", None)
            props["combattente"] = c_comb.isChecked()
            if c_comb.isChecked():
                props["hp"] = s_hp.value()
                props["attacco"] = s_att.value()
                props["difesa"] = s_dif.value()
                props["fuga"] = c_fuga.isChecked()
                props["intro_scontro"] = e_intro.text().strip()
            if s_stato.value():
                props["stato_iniziale"] = s_stato.value()
            else:
                props.pop("stato_iniziale", None)
            if e_saluto.toPlainText().strip():
                props["saluto"] = e_saluto.toPlainText()
            else:
                props.pop("saluto", None)
            if dialogo_lav:
                props["dialogo"] = dialogo_lav
            else:
                props.pop("dialogo", None)
            if sconfitto_lav:
                props["sconfitto"] = sconfitto_lav
            else:
                props.pop("sconfitto", None)
            self._segna_modifica()
            self._aggiorna_voce_corrente(f"{o.nome}   ·   {oid}")
            self.statusBar().showMessage(f"Oggetto «{oid}» aggiornato.", 3000)
        self._aggiungi_applica(cont, applica)
        self._mostra_dettaglio(cont)

    def _battute_widget(self, dialogo):
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 10, 0, 0)
        lab = QLabel("BATTUTE (dialogo a livelli)")
        lab.setObjectName("sezione")
        v.addWidget(lab)
        lw = QListWidget()
        lw.setMaximumHeight(140)

        def refill(sel=-1):
            lw.clear()
            for b in dialogo:
                et = b.get("etichetta") or "(senza etichetta)"
                marca = "  ·  una volta" if b.get("una_volta") else ""
                cond = f"  ·  {len(b.get('se', []))} cond." if b.get("se") else ""
                lw.addItem(et + marca + cond)
            if 0 <= sel < lw.count():
                lw.setCurrentRow(sel)
        refill()
        v.addWidget(lw)
        riga = QHBoxLayout()
        b_add = QPushButton("+ aggiungi")
        b_mod = QPushButton("modifica")
        b_del = QPushButton("rimuovi")
        b_su = QPushButton("↑")
        b_giu = QPushButton("↓")
        for b in (b_add, b_mod, b_del, b_su, b_giu):
            riga.addWidget(b)
        riga.addStretch(1)
        v.addLayout(riga)

        def aggiungi():
            d = DialogoBattuta(self, self.mondo, self.tema)
            if d.exec():
                dialogo.append(d.battuta())
                refill(len(dialogo) - 1)
                self._segna_modifica()

        def modifica():
            r = lw.currentRow()
            if r < 0:
                return
            d = DialogoBattuta(self, self.mondo, self.tema, dialogo[r])
            if d.exec():
                dialogo[r] = d.battuta()
                refill(r)
                self._segna_modifica()

        def rimuovi():
            r = lw.currentRow()
            if r >= 0:
                dialogo.pop(r)
                refill(min(r, len(dialogo) - 1))
                self._segna_modifica()

        def muovi(delta):
            r = lw.currentRow()
            j = r + delta
            if r >= 0 and 0 <= j < len(dialogo):
                dialogo[r], dialogo[j] = dialogo[j], dialogo[r]
                refill(j)
                self._segna_modifica()
        b_add.clicked.connect(aggiungi)
        b_mod.clicked.connect(modifica)
        b_del.clicked.connect(rimuovi)
        b_su.clicked.connect(lambda: muovi(-1))
        b_giu.clicked.connect(lambda: muovi(1))
        return box

    # ---------- form: VERBO ----------

    def _form_verbo(self, vid):
        from advcore.parser import VERBI_BUILTIN
        v = self.mondo.verbi[vid]
        cont, form = self._form_base(f"Verbo · {vid}")
        e_sin = QLineEdit(", ".join(v.sinonimi))
        cb_tipo = self._combo(["intransitivo", "transitivo", "ditransitivo"], v.tipo)
        e_prep = QLineEdit(", ".join(v.preposizioni))
        form.addRow(self._campetto("sinonimi (csv)"), e_sin)
        form.addRow(self._campetto("tipo"), cb_tipo)
        form.addRow(self._campetto("preposizioni (csv)"), e_prep)
        if vid in VERBI_BUILTIN:
            nota = QLabel("Estende un verbo predefinito del motore (aggiunge sinonimi).")
            nota.setObjectName("campetto"); nota.setWordWrap(True)
            form.addRow(nota)

        def applica():
            v.sinonimi = [s.strip() for s in e_sin.text().split(",") if s.strip()]
            v.tipo = cb_tipo.currentText()
            v.preposizioni = [s.strip() for s in e_prep.text().split(",") if s.strip()]
            self._segna_modifica()
            self.statusBar().showMessage(f"Verbo «{vid}» aggiornato.", 3000)
        self._aggiungi_applica(cont, applica)
        self._mostra_dettaglio(cont)

    # ---------- form: FLAG ----------

    def _form_flag(self, nome):
        val = self.mondo.flags[nome]
        cont, form = self._form_base(f"Flag · {nome}")
        tipo0 = ("vero/falso" if isinstance(val, bool)
                 else "numero" if isinstance(val, int) else "testo")
        cb_tipo = self._combo(["vero/falso", "numero", "testo"], tipo0)
        c_bool = QCheckBox("vero")
        c_bool.setChecked(val is True)
        e_val = QLineEdit("" if isinstance(val, bool) else str(val))
        form.addRow(self._campetto("tipo"), cb_tipo)
        form.addRow(self._campetto("se vero/falso"), c_bool)
        form.addRow(self._campetto("se numero/testo"), e_val)

        def applica():
            t = cb_tipo.currentText()
            if t == "vero/falso":
                nuovo = c_bool.isChecked()
            elif t == "numero":
                try:
                    nuovo = int(e_val.text())
                except ValueError:
                    return self._err("Il valore numerico non è valido.")
            else:
                nuovo = e_val.text()
            self.mondo.flags[nome] = nuovo
            self._segna_modifica()
            self._aggiorna_voce_corrente(f"{nome} = {nuovo}")
            self.statusBar().showMessage(f"Flag «{nome}» = {nuovo}", 3000)
        self._aggiungi_applica(cont, applica)
        self._mostra_dettaglio(cont)

    # ---------- form: REGOLA ----------

    def _form_regola(self, idx):
        if idx is None:
            self._reg_idx = None
            self._reg = {"id": "", "quando": {}, "se": [], "se_modo": "tutte",
                         "allora": [], "altrimenti": []}
        else:
            r = self.mondo.regole[idx]
            self._reg_idx = idx
            se_voci, modo = r.se, "tutte"
            if (len(r.se) == 1 and isinstance(r.se[0], dict) and "oppure" in r.se[0]):
                se_voci, modo = r.se[0]["oppure"], "almeno_una"
            self._reg = {"id": r.id, "quando": copy.deepcopy(r.quando),
                         "se": [copy.deepcopy(c) for c in se_voci], "se_modo": modo,
                         "allora": [copy.deepcopy(e) for e in r.allora],
                         "altrimenti": [copy.deepcopy(e) for e in r.altrimenti]}
        self._disegna_regola()

    def _disegna_regola(self):
        reg = self._reg
        cont, form = self._form_base(
            "Regola" + (f" · {reg['id']}" if reg["id"] else " (nuova)"))
        e_id = QLineEdit(reg["id"])
        e_id.textChanged.connect(lambda t: reg.__setitem__("id", t.strip()))
        form.addRow(self._campetto("id regola"), e_id)

        q = reg["quando"]
        opz = R.opzioni(self.mondo)
        innesco = q.get("evento") or "comando"
        cb_inn = QComboBox()
        for label, key in R.INNESCHI:
            cb_inn.addItem(label, key)
        cb_inn.setCurrentIndex([k for _, k in R.INNESCHI].index(innesco))
        cb_inn.currentIndexChanged.connect(
            lambda: self._cambia_innesco(cb_inn.currentData()))
        form.addRow(self._campetto("innesco"), cb_inn)

        if innesco == "comando":
            cb_v = self._combo(opz["verbo"], q.get("verbo", ""))
            if not q.get("verbo") and opz["verbo"]:
                q["verbo"] = cb_v.currentText()
            cb_v.currentTextChanged.connect(lambda t: q.__setitem__("verbo", t))
            cb_o = self._combo_opz(["(nessuno)"] + opz["oggetto"], q.get("oggetto"))
            cb_o.currentTextChanged.connect(lambda t: self._q_set(q, "oggetto", t))
            cb_p = self._combo_opz(["(nessuna)", "con", "in", "su"], q.get("prep"))
            cb_p.currentTextChanged.connect(lambda t: self._q_set(q, "prep", t))
            cb_oi = self._combo_opz(["(nessuno)"] + opz["oggetto"],
                                    q.get("oggetto_indiretto"))
            cb_oi.currentTextChanged.connect(
                lambda t: self._q_set(q, "oggetto_indiretto", t))
            form.addRow(self._campetto("verbo"), cb_v)
            form.addRow(self._campetto("oggetto"), cb_o)
            form.addRow(self._campetto("preposizione"), cb_p)
            form.addRow(self._campetto("oggetto indiretto"), cb_oi)
        elif innesco == "turno":
            form.addRow("", QLabel("Valutata dopo ogni turno."))
        elif innesco == "entra":
            cb_s = self._combo(opz["stanza"], q.get("stanza", ""))
            if not q.get("stanza") and opz["stanza"]:
                q["stanza"] = cb_s.currentText()
            cb_s.currentTextChanged.connect(lambda t: q.__setitem__("stanza", t))
            form.addRow(self._campetto("stanza d'ingresso"), cb_s)
        elif innesco == "timer":
            cb_t = QComboBox(); cb_t.setEditable(True)
            cb_t.addItems(opz["timer"])
            cb_t.setCurrentText(q.get("timer", ""))
            if not q.get("timer") and opz["timer"]:
                q["timer"] = cb_t.currentText()
            cb_t.currentTextChanged.connect(lambda t: q.__setitem__("timer", t.strip()))
            form.addRow(self._campetto("nome del timer"), cb_t)

        cb_modo = QComboBox()
        cb_modo.addItem("tutte vere (E / AND)", "tutte")
        cb_modo.addItem("almeno una vera (O / OR)", "almeno_una")
        cb_modo.setCurrentIndex(0 if reg.get("se_modo", "tutte") == "tutte" else 1)
        cb_modo.currentIndexChanged.connect(
            lambda: reg.__setitem__("se_modo", cb_modo.currentData()))
        form.addRow(self._campetto("le condizioni valgono se"), cb_modo)
        form.addRow(self._lista_voci("SE — condizioni", reg["se"],
                                     R.TIPI_CONDIZIONE, R.riassunto_condizione))
        form.addRow(self._lista_voci("ALLORA — effetti se vere", reg["allora"],
                                     R.TIPI_EFFETTO, R.riassunto_effetto))
        form.addRow(self._lista_voci("ALTRIMENTI — effetti se false",
                                     reg["altrimenti"], R.TIPI_EFFETTO,
                                     R.riassunto_effetto))
        self._aggiungi_applica(cont, self._salva_regola)
        self._mostra_dettaglio(cont)

    def _combo_opz(self, opzioni, valore):
        return combo_cerca(opzioni, valore if valore else None)

    def _q_set(self, q, chiave, testo):
        if not testo or testo.startswith("("):
            q.pop(chiave, None)
        else:
            q[chiave] = testo

    def _cambia_innesco(self, nuovo):
        self._reg["quando"].clear()
        if nuovo != "comando":
            self._reg["quando"]["evento"] = nuovo
        # Rinviamo il ridisegno: ricostruire ora distruggerebbe il combo
        # dell'innesco mentre sta ancora gestendo il proprio segnale (crash).
        QTimer.singleShot(0, self._disegna_regola)

    def _lista_voci(self, titolo, lista, tipi, riass):
        return lista_voci_widget(self, self.mondo, self.tema, titolo, lista,
                                 tipi, riass, self._segna_modifica)

    def _salva_regola(self):
        reg = self._reg
        q = reg["quando"]
        rid = reg["id"].strip() or f"regola_{len(self.mondo.regole)}"
        ev = q.get("evento")
        if ev == "entra" and not q.get("stanza"):
            return self._err("Scegli la stanza d'ingresso.")
        if ev == "timer" and not q.get("timer"):
            return self._err("Indica il nome del timer.")
        if not ev and not q.get("verbo"):
            return self._err("Scegli un verbo o un innesco-evento.")
        se_voci = reg["se"]
        if reg.get("se_modo") == "almeno_una" and len(se_voci) >= 2:
            se_finale = [{"oppure": se_voci}]
        else:
            se_finale = se_voci
        nuova = Regola(id=rid, quando=q, se=se_finale,
                       allora=reg["allora"], altrimenti=reg["altrimenti"])
        if self._reg_idx is None:
            self.mondo.regole.append(nuova)
            self._reg_idx = len(self.mondo.regole) - 1
        else:
            self.mondo.regole[self._reg_idx] = nuova
        self._segna_modifica()
        riga = self.lista_cat.currentRow()
        self._scegli_categoria(riga)
        self.lista_el.setCurrentRow(self._reg_idx)
        self.statusBar().showMessage(f"Regola «{rid}» salvata.", 3000)

    # ---------- nuovo / elimina ----------

    def _err(self, msg):
        QMessageBox.warning(self, "Attenzione", msg)

    def _chiedi_nome(self, domanda, predefinito):
        testo, ok = QInputDialog.getText(self, "Nome", domanda, text=predefinito)
        testo = testo.strip()
        return testo if (ok and testo) else predefinito

    def _nuovo(self):
        cat = CATEGORIE[self.lista_cat.currentRow()]
        if cat == "Flag iniziali":
            nome, ok = QInputDialog.getText(self, "Nuovo flag", "Nome del flag:")
            nome = nome.strip()
            if not (ok and nome):
                return
            if nome in self.mondo.flags:
                return self._err("Esiste già un flag con questo nome.")
            self.mondo.flags[nome] = False
        else:
            nome, ok = QInputDialog.getText(self, "Nuovo elemento",
                                            "Identificatore (id) univoco:")
            nome = nome.strip()
            if not (ok and nome):
                return
            if cat == "Stanze":
                if nome in self.mondo.stanze:
                    return self._err("Esiste già una stanza con questo id.")
                etic = self._chiedi_nome("Nome della stanza (mostrato al giocatore):", nome)
                self.mondo.stanze[nome] = Stanza(id=nome, nome=etic, desc="", uscite={})
            elif cat == "Oggetti":
                if nome in self.mondo.oggetti:
                    return self._err("Esiste già un oggetto con questo id.")
                etic = self._chiedi_nome("Nome dell'oggetto (mostrato al giocatore):", nome)
                pos0 = next(iter(self.mondo.stanze), "")
                self.mondo.oggetti[nome] = Oggetto(id=nome, nome=etic, nomi=[nome],
                                                   aggettivi=[], posizione=pos0, props={})
            elif cat == "Verbi":
                if nome in self.mondo.verbi:
                    return self._err("Esiste già un verbo con questo id.")
                self.mondo.verbi[nome] = Verbo(id=nome, sinonimi=[],
                                               tipo="transitivo", preposizioni=[])
            elif cat == "Regole":
                self.mondo.regole.append(
                    Regola(id=nome, quando={}, se=[], allora=[], altrimenti=[]))
        self._segna_modifica()
        self._scegli_categoria(self.lista_cat.currentRow())
        self.lista_el.setCurrentRow(self.lista_el.count() - 1)

    def _elimina(self):
        cat = CATEGORIE[self.lista_cat.currentRow()]
        it = self.lista_el.currentItem()
        if it is None:
            return
        chiave = it.data(Qt.UserRole)
        if QMessageBox.question(self, "Elimina",
                                f"Eliminare «{it.text()}»?") != QMessageBox.StandardButton.Yes:
            return
        if cat == "Regole":
            if isinstance(chiave, int) and 0 <= chiave < len(self.mondo.regole):
                self.mondo.regole.pop(chiave)
        else:
            deposito = {"Stanze": self.mondo.stanze, "Oggetti": self.mondo.oggetti,
                        "Verbi": self.mondo.verbi, "Flag iniziali": self.mondo.flags}.get(cat)
            if deposito is not None:
                deposito.pop(chiave, None)
        self._segna_modifica()
        self._scegli_categoria(self.lista_cat.currentRow())

    def _id_unico(self, esistenti, base):
        base = base or "elemento"
        cand = f"{base}_copia"
        n = 2
        while cand in esistenti:
            cand = f"{base}_copia{n}"
            n += 1
        return cand

    def _duplica(self):
        import copy
        cat = CATEGORIE[self.lista_cat.currentRow()]
        it = self.lista_el.currentItem()
        if it is None:
            return
        chiave = it.data(Qt.UserRole)
        nuovo_sel = None
        if cat == "Stanze":
            sugg = self._id_unico(self.mondo.stanze, chiave)
            nid, ok = QInputDialog.getText(self, "Duplica stanza", "id della copia:", text=sugg)
            nid = nid.strip()
            if not (ok and nid):
                return
            if nid in self.mondo.stanze:
                return self._err("Esiste già una stanza con questo id.")
            s = self.mondo.stanze[chiave]
            self.mondo.stanze[nid] = Stanza(id=nid, nome=s.nome + " (copia)", desc=s.desc,
                                            uscite=copy.deepcopy(s.uscite),
                                            buia=getattr(s, "buia", False),
                                            immagine=getattr(s, "immagine", ""))
            nuovo_sel = nid
        elif cat == "Oggetti":
            sugg = self._id_unico(self.mondo.oggetti, chiave)
            nid, ok = QInputDialog.getText(self, "Duplica oggetto", "id della copia:", text=sugg)
            nid = nid.strip()
            if not (ok and nid):
                return
            if nid in self.mondo.oggetti:
                return self._err("Esiste già un oggetto con questo id.")
            o = self.mondo.oggetti[chiave]
            self.mondo.oggetti[nid] = Oggetto(id=nid, nome=o.nome + " (copia)",
                                              nomi=list(o.nomi), aggettivi=list(o.aggettivi),
                                              posizione=o.posizione, props=copy.deepcopy(o.props))
            nuovo_sel = nid
        elif cat == "Regole":
            r = self.mondo.regole[chiave]
            ids = {x.id for x in self.mondo.regole}
            nid = self._id_unico(ids, r.id or "regola")
            self.mondo.regole.append(Regola(id=nid, quando=copy.deepcopy(r.quando),
                                            se=copy.deepcopy(r.se),
                                            allora=copy.deepcopy(r.allora),
                                            altrimenti=copy.deepcopy(r.altrimenti)))
            nuovo_sel = len(self.mondo.regole) - 1
        else:
            return
        self._segna_modifica()
        self._scegli_categoria(self.lista_cat.currentRow())
        for i in range(self.lista_el.count()):
            if self.lista_el.item(i).data(Qt.UserRole) == nuovo_sel:
                self.lista_el.setCurrentRow(i)
                break

    def _scheda_sola_lettura(self, cat, chiave):
        singolari = {"Oggetti": "Oggetto", "Verbi": "Verbo",
                     "Regole": "Regola", "Flag iniziali": "Flag"}
        cont, form = self._form_base(singolari.get(cat, cat))
        testo = riassunto(self.mondo, cat, chiave)
        vis = QLabel(testo)
        vis.setWordWrap(True)
        vis.setTextInteractionFlags(Qt.TextSelectableByMouse)
        vis.setStyleSheet("font-family: 'DejaVu Sans Mono', Consolas, monospace;")
        form.addRow(vis)
        nota = QLabel("La modifica di questa categoria arriverà in un prossimo passo. "
                      "Per ora usa l'editor da terminale (edit.py) per cambiarla.")
        nota.setObjectName("campetto")
        nota.setWordWrap(True)
        form.addRow(nota)
        self._mostra_dettaglio(cont)

    # ---------- infrastruttura dettaglio ----------

    def _form_base(self, titolo):
        cont = QWidget()
        v = QVBoxLayout(cont)
        v.setContentsMargins(22, 20, 22, 20)
        v.setSpacing(14)
        t = QLabel(titolo)
        t.setObjectName("titolo")
        v.addWidget(t)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignTop)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        v.addLayout(form)
        v.addStretch(1)
        return cont, form

    def _campetto(self, testo):
        lab = QLabel(testo)
        lab.setObjectName("campetto")
        return lab

    def _aggiungi_applica(self, cont, slot):
        riga = QHBoxLayout()
        riga.addStretch(1)
        b = QPushButton("Applica")
        b.setObjectName("primario")
        b.clicked.connect(slot)
        riga.addWidget(b)
        cont.layout().addLayout(riga)

    def _mostra_dettaglio(self, widget):
        self.dettaglio.setWidget(widget)

    # ---------- file ----------

    def _carica_in_ui(self):
        self._aggiorna_titolo()
        self.lista_cat.setCurrentRow(0)
        self._scegli_categoria(0)

    def _conferma_abbandono(self) -> bool:
        """Se ci sono modifiche non salvate chiede cosa fare. Ritorna True se si
        può proseguire (salvato o scartato), False se l'utente annulla."""
        if not self.modificato:
            return True
        r = QMessageBox.question(
            self, "Modifiche non salvate",
            "L'avventura corrente ha modifiche non salvate. Vuoi salvarle?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save)
        if r == QMessageBox.StandardButton.Save:
            return self._salva()
        if r == QMessageBox.StandardButton.Discard:
            return True
        return False

    def _nuova_avventura(self):
        if not self._conferma_abbandono():
            return
        self.mondo = Mondo()
        self.percorso = None
        self.modificato = False
        self._carica_in_ui()
        self.statusBar().showMessage("Nuova avventura.", 3000)

    def _chiudi_avventura(self):
        if not self._conferma_abbandono():
            return
        self.mondo = Mondo()
        self.percorso = None
        self.modificato = False
        self._carica_in_ui()
        self.statusBar().showMessage("Avventura chiusa.", 3000)

    def _apri(self):
        if not self._conferma_abbandono():
            return
        f, _ = QFileDialog.getOpenFileName(
            self, "Apri avventura", _dir_default(), "Avventure (*.json)")
        if f:
            self.mondo = carica_mondo(f)
            self.percorso = f
            self.modificato = False
            self._carica_in_ui()

    def _salva(self) -> bool:
        if self.percorso is None:
            return self._salva_con_nome()
        salva_mondo(self.mondo, self.percorso)
        self.modificato = False
        self._aggiorna_titolo()
        self.statusBar().showMessage(f"Salvato in {self.percorso}", 4000)
        return True

    def _salva_con_nome(self) -> bool:
        f, _ = QFileDialog.getSaveFileName(
            self, "Salva con nome", _dir_default(), "Avventure (*.json)")
        if not f:
            return False
        if not f.lower().endswith(".json"):
            f += ".json"
        self.percorso = f
        salva_mondo(self.mondo, f)
        self.modificato = False
        self._aggiorna_titolo()
        self.statusBar().showMessage(f"Salvato in {f}", 4000)
        return True

    def closeEvent(self, ev):
        if self._conferma_abbandono():
            ev.accept()
        else:
            ev.ignore()

    def _verifica(self):
        problemi = valida(self.mondo)
        if not problemi:
            self.statusBar().showMessage("Verifica: nessun problema.", 5000)
        else:
            n_err = sum(1 for p in problemi if p.gravita == "errore")
            self.statusBar().showMessage(
                f"Verifica: {n_err} errori, {len(problemi) - n_err} avvisi "
                f"(dettagli in edit.py).", 6000)

    # ---------- stato / tema ----------

    def _segna_modifica(self):
        self.modificato = True
        self._aggiorna_titolo()
        if getattr(self, "dock_problemi", None) and self.dock_problemi.isVisible():
            self._aggiorna_problemi()

    def _aggiorna_titolo(self):
        nome = self.mondo.meta.get("titolo") or "(senza nome)"
        stella = " *" if self.modificato else ""
        self.setWindowTitle(f"{nome}{stella} — Pasifae Editor")

    def _cambia_tema(self, nome):
        self.tema = nome
        self._applica_tema()

    def _applica_tema(self):
        self.setStyleSheet(tema.qss(self.tema))


def main():
    percorso = sys.argv[1] if len(sys.argv) > 1 else None
    app = QApplication(sys.argv)
    app.setApplicationName("Pasifae")
    app.setApplicationDisplayName("Pasifae Editor")
    from gui import risorse
    app.setWindowIcon(risorse.icona_app())
    app.setFont(QFont("Segoe UI", 10))
    Editor(percorso).show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
