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
    QComboBox, QInputDialog, QFileDialog, QMessageBox,
)

from advcore import (  # noqa: E402
    carica_mondo, salva_mondo, Mondo, Motore, Stanza, Oggetto, Regola,
)
from advcore.model import SCARTATO  # noqa: E402
from gui.editor import Editor, DialogoVoce, combo_cerca, CATEGORIE  # noqa: E402
from gui import regole as R  # noqa: E402
from gui import analisi as A  # noqa: E402
from gui.anteprima import FinestraGioco  # noqa: E402
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
