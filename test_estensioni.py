# SPDX-License-Identifier: GPL-3.0-or-later
"""Test delle estensioni del motore (senza terminale).

Copre contenitori apribili, oggetti indossabili, punteggio/mosse e il fatto che
i verbi standard funzionino anche in un'avventura che non li dichiara.
Eseguibile con:  python3 test_estensioni.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from advcore import carica_mondo, Motore, Mondo, Stanza, Oggetto, Verbo, Regola


def _al_tesoro():
    """Porta una partita dell'avventura di esempio fino alla camera del tesoro."""
    m = carica_mondo("avventure/caverna.json")
    mot = Motore(m)
    mot.avvia()
    for c in ["prendi lampada", "accendi lampada", "nord", "prendi moneta",
              "metti moneta nella fessura", "giu"]:
        mot.esegui(c)
    return m, mot


def test_contenitore_apri_e_prendi():
    m, mot = _al_tesoro()
    # col baule chiuso il mantello non è raggiungibile
    assert "Non vedo" in mot.esegui("prendi mantello")
    assert "chiuso" in mot.esegui("esamina baule").lower()
    aperto = mot.esegui("apri baule")
    assert "mantello" in aperto
    assert "Prendi" in mot.esegui("prendi mantello")
    assert m.oggetti["mantello"].posizione == "inventario"


def test_contenitore_metti_dentro():
    m, mot = _al_tesoro()
    mot.esegui("apri baule")
    mot.esegui("prendi mantello")
    assert "Metti" in mot.esegui("metti mantello nel baule")
    assert m.oggetti["mantello"].posizione == "baule"
    # se richiudo, non posso più metterci nulla
    mot.esegui("prendi mantello")
    mot.esegui("chiudi baule")
    assert "chiuso" in mot.esegui("metti mantello nel baule").lower()


def test_contenitore_annidato_in_scope():
    # scatola aperta dentro un baule aperto: l'anello dentro la scatola deve
    # essere visibile/prendibile anche se annidato a due livelli.
    m = Mondo(meta={"titolo": "Minimal", "stanza_iniziale": "qui"})
    m.stanze["qui"] = Stanza(id="qui", nome="Qui", desc="Una stanza spoglia.")
    m.oggetti["baule"] = Oggetto(id="baule", nome="baule", nomi=["baule"],
                                 posizione="qui",
                                 props={"contenitore": True, "aperto": True})
    m.oggetti["scatola"] = Oggetto(id="scatola", nome="scatola", nomi=["scatola"],
                                   posizione="baule",
                                   props={"contenitore": True, "aperto": True})
    m.oggetti["anello"] = Oggetto(id="anello", nome="anello", nomi=["anello"],
                                  posizione="scatola", props={"prendibile": True})
    mot = Motore(m)
    mot.avvia()
    assert "Prendi" in mot.esegui("prendi anello")
    assert m.oggetti["anello"].posizione == "inventario"


def test_indossabile():
    m, mot = _al_tesoro()
    mot.esegui("apri baule")
    mot.esegui("prendi mantello")
    assert "Indossi" in mot.esegui("indossa mantello")
    assert m.oggetti["mantello"].props.get("indossato") is True
    assert "(indosso)" in mot.esegui("inventario")
    assert "togli" in mot.esegui("togli mantello").lower()
    assert m.oggetti["mantello"].props.get("indossato") is False


def test_punteggio_e_mosse():
    m, mot = _al_tesoro()
    assert m.punteggio == 0
    assert m.mosse == 6                       # i 6 comandi di _al_tesoro
    vittoria = mot.esegui("prendi calice")    # +100 punti
    assert "HAI VINTO" in vittoria
    assert m.punteggio == 100


def test_verbi_predefiniti_sempre_disponibili():
    # un'avventura minimale che NON dichiara alcun verbo
    m = Mondo(meta={"titolo": "Minimal", "stanza_iniziale": "qui"})
    m.stanze["qui"] = Stanza(id="qui", nome="Qui", desc="Una stanza spoglia.")
    m.oggetti["sasso"] = Oggetto(id="sasso", nome="sasso", nomi=["sasso"],
                                 posizione="qui", props={"prendibile": True})
    mot = Motore(m)
    mot.avvia()
    # 'prendi' funziona anche senza essere stato dichiarato
    assert "Prendi" in mot.esegui("prendi sasso")
    assert m.oggetti["sasso"].posizione == "inventario"


def test_riavvia_ripristina_stato():
    m, mot = _al_tesoro()              # gioca 6 mosse, sposta oggetti, accende luce
    m.punteggio = 99
    testa = mot.riavvia()
    assert m.mosse == 0 and m.punteggio == 0
    assert m.flags["lampada_accesa"] is False
    assert m.oggetti["lampada"].posizione == "ingresso"   # tornata al posto
    assert m.oggetti["moneta"].posizione == "corridoio"
    assert m.stanza_corrente == m.meta["stanza_iniziale"]
    assert "CAVERNA" in testa.upper()


def test_preposizioni_articolate():
    # «nello zaino», «nell'astuccio»: tutte le forme articolate di «in» e «su»
    # devono dividere il comando in oggetto diretto e indiretto.
    m = Mondo(meta={"titolo": "Minimal", "stanza_iniziale": "qui"})
    m.stanze["qui"] = Stanza(id="qui", nome="Qui", desc="Una stanza spoglia.")
    m.oggetti["zaino"] = Oggetto(id="zaino", nome="zaino", nomi=["zaino"],
                                 posizione="qui",
                                 props={"contenitore": True, "aperto": True})
    m.oggetti["astuccio"] = Oggetto(id="astuccio", nome="astuccio",
                                    nomi=["astuccio"], posizione="qui",
                                    props={"contenitore": True, "aperto": True})
    m.oggetti["sasso"] = Oggetto(id="sasso", nome="sasso", nomi=["sasso"],
                                 posizione="qui", props={"prendibile": True})
    mot = Motore(m)
    mot.avvia()
    mot.esegui("prendi sasso")
    assert "Metti" in mot.esegui("metti sasso nello zaino")
    assert m.oggetti["sasso"].posizione == "zaino"
    mot.esegui("prendi sasso")
    assert "Metti" in mot.esegui("metti sasso nell'astuccio")
    assert m.oggetti["sasso"].posizione == "astuccio"


def test_aiuto():
    m = carica_mondo("avventure/caverna.json")
    mot = Motore(m)
    mot.avvia()
    r = mot.esegui("aiuto")
    assert "Comandi" in r and "salva" in r and "parla" in r
    # la caverna dichiara verbi ad hoc e usa il punteggio: devono comparire
    assert "accendi" in r and "spegni" in r
    assert "punteggio" in r


def test_aiuto_solo_verbi_usati():
    # L'aiuto elenca solo i verbi che l'avventura usa davvero: qui niente
    # contenitori, indumenti, personaggi o punteggio, ma un verbo ad hoc.
    m = Mondo(meta={"titolo": "Minimal", "stanza_iniziale": "qui"})
    m.stanze["qui"] = Stanza(id="qui", nome="Qui", desc="Una stanza spoglia.")
    m.oggetti["campana"] = Oggetto(id="campana", nome="campana",
                                   nomi=["campana"], posizione="qui",
                                   props={"scenario": True})
    m.oggetti["sasso"] = Oggetto(id="sasso", nome="sasso", nomi=["sasso"],
                                 posizione="qui", props={"prendibile": True})
    m.verbi["suona"] = Verbo(id="suona", sinonimi=["suonare"])
    m.regole.append(Regola(id="r_suona",
                           quando={"verbo": "suona", "oggetto": "campana"},
                           allora=[{"stampa": "Din don."}]))
    mot = Motore(m)
    mot.avvia()
    r = mot.esegui("aiuto")
    assert "suona <oggetto>" in r          # verbo ad hoc dichiarato
    assert "prendi" in r                   # c'è un oggetto prendibile
    assert "guarda" in r and "salva" in r  # sempre presenti
    for assente in ("apri", "indossa", "parla", "attacca", "punteggio"):
        assert assente not in r, f"«{assente}» non dovrebbe comparire"


def test_immagine_stanza_opzionale():
    """Il campo `immagine` della stanza è opzionale e retrocompatibile:
    sopravvive al round-trip su file, non compare nel JSON quando è vuoto,
    e le avventure esistenti (senza campo) continuano a caricarsi."""
    import json
    import tempfile
    from advcore import salva_mondo

    m = Mondo(meta={"titolo": "Con figure", "stanza_iniziale": "atrio"})
    m.stanze["atrio"] = Stanza(id="atrio", nome="Atrio", desc="",
                               immagine="atrio.png")
    m.stanze["cella"] = Stanza(id="cella", nome="Cella", desc="")

    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "figure.json"
        salva_mondo(m, f)
        dati = json.loads(f.read_text(encoding="utf-8"))
        assert dati["stanze"]["atrio"]["immagine"] == "atrio.png"
        assert "immagine" not in dati["stanze"]["cella"]     # niente rumore
        m2 = carica_mondo(f)
        assert m2.stanze["atrio"].immagine == "atrio.png"
        assert m2.stanze["cella"].immagine == ""

    # un'avventura esistente, senza campo, carica con immagine vuota
    m3 = carica_mondo("avventure/caverna.json")
    assert all(s.immagine == "" for s in m3.stanze.values())


def main() -> int:
    for nome, fn in sorted(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()
            print(f"  ok  {nome}")
    print("Tutti i test delle estensioni superati.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
