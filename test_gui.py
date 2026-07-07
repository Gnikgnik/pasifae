# SPDX-License-Identifier: GPL-3.0-or-later
"""Suite di test automatici dell'interfaccia (pytest-qt).

Blocca le regressioni incontrate durante lo sviluppo e verifica i comportamenti
chiave dell'editor e dell'anteprima. Si esegue con:

    pytest test_gui.py
    python3 test_gui.py      # equivalente (delega a pytest)

Gira in modalità offscreen, quindi non apre finestre.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
RADICE = Path(__file__).resolve().parent
sys.path.insert(0, str(RADICE))
AVV = RADICE / "avventure"

import pytest  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication, QComboBox, QInputDialog, QFileDialog, QLabel, QLineEdit,
    QMenu, QMessageBox, QPushButton,
)

from advcore import (  # noqa: E402
    carica_mondo, salva_mondo, salva_partita, Mondo, Motore, Stanza, Oggetto,
    Regola,
)
from advcore.model import SCARTATO  # noqa: E402
from gui.editor import Editor, DialogoVoce, combo_cerca, CATEGORIE  # noqa: E402
from gui import regole as R  # noqa: E402
from gui import analisi as A  # noqa: E402
from gui.anteprima import FinestraGioco, DialogoProvaDa  # noqa: E402
from gui.player import Player  # noqa: E402


@pytest.fixture(autouse=True)
def _niente_dialoghi_bloccanti(monkeypatch):
    """In offscreen un QMessageBox modale bloccherebbe la chiusura delle finestre
    in fase di teardown. Lo neutralizziamo (i test che servono lo riconfigurano)."""
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.Discard)


# --------------------------- aiutanti ---------------------------

def mondo_semplice():
    m = Mondo()
    m.stanze["sala"] = Stanza(id="sala", nome="Sala", desc="Una sala.",
                              uscite={"nord": "corridoio"})
    m.stanze["corridoio"] = Stanza(id="corridoio", nome="Corridoio", desc="Buio.",
                                   uscite={"sud": "sala"})
    m.meta["stanza_iniziale"] = "sala"
    m.oggetti["lampada"] = Oggetto(id="lampada", nome="lampada", nomi=["lampada"],
                                   aggettivi=[], posizione="sala",
                                   props={"prendibile": True})
    return m


def innesco_combo(editor):
    for cb in editor.dettaglio.widget().findChildren(QComboBox):
        dati = [cb.itemData(i) for i in range(cb.count())]
        if dati and dati[0] == "comando":
            return cb
    return None


# --------------------------- file / avvio ---------------------------

def test_avvio_vuoto(qtbot):
    e = Editor(None)
    qtbot.addWidget(e)
    assert e.mondo.stanze == {}
    assert e.percorso is None
    assert "(senza nome)" in e.windowTitle()


def test_crea_stanza_id_e_nome(qtbot, monkeypatch):
    e = Editor(None)
    qtbot.addWidget(e)
    risposte = iter([("vetta", True), ("La Vetta Innevata", True)])
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: next(risposte))
    e.lista_cat.setCurrentRow(CATEGORIE.index("Stanze"))
    e._nuovo()
    assert "vetta" in e.mondo.stanze
    assert e.mondo.stanze["vetta"].nome == "La Vetta Innevata"


def test_salva_nuovo_chiede_nome(qtbot, monkeypatch, tmp_path):
    e = Editor(None)
    qtbot.addWidget(e)
    e.mondo = mondo_semplice()
    e._segna_modifica()
    pth = str(tmp_path / "mia.json")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (pth, ""))
    assert e._salva() is True
    assert e.percorso == pth
    assert e.modificato is False
    assert "sala" in carica_mondo(pth).stanze


def test_conferma_abbandono(qtbot, monkeypatch):
    e = Editor(None)
    qtbot.addWidget(e)
    e._segna_modifica()
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.Discard)
    assert e._conferma_abbandono() is True
    e._segna_modifica()
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.Cancel)
    assert e._conferma_abbandono() is False


def test_closeevent_conferma(qtbot, monkeypatch):
    """Il closeEvent reale: con 'Annulla' la finestra non si chiude."""
    from PySide6.QtGui import QCloseEvent
    e = Editor(None)
    qtbot.addWidget(e)
    e._segna_modifica()
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.Cancel)
    ev = QCloseEvent()
    Editor.closeEvent(e, ev)
    assert not ev.isAccepted()


# --------------------------- regressione: segfault innesco ---------------------------

def test_cambia_innesco_non_crasha(qtbot):
    """Cambiare l'innesco di una regola NON deve mandare in crash (segfault)."""
    e = Editor(str(AVV / "caverna.json"))
    qtbot.addWidget(e)
    e.lista_cat.setCurrentRow(CATEGORIE.index("Regole"))
    e.lista_el.setCurrentRow(0)
    chiavi = [k for _, k in R.INNESCHI]
    for chiave in ["turno", "entra", "timer", "comando", "entra"]:
        cb = innesco_combo(e)
        assert cb is not None
        cb.setCurrentIndex(chiavi.index(chiave))
        qtbot.wait(20)  # lascia eseguire il ridisegno rinviato (QTimer.singleShot)
        if chiave == "comando":
            assert "evento" not in e._reg["quando"]
        else:
            assert e._reg["quando"].get("evento") == chiave


# --------------------------- modifica in posizione ---------------------------

@pytest.mark.parametrize("tipi,voce", [
    (R.TIPI_CONDIZIONE, {"flag": "p", "uguale": False}),
    (R.TIPI_CONDIZIONE, {"oggetto_in": ["lampada", "inventario"]}),
    (R.TIPI_CONDIZIONE, {"flag": "hp", "minore": 10}),
    (R.TIPI_CONDIZIONE, {"flag": "hp", "maggiore_uguale": 3}),
    (R.TIPI_CONDIZIONE, {"flag": "hp", "minore_uguale": 5}),
    (R.TIPI_EFFETTO, {"set_flag": "p", "valore": True}),
    (R.TIPI_EFFETTO, {"sposta_oggetto": "lampada", "a": "inventario"}),
    (R.TIPI_EFFETTO, {"scarta_oggetto": "lampada", "stampa": "Si spegne."}),
    (R.TIPI_EFFETTO, {"avvia_timer": "cera", "turni": 3}),
])
def test_modifica_voce_round_trip(qtbot, tipi, voce):
    m = mondo_semplice()
    d = DialogoVoce(None, m, tipi, "scuro", voce=voce)
    qtbot.addWidget(d)
    assert d.valore() == voce


def test_condizione_negata_round_trip(qtbot):
    m = mondo_semplice()
    voce = {"non": {"flag": "chiave", "uguale": True}}
    d = DialogoVoce(None, m, R.TIPI_CONDIZIONE, "scuro", voce=voce, consenti_non=True)
    qtbot.addWidget(d)
    assert d.valore() == voce
    assert d._chk_non.isChecked()


def test_regola_modalita_or(qtbot):
    """In modalità OR la regola viene salvata come un nodo 'oppure' e ricaricata."""
    m = mondo_semplice()
    m.flags = {"porta": True, "chiave": False}
    e = Editor(None); e.mondo = m
    qtbot.addWidget(e)
    e.lista_cat.setCurrentRow(CATEGORIE.index("Regole"))
    e._form_regola(None)
    e._reg["id"] = "r_or"
    e._reg["quando"] = {"verbo": "guarda"}
    e._reg["se"] = [{"flag": "porta"}, {"flag": "chiave"}]
    e._reg["se_modo"] = "almeno_una"
    e._reg["allora"] = [{"stampa": "ok"}]
    e._salva_regola()
    r = e.mondo.regole[-1]
    assert r.se == [{"oppure": [{"flag": "porta"}, {"flag": "chiave"}]}]
    # ricarico: torna in modalità OR con le condizioni piatte
    e._form_regola(len(e.mondo.regole) - 1)
    assert e._reg["se_modo"] == "almeno_una"
    assert e._reg["se"] == [{"flag": "porta"}, {"flag": "chiave"}]


def test_editor_prep_multipla(qtbot):
    """Nel form della regola si possono scrivere più preposizioni separate
    da virgola («su, con»): l'innesco le salva come lista; una sola resta
    stringa; «(nessuna)» la toglie. Una regola con lista si riapre
    mostrando «su, con»."""
    m = mondo_semplice()
    m.regole.append(Regola(id="r_multi",
                           quando={"verbo": "guarda", "oggetto": "lampada",
                                   "prep": ["su", "con"]}))
    e = Editor(None); e.mondo = m
    qtbot.addWidget(e)
    q = {"verbo": "usa"}
    e._q_set_prep(q, "su, con")
    assert q["prep"] == ["su", "con"]
    e._q_set_prep(q, "su")
    assert q["prep"] == "su"
    e._q_set_prep(q, "(nessuna)")
    assert "prep" not in q
    # il form mostra la lista esistente come testo «su, con»
    e.lista_cat.setCurrentRow(CATEGORIE.index("Regole"))
    e._form_regola(len(m.regole) - 1)
    testi = [cb.currentText()
             for cb in e.dettaglio.widget().findChildren(QComboBox)]
    assert "su, con" in testi, testi


def test_player_blank_e_apertura(qtbot):
    """Senza avventura il player parte in blank; aprendone una si abilita."""
    p = Player()
    qtbot.addWidget(p)
    assert p.mondo is None and p.motore is None
    assert not p.input.isEnabled()
    assert all(not a.isEnabled() for a in p._azioni_partita)
    assert p.windowTitle() == "Pasifae Play"
    p._apri_avventura(str(AVV / "caverna.json"))
    assert p.mondo is not None and p.motore is not None
    assert p.input.isEnabled()
    assert all(a.isEnabled() for a in p._azioni_partita)
    assert "Pasifae" in p.windowTitle()
    p.input.setText("guarda"); p._invia()
    assert p.mondo.mosse >= 1


def test_player_percorso_diretto(qtbot):
    p = Player(str(AVV / "faro.json"))
    qtbot.addWidget(p)
    assert p.motore is not None and p.input.isEnabled()


def test_player_salva_aggiunge_estensione(qtbot, monkeypatch, tmp_path):
    """Il dialogo "Salva partita" non impone un'estensione: se l'utente scrive
    solo «lab1» il file nasce senza suffisso e il dialogo di caricamento, che
    filtra per estensione, non lo mostra più. Il player deve aggiungere .save
    (rispettando però un'estensione scelta dall'utente)."""
    p = Player(str(AVV / "faro.json"))
    qtbot.addWidget(p)
    scelto = tmp_path / "lab1"                    # nome senza estensione
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        lambda *a, **k: (str(scelto), ""))
    p._salva()
    assert not scelto.exists()
    assert (tmp_path / "lab1.save").exists()
    scelto = tmp_path / "lab2.json"               # estensione esplicita
    p._salva()
    assert scelto.exists()


def test_player_carica_vede_sav_e_senza_estensione(qtbot, monkeypatch, tmp_path):
    """Il filtro di "Carica partita" deve mostrare anche i «.sav» dei player
    da terminale e offrire «Tutti i file» per i vecchi salvataggi nati senza
    estensione; un file senza estensione deve comunque caricarsi."""
    p = Player(str(AVV / "faro.json"))
    qtbot.addWidget(p)
    p.mondo.punteggio = 7
    salvato = tmp_path / "vecchio"                # salvataggio senza estensione
    salva_partita(p.mondo, salvato)

    p2 = Player(str(AVV / "faro.json"))
    qtbot.addWidget(p2)
    catturato = {}

    def finto_open(parent, titolo, cartella, filtro):
        catturato["filtro"] = filtro
        return str(salvato), ""

    monkeypatch.setattr(QFileDialog, "getOpenFileName", finto_open)
    p2._carica()
    assert "(*.save *.sav *.json)" in catturato["filtro"], catturato
    assert "Tutti i file" in catturato["filtro"], catturato
    assert p2.mondo.punteggio == 7


def test_animazione_non_riscrive_tutta_la_cronologia(qtbot):
    """L'animazione "telescrivente" avanza ogni 22ms: se ogni fotogramma
    riscrive con setHtml() l'intera cronologia (che cresce nel tempo), il
    ridisegno rallenta con la partita e produce il farfallio visto su Linux.
    Un fotogramma deve toccare solo la voce in corso di animazione."""
    p = Player(str(AVV / "faro.json"))
    qtbot.addWidget(p)
    for i in range(30):
        p._voci.append(("risposta", f"voce numero {i} già mostrata per intero"))

    chiamate = []
    originale = p.vista.setHtml
    p.vista.setHtml = lambda h: (chiamate.append(h), originale(h))[-1]

    p._mostra("una risposta con diverse parole da animare piano piano", "risposta")
    passi = len(p._anim_cuts)
    assert passi > 3
    for _ in range(passi):
        p._anima_passo()

    # il numero di setHtml() non deve crescere con i fotogrammi dell'animazione
    assert len(chiamate) <= 3, len(chiamate)
    assert p.vista.toPlainText().splitlines()[-1] == \
        "una risposta con diverse parole da animare piano piano"


def test_animazione_voce_su_riga_propria(qtbot):
    """Durante l'animazione la voce in corso di stampa non deve fondersi con
    il blocco precedente: l'insertHtml() per-fotogramma attaccava la risposta
    alla riga del comando ("› guardaBIBLIOTECA…")."""
    p = Player(str(AVV / "faro.json"))
    qtbot.addWidget(p)
    p._anim_finisci()
    p._mostra("› guarda", "comando")
    p._mostra("Una risposta animata di parecchie parole", "risposta")
    assert p._anim.isActive()
    righe = p.vista.toPlainText().splitlines()
    assert righe[-1].rstrip() == "Una", righe[-2:]
    assert righe[-2] == "› guarda", righe[-2:]


def test_vista_segue_il_fondo_quando_il_layout_arriva_dopo(qtbot):
    """Dopo setHtml() la corsa della scrollbar è *stimata*: il layout vero
    arriva dopo e, se la stima era corta, l'ultima riga stampata resta fuori
    dallo schermo (visto giocando a "Il labirinto"). Se la vista era in
    fondo, deve restarci quando la corsa cresce."""
    p = Player(str(AVV / "faro.json"))
    qtbot.addWidget(p)
    p.resize(880, 500)
    p.show()
    for i in range(30):
        p._voci.append(("risposta", f"voce {i} " + "con testo che scorre " * 4))
    p._anim_finisci()            # _ridisegna() + scorrimento in fondo
    barra = p.vista.verticalScrollBar()
    assert barra.value() == barra.maximum() > 0
    # il layout tardivo allunga la corsa: la vista deve seguire il fondo
    barra.setRange(0, barra.maximum() + 200)
    assert barra.value() == barra.maximum(), (barra.value(), barra.maximum())


def test_vista_non_scatta_se_l_utente_sta_rileggendo(qtbot):
    """Se l'utente ha scorso in su per rileggere, un semplice cambio di corsa
    (per esempio dal ridimensionamento della finestra) non deve trascinarlo
    in fondo: ci pensa il prossimo output, come sempre."""
    p = Player(str(AVV / "faro.json"))
    qtbot.addWidget(p)
    p.resize(880, 500)
    p.show()
    for i in range(30):
        p._voci.append(("risposta", f"voce {i} " + "con testo che scorre " * 4))
    p._anim_finisci()
    barra = p.vista.verticalScrollBar()
    barra.setValue(barra.maximum() // 2)          # l'utente sta rileggendo
    barra.setRange(0, barra.maximum() + 200)
    assert barra.value() < barra.maximum()


def test_anteprima_parte_dal_punto_scelto(qtbot):
    """Per provare un'avventura lunga si deve poter partire da una stanza
    scelta, con oggetti già in tasca e flag preimpostati; e «Riavvia» deve
    tornare a QUEL punto, non all'inizio dell'avventura."""
    m = carica_mondo(str(AVV / "caverna.json"))
    f = FinestraGioco(m, "scuro", partenza={
        "stanza": "tesoro",
        "inventario": ["lampada", "chiave"],
        "flags": {"lampada_accesa": True},
    })
    qtbot.addWidget(f)
    assert f.mondo.stanza_corrente == "tesoro"
    assert f.mondo.oggetti["lampada"].posizione == "inventario"
    assert f.mondo.oggetti["chiave"].posizione == "inventario"
    assert f.mondo.flags["lampada_accesa"] is True
    # il mondo dell'editor non deve essere toccato
    assert m.stanza_corrente == "ingresso"
    assert m.oggetti["lampada"].posizione == "ingresso"
    assert m.flags["lampada_accesa"] is False
    # «Riavvia» torna al punto scelto, non a "ingresso"
    f.motore.esegui("nord")
    f._riavvia()
    assert f.mondo.stanza_corrente == "tesoro"
    assert f.mondo.oggetti["chiave"].posizione == "inventario"


def test_dialogo_prova_da(qtbot):
    """Il dialogo «Prova da…» raccoglie stanza di partenza, oggetti da mettere
    nell'inventario e flag da impostare (col valore interpretato)."""
    m = carica_mondo(str(AVV / "caverna.json"))
    d = DialogoProvaDa(m, "scuro", stanza="cripta")
    qtbot.addWidget(d)
    # la stanza passata (clic destro sulla lista) è preselezionata
    assert d.cb_stanza.currentData() == "cripta"
    d.cb_stanza.setCurrentIndex(d.cb_stanza.findData("tesoro"))
    # spunta un oggetto e un flag con valore
    for i in range(d.lista_oggetti.count()):
        it = d.lista_oggetti.item(i)
        if it.data(Qt.UserRole) == "lampada":
            it.setCheckState(Qt.Checked)
    albero = d.albero_flag
    for i in range(albero.topLevelItemCount()):
        it = albero.topLevelItem(i)
        if it.text(0) == "lampada_accesa":
            it.setCheckState(0, Qt.Checked)
            it.setText(1, "vero")
    p = d.partenza()
    assert p == {"stanza": "tesoro", "inventario": ["lampada"],
                 "flags": {"lampada_accesa": True}}


def test_flag_noti_include_quelli_delle_regole():
    """La scelta dei flag nel «Prova da…» deve offrire anche i flag che
    nascono solo durante il gioco (impostati dalle regole), non solo quelli
    iniziali."""
    m = carica_mondo(str(AVV / "caverna.json"))
    noti = A.flag_noti(m)
    assert set(m.flags) <= set(noti)


def test_editor_ha_prova_da(qtbot):
    """L'editor offre «Prova da…» accanto a «Prova l'avventura…»."""
    e = Editor(str(AVV / "caverna.json"))
    qtbot.addWidget(e)
    azioni = [a.text() for m in e.menuBar().findChildren(QMenu)
              for a in m.actions()]
    assert any("Prova da" in t for t in azioni), azioni


def test_player_colonna_di_lettura_limitata(qtbot):
    """Su finestre larghe il testo non deve stendersi da bordo a bordo
    (righe chilometriche, faticose da leggere): la colonna si ferma a una
    larghezza comoda e resta centrata. Su finestre strette usa tutto."""
    p = Player(str(AVV / "faro.json"))
    qtbot.addWidget(p)
    p.show()
    p.resize(1600, 700)
    QApplication.processEvents()
    assert p.vista.viewport().width() <= 760, p.vista.viewport().width()
    p.resize(640, 700)
    QApplication.processEvents()
    assert p.vista.viewport().width() >= 560, p.vista.viewport().width()


def test_player_dimensione_testo(qtbot, monkeypatch, tmp_path):
    """La dimensione del testo si regola (più grande / più piccola / normale)
    e viene ricordata tra le sessioni."""
    from PySide6.QtCore import QSettings
    import gui.player as gp
    ini = str(tmp_path / "prova.ini")
    monkeypatch.setattr(gp, "_impostazioni",
                        lambda: QSettings(ini, QSettings.IniFormat))
    p = Player(str(AVV / "faro.json"))
    qtbot.addWidget(p)
    assert p.dim_testo == 16
    p._cambia_dim(+2)
    assert p.dim_testo == 18
    assert "font-size:18px" in p.vista.toHtml()
    # una nuova finestra ricorda la scelta
    p2 = Player(str(AVV / "faro.json"))
    qtbot.addWidget(p2)
    assert p2.dim_testo == 18
    p2._dim_normale()
    assert p2.dim_testo == 16


# un PNG 1×1 valido, per non dipendere da QPixmap (che esige QApplication)
_PNG_MINIMO = __import__("base64").b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8"
    "z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


def _avventura_con_immagine(tmp_path, con_file=True):
    """Avventura minima: l'atrio ha un'illustrazione, la cella no."""
    import json
    if con_file:
        (tmp_path / "atrio.png").write_bytes(_PNG_MINIMO)
    dati = {
        "meta": {"titolo": "Figure", "stanza_iniziale": "atrio"},
        "stanze": {
            "atrio": {"nome": "Atrio", "desc": "Un atrio.",
                      "uscite": {"nord": "cella"}, "immagine": "atrio.png"},
            "cella": {"nome": "Cella", "desc": "Una cella.",
                      "uscite": {"sud": "atrio"}},
        },
    }
    f = tmp_path / "figure.json"
    f.write_text(json.dumps(dati), encoding="utf-8")
    return str(f)


def test_player_illustrazione_stanza(qtbot, tmp_path):
    """La stanza con illustrazione la mostra in un pannello dedicato a fianco
    della trascrizione (mai inline nel QTextEdit); nelle stanze senza immagine
    il pannello collassa. Il percorso è relativo al JSON dell'avventura."""
    p = Player(_avventura_con_immagine(tmp_path))
    qtbot.addWidget(p)
    p.show()
    QApplication.processEvents()
    assert p.immagine.isVisible()
    assert p.immagine.pixmap() and not p.immagine.pixmap().isNull()
    p.input.setText("nord"); p._invia()            # la cella non ha immagine
    QApplication.processEvents()
    assert not p.immagine.isVisible()
    p.input.setText("sud"); p._invia()             # di ritorno nell'atrio
    QApplication.processEvents()
    assert p.immagine.isVisible()


def test_player_illustrazione_a_fianco(qtbot, tmp_path):
    """L'illustrazione occupa una colonna a tutta altezza a sinistra della
    trascrizione, in uno splitter orizzontale regolabile: molto più grande
    della vecchia striscia da 240 px. Senza immagine la colonna collassa e
    il testo riprende tutta la larghezza."""
    from PySide6.QtWidgets import QSplitter
    p = Player(_avventura_con_immagine(tmp_path))
    qtbot.addWidget(p)
    p.show()
    QApplication.processEvents()
    assert isinstance(p.spartizione, QSplitter)
    assert p.spartizione.orientation() == Qt.Horizontal
    assert p.spartizione.indexOf(p.immagine) == 0      # immagine a sinistra
    assert p.immagine.height() > 300                   # niente tetto a 240 px
    larghezza_vista = p.vista.width()
    p.input.setText("nord"); p._invia()                # la cella: senza immagine
    QApplication.processEvents()
    assert not p.immagine.isVisible()
    assert p.vista.width() > larghezza_vista           # il testo si riallarga


def test_player_illustrazione_mancante_o_assente(qtbot, tmp_path):
    """File dell'immagine sparito: il player non deve rompersi, solo
    collassare il pannello. Un'avventura senza immagini (retrocompatibile)
    non mostra mai il pannello."""
    p = Player(_avventura_con_immagine(tmp_path, con_file=False))
    qtbot.addWidget(p)
    p.show()
    QApplication.processEvents()
    assert not p.immagine.isVisible()
    p2 = Player(str(AVV / "faro.json"))
    qtbot.addWidget(p2)
    p2.show()
    QApplication.processEvents()
    assert not p2.immagine.isVisible()


def test_player_illustrazioni_disattivabili(qtbot, monkeypatch, tmp_path):
    """Visualizza ▸ Illustrazioni spegne il pannello e la scelta viene
    ricordata tra le sessioni."""
    from PySide6.QtCore import QSettings
    import gui.player as gp
    ini = str(tmp_path / "prova.ini")
    monkeypatch.setattr(gp, "_impostazioni",
                        lambda: QSettings(ini, QSettings.IniFormat))
    avventura = _avventura_con_immagine(tmp_path)
    p = Player(avventura)
    qtbot.addWidget(p)
    p.show()
    QApplication.processEvents()
    assert p.immagine.isVisible()
    p._imposta_illustrazioni(False)
    QApplication.processEvents()
    assert not p.immagine.isVisible()
    p2 = Player(avventura)                         # nuova sessione: ricorda
    qtbot.addWidget(p2)
    p2.show()
    QApplication.processEvents()
    assert not p2.immagine.isVisible()
    p2._imposta_illustrazioni(True)
    QApplication.processEvents()
    assert p2.immagine.isVisible()


def test_copia_immagine_accanto(tmp_path):
    """La scelta di un'illustrazione copia il file accanto al JSON
    dell'avventura (portabilità) e restituisce il nome relativo da scrivere
    nel campo `immagine`."""
    from gui.editor import copia_immagine_accanto
    src_dir = tmp_path / "altrove"; src_dir.mkdir()
    src = src_dir / "torre.png"; src.write_bytes(b"png finto")
    avv_dir = tmp_path / "gioco"; avv_dir.mkdir()
    json_path = avv_dir / "avv.json"
    nome = copia_immagine_accanto(str(src), str(json_path))
    assert nome == "torre.png"
    assert (avv_dir / "torre.png").read_bytes() == b"png finto"
    # file già accanto al JSON: nessuna copia, solo il nome relativo
    nome2 = copia_immagine_accanto(str(avv_dir / "torre.png"), str(json_path))
    assert nome2 == "torre.png"
    # avventura mai salvata: non esiste una cartella dove copiare
    with pytest.raises(ValueError):
        copia_immagine_accanto(str(src), None)


def test_editor_immagine_stanza(qtbot, monkeypatch, tmp_path):
    """Nel form della stanza si sceglie un'illustrazione (copiata accanto al
    JSON), appare la miniatura, e Applica scrive il campo; «Togli» la
    rimuove dalla stanza senza cancellare il file."""
    from PySide6.QtGui import QPixmap
    src_dir = tmp_path / "scelta"; src_dir.mkdir()
    img = src_dir / "sala.png"
    pm = QPixmap(32, 32); pm.fill(Qt.darkGreen); pm.save(str(img))

    e = Editor(None)
    qtbot.addWidget(e)
    e.mondo = mondo_semplice()
    e.percorso = str(tmp_path / "avv.json")
    e._carica_in_ui()                     # categoria Stanze → form di «sala»
    dett = e.dettaglio.widget()
    campo = dett.findChild(QLineEdit, "campo_immagine")
    assert campo is not None and campo.text() == ""
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        lambda *a, **k: (str(img), ""))
    dett.findChild(QPushButton, "sfoglia_immagine").click()
    assert campo.text() == "sala.png"
    assert (tmp_path / "sala.png").exists()        # copiata accanto al JSON
    miniatura = dett.findChild(QLabel, "miniatura_immagine")
    assert miniatura.pixmap() and not miniatura.pixmap().isNull()
    dett.findChild(QPushButton, "primario").click()          # Applica
    assert e.mondo.stanze["sala"].immagine == "sala.png"
    dett.findChild(QPushButton, "togli_immagine").click()
    assert campo.text() == ""
    dett.findChild(QPushButton, "primario").click()
    assert e.mondo.stanze["sala"].immagine == ""
    assert (tmp_path / "sala.png").exists()        # il file resta


def test_player_cornice_input_segue_il_fuoco(qtbot):
    """La riga di comando è in una cornice che si accende quando ha il fuoco,
    per guidare l'occhio al punto d'interazione."""
    p = Player(str(AVV / "faro.json"))
    qtbot.addWidget(p)
    p.show()
    p.input.setFocus()
    QApplication.processEvents()
    assert p.cornice_input.property("fuoco") is True
    p.vista.setFocus()
    QApplication.processEvents()
    assert p.cornice_input.property("fuoco") is False


def test_player_gerarchia_tipografica(qtbot):
    """Nella trascrizione il nome della stanza spicca (più grande e in
    grassetto), il titolo del gioco perde i «==» decorativi e la riga delle
    uscite è in tono muto. La classificazione usa le convenzioni testuali
    del motore e i nomi delle stanze del mondo caricato."""
    p = Player(str(AVV / "caverna.json"))
    qtbot.addWidget(p)
    p._anim_finisci()
    h = p.vista.toHtml()
    assert "INGRESSO DELLA CAVERNA" in h
    da_titolo = h.split("INGRESSO DELLA CAVERNA")[0].rsplit("<", 1)[-1]
    assert "font-weight:700" in da_titolo, da_titolo
    # il titolo del gioco appare senza i "==" attorno
    assert "== La Caverna della Moneta ==" not in p.vista.toPlainText()
    assert "La Caverna della Moneta" in p.vista.toPlainText()
    # la riga delle uscite è nel colore muto del tema
    from gui import tema as T
    da_uscite = h.split("Uscite:")[0].rsplit("<", 1)[-1]
    assert T.PALETTE["scuro"]["muto"] in da_uscite, da_uscite


def test_player_accento_avventura(qtbot, tmp_path):
    """Un'avventura può dichiarare un colore accento nei metadati
    («colore»): il player lo usa per prompt e titolo. Un valore non valido
    viene ignorato."""
    m = carica_mondo(str(AVV / "caverna.json"))
    m.meta["colore"] = "#c04030"
    f = str(tmp_path / "tinta.json")
    salva_mondo(m, f)
    p = Player(f)
    qtbot.addWidget(p)
    assert "#c04030" in p.styleSheet()
    m.meta["colore"] = "rosso; } * { color: red"      # non valido: ignorato
    f2 = str(tmp_path / "brutta.json")
    salva_mondo(m, f2)
    p2 = Player(f2)
    qtbot.addWidget(p2)
    assert "rosso" not in p2.styleSheet()


def test_player_carattere_con_grazie(qtbot, monkeypatch, tmp_path):
    """Il corpo del racconto può usare un carattere con grazie (opzione in
    Visualizza), ricordato tra le sessioni."""
    from PySide6.QtCore import QSettings
    import gui.player as gp
    ini = str(tmp_path / "prova.ini")
    monkeypatch.setattr(gp, "_impostazioni",
                        lambda: QSettings(ini, QSettings.IniFormat))
    p = Player(str(AVV / "caverna.json"))
    qtbot.addWidget(p)
    assert p.grazie is False
    p._imposta_grazie(True)
    assert "serif" in p.vista.toHtml()
    p2 = Player(str(AVV / "caverna.json"))
    qtbot.addWidget(p2)
    assert p2.grazie is True


def test_player_stanza_nella_barra_di_stato(qtbot):
    """La barra di stato mostra anche la stanza corrente, per orientarsi
    senza ridare «guarda»."""
    p = Player(str(AVV / "caverna.json"))
    qtbot.addWidget(p)
    assert "Ingresso della caverna" in p.stato.text()
    p._anim_finisci()
    p.input.setText("nord"); p._invia()
    assert "Ingresso della caverna" not in p.stato.text()


def test_compila_nome_sicuro():
    from gui import compila
    assert compila.nome_sicuro("La Caverna! #1") == "La_Caverna_1"
    assert compila.nome_sicuro(None) == "Avventura"
    assert compila.nome_sicuro("   ") == "Avventura"


def test_compila_prepara(tmp_path):
    import ast
    from gui import compila
    from advcore import carica_mondo
    m = carica_mondo(str(AVV / "faro.json"))
    spec, nome = compila.prepara(m, str(tmp_path))
    assert nome == "Il_Faro_Abbandonato"
    assert (tmp_path / "avventura.json").exists()
    src = open(spec, encoding="utf-8").read()
    ast.parse(src)                                  # lo spec è Python valido
    assert "avventura.json" in src and "pasifae.ico" in src
    assert f"name={nome!r}" in src


def test_compila_prepara_con_immagini(tmp_path):
    """Le illustrazioni riferite dalle stanze vengono copiate nel progetto di
    build ed elencate nello spec (datas): il gioco compilato le porta con sé.
    Un'immagine mancante non blocca la compilazione; senza illustrazioni lo
    spec resta com'era."""
    import ast
    from gui import compila
    origine = _avventura_con_immagine(tmp_path)
    m = carica_mondo(origine)
    m.stanze["cella"].immagine = "sparita.png"     # riferita ma senza file
    build = tmp_path / "build"
    spec, _ = compila.prepara(m, str(build), origine=origine)
    assert (build / "atrio.png").exists()
    src = open(spec, encoding="utf-8").read()
    ast.parse(src)                                  # lo spec è Python valido
    assert "atrio.png" in src
    assert "sparita.png" not in src
    # avventura senza illustrazioni: nessun file extra (retrocompatibile)
    m2 = carica_mondo(str(AVV / "faro.json"))
    spec2, _ = compila.prepara(m2, str(tmp_path / "build2"), origine=str(AVV / "faro.json"))
    assert ".png" not in open(spec2, encoding="utf-8").read()


def test_player_senza_avventura_inclusa():
    from gui import player
    assert player._avventura_inclusa() is None      # da sorgente: nessun bundle


def test_condizioni_logiche_motore():
    from advcore.rules import valuta_condizioni as V
    m = Mondo()
    m.flags = {"hp": 5, "porta": True, "chiave": False}
    assert V([{"flag": "hp", "minore": 10}], m) is True
    assert V([{"flag": "hp", "maggiore_uguale": 6}], m) is False
    assert V([{"non": {"flag": "chiave"}}], m) is True
    assert V([{"oppure": [{"flag": "chiave"}, {"flag": "porta"}]}], m) is True
    assert V([{"non": {"flag": "chiave"}},
              {"oppure": [{"flag": "porta"}, {"flag": "hp", "maggiore": 10}]}], m) is True


# --------------------------- duplica / elimina regola ---------------------------

def test_duplica_stanza_oggetto_regola(qtbot, monkeypatch):
    e = Editor(str(AVV / "caverna.json"))
    qtbot.addWidget(e)
    # stanza
    e.lista_cat.setCurrentRow(CATEGORIE.index("Stanze"))
    e.lista_el.setCurrentRow(0)
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("ingresso_bis", True))
    e._duplica()
    assert "ingresso_bis" in e.mondo.stanze
    # oggetto (props copiate in profondità)
    e.lista_cat.setCurrentRow(CATEGORIE.index("Oggetti"))
    e.lista_el.setCurrentRow(0)
    oid0 = list(e.mondo.oggetti)[0]
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("oggetto_bis", True))
    e._duplica()
    assert "oggetto_bis" in e.mondo.oggetti
    assert e.mondo.oggetti["oggetto_bis"].props is not e.mondo.oggetti[oid0].props
    # regola
    e.lista_cat.setCurrentRow(CATEGORIE.index("Regole"))
    n = len(e.mondo.regole)
    e.lista_el.setCurrentRow(0)
    e._duplica()
    assert len(e.mondo.regole) == n + 1


def test_elimina_regola(qtbot, monkeypatch):
    """Le regole sono una lista: l'eliminazione non deve sollevare eccezioni."""
    e = Editor(str(AVV / "caverna.json"))
    qtbot.addWidget(e)
    e.lista_cat.setCurrentRow(CATEGORIE.index("Regole"))
    n = len(e.mondo.regole)
    assert n > 0
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.Yes)
    e.lista_el.setCurrentRow(0)
    e._elimina()
    assert len(e.mondo.regole) == n - 1


# --------------------------- regressione: Invio nell'anteprima ---------------------------

def test_anteprima_invio_processa_comando(qtbot):
    """Premere Invio nell'anteprima deve inviare il comando (non i pulsanti)."""
    f = FinestraGioco(mondo_semplice(), "scuro")
    qtbot.addWidget(f)
    f.show()
    mosse0 = f.mondo.mosse
    f.input.setFocus()
    qtbot.keyClicks(f.input, "prendi lampada")
    qtbot.keyClick(f.input, Qt.Key_Return)
    assert f.input.text() == ""
    assert f.mondo.mosse == mosse0 + 1
    assert f.mondo.oggetti["lampada"].posizione == "inventario"


def test_anteprima_non_altera_originale(qtbot):
    m = mondo_semplice()
    f = FinestraGioco(m, "scuro")
    qtbot.addWidget(f)
    f.input.setText("prendi lampada"); f._invia()
    f.input.setText("nord"); f._invia()
    # la copia avanza, l'originale resta intatto
    assert f.mondo.stanza_corrente == "corridoio"
    assert m.oggetti["lampada"].posizione == "sala"
    assert m.stanza_corrente in ("", "sala")


def test_anteprima_mostra_illustrazione(qtbot, tmp_path):
    """La finestra «Prova l'avventura» mostra l'illustrazione della stanza
    corrente, risolta rispetto al JSON dell'avventura in modifica; senza
    percorso (avventura mai salvata) il pannello resta collassato."""
    percorso = _avventura_con_immagine(tmp_path)
    m = carica_mondo(percorso)
    f = FinestraGioco(m, "scuro", percorso=percorso)
    qtbot.addWidget(f)
    f.show()
    QApplication.processEvents()
    assert f.immagine.isVisible()
    f.input.setText("nord"); f._invia()            # la cella non ha immagine
    QApplication.processEvents()
    assert not f.immagine.isVisible()
    f2 = FinestraGioco(m, "scuro")                 # nessun percorso noto
    qtbot.addWidget(f2)
    f2.show()
    QApplication.processEvents()
    assert not f2.immagine.isVisible()


def test_anteprima_illustrazione_a_fianco(qtbot, tmp_path):
    """Come nel player, l'anteprima mostra l'illustrazione in una colonna
    a tutta altezza a sinistra della trascrizione, in uno splitter
    orizzontale regolabile."""
    from PySide6.QtWidgets import QSplitter
    percorso = _avventura_con_immagine(tmp_path)
    m = carica_mondo(percorso)
    f = FinestraGioco(m, "scuro", percorso=percorso)
    qtbot.addWidget(f)
    f.show()
    QApplication.processEvents()
    assert isinstance(f.spartizione, QSplitter)
    assert f.spartizione.orientation() == Qt.Horizontal
    assert f.spartizione.indexOf(f.immagine) == 0      # immagine a sinistra
    assert f.immagine.height() > 300                   # niente tetto a 240 px


# --------------------------- ricerca / filtri ---------------------------

def test_combo_cerca_filtrabile(qtbot):
    cb = combo_cerca(["lampada_atrio", "chiave_oro", "baule"])
    voci = [cb.itemText(i) for i in range(cb.count())]
    assert voci == ["baule", "chiave_oro", "lampada_atrio"]  # ordinata
    comp = cb.completer()
    assert cb.isEditable()
    assert comp.filterMode() == Qt.MatchContains
    assert comp.caseSensitivity() == Qt.CaseInsensitive


def test_filtro_elementi(qtbot):
    m = Mondo()
    m.stanze["sala"] = Stanza(id="sala", nome="Sala", desc="", uscite={})
    for n in ("gemma_rossa", "gemma_blu", "torcia", "chiave"):
        m.oggetti[n] = Oggetto(id=n, nome=n, nomi=[n], aggettivi=[],
                               posizione="sala", props={})
    e = Editor(None); e.mondo = m
    qtbot.addWidget(e)
    e.lista_cat.setCurrentRow(CATEGORIE.index("Oggetti"))
    e._scegli_categoria(CATEGORIE.index("Oggetti"))
    e.filtro_el.setText("gemma")
    visibili = [e.lista_el.item(i).text() for i in range(e.lista_el.count())
                if not e.lista_el.item(i).isHidden()]
    assert len(visibili) == 2


def test_posizione_include_contenitori(qtbot):
    m = Mondo()
    m.stanze["sala"] = Stanza(id="sala", nome="Sala", desc="", uscite={})
    m.oggetti["cassa"] = Oggetto(id="cassa", nome="cassa", nomi=["cassa"],
                                 aggettivi=[], posizione="sala",
                                 props={"contenitore": True})
    m.oggetti["sasso"] = Oggetto(id="sasso", nome="sasso", nomi=["sasso"],
                                 aggettivi=[], posizione="sala", props={})
    m.oggetti["gemma"] = Oggetto(id="gemma", nome="gemma", nomi=["gemma"],
                                 aggettivi=[], posizione="sala", props={})
    e = Editor(None); e.mondo = m
    qtbot.addWidget(e)
    luoghi = e._opz_luoghi(escludi="gemma")
    assert "cassa" in luoghi          # contenitore incluso
    assert "sasso" not in luoghi      # non-contenitore escluso
    assert "gemma" not in luoghi      # se stesso escluso
    assert "sala" in luoghi and "inventario" in luoghi


# --------------------------- problemi / dove è usato ---------------------------

def test_avventure_ufficiali_senza_problemi():
    for nome in ("faro", "caverna", "duello", "tutorial"):
        m = carica_mondo(str(AVV / f"{nome}.json"))
        assert A.analizza_problemi(m) == [], f"{nome} ha problemi inattesi"


def test_problemi_rilevati():
    m = mondo_semplice()
    m.stanze["sala"].uscite["est"] = "inesistente"
    m.oggetti["lampada"].posizione = "boh"
    testi = " | ".join(p["testo"] for p in A.analizza_problemi(m))
    assert "inesistente" in testi
    assert "boh" in testi


def test_problema_immagine_mancante(tmp_path):
    """Con il percorso del JSON, l'analisi segnala (non grave) le stanze la
    cui illustrazione punta a un file inesistente; senza percorso il
    controllo si salta (non c'è una base per risolvere i nomi)."""
    percorso = _avventura_con_immagine(tmp_path)
    m = carica_mondo(percorso)
    assert A.analizza_problemi(m, percorso=percorso) == []
    m.stanze["cella"].immagine = "sparita.png"
    probs = A.analizza_problemi(m, percorso=percorso)
    assert any("sparita.png" in p["testo"] and p["chiave"] == "cella"
               and not p["grave"] for p in probs), probs
    assert A.analizza_problemi(m) == []            # senza percorso: nessun avviso


def test_dove_usato():
    m = carica_mondo(str(AVV / "caverna.json"))
    usi = A.usi_di(m, "flag", "lampada_accesa")
    assert any("luce" in u["testo"] for u in usi)
    assert any(u["categoria"] == "Regole" for u in usi)


# --------------------------- concatenazione dei puzzle ---------------------------

def _mondo_con_catena():
    """Sala --(nord, se porta_aperta)--> tesoro. La chiave apre la porta,
    entrare nel tesoro dà la vittoria: tre passi concatenati."""
    from advcore.model import Regola
    m = Mondo()
    m.stanze["sala"] = Stanza(id="sala", nome="Sala", desc="Una sala.",
                              uscite={"nord": {"to": "tesoro",
                                               "se": "porta_aperta"}})
    m.stanze["tesoro"] = Stanza(id="tesoro", nome="Tesoro", desc="Oro!",
                                uscite={"sud": "sala"})
    m.meta["stanza_iniziale"] = "sala"
    m.oggetti["chiave"] = Oggetto(id="chiave", nome="chiave", nomi=["chiave"],
                                  aggettivi=[], posizione="sala",
                                  props={"prendibile": True})
    m.regole.append(Regola(
        id="apri_porta",
        quando={"verbo": "usa", "oggetto": "chiave"},
        se=[{"oggetto_in": ["chiave", "inventario"]}],
        allora=[{"set_flag": "porta_aperta"},
                {"stampa": "La porta si apre."}]))
    m.regole.append(Regola(
        id="trionfo",
        quando={"evento": "entra", "stanza": "tesoro"},
        allora=[{"vittoria": "Ce l'hai fatta!"}]))
    return m


def test_catena_puzzle():
    """Ogni passo di avanzamento (regola, uscita condizionata, ...) dichiara
    cosa richiede e cosa produce: da qui si ricostruisce la concatenazione
    dei puzzle a ritroso dai finali."""
    passi = A.catena_puzzle(_mondo_con_catena())
    apri = next(p for p in passi if "apri_porta" in p["titolo"])
    assert ("oggetto", "chiave") in apri["richiede"]
    assert ("flag", "porta_aperta") in apri["produce"]
    assert apri["categoria"] == "Regole" and apri["chiave"] == 0
    uscita = next(p for p in passi if "nord" in p["titolo"])
    assert ("flag", "porta_aperta") in uscita["richiede"]
    assert ("stanza", "tesoro") in uscita["produce"]
    fine = next(p for p in passi if "trionfo" in p["titolo"])
    assert ("stanza", "tesoro") in fine["richiede"]
    assert ("fine", "vittoria") in fine["produce"]
    # le regole senza produzioni (solo testo) non sono passi della catena
    assert not any("stampa" in str(p) and not p["produce"] for p in passi)


def test_catena_puzzle_uguale_falso_non_concatena():
    """«flag uguale a falso» chiede l'ASSENZA del progresso (come «non»):
    non va tra i requisiti. Un confronto con un valore vero invece sì."""
    from advcore.model import Regola
    m = Mondo()
    m.stanze["sala"] = Stanza(id="sala", nome="Sala", desc="Una sala.")
    m.meta["stanza_iniziale"] = "sala"
    m.regole.append(Regola(
        id="meccanismo",
        quando={"verbo": "usa", "oggetto": "leva"},
        se=[{"flag": "porta_aperta", "uguale": False},
            {"flag": "ingranaggi", "uguale": 3}],
        allora=[{"set_flag": "porta_aperta"}]))
    m.oggetti["leva"] = Oggetto(id="leva", nome="leva", nomi=["leva"],
                                aggettivi=[], posizione="sala", props={})
    (passo,) = A.catena_puzzle(m)
    assert ("flag", "porta_aperta") not in passo["richiede"]
    assert ("flag", "ingranaggi") in passo["richiede"]


def test_finestra_catena_puzzle(qtbot):
    """La finestra «Concatenazione dei puzzle» mostra l'albero a ritroso dal
    finale: vittoria ← regola d'ingresso ← raggiungere la stanza ← uscita
    condizionata ← flag ← regola della chiave ← oggetto."""
    from gui.catena import FinestraCatena
    f = FinestraCatena(_mondo_con_catena(), "scuro")
    qtbot.addWidget(f)

    def testi(item):
        out = [item.text(0)]
        for i in range(item.childCount()):
            out += testi(item.child(i))
        return out

    tutti = []
    for i in range(f.albero.topLevelItemCount()):
        tutti += testi(f.albero.topLevelItem(i))
    assert any("vittoria" in t.lower() for t in tutti)
    assert any("apri_porta" in t for t in tutti)
    assert any("chiave" in t for t in tutti)
    assert any("porta_aperta" in t for t in tutti)


def test_menu_concatenazione_puzzle(qtbot):
    """La voce sta nel menu Strumenti dell'editor."""
    e = Editor(None)
    qtbot.addWidget(e)
    voci = [a.text() for top in e.menuBar().actions() if top.menu()
            for a in top.menu().actions()]
    assert any("Concatenazione dei puzzle" in v for v in voci)


# --------------------------- regressione motore: ordine di scarta ---------------------------

def test_scarta_oggetto_rimuove_anche_con_messaggio():
    """scarta_oggetto deve togliere l'oggetto ANCHE quando porta un messaggio
    (il ramo 'stampa' non deve prevalere)."""
    m = mondo_semplice()
    out = []
    from advcore.rules import esegui_effetti
    esegui_effetti([{"scarta_oggetto": "lampada", "stampa": "Si spegne."}], m, out)
    assert m.oggetti["lampada"].posizione == SCARTATO
    assert "Si spegne." in out


def test_timer_dichiarati_nelle_opzioni():
    m = mondo_semplice()
    m.meta["timer"] = ["bomba", "allarme"]
    assert R.opzioni(m)["timer"] == ["allarme", "bomba"]


# --------------------------- mappa trascinabile ---------------------------

def test_mappa_stanze_trascinabili(qtbot):
    """I riquadri delle stanze si trascinano: la posizione finisce in
    meta["editor"]["mappa"] (il motore la ignora), i collegamenti seguono
    il nodo e il rilascio segnala la modifica all'editor."""
    from gui.mappa import PannelloMappa, BOX_W, BOX_H
    m = mondo_semplice()
    chiamate = []
    f = PannelloMappa(m, "scuro", su_modifica=lambda: chiamate.append(1))
    qtbot.addWidget(f)

    nodo = f.nodi["corridoio"]
    prima = nodo.pos()
    nodo.setPos(prima.x() + 300, prima.y() + 120)

    # posizione registrata nei metadati dell'editor
    assert m.meta["editor"]["mappa"]["corridoio"] == [
        round(prima.x() + 300), round(prima.y() + 120)]

    # il collegamento segue: un estremo raggiunge il bordo del nodo spostato
    # (gli item sono persistenti: durante il drag cambia solo la geometria)
    cx = nodo.pos().x() + BOX_W / 2
    cy = nodo.pos().y() + BOX_H / 2
    estremi = []
    for e in f._collegamenti:
        tracciato = e["linea"].path()
        estremi += [tracciato.pointAtPercent(0), tracciato.pointAtPercent(1)]
    assert any(abs(p.x() - cx) <= BOX_W and abs(p.y() - cy) <= BOX_H
               for p in estremi)

    # la modifica è segnalata una volta sola, al rilascio del mouse
    assert not chiamate
    f._fine_trascinamento("corridoio")
    assert chiamate == [1]
    f._fine_trascinamento("corridoio")      # senza nuovo spostamento: silenzio
    assert chiamate == [1]


def test_mappa_posizioni_salvate_e_riordino(qtbot):
    """All'apertura la mappa rispetta le posizioni salvate in meta, il
    round-trip su file le conserva e «Riordina» torna al layout automatico."""
    import tempfile
    from gui.mappa import PannelloMappa
    m = mondo_semplice()
    m.meta["editor"] = {"mappa": {"sala": [40, 60], "corridoio": [420, 200]}}
    f = PannelloMappa(m, "scuro")
    qtbot.addWidget(f)
    assert (f.nodi["sala"].pos().x(), f.nodi["sala"].pos().y()) == (40, 60)
    assert f.nodi["corridoio"].pos().x() == 420

    # le posizioni vivono in meta: sopravvivono a salva/carica senza
    # che il motore ne sappia nulla
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
        percorso = tmp.name
    salva_mondo(m, percorso)
    m2 = carica_mondo(percorso)
    os.unlink(percorso)
    assert m2.meta["editor"]["mappa"]["corridoio"] == [420, 200]

    # «Riordina» dimentica le posizioni manuali e rifà il layout automatico
    f._riordina()
    assert not m.meta.get("editor", {}).get("mappa")
    assert (f.nodi["sala"].pos().x(), f.nodi["sala"].pos().y()) != (40, 60)


def test_mappa_doppio_clic_apre_stanza(qtbot):
    """Doppio clic su un riquadro della mappa: l'editor seleziona quella
    stanza (callback vai_a, come nella Concatenazione dei puzzle) e la
    finestra si chiude."""
    from PySide6.QtCore import QPointF
    from gui.mappa import FinestraMappa, BOX_W, BOX_H
    m = mondo_semplice()
    aperture = []
    f = FinestraMappa(m, "scuro",
                      vai_a=lambda cat, ch: aperture.append((cat, ch)))
    qtbot.addWidget(f)
    f.show()

    p = f.pannello
    nodo = p.nodi["corridoio"]
    centro = p.vista.mapFromScene(nodo.pos() + QPointF(BOX_W / 2, BOX_H / 2))
    qtbot.mouseDClick(p.vista.viewport(), Qt.LeftButton, pos=centro)

    assert aperture == [("Stanze", "corridoio")]
    assert f.isHidden()          # la finestra si è chiusa per lasciare l'editor


def test_mappa_crea_ed_elimina_uscite(qtbot, monkeypatch):
    """Dalla mappa si creano uscite (con ritorno opzionale) e si eliminano;
    una direzione già occupata non viene sovrascritta; ogni cambiamento
    segnala la modifica all'editor."""
    from gui.mappa import PannelloMappa
    m = mondo_semplice()
    m.stanze["cantina"] = Stanza(id="cantina", nome="Cantina", desc="")
    chiamate = []
    f = PannelloMappa(m, "scuro", su_modifica=lambda: chiamate.append(1))
    qtbot.addWidget(f)

    f._crea_uscita("sala", "cantina", "giu", ritorno=True)
    assert m.stanze["sala"].uscite["giu"] == "cantina"
    assert m.stanze["cantina"].uscite["su"] == "sala"       # il ritorno
    assert chiamate

    # direzione già occupata: rifiuto senza sovrascrivere
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    f._crea_uscita("sala", "cantina", "nord", ritorno=False)
    assert m.stanze["sala"].uscite["nord"] == "corridoio"

    f._elimina_uscita("sala", "giu")
    assert "giu" not in m.stanze["sala"].uscite


def test_mappa_trascinamento_destro_crea_uscita(qtbot, monkeypatch):
    """Trascinare col tasto destro da una stanza a un'altra chiede la
    direzione e crea l'uscita."""
    from PySide6.QtCore import QPointF
    from gui.mappa import PannelloMappa, BOX_W, BOX_H
    m = mondo_semplice()
    f = PannelloMappa(m, "scuro")
    qtbot.addWidget(f)
    f.show()
    monkeypatch.setattr(PannelloMappa, "_chiedi_uscita",
                        lambda self, src, dst: ("est", False))

    def vp(sid):
        n = f.nodi[sid]
        return f.vista.mapFromScene(n.pos() + QPointF(BOX_W / 2, BOX_H / 2))

    qtbot.mousePress(f.vista.viewport(), Qt.RightButton, pos=vp("sala"))
    qtbot.mouseMove(f.vista.viewport(), pos=vp("corridoio"))
    qtbot.mouseRelease(f.vista.viewport(), Qt.RightButton,
                       pos=vp("corridoio"))
    # il dialogo è differito a dopo il rilascio (grab Wayland): un giro
    # di event loop prima di verificare
    qtbot.waitUntil(
        lambda: m.stanze["sala"].uscite.get("est") == "corridoio",
        timeout=1000)


def test_mappa_nuova_stanza_dal_canvas(qtbot, monkeypatch):
    """Il clic destro sul canvas crea una stanza nel punto scelto (posizione
    nei metadati, nodo nella scena); id duplicato rifiutato."""
    from PySide6.QtCore import QPointF
    from gui.mappa import PannelloMappa
    m = mondo_semplice()
    chiamate = []
    f = PannelloMappa(m, "scuro", su_modifica=lambda: chiamate.append(1))
    qtbot.addWidget(f)

    f._crea_stanza("cantina", "Cantina", QPointF(500, 300))
    assert "cantina" in m.stanze and m.stanze["cantina"].nome == "Cantina"
    assert m.meta["editor"]["mappa"]["cantina"] == [500, 300]
    assert "cantina" in f.nodi
    assert chiamate

    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    f._crea_stanza("sala", "Doppione", QPointF(0, 0))
    assert m.stanze["sala"].nome == "Sala"                  # intatta


def test_mappa_menu_contestuale_non_scavalca_i_nodi(qtbot, monkeypatch):
    """Su Linux il menu contestuale scatta alla PRESSIONE del destro, subito
    dopo il press che ha avviato il collegamento: con la linea provvisoria
    sotto il cursore non deve aprirsi il menu del canvas (regressione: si
    apriva sempre «Nuova stanza», mai il menu delle uscite né il drag)."""
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QContextMenuEvent
    from gui.mappa import PannelloMappa, BOX_W, BOX_H
    m = mondo_semplice()
    f = PannelloMappa(m, "scuro")
    qtbot.addWidget(f)
    f.show()
    canvas, stanza = [], []
    monkeypatch.setattr(PannelloMappa, "_menu_canvas",
                        lambda self, g, s: canvas.append(s))
    monkeypatch.setattr(PannelloMappa, "_menu_stanza",
                        lambda self, sid, p: stanza.append(sid))

    def vp(sid):
        n = f.nodi[sid]
        return f.vista.mapFromScene(n.pos() + QPointF(BOX_W / 2, BOX_H / 2))

    # contesto sul nodo, a riposo: niente menu del canvas
    f.vista.contextMenuEvent(
        QContextMenuEvent(QContextMenuEvent.Mouse, vp("sala"),
                          f.vista.viewport().mapToGlobal(vp("sala"))))
    assert not canvas

    # press destro sul nodo: parte il collegamento; il menu contestuale
    # che arriva subito dopo non deve aprire «Nuova stanza»
    qtbot.mousePress(f.vista.viewport(), Qt.RightButton, pos=vp("sala"))
    assert f._collegamento_da == "sala"
    f.vista.contextMenuEvent(
        QContextMenuEvent(QContextMenuEvent.Mouse, vp("sala"),
                          f.vista.viewport().mapToGlobal(vp("sala"))))
    assert not canvas

    # rilascio fermo: menu delle uscite della stanza (differito)
    qtbot.mouseRelease(f.vista.viewport(), Qt.RightButton, pos=vp("sala"))
    qtbot.waitUntil(lambda: stanza == ["sala"], timeout=1000)

    # sul vuoto, a riposo: il menu del canvas sì
    lontano = f.vista.mapFromScene(QPointF(-400, -400))
    f.vista.contextMenuEvent(
        QContextMenuEvent(QContextMenuEvent.Mouse, lontano,
                          f.vista.viewport().mapToGlobal(lontano)))
    assert len(canvas) == 1


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
