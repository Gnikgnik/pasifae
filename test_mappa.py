# SPDX-License-Identifier: GPL-3.0-or-later
"""Test della mappa testuale (senza terminale).

Eseguibile con:  python3 test_mappa.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from advcore import carica_mondo, mappa_testuale, uscite_visibili, Mondo, Stanza, Oggetto


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
    # tesoro/cripta sono collegate fra loro (est/ovest): pur raggiungibili
    # dal resto solo via «giu», hanno una propria area della griglia, non
    # finiscono fra le stanze isolate
    assert "non collegate" not in testo


def test_mappa_gruppo_raggiunto_solo_da_uscita_non_cardinale_resta_in_griglia():
    """Un gruppo di stanze collegate fra loro cardinalmente, ma raggiungibile
    dal resto del mondo solo tramite un'uscita non cardinale (dentro/fuori/
    su/giu), non deve essere appiattito in un'unica riga «isolate»: la sua
    struttura interna (est/ovest/nord/sud) va preservata in un'area propria
    della griglia."""
    from advcore.mappa import _layout
    m = Mondo(meta={"stanza_iniziale": "a"})
    m.stanze["a"] = Stanza(id="a", nome="A", desc="", uscite={"dentro": "x"})
    m.stanze["x"] = Stanza(id="x", nome="X", desc="",
                           uscite={"fuori": "a", "est": "y"})
    m.stanze["y"] = Stanza(id="y", nome="Y", desc="",
                           uscite={"ovest": "x", "est": "z"})
    m.stanze["z"] = Stanza(id="z", nome="Z", desc="", uscite={"ovest": "y"})

    coord, isolate = _layout(m)
    # «a» non ha uscite cardinali (solo «dentro»): resta isolata a sé; il
    # gruppo x/y/z invece, pur raggiunto solo da un'uscita non cardinale,
    # non lo è più
    assert isolate == ["a"]
    assert "x" in coord and "y" in coord and "z" in coord
    # y è a est di x, z è a est di y: la geometria relativa è preservata
    xx, xy = coord["x"]
    yx, yy = coord["y"]
    zx, zy = coord["z"]
    assert (yx, yy) == (xx + 1, xy)
    assert (zx, zy) == (xx + 2, xy)

    testo = mappa_testuale(m)
    assert "X" in testo and "Y" in testo and "Z" in testo
    # solo «a» (senza uscite cardinali) finisce fra le stanze isolate
    riga_isolate = testo.split("Stanze non collegate alla griglia:")[1]
    assert "a" in riga_isolate and "x" not in riga_isolate


def test_mappa_vuota():
    m = Mondo()
    assert "nessuna stanza" in mappa_testuale(m)


def test_uscite_visibili_esclude_condizionate_bloccate():
    """Un'uscita condizionata resta fuori finché il flag non è impostato;
    un'uscita semplice (senza «se») è sempre visibile."""
    m = Mondo(meta={"stanza_iniziale": "a"})
    m.stanze["a"] = Stanza(id="a", nome="A", desc="", uscite={
        "nord": "b",
        "sud": {"to": "c", "se": "porta_aperta"},
    })
    m.stanze["b"] = Stanza(id="b", nome="B", desc="", uscite={})
    m.stanze["c"] = Stanza(id="c", nome="C", desc="", uscite={})

    assert uscite_visibili(m, m.stanze["a"]) == [("nord", "b")]

    m.flags["porta_aperta"] = True
    assert uscite_visibili(m, m.stanze["a"]) == [("nord", "b"), ("sud", "c")]


def main() -> int:
    for nome, fn in sorted(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()
            print(f"  ok  {nome}")
    print("Tutti i test della mappa superati.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
