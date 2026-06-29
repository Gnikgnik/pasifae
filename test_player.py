# SPDX-License-Identifier: GPL-3.0-or-later
"""Test della logica pura del player (senza curses, senza terminale).

Verifica a capo automatico, scorrimento della trascrizione e navigazione dello
storico comandi. Le parti curses si controllano a parte con py_compile.
Eseguibile con:  python3 test_player.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from play_curses import Trascrizione, StoricoComandi


def test_a_capo():
    t = Trascrizione()
    t.aggiungi("parola " * 20, "out")              # riga lunga da spezzare
    righe = t.righe_display(20)
    assert all(len(testo) <= 20 for _, testo in righe), righe
    assert len(righe) > 1


def test_righe_vuote_e_stili():
    t = Trascrizione()
    t.aggiungi("riga1\n\nriga3", "out")
    righe = t.righe_display(40)
    testi = [testo for _, testo in righe]
    assert testi == ["riga1", "", "riga3"], testi


def test_separatore_tra_turni():
    t = Trascrizione()
    t.aggiungi("intro", "out")
    t.aggiungi("> nord", "cmd")                    # deve inserire una riga vuota prima
    righe = t.righe_display(40)
    testi = [testo for _, testo in righe]
    assert testi == ["intro", "", "> nord"], testi


def test_scorrimento_clamp():
    t = Trascrizione()
    for i in range(100):
        t.aggiungi(f"riga {i}", "out")
    righe = t.righe_display(40)
    t.scorri_su(1000)                              # oltre il limite
    t.clamp(len(righe), visibili=10)
    assert t.scroll == len(righe) - 10, t.scroll   # bloccato in cima
    t.scorri_giu(1000)
    assert t.scroll == 0


def test_storico():
    s = StoricoComandi()
    s.aggiungi("nord")
    s.aggiungi("prendi lampada")
    assert s.precedente("") == "prendi lampada"
    assert s.precedente("") == "nord"
    assert s.precedente("") == "nord"             # non va oltre il primo
    assert s.successivo("") == "prendi lampada"
    assert s.successivo("") == ""                 # torna alla bozza vuota


def test_storico_conserva_bozza():
    s = StoricoComandi()
    s.aggiungi("guarda")
    assert s.precedente("sto scrivendo") == "guarda"
    assert s.successivo("guarda") == "sto scrivendo"   # bozza recuperata


def main() -> int:
    for nome, fn in sorted(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()
            print(f"  ok  {nome}")
    print("Tutti i test del player superati.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
