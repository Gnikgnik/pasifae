# SPDX-License-Identifier: GPL-3.0-or-later
"""Test delle estensioni del motore (senza terminale).

Copre contenitori apribili, oggetti indossabili, punteggio/mosse e il fatto che
i verbi standard funzionino anche in un'avventura che non li dichiara.
Eseguibile con:  python3 test_estensioni.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from advcore import carica_mondo, Motore, Mondo, Stanza, Oggetto


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


def test_aiuto():
    m = carica_mondo("avventure/caverna.json")
    mot = Motore(m)
    mot.avvia()
    r = mot.esegui("aiuto")
    assert "Comandi" in r and "salva" in r and "parla" in r


def main() -> int:
    for nome, fn in sorted(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()
            print(f"  ok  {nome}")
    print("Tutti i test delle estensioni superati.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
