# SPDX-License-Identifier: GPL-3.0-or-later
"""Test dell'editor senza terminale.

Verifica la logica pura (parsing valori, CSV, riassunti, clonazione) e, soprattutto,
che le schermate urwid si COSTRUISCANO e si DISEGNINO senza errori: ogni vista
viene renderizzata su una canvas di dimensione fissa (cosa che non richiede una
TTY) e se ne controlla il contenuto. Eseguibile con:  python3 test_editor.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from advcore import carica_mondo
from edit import (EditorApp, CampoScelta, parse_valore, csv_a_lista,
                  lista_a_csv, clona_mondo, riassunto_condizione,
                  riassunto_effetto, tipo_condizione, tipo_effetto)


def _testo(widget, dim=(100, 40)) -> str:
    """Disegna un widget box su una canvas finta e ne restituisce il testo."""
    canvas = widget.render(dim, focus=True)
    return "\n".join(r.decode("utf-8", "replace") for r in canvas.text)


def test_parse_valore():
    assert parse_valore("true") is True
    assert parse_valore("Falso") is False
    assert parse_valore("42") == 42
    assert parse_valore("ciao") == "ciao"


def test_csv():
    assert csv_a_lista("a, b ,c") == ["a", "b", "c"]
    assert csv_a_lista("  ") == []
    assert lista_a_csv(["x", "y"]) == "x, y"


def test_riassunti_e_tipi():
    assert "porta" in riassunto_condizione({"flag": "porta", "uguale": True})
    assert "VITTORIA" in riassunto_effetto({"vittoria": "ok"})
    assert tipo_condizione({"oggetto_in": ["a", "b"]}) == "oggetto_in"
    assert tipo_effetto({"sposta_oggetto": "x", "a": "y"}) == "sposta_oggetto"


def test_clona_indipendente():
    m = carica_mondo("avventure/caverna.json")
    c = clona_mondo(m)
    c.stanze["ingresso"].nome = "MODIFICATO"
    c.flags["porta_aperta"] = True
    assert m.stanze["ingresso"].nome != "MODIFICATO"   # l'originale non cambia
    assert m.flags["porta_aperta"] is False


def _app():
    return EditorApp(carica_mondo("avventure/caverna.json"),
                     "avventure/caverna.json")


def test_render_home():
    app = _app()
    app.push(app.vista_home, "")
    t = _testo(app.frame)
    assert "Stanze" in t and "Regole" in t and "Anteprima" in t, t


def test_render_form_stanza():
    app = _app()
    app.stack.append((app.vista_home, ""))
    w = app.form_stanza("ingresso")
    t = _testo(w)
    assert "Uscite" in t and "buia" in t, t


def test_render_form_oggetto():
    app = _app()
    w = app.form_oggetto("lampada")
    t = _testo(w)
    assert "prendibile" in t and "Proprietà" in t, t


def test_render_form_regola():
    app = _app()
    app.stack.append((app.vista_home, ""))
    app.apri_regola(2)                      # la regola della moneta nella fessura
    t = _testo(app.frame)
    assert "QUANDO" in t and "ALLORA" in t and "ALTRIMENTI" in t, t


def test_render_anteprima():
    app = _app()
    w = app.vista_anteprima()
    t = _testo(w)
    assert "INGRESSO DELLA CAVERNA" in t, t


def test_salva_oggetto_nuovo():
    import urwid
    app = _app()
    c = {
        "id": urwid.Edit("", "gemma"),
        "nome": urwid.Edit("", "gemma luminosa"),
        "nomi": urwid.Edit("", "gemma, pietra"),
        "aggettivi": urwid.Edit("", "luminosa"),
        "posizione": CampoScelta(app, "posizione", "tesoro", app.opz_luoghi),
        "desc": urwid.Edit("", "brilla di luce propria"),
        "in_stanza": urwid.Edit("", ""),
        "prendibile": urwid.CheckBox("", True),
        "scenario": urwid.CheckBox("", False),
        "contenitore": urwid.CheckBox("", False),
        "aperto": urwid.CheckBox("", False),
        "indossabile": urwid.CheckBox("", False),
        "png": urwid.CheckBox("", False),
        "combattente": urwid.CheckBox("", False),
        "hp": urwid.Edit("", "10"),
        "attacco": urwid.Edit("", "3"),
        "difesa": urwid.Edit("", "1"),
        "fuga": urwid.CheckBox("", True),
        "intro_scontro": urwid.Edit("", ""),
        "luce_on": urwid.CheckBox("", True),
        "luce_flag": app._campo_flag("flag", ""),
        "_props_orig": {},
    }
    app._salva_oggetto(c, nuovo=True)
    o = app.mondo.oggetti["gemma"]
    assert o.posizione == "tesoro"
    assert o.props.get("prendibile") is True
    assert o.props.get("luce") is True          # luce sempre accesa (flag vuoto)
    assert "pietra" in o.nomi


def test_salva_condizione_flag():
    import urwid
    from edit import CampoFlag
    app = _app()
    app._reg = {"se": []}
    app.mondo.flags["porta_aperta"] = False
    c = {
        "flag": CampoFlag(app, "flag", "porta_aperta", app.opz_flag),
        "op": CampoScelta(app, "op", "uguale", lambda: []),
        "valore": urwid.Edit("", "true"),
    }
    app._salva_condizione("flag", None, c)
    assert app._reg["se"][0] == {"flag": "porta_aperta", "uguale": True}


def test_campo_flag_nuovo_autodichiara():
    app = _app()
    app.mondo.flags = {}
    cf = app._campo_flag("flag", "")
    cf._nuovo("segreto")
    assert cf.get() == "segreto"
    assert "segreto" in app.mondo.flags        # auto-dichiarato


def test_salva_regola_nuova():
    import urwid
    app = _app()
    n = len(app.mondo.regole)
    app._reg_idx = None
    app._reg = {"id": "", "quando": {"verbo": "prendi", "oggetto": "calice"},
                "se": [], "allora": [{"vittoria": "ok"}], "altrimenti": []}
    app._reg_e_id = urwid.Edit("", "mia_regola")
    app._salva_regola()
    assert len(app.mondo.regole) == n + 1
    r = app.mondo.regole[-1]
    assert r.id == "mia_regola" and r.quando["verbo"] == "prendi"


def test_render_verifica_pulita():
    app = _app()
    app.stack.append((app.vista_home, ""))
    t = _testo(app.vista_verifica())
    assert "Nessun problema" in t, t


def test_verifica_segnala_e_naviga():
    app = _app()
    app.stack.append((app.vista_home, ""))
    # rompo un'uscita e verifico che compaia nella schermata
    app.mondo.stanze["ingresso"].uscite["nord"] = "fantasma"
    t = _testo(app.vista_verifica())
    assert "fantasma" in t and "errore" in t, t
    # il salto al problema apre il form della stanza colpevole
    from advcore import valida
    pr = next(p for p in valida(app.mondo)
              if p.categoria == "stanza" and "fantasma" in p.messaggio)
    prima = len(app.stack)
    app._vai_problema(pr)
    assert len(app.stack) == prima + 1
    assert "Uscite" in _testo(app.frame)


def test_salva_oggetto_conserva_dialogo():
    import urwid
    app = _app()
    # il gnomo ha un dialogo: salvandolo dall'editor non deve sparire
    orig = dict(app.mondo.oggetti["gnomo"].props)
    c = {
        "id": urwid.Edit("", "gnomo"),
        "nome": urwid.Edit("", "gnomo barbuto"),
        "nomi": urwid.Edit("", "gnomo"),
        "aggettivi": urwid.Edit("", "barbuto"),
        "posizione": CampoScelta(app, "posizione", "ingresso", app.opz_luoghi),
        "desc": urwid.Edit("", orig.get("desc", "")),
        "in_stanza": urwid.Edit("", ""),
        "prendibile": urwid.CheckBox("", False),
        "scenario": urwid.CheckBox("", False),
        "contenitore": urwid.CheckBox("", False),
        "aperto": urwid.CheckBox("", False),
        "indossabile": urwid.CheckBox("", False),
        "png": urwid.CheckBox("", True),
        "combattente": urwid.CheckBox("", False),
        "hp": urwid.Edit("", "10"),
        "attacco": urwid.Edit("", "3"),
        "difesa": urwid.Edit("", "1"),
        "fuga": urwid.CheckBox("", True),
        "intro_scontro": urwid.Edit("", ""),
        "luce_on": urwid.CheckBox("", False),
        "luce_flag": app._campo_flag("flag", ""),
        "_props_orig": orig,
    }
    app._salva_oggetto(c, nuovo=False)
    props = app.mondo.oggetti["gnomo"].props
    assert props.get("png") is True
    assert "dialogo" in props and len(props["dialogo"]) == 2
    assert "saluto" in props


def test_render_dialogo():
    app = _app()
    app.stack.append((app.vista_home, ""))
    t = _testo(app.vista_dialogo("gnomo"))
    assert "Dialogo" in t and "Chiedi del passaggio" in t, t


def test_render_form_battuta():
    app = _app()
    app.stack.append((app.vista_home, ""))
    app.vista_dialogo("gnomo")          # inizializza la copia di lavoro
    app._apri_battuta(0)                 # apre la prima battuta
    t = _testo(app.frame)
    assert "Battuta" in t and "SE" in t and "ALLORA" in t, t


def test_salva_dialogo_scrive_props():
    app = _app()
    app._dlg_oid = "gnomo"
    app._dlg = {"saluto": "Salve!",
                "battute": [{"etichetta": "Chiedi", "testo": "Risposta",
                             "se": [], "allora": [], "una_volta": False}]}
    app._harvest = None
    app._salva_dialogo("gnomo")
    props = app.mondo.oggetti["gnomo"].props
    assert props.get("png") is True
    assert props.get("saluto") == "Salve!"
    assert len(props["dialogo"]) == 1
    assert props["dialogo"][0]["etichetta"] == "Chiedi"


def test_salva_dialogo_vuoto_rimuove():
    app = _app()
    app._dlg_oid = "gnomo"
    app._dlg = {"saluto": "", "battute": []}
    app._harvest = None
    app._salva_dialogo("gnomo")
    assert "dialogo" not in app.mondo.oggetti["gnomo"].props


def test_cerca():
    app = _app()
    assert app._cerca("") == []
    ris = app._cerca("lampada")
    assert any(cat == "oggetto" for _, cat, _ in ris)
    # cerca su testo della descrizione di una stanza
    assert any(cat == "stanza" for _, cat, _ in app._cerca("caverna"))
    # cerca un verbo
    assert any(cat == "verbo" for _, cat, _ in app._cerca("prendi"))


def test_render_cerca():
    app = _app()
    app.stack.append((app.vista_home, ""))
    app._query = "gnomo"
    t = _testo(app.vista_cerca())
    assert "gnomo" in t and "risultat" in t.lower(), t


def test_duplica_oggetto():
    app = _app()
    app.stack.append((app.vista_home, ""))
    app._duplica_oggetto("lampada")
    assert "lampada_copia" in app.mondo.oggetti
    # la copia è indipendente dall'originale
    app.mondo.oggetti["lampada_copia"].props["prendibile"] = False
    assert app.mondo.oggetti["lampada"].props.get("prendibile") is True


def test_duplica_stanza_e_verbo():
    app = _app()
    app.stack.append((app.vista_home, ""))
    app._duplica_stanza("ingresso")
    assert "ingresso_copia" in app.mondo.stanze
    app._duplica_verbo("prendi")
    assert "prendi_copia" in app.mondo.verbi


def test_nuovo_id_evita_collisioni():
    esistenti = {"x_copia", "x_copia2"}
    assert EditorApp._nuovo_id("x", esistenti) == "x_copia3"


def test_render_mappa():
    app = _app()
    app.stack.append((app.vista_home, ""))
    t = _testo(app.vista_mappa())
    assert "MAPPA" in t and "Oggetti per stanza" in t, t


def test_tab_sposta_il_fuoco():
    import urwid
    from edit import ListBoxTab
    righe = [urwid.Text("intestazione"),
             urwid.AttrMap(urwid.Button("uno"), "x"),
             urwid.Text("separatore"),
             urwid.AttrMap(urwid.Button("due"), "x")]
    lb = ListBoxTab(urwid.SimpleFocusListWalker(righe))
    lb.render((30, 8), focus=True)
    assert lb.focus_position == 1
    lb.keypress((30, 8), "tab")
    assert lb.focus_position == 3          # salta il Text non selezionabile
    lb.keypress((30, 8), "tab")
    assert lb.focus_position == 1          # ritorno a capo
    lb.keypress((30, 8), "shift tab")
    assert lb.focus_position == 3


def test_opz_direzioni_chiuse():
    app = _app()
    dirs = [v for _, v in app.opz_direzioni()]
    assert dirs == ["nord", "sud", "est", "ovest", "su", "giu", "dentro", "fuori"]


def test_salva_meta_versione_gioco():
    import urwid
    app = _app()
    app.stack.append((app.vista_home, "Home"))
    c = {"titolo": urwid.Edit("", "T"), "autore": urwid.Edit("", "A"),
         "versione": urwid.Edit("", "2.3.0"), "intro": urwid.Edit("", "I"),
         "stanza_iniziale": CampoScelta(app, "s", "ingresso", app.opz_stanze)}
    app._salva_meta(c)
    assert app.mondo.meta["versione"] == "2.3.0"


def test_render_meta_mostra_versione():
    app = _app()
    app.stack.append((app.vista_home, "Home"))
    app.mondo.meta["versione"] = "0.9.1"
    t = _testo(app.vista_meta())
    assert "versione del gioco" in t and "0.9.1" in t


def test_verbi_predefiniti_in_elenco_e_selettore():
    app = _app()
    # 'aiuto' è predefinito e la caverna non lo dichiara
    assert "aiuto" not in app.mondo.verbi
    t = _testo(app.vista_verbi())
    assert "predefinito" in t and "aiuto" in t
    assert "aiuto" in [v for _, v in app.opz_verbi()]


def test_verbo_predefinito_sola_lettura():
    app = _app()
    app.stack.append((app.vista_home, "Home"))
    t = _testo(app.form_verbo("aiuto"))
    assert "predefinito" in t.lower()
    assert "Salva" not in t and "Elimina" not in t


def test_uscita_bloccata_costruzione():
    app = _app()
    app._lav_uscite = [{"dir": "ovest", "to": "ingresso", "se": "porta",
                        "bloccata": "Sbarrato!"}]
    assert app._uscite_da_lav()["ovest"] == {
        "to": "ingresso", "se": "porta", "bloccata": "Sbarrato!"}
    # senza flag -> uscita semplice (il messaggio viene ignorato)
    app._lav_uscite = [{"dir": "est", "to": "sala", "se": "", "bloccata": "x"}]
    assert app._uscite_da_lav()["est"] == "sala"


def test_uscita_bloccata_caricata_e_round_trip():
    from advcore import Stanza
    app = _app()
    app.mondo.stanze["A"] = Stanza(
        id="A", nome="A", desc="",
        uscite={"ovest": {"to": "ingresso", "se": "porta",
                          "bloccata": "Sbarrato!"}})
    app.stack.append((app.vista_home, "Home"))
    app._lav_stanza_id = None
    app.form_stanza("A")                       # popola la copia di lavoro
    assert app._lav_uscite[0]["bloccata"] == "Sbarrato!"   # non si perde
    assert app._uscite_da_lav()["ovest"]["bloccata"] == "Sbarrato!"


def test_salva_condizione_stato_min():
    import urwid
    app = _app()
    app._reg = {"se": []}
    app._salva_condizione("stato_min", None, {"stato_min": urwid.Edit("", "2")})
    assert app._reg["se"][0] == {"stato_min": 2}


def test_salva_effetti_stato_e_scontro():
    import urwid
    app = _app()
    app._reg = {"allora": []}
    app._salva_effetto("allora", "stato", None, {"stato": urwid.Edit("", "1")})
    app._salva_effetto("allora", "avanza_stato", None,
                       {"avanza_stato": urwid.Edit("", "2")})
    sel = CampoScelta(app, "png", "lampada", app.opz_oggetti)
    app._salva_effetto("allora", "inizia_scontro", None, {"inizia_scontro": sel})
    assert {"stato": 1} in app._reg["allora"]
    assert {"avanza_stato": 2} in app._reg["allora"]
    assert {"inizia_scontro": "lampada"} in app._reg["allora"]


def test_props_combattente():
    import urwid
    app = _app()
    c = {
        "_props_orig": {}, "prendibile": urwid.CheckBox("", False),
        "scenario": urwid.CheckBox("", False),
        "contenitore": urwid.CheckBox("", False),
        "aperto": urwid.CheckBox("", False),
        "indossabile": urwid.CheckBox("", False),
        "png": urwid.CheckBox("", True), "desc": urwid.Edit("", ""),
        "in_stanza": urwid.Edit("", ""), "luce_on": urwid.CheckBox("", False),
        "luce_flag": app._campo_flag("flag", ""),
        "combattente": urwid.CheckBox("", True), "hp": urwid.Edit("", "12"),
        "attacco": urwid.Edit("", "4"), "difesa": urwid.Edit("", "2"),
        "fuga": urwid.CheckBox("", False), "intro_scontro": urwid.Edit("", "Arriva!"),
    }
    props = app._props_da_form(c)
    assert props["combattente"] is True
    assert props["hp"] == 12 and props["attacco"] == 4 and props["difesa"] == 2
    assert props["fuga"] is False                 # non fuggibile (spunta off)
    assert props["intro_scontro"] == "Arriva!"


def test_verbi_di_sistema_sempre_marcati():
    # la caverna dichiara «apri», «usa»… che sono anche verbi di sistema
    app = _app()
    assert "apri" in app.mondo.verbi
    t = _testo(app.vista_verbi(), (80, 44))
    assert "esteso" in t                      # i dichiarati-di-sistema sono marcati
    assert "sola lettura" in t                # i puri builtin restano marcati
    opz = dict((v, e) for e, v in app.opz_verbi())
    assert "predefinito" in opz["apri"]       # marcato anche nel selettore


def test_trova_edit_a_fuoco():
    import urwid
    from edit import _trova_edit
    e = urwid.Edit("", "x")
    lb = urwid.ListBox(urwid.SimpleFocusListWalker([urwid.AttrMap(e, "x")]))
    assert _trova_edit(urwid.Frame(lb)) is e
    assert _trova_edit(urwid.SolidFill(" ")) is None


def test_filtro_incolla_blocco():
    import urwid
    from edit import _trova_edit
    app = _app()
    e = urwid.Edit("", "", multiline=True)
    lb = urwid.ListBox(urwid.SimpleFocusListWalker([urwid.AttrMap(e, "x")]))
    fr = urwid.Frame(lb)
    app.frame.body = lb
    app.loop = type("L", (), {"widget": fr})()
    keys = ["begin paste"] + list("Riga1") + ["enter"] + list("Riga2") + ["end paste"]
    passanti = app._filtro_input(keys, None)
    assert passanti == []                       # i tasti dell'incolla non navigano
    assert e.edit_text == "Riga1\nRiga2"        # blocco multiriga inserito intero
    # un campo non multiriga riceve gli a-capo come spazi
    e2 = urwid.Edit("", "")
    lb.body[:] = [urwid.AttrMap(e2, "x")]
    app._filtro_input(["begin paste"] + list("a") + ["enter"] + list("b") + ["end paste"], None)
    assert e2.edit_text == "a b"


def test_salva_condizione_mosse_min():
    import urwid
    app = _app()
    app._reg = {"se": []}
    app._salva_condizione("mosse_min", None, {"mosse_min": urwid.Edit("", "3")})
    assert app._reg["se"][0] == {"mosse_min": 3}


def test_salva_effetti_timer():
    import urwid
    app = _app()
    app._reg = {"allora": []}
    app._salva_effetto("allora", "avvia_timer", None,
                       {"avvia_timer": urwid.Edit("", "bomba"),
                        "turni": urwid.Edit("", "3")})
    app._salva_effetto("allora", "ferma_timer", None,
                       {"ferma_timer": urwid.Edit("", "bomba")})
    assert {"avvia_timer": "bomba", "turni": 3} in app._reg["allora"]
    assert {"ferma_timer": "bomba"} in app._reg["allora"]


def test_quando_breve_eventi():
    from edit import quando_breve
    assert quando_breve({"evento": "turno"}) == "ogni turno"
    assert "ingresso" in quando_breve({"evento": "entra", "stanza": "x"})
    assert "timer" in quando_breve({"evento": "timer", "timer": "t"})
    assert quando_breve({"verbo": "usa", "oggetto": "leva"}) == "usa leva"


def test_regola_evento_turno_round_trip():
    app = _app()
    n = len(app.mondo.regole)
    app._reg = {"id": "ogni", "quando": {"evento": "turno"},
                "se": [], "allora": [], "altrimenti": []}
    app._reg_idx = None
    app.form_regola()              # imposta _reg_e_id / _reg_timer_edit
    app._salva_regola()
    assert len(app.mondo.regole) == n + 1
    assert app.mondo.regole[-1].quando == {"evento": "turno"}


def test_regola_entra_richiede_stanza():
    app = _app()
    app._reg = {"id": "ing", "quando": {"evento": "entra"},
                "se": [], "allora": [], "altrimenti": []}
    app._reg_idx = None
    app.form_regola()
    app._salva_regola()            # manca la stanza: non deve salvare
    assert all(r.id != "ing" for r in app.mondo.regole)


def main() -> int:
    for nome, fn in sorted(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()
            print(f"  ok  {nome}")
    print("Tutti i test dell'editor superati.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
