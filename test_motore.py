# SPDX-License-Identifier: GPL-3.0-or-later
"""Test headless del motore: nessun terminale, solo stringhe dentro/fuori.

Gioca il percorso vincente dell'avventura di esempio e verifica i punti
chiave: buio senza luce, lampada, puzzle della moneta, vittoria. Eseguibile
con:  python3 test_motore.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from advcore import carica_mondo, Motore


def test_abbreviazioni_direzioni():
    from advcore import Mondo, Stanza

    def mondo():
        S = lambda i, u: Stanza(id=i, nome=i.upper(), desc="", uscite=u)
        m = Mondo(meta={"stanza_iniziale": "c"})
        m.stanze = {"c": S("c", {"nord": "n", "sud": "s", "est": "e", "ovest": "o"}),
                    "n": S("n", {}), "s": S("s", {}), "e": S("e", {}), "o": S("o", {})}
        return m

    for ab, atteso in [("n", "N"), ("s", "S"), ("e", "E"), ("o", "O"), ("w", "O")]:
        mot = Motore(mondo())
        mot.avvia()
        assert mot.esegui(ab).splitlines()[0] == atteso, (ab, atteso)


def test_rumore_ancora_scartato():
    from advcore import Mondo
    from advcore.parser import Parser
    p = Parser(Mondo())
    # le parole-rumore non-direzione restano scartate
    assert p._tokenizza("prendi la lampada") == ["prendi", "lampada"]
    # «e» (est) invece sopravvive
    assert p._tokenizza("e") == ["e"]


def _mondo_eventi():
    from advcore import Mondo, Stanza, Oggetto, Regola
    m = Mondo(meta={"stanza_iniziale": "a"})
    m.flags = {"contatti": 0, "visto_b": False}
    m.stanze["a"] = Stanza(id="a", nome="A", desc="A", uscite={"est": "b"})
    m.stanze["b"] = Stanza(id="b", nome="B", desc="B", uscite={"ovest": "a"})
    m.oggetti["leva"] = Oggetto(id="leva", nome="leva", nomi=["leva"],
                                posizione="a", props={"scenario": True})
    m.regole = [
        Regola(id="battito", quando={"evento": "turno"},
               allora=[{"incrementa": "contatti", "di": 1}]),
        Regola(id="ing", quando={"evento": "entra", "stanza": "b"},
               se=[{"flag": "visto_b", "uguale": False}],
               allora=[{"set_flag": "visto_b", "valore": True},
                       {"stampa": "luce rossa"}]),
        Regola(id="acc", quando={"verbo": "usa", "oggetto": "leva"},
               allora=[{"avvia_timer": "bomba", "turni": 2}]),
        Regola(id="boom", quando={"evento": "timer", "timer": "bomba"},
               allora=[{"sconfitta": "BOOM"}]),
    ]
    return m


def test_evento_ogni_turno():
    mot = Motore(_mondo_eventi())
    mot.avvia()
    mot.esegui("guarda")
    mot.esegui("guarda")
    assert mot.mondo.flags["contatti"] == 2


def test_evento_entra_con_guardia():
    mot = Motore(_mondo_eventi())
    mot.avvia()
    assert "luce rossa" in mot.esegui("est")     # primo ingresso in B
    mot.esegui("ovest")
    assert "luce rossa" not in mot.esegui("est")  # rientro: la guardia tace


def test_timer_scade_dopo_k_turni():
    mot = Motore(_mondo_eventi())
    mot.avvia()
    mot.esegui("usa leva")
    assert mot.mondo.timer.get("bomba") == 2     # non scala nel turno di avvio
    mot.esegui("guarda")
    assert mot.mondo.timer.get("bomba") == 1
    mot.esegui("guarda")
    assert mot.mondo.finita is True              # scaduto


def test_annulla_ripristina_il_turno():
    mot = Motore(_mondo_eventi())
    mot.avvia()
    mot.esegui("est")
    assert mot.mondo.stanza_corrente == "b" and mot.mondo.flags["contatti"] == 1
    mot.esegui("annulla")
    assert mot.mondo.stanza_corrente == "a"      # posizione ripristinata
    assert mot.mondo.mosse == 0
    assert mot.mondo.flags["contatti"] == 0      # anche l'effetto-evento è annullato


def test_condizione_mosse_min():
    from advcore import Mondo, Stanza, Regola
    m = Mondo(meta={"stanza_iniziale": "a"})
    m.flags = {"sveglia": False}
    m.stanze["a"] = Stanza(id="a", nome="A", desc="A", uscite={})
    m.regole = [Regola(id="t", quando={"evento": "turno"},
                       se=[{"mosse_min": 3}, {"flag": "sveglia", "uguale": False}],
                       allora=[{"set_flag": "sveglia", "valore": True},
                               {"stampa": "ORA"}])]
    mot = Motore(m)
    mot.avvia()
    assert "ORA" not in mot.esegui("guarda")     # mossa 1
    assert "ORA" not in mot.esegui("guarda")     # mossa 2
    assert "ORA" in mot.esegui("guarda")         # mossa 3


def _mondo_baule():
    """Baule chiuso a chiave: la regola dell'autore decide se aprirlo."""
    from advcore import Mondo, Stanza, Oggetto, Regola
    m = Mondo(meta={"stanza_iniziale": "cripta"})
    m.stanze["cripta"] = Stanza(id="cripta", nome="Cripta", desc="Una cripta.")
    m.oggetti["baule"] = Oggetto(
        id="baule", nome="baule", nomi=["baule"], posizione="cripta",
        props={"scenario": True, "contenitore": True, "aperto": False})
    m.oggetti["chiave"] = Oggetto(
        id="chiave", nome="chiave", nomi=["chiave"], posizione="cripta",
        props={"prendibile": True})
    m.oggetti["medaglione"] = Oggetto(
        id="medaglione", nome="medaglione", nomi=["medaglione"],
        posizione="baule", props={"prendibile": True})
    m.regole = [
        Regola(id="serratura", quando={"verbo": "apri", "oggetto": "baule"},
               se=[{"oggetto_in": ["chiave", "inventario"]}],
               allora=[{"apri_oggetto": "baule"},
                       {"stampa": "La serratura scatta e il baule si apre."}],
               altrimenti=[{"stampa": "È chiuso a chiave."}]),
        Regola(id="coperchio", quando={"verbo": "chiudi", "oggetto": "baule"},
               allora=[{"chiudi_oggetto": "baule"},
                       {"stampa": "Richiudi il coperchio."}]),
    ]
    return m


def test_apri_oggetto_condizionato():
    mot = Motore(_mondo_baule())
    mot.avvia()
    # senza chiave: la regola rifiuta e il baule resta chiuso
    assert "chiuso a chiave" in mot.esegui("apri baule")
    assert mot.mondo.oggetti["baule"].props.get("aperto") is False
    assert "Non vedo" in mot.esegui("prendi medaglione")   # contenuto fuori scope
    # con la chiave: l'effetto apri_oggetto apre davvero
    mot.esegui("prendi chiave")
    assert "si apre" in mot.esegui("apri baule")
    assert mot.mondo.oggetti["baule"].props.get("aperto") is True
    assert "medaglione" in mot.esegui("prendi medaglione")  # ora in scope


def test_chiudi_oggetto_e_casi_limite():
    from advcore.rules import esegui_effetti
    mot = Motore(_mondo_baule())
    mot.avvia()
    mot.esegui("prendi chiave")
    mot.esegui("apri baule")
    assert "Richiudi" in mot.esegui("chiudi baule")
    assert mot.mondo.oggetti["baule"].props.get("aperto") is False
    # su un non-contenitore o su un id inesistente l'effetto non fa nulla
    out: list[str] = []
    esegui_effetti([{"apri_oggetto": "chiave"},
                    {"apri_oggetto": "fantasma"}], mot.mondo, out)
    assert "aperto" not in mot.mondo.oggetti["chiave"].props
    assert out == []


def _mondo_combat():
    from advcore import Mondo, Stanza, Oggetto
    m = Mondo(meta={"stanza_iniziale": "a"})
    m.flags = {"pg_hp": 20, "pg_attacco": 5, "pg_difesa": 1}
    m.stanze["a"] = Stanza(id="a", nome="ARENA", desc="", uscite={})
    m.oggetti["chiave"] = Oggetto(id="chiave", nome="chiave", nomi=["chiave"],
                                  posizione="guardia", props={"prendibile": True})
    m.oggetti["guardia"] = Oggetto(
        id="guardia", nome="guardia", nomi=["guardia"], posizione="a",
        props={"combattente": True, "hp": 10, "attacco": 4, "difesa": 2,
               "intro_scontro": "La guardia attacca!",
               "sconfitto": [{"set_flag": "vinta", "valore": True},
                             {"sposta_oggetto": "chiave", "a": "a"}]})
    return m


def test_stato_conversazione():
    from advcore import Mondo, Stanza, Oggetto
    m = Mondo(meta={"stanza_iniziale": "s"})
    m.stanze["s"] = Stanza(id="s", nome="S", desc="", uscite={})
    m.oggetti["png"] = Oggetto(
        id="png", nome="tizio", nomi=["tizio"], posizione="s",
        props={"png": True, "stato_iniziale": 0, "dialogo": [
            {"etichetta": "ciao", "testo": "«ciao»", "allora": [{"stato": 1}]},
            {"etichetta": "segreto", "se": [{"stato_min": 1}], "testo": "«ok»"},
        ]})
    mot = Motore(m)
    mot.avvia()
    apertura = mot.esegui("parla con tizio")
    assert "segreto" not in apertura            # gated, stato 0
    dopo = mot.esegui("1")                       # scelgo "ciao" -> stato 1
    assert "segreto" in dopo                     # ora compare


def test_combattimento_vittoria():
    mot = Motore(_mondo_combat())
    mot.avvia()
    mot.esegui("attacca guardia")
    for _ in range(6):
        if "sconfitt" in mot.esegui("attacca").lower():
            break
    assert mot.mondo.flags.get("vinta") is True          # effetto sconfitto
    assert mot.mondo.oggetti["chiave"].posizione == "a"  # bottino rilasciato
    assert mot.mondo.scontro == ""                       # scontro chiuso


def test_combattimento_sconfitta():
    m = _mondo_combat()
    m.flags["pg_hp"] = 3
    m.oggetti["guardia"].props["hp"] = 100
    mot = Motore(m)
    mot.avvia()
    mot.esegui("attacca guardia")
    for _ in range(5):
        if mot.mondo.finita:
            break
        mot.esegui("attacca")
    assert mot.mondo.finita is True


def test_combattimento_fuga():
    mot = Motore(_mondo_combat())
    mot.avvia()
    mot.esegui("attacca guardia")
    r = mot.esegui("fuggi")
    assert mot.mondo.scontro == "" and "fugg" in r.lower()
    m2 = _mondo_combat()
    m2.oggetti["guardia"].props["fuga"] = False
    mot2 = Motore(m2)
    mot2.avvia()
    mot2.esegui("attacca guardia")
    mot2.esegui("fuggi")
    assert mot2.mondo.scontro == "guardia"      # non fuggibile: resta


def test_frase_in_stanza_dinamica():
    from advcore import Mondo, Stanza, Oggetto
    m = Mondo(meta={"stanza_iniziale": "sala"})
    m.stanze["sala"] = Stanza(id="sala", nome="Sala", desc="Una sala vuota.")
    m.oggetti["chiave"] = Oggetto(
        id="chiave", nome="chiave", nomi=["chiave"], posizione="sala",
        props={"prendibile": True, "in_stanza": "Una chiave luccica sul pavimento."})
    m.oggetti["moneta"] = Oggetto(
        id="moneta", nome="moneta", nomi=["moneta"], posizione="sala",
        props={"prendibile": True})
    mot = Motore(m)
    mot.avvia()
    desc = mot.esegui("guarda")
    assert "Una chiave luccica sul pavimento." in desc   # frase di presenza
    assert "Qui vedi: moneta." in desc                   # elenco per gli altri
    mot.esegui("prendi chiave")
    desc2 = mot.esegui("guarda")
    assert "Una chiave luccica" not in desc2             # sparisce quando presa
    assert "Una sala vuota." in desc2                    # la prosa fissa resta


def main() -> int:
    mondo = carica_mondo("avventure/caverna.json")
    m = Motore(mondo)

    avvio = m.avvia()
    assert "INGRESSO DELLA CAVERNA" in avvio, avvio
    assert "lampada" in avvio, avvio

    # senza lampada accesa, il corridoio e' buio
    m.esegui("nord")
    buio = m.esegui("guarda")
    assert "buio" in buio.lower(), buio

    # torno, prendo e accendo la lampada
    m.esegui("sud")
    assert "Prendi" in m.esegui("prendi lampada")
    acceso = m.esegui("accendi lampada")
    assert "luce dorata" in acceso, acceso

    # ora il corridoio e' illuminato
    corridoio = m.esegui("nord")
    assert "CORRIDOIO BUIO" in corridoio, corridoio

    # la botola e' bloccata finche' non risolvo il puzzle
    bloccata = m.esegui("giu")
    assert "sprangata" in bloccata.lower(), bloccata

    # prendo la moneta e la infilo nella fessura (verbo+prep+ogg indiretto)
    m.esegui("prendi moneta")
    puzzle = m.esegui("metti moneta nella fessura")
    assert "si apre" in puzzle.lower(), puzzle

    # ora la botola e' aperta: scendo e prendo il tesoro
    tesoro = m.esegui("giu")
    assert "CAMERA DEL TESORO" in tesoro, tesoro
    vittoria = m.esegui("prendi calice")
    assert "HAI VINTO" in vittoria, vittoria
    assert mondo.finita

    # verifico anche la disambiguazione e gli errori del parser
    m2 = Motore(carica_mondo("avventure/caverna.json"))
    assert "Non conosco il verbo" in m2.esegui("danza")
    assert "Non vedo" in m2.esegui("prendi drago")

    print("Tutti i test superati.")
    print("\n--- estratto della sessione vincente ---")
    print(vittoria)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
