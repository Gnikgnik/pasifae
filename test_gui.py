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
    """La stanza con illustrazione la mostra in un pannello dedicato sopra la
    trascrizione (mai inline nel QTextEdit); nelle stanze senza immagine il
    pannello collassa. Il percorso è relativo al JSON dell'avventura."""
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


def test_dove_usato():
    m = carica_mondo(str(AVV / "caverna.json"))
    usi = A.usi_di(m, "flag", "lampada_accesa")
    assert any("luce" in u["testo"] for u in usi)
    assert any(u["categoria"] == "Regole" for u in usi)


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


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
