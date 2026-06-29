# SPDX-License-Identifier: GPL-3.0-or-later
"""Test del testo dinamico (advcore/testo.py) e della sua integrazione nel motore."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from advcore import Mondo, Motore, Stanza, Regola, Verbo
from advcore.testo import rendi_testo


def _mondo():
    m = Mondo()
    m.flags = {"monete": 3, "porta": True, "eroe": "Lyra", "chiave": False}
    m.stanze["sala"] = Stanza(id="sala", nome="Sala", desc="", uscite={})
    m.stanza_corrente = "sala"
    m.punteggio = 10
    m.mosse = 4
    return m


def test_interpolazione():
    m = _mondo()
    assert rendi_testo("Hai {monete} monete.", m) == "Hai 3 monete."
    assert rendi_testo("Io sono {eroe}.", m) == "Io sono Lyra."
    assert rendi_testo("Punti {punteggio}, mosse {mosse}, qui: {stanza}.", m) == \
        "Punti 10, mosse 4, qui: Sala."
    assert rendi_testo("La porta è {porta}.", m) == "La porta è sì."


def test_token_sconosciuto_invariato():
    m = _mondo()
    assert rendi_testo("Un {boh} e una [nota] qualsiasi.", m) == \
        "Un {boh} e una [nota] qualsiasi."


def test_condizionali():
    m = _mondo()
    assert rendi_testo("[porta: aperta]", m) == "aperta"
    assert rendi_testo("[chiave: sì|no]", m) == "no"
    assert rendi_testo("[monete=3: tre|altro]", m) == "tre"
    assert rendi_testo("[monete=0: zero]", m) == ""
    assert rendi_testo("[prima_volta: nuovo|noto]", m, {"prima_volta": True}) == "nuovo"


def test_misto():
    m = _mondo()
    assert rendi_testo("{eroe} ha {monete} monete [porta: e via libera|e via chiusa].", m) == \
        "Lyra ha 3 monete e via libera."


def test_motore_descrizione_e_prima_volta():
    m = Mondo()
    m.flags = {"monete": 0}
    m.stanze["atrio"] = Stanza(id="atrio", nome="Atrio", uscite={"nord": "sala"},
                               desc="Atrio. [prima_volta: Mai stato qui.|Di nuovo qui.] "
                                    "Monete: {monete}.")
    m.stanze["sala"] = Stanza(id="sala", nome="Sala", uscite={"sud": "atrio"}, desc="Sala.")
    m.meta["stanza_iniziale"] = "atrio"
    m.verbi["cerca"] = Verbo(id="cerca", sinonimi=["cerca"], tipo="intransitivo")
    m.regole.append(Regola(id="r", quando={"verbo": "cerca"}, se=[],
                           allora=[{"incrementa": "monete", "di": 5},
                                   {"stampa": "Trovi monete! Ora: {monete}."}],
                           altrimenti=[]))
    mot = Motore(m)
    avvio = mot.avvia()
    assert "Mai stato qui." in avvio and "Monete: 0." in avvio
    assert "Trovi monete! Ora: 5." in mot.esegui("cerca")
    mot.esegui("nord")
    ritorno = mot.esegui("sud")
    assert "Di nuovo qui." in ritorno and "Monete: 5." in ritorno


def main() -> int:
    falliti = 0
    for nome, fn in sorted(globals().items()):
        if nome.startswith("test_"):
            try:
                fn()
            except AssertionError as e:
                print(f"FALLITO {nome}: {e}")
                falliti += 1
    print("ok" if not falliti else f"{falliti} test falliti")
    return 1 if falliti else 0


if __name__ == "__main__":
    raise SystemExit(main())
