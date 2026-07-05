# SPDX-License-Identifier: GPL-3.0-or-later
"""Test della validazione del Mondo (senza terminale).

Verifica che l'avventura di esempio sia pulita e che, introducendo riferimenti
rotti, vengano segnalati con la gravità corretta. Eseguibile con:
    python3 test_validazione.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from advcore import carica_mondo, valida, Oggetto, Regola


def _per_categoria(problemi, categoria):
    return [p for p in problemi if p.categoria == categoria]


def test_regola_evento_valida():
    m = carica_mondo("avventure/caverna.json")
    # una regola-evento ben formata non deve produrre errori
    m.regole.append(Regola(id="ogni", quando={"evento": "turno"},
                           allora=[{"stampa": "tic"}]))
    m.regole.append(Regola(id="ing", quando={"evento": "entra",
                                             "stanza": next(iter(m.stanze))},
                           allora=[{"stampa": "qui"}]))
    errori = [p for p in valida(m) if p.gravita == "errore"]
    assert errori == [], [p.messaggio for p in errori]


def test_regola_evento_incompleta():
    m = carica_mondo("avventure/caverna.json")
    m.regole.append(Regola(id="rotta", quando={"evento": "entra"},  # manca stanza
                           allora=[{"stampa": "x"}]))
    assert any(p.gravita == "errore" and "rotta" in p.dove for p in valida(m))


def test_avventura_esempio_pulita():
    m = carica_mondo("avventure/caverna.json")
    errori = [p for p in valida(m) if p.gravita == "errore"]
    assert errori == [], [p.messaggio for p in errori]


def test_prep_lista_validata():
    """Anche con una lista di preposizioni la validazione controlla ogni voce:
    quelle note passano, una sconosciuta produce l'avviso."""
    m = carica_mondo("avventure/caverna.json")
    ogg = next(iter(m.oggetti))
    m.regole.append(Regola(id="r_lista",
                           quando={"verbo": "guarda", "oggetto": ogg,
                                   "prep": ["su", "con"]},
                           allora=[{"stampa": "ok"}]))
    assert not any("preposizione" in p.messaggio for p in valida(m))
    m.regole[-1].quando["prep"] = ["su", "boh"]
    assert any("preposizione" in p.messaggio and "boh" in p.messaggio
               for p in valida(m))


def test_uscita_rotta():
    m = carica_mondo("avventure/caverna.json")
    m.stanze["ingresso"].uscite["nord"] = "stanza_fantasma"
    problemi = valida(m)
    rotte = [p for p in problemi
             if p.gravita == "errore" and "stanza_fantasma" in p.messaggio]
    assert rotte and rotte[0].categoria == "stanza"


def test_posizione_oggetto_rotta():
    m = carica_mondo("avventure/caverna.json")
    m.oggetti["lampada"].posizione = "luogo_che_non_esiste"
    problemi = valida(m)
    assert any(p.gravita == "errore" and p.categoria == "oggetto"
               and "lampada" in p.dove for p in problemi)


def test_regola_con_verbo_e_oggetto_inesistenti():
    m = carica_mondo("avventure/caverna.json")
    m.regole.append(Regola(id="rotta",
                           quando={"verbo": "danza", "oggetto": "unicorno"}))
    errori = [p for p in valida(m)
              if p.gravita == "errore" and p.categoria == "regola"]
    msgs = " ".join(p.messaggio for p in errori)
    assert "danza" in msgs and "unicorno" in msgs


def test_flag_mai_impostato_e_avviso():
    m = carica_mondo("avventure/caverna.json")
    # un'uscita che dipende da un flag inesistente -> avviso, non errore
    m.stanze["ingresso"].uscite["est"] = {"to": "corridoio", "se": "flag_inventato"}
    avvisi = [p for p in valida(m) if p.gravita == "avviso"
              and "flag_inventato" in p.messaggio]
    assert avvisi


def test_sinonimo_verbo_ambiguo():
    m = carica_mondo("avventure/caverna.json")
    # rendo "x" sinonimo sia di esamina sia di prendi
    m.verbi["prendi"].sinonimi.append("x")
    avvisi = [p for p in valida(m) if p.categoria == "verbo"]
    assert any("x" in p.dove for p in avvisi)


def test_verbi_predefiniti_accettati():
    # una regola che innesca su un verbo predefinito (apri/usa/esamina) non
    # deve essere segnalata come «verbo inesistente», anche se non dichiarato
    m = carica_mondo("avventure/caverna.json")
    m.regole.append(Regola(id="apri_qualcosa",
                           quando={"verbo": "apri", "oggetto": "lampada"}))
    errori = [p for p in valida(m)
              if p.gravita == "errore" and "apri" in p.messaggio]
    assert not errori


def main() -> int:
    for nome, fn in sorted(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()
            print(f"  ok  {nome}")
    print("Tutti i test della validazione superati.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
