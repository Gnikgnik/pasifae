# SPDX-License-Identifier: GPL-3.0-or-later
"""Test della mappa testuale (senza terminale).

Eseguibile con:  python3 test_mappa.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from advcore import carica_mondo, mappa_testuale, Mondo, Stanza, Oggetto


def test_mappa_griglia_cardinale():
    m = Mondo(meta={"titolo": "G", "stanza_iniziale": "a"})
    m.stanze["a"] = Stanza(id="a", nome="A", desc="", uscite={"est": "b", "sud": "c"})
    m.stanze["b"] = Stanza(id="b", nome="B", desc="", uscite={"ovest": "a"})
    m.stanze["c"] = Stanza(id="c", nome="C", desc="", uscite={"nord": "a"})
    m.oggetti["spada"] = Oggetto(id="spada", nome="spada", posizione="a",
                                 props={"prendibile": True})
    testo = mappa_testuale(m)
    # tutte e tre le stanze compaiono, nessuna isolata
    assert "A" in testo and "B" in testo and "C" in testo
    assert "non collegate" not in testo
    # la distribuzione mostra la spada in a
    assert "a: spada" in testo
    # B (est di A) sta a destra di A sulla stessa riga di testo
    riga_con_a = next(r for r in testo.split("\n") if "| *A" in r or "| A" in r)
    assert riga_con_a.index("A") < riga_con_a.rindex("B")


def test_mappa_marca_iniziale_e_conteggio():
    m = carica_mondo("avventure/caverna.json")
    testo = mappa_testuale(m)
    assert "*Ingresso" in testo or "*ingresso" in testo.lower()  # stanza iniziale
    assert "#2" in testo                                        # conteggio oggetti
    assert "@gnomo" in testo                                    # png marcato con @


def test_mappa_collegamenti_speciali_e_isolate():
    m = carica_mondo("avventure/caverna.json")
    testo = mappa_testuale(m)
    # «giu» non sta sulla griglia: deve finire nei collegamenti speciali
    assert "giu" in testo and "tesoro" in testo
    # tesoro/cripta raggiungibili solo via giu -> non posizionate
    assert "non collegate" in testo


def test_mappa_vuota():
    m = Mondo()
    assert "nessuna stanza" in mappa_testuale(m)


def main() -> int:
    for nome, fn in sorted(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()
            print(f"  ok  {nome}")
    print("Tutti i test della mappa superati.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
