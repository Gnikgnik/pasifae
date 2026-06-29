# SPDX-License-Identifier: GPL-3.0-or-later
"""Test di personaggi/dialoghi e oggetti combinabili (senza terminale).

Eseguibile con:  python3 test_dialoghi.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from advcore import carica_mondo, Motore


def _gioca():
    m = carica_mondo("avventure/caverna.json")
    mot = Motore(m)
    mot.avvia()
    return m, mot


def test_dialogo_menu_e_dono():
    m, mot = _gioca()
    apertura = mot.esegui("parla con gnomo")
    assert "Chiedi del passaggio" in apertura
    assert m.conversazione == "gnomo"
    # la battuta "una volta" regala la chiave e assegna punti
    scelta = mot.esegui("2")
    assert m.oggetti["chiave"].posizione == "inventario"
    assert m.punteggio == 10
    # ora quella battuta non è più disponibile
    assert "Chiedi un aiuto" not in scelta
    mot.esegui("esci")
    assert m.conversazione == ""


def test_dialogo_uscita_e_input_non_valido():
    m, mot = _gioca()
    mot.esegui("parla gnomo")
    assert m.conversazione == "gnomo"
    fuori = mot.esegui("salta")           # non un numero, resta in conversazione
    assert "conversazione" in fuori.lower()
    assert m.conversazione == "gnomo"
    mot.esegui("0")                        # 0 = saluta e vai
    assert m.conversazione == ""


def test_parla_con_non_png():
    m, mot = _gioca()
    risposta = mot.esegui("parla con lampada")
    assert "conversazione" in risposta.lower()
    assert m.conversazione == ""           # non entra in dialogo


def _porta_al_tesoro_con_chiave(mot):
    mot.esegui("parla con gnomo")
    mot.esegui("2")          # ottiene la chiave
    mot.esegui("esci")
    for c in ["prendi lampada", "accendi lampada", "nord", "prendi moneta",
              "metti moneta nella fessura", "giu"]:
        mot.esegui(c)


def test_combinazione_oggetti():
    m, mot = _gioca()
    _porta_al_tesoro_con_chiave(mot)
    assert "chiusa" in mot.esegui("ovest").lower()      # lucchetto sbarra
    r = mot.esegui("usa chiave con lucchetto")
    assert "apre" in r.lower()
    assert m.flags["lucchetto_aperto"] is True
    assert "CRIPTA" in mot.esegui("ovest")


def test_combinazione_simmetrica():
    m, mot = _gioca()
    _porta_al_tesoro_con_chiave(mot)
    # ordine invertito: deve funzionare comunque
    r = mot.esegui("usa lucchetto con chiave")
    assert "apre" in r.lower()
    assert m.flags["lucchetto_aperto"] is True


def test_usa_senza_regola():
    m, mot = _gioca()
    assert "usar" in mot.esegui("usa lampada").lower()   # messaggio di default


def main() -> int:
    for nome, fn in sorted(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()
            print(f"  ok  {nome}")
    print("Tutti i test di dialoghi e combinazioni superati.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
