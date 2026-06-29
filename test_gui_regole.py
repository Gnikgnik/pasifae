# SPDX-License-Identifier: GPL-3.0-or-later
"""Test della logica pura dell'editor regole (gui/regole.py), senza Qt."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gui import regole as R


def test_assembla_condizioni():
    assert R.ASSEMBLA["flag_uguale"]({"flag": "p", "valore": True}) == \
        {"flag": "p", "uguale": True}
    assert R.ASSEMBLA["oggetto_in"]({"oggetto": "x", "luogo": "inventario"}) == \
        {"oggetto_in": ["x", "inventario"]}
    assert R.ASSEMBLA["mosse_min"]({"n": 3}) == {"mosse_min": 3}


def test_assembla_effetti():
    assert R.ASSEMBLA["set_flag"]({"flag": "p", "valore": False}) == \
        {"set_flag": "p", "valore": False}
    assert R.ASSEMBLA["avvia_timer"]({"nome": "b", "turni": 3}) == \
        {"avvia_timer": "b", "turni": 3}
    assert R.ASSEMBLA["sposta_oggetto"]({"oggetto": "k", "a": "stanza"}) == \
        {"sposta_oggetto": "k", "a": "stanza"}


def test_val_da_testo():
    assert R.val_da_testo("vero") is True
    assert R.val_da_testo("falso") is False
    assert R.val_da_testo("7") == 7
    assert R.val_da_testo("ciao") == "ciao"


def test_riassunti_e_innesco():
    assert "p" in R.riassunto_condizione({"flag": "p", "uguale": True})
    assert R.quando_breve({"evento": "turno"}) == "a ogni turno"
    assert "ingresso" in R.quando_breve({"evento": "entra", "stanza": "x"})
    assert R.riassunto_effetto({"avvia_timer": "b", "turni": 3}).startswith("avvia timer")


def test_cataloghi_coerenti():
    # ogni tipo del catalogo ha i campi e l'assemblatore
    for _, key in R.TIPI_CONDIZIONE + R.TIPI_EFFETTO:
        assert key in R.CAMPI, key
        assert key in R.ASSEMBLA, key


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
