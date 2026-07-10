# SPDX-License-Identifier: GPL-3.0-or-later
"""Test di personaggi/dialoghi e oggetti combinabili (senza terminale).

Eseguibile con:  python3 test_dialoghi.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from advcore import carica_mondo, Motore, Mondo, Stanza, Oggetto, Regola


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


def _mondo_terminale(congedo=None):
    """Un oggetto NON marcato «png» (un terminale), con un dialogo aperto
    dal verbo «usa» tramite una regola (effetto avvia_dialogo), non da
    «parla» — vedi test_avvia_dialogo_da_regola_su_oggetto_non_png."""
    m = Mondo(meta={"titolo": "Terminale", "stanza_iniziale": "qui"})
    m.stanze["qui"] = Stanza(id="qui", nome="Qui", desc="Una stanza con un terminale.")
    props = {
        "scenario": True,
        "saluto": "Il cursore lampeggia in attesa di un comando.",
        "dialogo": [{"etichetta": "Chiedi lo stato del sistema",
                     "testo": "SISTEMA OK.", "se": [], "allora": [],
                     "una_volta": False}],
    }
    if congedo is not None:
        props["congedo"] = congedo
    m.oggetti["terminale"] = Oggetto(id="terminale", nome="terminale",
                                     nomi=["terminale"], posizione="qui",
                                     props=props)
    m.regole.append(Regola(id="r_usa_terminale",
                           quando={"verbo": "usa", "oggetto": "terminale"},
                           allora=[{"avvia_dialogo": "terminale"}]))
    mot = Motore(m)
    mot.avvia()
    return m, mot


def test_avvia_dialogo_da_regola_su_oggetto_non_png():
    """Un oggetto non marcato «png» (un terminale) può avviare un dialogo
    se una regola dell'autore lo aggancia a un verbo qualsiasi (qui «usa»)
    con l'effetto avvia_dialogo — «parla» resta bloccato dal controllo sul
    png, così l'autore sceglie il verbo giusto per l'oggetto giusto."""
    m, mot = _mondo_terminale()
    bloccato = mot.esegui("parla con terminale")
    assert "conversazione" in bloccato.lower()
    assert m.conversazione == ""

    apertura = mot.esegui("usa terminale")
    assert "cursore" in apertura.lower()
    assert "Chiedi lo stato" in apertura
    assert m.conversazione == "terminale"

    risposta = mot.esegui("1")
    assert "SISTEMA OK" in risposta


def test_congedo_personalizzato():
    """Il messaggio di congedo di un dialogo è personalizzabile (props
    «congedo»): utile per un terminale, per cui «Saluti terminale.» non
    avrebbe senso. Senza la prop, il motore usa il saluto di default."""
    m, mot = _mondo_terminale(congedo="Il terminale torna alla schermata inattiva.")
    mot.esegui("usa terminale")
    assert mot.esegui("esci") == "Il terminale torna alla schermata inattiva."

    m2, mot2 = _mondo_terminale()
    mot2.esegui("usa terminale")
    assert mot2.esegui("esci") == "Saluti terminale."


def test_congedo_personalizzato_a_battute_esaurite():
    """Il congedo personalizzato vale anche quando le battute finiscono da
    sole (non solo quando il giocatore scrive «esci»)."""
    m, mot = _mondo_terminale(congedo="Il terminale torna alla schermata inattiva.")
    m.oggetti["terminale"].props["dialogo"][0]["una_volta"] = True
    mot.esegui("usa terminale")
    fine = mot.esegui("1")
    assert "Non hai altro da chiedere. Il terminale torna alla schermata inattiva." in fine
    assert m.conversazione == ""


def test_etichetta_uscita_personalizzata():
    """La voce «0.» del menu di dialogo è personalizzabile (props
    «etichetta_uscita»): «(saluta e vai)» non ha senso per un terminale.
    Senza la prop, resta l'etichetta di default, invariata."""
    m, mot = _mondo_terminale()
    m.oggetti["terminale"].props["etichetta_uscita"] = "torna alla shell"
    apertura = mot.esegui("usa terminale")
    assert "0. (torna alla shell)" in apertura
    assert "saluta e vai" not in apertura

    m2, mot2 = _mondo_terminale()
    apertura2 = mot2.esegui("usa terminale")
    assert "0. (saluta e vai)" in apertura2


def main() -> int:
    for nome, fn in sorted(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()
            print(f"  ok  {nome}")
    print("Tutti i test di dialoghi e combinazioni superati.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
