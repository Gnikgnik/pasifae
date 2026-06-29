# SPDX-License-Identifier: GPL-3.0-or-later
"""Test del salvataggio/caricamento partita (senza terminale).

Gioca a meta' puzzle, salva, ricarica l'avventura da zero, riapplica lo stato e
verifica che la partita riprenda identica. Eseguibile con:
    python3 test_salvataggio.py
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from advcore import (carica_mondo, Motore, salva_partita, carica_partita,
                     stato_partita, applica_stato)


def test_round_trip_scontro():
    from advcore import Mondo, Stanza, Oggetto
    def mondo():
        m = Mondo(meta={"stanza_iniziale": "a"})
        m.flags = {"pg_hp": 20, "pg_attacco": 5, "pg_difesa": 1}
        m.stanze["a"] = Stanza(id="a", nome="A", desc="", uscite={})
        m.oggetti["orco"] = Oggetto(
            id="orco", nome="orco", nomi=["orco"], posizione="a",
            props={"combattente": True, "hp": 30, "attacco": 4, "difesa": 1})
        return m
    mot = Motore(mondo())
    mot.avvia()
    mot.esegui("attacca orco")
    mot.esegui("attacca")               # un round: PF di entrambi cambiano
    stato = stato_partita(mot.mondo)
    assert stato["scontro"] == "orco"
    # ricarico pulito e riapplico
    m2 = mondo()
    applica_stato(m2, stato)
    assert m2.scontro == "orco"
    assert m2.flags["__hp_orco"] == mot.mondo.flags["__hp_orco"]
    assert m2.flags["pg_hp"] == mot.mondo.flags["pg_hp"]


def test_round_trip_stato():
    m = carica_mondo("avventure/caverna.json")
    mot = Motore(m)
    mot.avvia()
    # porto avanti la partita: prendo e accendo la lampada, vado nel corridoio,
    # prendo la moneta (ma NON risolvo ancora il puzzle)
    mot.esegui("prendi lampada")
    mot.esegui("accendi lampada")
    mot.esegui("nord")
    mot.esegui("prendi moneta")

    stato = stato_partita(m)
    assert stato["stanza_corrente"] == "corridoio"
    assert stato["flags"]["lampada_accesa"] is True
    assert stato["oggetti"]["moneta"]["pos"] == "inventario"
    assert "ingresso" in stato["visitate"] and "corridoio" in stato["visitate"]

    # ricarico l'avventura PULITA e ci riapplico lo stato
    m2 = carica_mondo("avventure/caverna.json")
    applica_stato(m2, stato)
    mot2 = Motore(m2)
    assert m2.stanza_corrente == "corridoio"
    assert m2.flags["lampada_accesa"] is True
    assert m2.oggetti["moneta"].posizione == "inventario"
    # e da qui posso concludere il puzzle e vincere
    mot2.esegui("metti moneta nella fessura")
    mot2.esegui("giu")
    vittoria = mot2.esegui("prendi calice")
    assert "HAI VINTO" in vittoria, vittoria


def test_salva_carica_su_file():
    m = carica_mondo("avventure/caverna.json")
    mot = Motore(m)
    mot.avvia()
    mot.esegui("prendi lampada")
    mot.esegui("accendi lampada")
    mot.esegui("nord")

    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "slot1.sav"
        salva_partita(m, f)
        assert f.exists()
        # nuova sessione: avventura pulita + caricamento da file
        m2 = carica_mondo("avventure/caverna.json")
        assert m2.stanza_corrente == "ingresso"      # parte da capo...
        carica_partita(m2, f)
        assert m2.stanza_corrente == "corridoio"     # ...poi riprende
        assert m2.flags["lampada_accesa"] is True


def test_salva_stato_esteso():
    """Apertura contenitori, indumenti indossati, punteggio e mosse devono
    sopravvivere al salvataggio/caricamento."""
    m = carica_mondo("avventure/caverna.json")
    mot = Motore(m)
    mot.avvia()
    for c in ["prendi lampada", "accendi lampada", "nord", "prendi moneta",
              "metti moneta nella fessura", "giu", "apri baule",
              "prendi mantello", "indossa mantello"]:
        mot.esegui(c)
    m.punteggio = 50
    stato = stato_partita(m)

    m2 = carica_mondo("avventure/caverna.json")
    applica_stato(m2, stato)
    assert m2.oggetti["baule"].props.get("aperto") is True
    assert m2.oggetti["mantello"].props.get("indossato") is True
    assert m2.oggetti["mantello"].posizione == "inventario"
    assert m2.punteggio == 50
    assert m2.mosse == m.mosse


def main() -> int:
    for nome, fn in sorted(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()
            print(f"  ok  {nome}")
    print("Tutti i test del salvataggio superati.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
