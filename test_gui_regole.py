# SPDX-License-Identifier: GPL-3.0-or-later
"""Test della logica pura dell'editor regole (gui/regole.py), senza Qt."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from advcore import Mondo, Regola
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


def test_apri_chiudi_contenitore():
    # assemblaggio, inverso (per la modifica) e riassunto leggibile
    assert R.ASSEMBLA["apri_oggetto"]({"oggetto": "baule"}) == {"apri_oggetto": "baule"}
    assert R.ASSEMBLA["chiudi_oggetto"]({"oggetto": "baule"}) == {"chiudi_oggetto": "baule"}
    assert R.da_dict({"apri_oggetto": "baule"}) == ("apri_oggetto", {"oggetto": "baule"})
    assert R.da_dict({"chiudi_oggetto": "baule"}) == ("chiudi_oggetto", {"oggetto": "baule"})
    assert "baule" in R.riassunto_effetto({"apri_oggetto": "baule"})
    assert "chiude" in R.riassunto_effetto({"chiudi_oggetto": "baule"})


def test_mostra_nascondi_oggetto():
    # assemblaggio, inverso (per la modifica) e riassunto leggibile
    assert R.ASSEMBLA["mostra_oggetto"]({"oggetto": "chiave"}) == {"mostra_oggetto": "chiave"}
    assert R.ASSEMBLA["nascondi_oggetto"]({"oggetto": "chiave"}) == {"nascondi_oggetto": "chiave"}
    assert R.da_dict({"mostra_oggetto": "chiave"}) == ("mostra_oggetto", {"oggetto": "chiave"})
    assert R.da_dict({"nascondi_oggetto": "chiave"}) == ("nascondi_oggetto", {"oggetto": "chiave"})
    assert "chiave" in R.riassunto_effetto({"mostra_oggetto": "chiave"})
    assert "chiave" in R.riassunto_effetto({"nascondi_oggetto": "chiave"})


def test_cambia_immagine():
    # assemblaggio, inverso (per la modifica) e riassunto leggibile: sia
    # con un'immagine sia con il ripristino del default (campo vuoto)
    assert R.ASSEMBLA["cambia_immagine"]({"stanza": "ingresso", "immagine": "buio.png"}) == \
        {"cambia_immagine": "ingresso", "immagine": "buio.png"}
    assert R.da_dict({"cambia_immagine": "ingresso", "immagine": "buio.png"}) == \
        ("cambia_immagine", {"stanza": "ingresso", "immagine": "buio.png"})
    assert "buio.png" in R.riassunto_effetto(
        {"cambia_immagine": "ingresso", "immagine": "buio.png"})
    assert "default" in R.riassunto_effetto(
        {"cambia_immagine": "ingresso", "immagine": ""})


def test_immagini_regole():
    """immagini_regole raccoglie i file usati da cambia_immagine nelle
    regole (utile a compila.py per impacchettarli): un ripristino al
    default (immagine vuota) non produce un file da cercare."""
    m = Mondo()
    m.regole.append(Regola(
        id="r1", quando={"verbo": "apri", "oggetto": "porta"},
        allora=[{"cambia_immagine": "ingresso", "immagine": "aperta.png"}]))
    m.regole.append(Regola(
        id="r2", quando={"verbo": "chiudi", "oggetto": "porta"},
        allora=[{"cambia_immagine": "ingresso", "immagine": ""}]))
    assert R.immagini_regole(m) == {"aperta.png"}


def test_val_da_testo():
    assert R.val_da_testo("vero") is True
    assert R.val_da_testo("falso") is False
    assert R.val_da_testo("7") == 7
    assert R.val_da_testo("ciao") == "ciao"


def test_avvia_dialogo():
    # assemblaggio, inverso (per la modifica) e riassunto leggibile: apre il
    # dialogo di un oggetto qualsiasi (non serve che sia un png), utile per
    # agganciarlo a un verbo diverso da "parla" (es. "usa" su un terminale)
    assert R.ASSEMBLA["avvia_dialogo"]({"oggetto": "terminale"}) == \
        {"avvia_dialogo": "terminale"}
    assert R.da_dict({"avvia_dialogo": "terminale"}) == \
        ("avvia_dialogo", {"oggetto": "terminale"})
    assert "terminale" in R.riassunto_effetto({"avvia_dialogo": "terminale"})


def test_riassunti_e_innesco():
    assert "p" in R.riassunto_condizione({"flag": "p", "uguale": True})
    assert R.quando_breve({"evento": "turno"}) == "a ogni turno"
    assert "ingresso" in R.quando_breve({"evento": "entra", "stanza": "x"})
    assert R.riassunto_effetto({"avvia_timer": "b", "turni": 3}).startswith("avvia timer")


def test_quando_breve_prep_lista():
    """Il riassunto della regola mostra le preposizioni multiple come «su/con»."""
    q = {"verbo": "usa", "oggetto": "chiave", "prep": ["su", "con"],
         "oggetto_indiretto": "automa"}
    assert R.quando_breve(q) == "comando: usa chiave su/con automa"


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
