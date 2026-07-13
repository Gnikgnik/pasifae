# SPDX-License-Identifier: GPL-3.0-or-later
"""Test delle estensioni del motore (senza terminale).

Copre contenitori apribili, oggetti indossabili, punteggio/mosse e il fatto che
i verbi standard funzionino anche in un'avventura che non li dichiara.
Eseguibile con:  python3 test_estensioni.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from advcore import carica_mondo, Motore, Mondo, Stanza, Oggetto, Verbo, Regola


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


def test_contenitore_annidato_in_scope():
    # scatola aperta dentro un baule aperto: l'anello dentro la scatola deve
    # essere visibile/prendibile anche se annidato a due livelli.
    m = Mondo(meta={"titolo": "Minimal", "stanza_iniziale": "qui"})
    m.stanze["qui"] = Stanza(id="qui", nome="Qui", desc="Una stanza spoglia.")
    m.oggetti["baule"] = Oggetto(id="baule", nome="baule", nomi=["baule"],
                                 posizione="qui",
                                 props={"contenitore": True, "aperto": True})
    m.oggetti["scatola"] = Oggetto(id="scatola", nome="scatola", nomi=["scatola"],
                                   posizione="baule",
                                   props={"contenitore": True, "aperto": True})
    m.oggetti["anello"] = Oggetto(id="anello", nome="anello", nomi=["anello"],
                                  posizione="scatola", props={"prendibile": True})
    mot = Motore(m)
    mot.avvia()
    assert "Prendi" in mot.esegui("prendi anello")
    assert m.oggetti["anello"].posizione == "inventario"


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


def test_preposizioni_articolate():
    # «nello zaino», «nell'astuccio»: tutte le forme articolate di «in» e «su»
    # devono dividere il comando in oggetto diretto e indiretto.
    m = Mondo(meta={"titolo": "Minimal", "stanza_iniziale": "qui"})
    m.stanze["qui"] = Stanza(id="qui", nome="Qui", desc="Una stanza spoglia.")
    m.oggetti["zaino"] = Oggetto(id="zaino", nome="zaino", nomi=["zaino"],
                                 posizione="qui",
                                 props={"contenitore": True, "aperto": True})
    m.oggetti["astuccio"] = Oggetto(id="astuccio", nome="astuccio",
                                    nomi=["astuccio"], posizione="qui",
                                    props={"contenitore": True, "aperto": True})
    m.oggetti["sasso"] = Oggetto(id="sasso", nome="sasso", nomi=["sasso"],
                                 posizione="qui", props={"prendibile": True})
    mot = Motore(m)
    mot.avvia()
    mot.esegui("prendi sasso")
    assert "Metti" in mot.esegui("metti sasso nello zaino")
    assert m.oggetti["sasso"].posizione == "zaino"
    mot.esegui("prendi sasso")
    assert "Metti" in mot.esegui("metti sasso nell'astuccio")
    assert m.oggetti["sasso"].posizione == "astuccio"


def test_aiuto():
    m = carica_mondo("avventure/caverna.json")
    mot = Motore(m)
    mot.avvia()
    r = mot.esegui("aiuto")
    assert "Comandi" in r and "salva" in r and "parla" in r
    # la caverna dichiara verbi ad hoc e usa il punteggio: devono comparire
    assert "accendi" in r and "spegni" in r
    assert "punteggio" in r


def test_aiuto_solo_verbi_usati():
    # L'aiuto elenca solo i verbi che l'avventura usa davvero: qui niente
    # contenitori, indumenti, personaggi o punteggio, ma un verbo ad hoc.
    m = Mondo(meta={"titolo": "Minimal", "stanza_iniziale": "qui"})
    m.stanze["qui"] = Stanza(id="qui", nome="Qui", desc="Una stanza spoglia.")
    m.oggetti["campana"] = Oggetto(id="campana", nome="campana",
                                   nomi=["campana"], posizione="qui",
                                   props={"scenario": True})
    m.oggetti["sasso"] = Oggetto(id="sasso", nome="sasso", nomi=["sasso"],
                                 posizione="qui", props={"prendibile": True})
    m.verbi["suona"] = Verbo(id="suona", sinonimi=["suonare"])
    m.regole.append(Regola(id="r_suona",
                           quando={"verbo": "suona", "oggetto": "campana"},
                           allora=[{"stampa": "Din don."}]))
    mot = Motore(m)
    mot.avvia()
    r = mot.esegui("aiuto")
    assert "suona <oggetto>" in r          # verbo ad hoc dichiarato
    assert "prendi" in r                   # c'è un oggetto prendibile
    assert "guarda" in r and "salva" in r  # sempre presenti
    for assente in ("apri", "indossa", "parla", "attacca", "punteggio"):
        assert assente not in r, f"«{assente}» non dovrebbe comparire"


def test_prep_lista_nella_regola():
    """`quando.prep` accetta anche una lista di preposizioni: una sola regola
    scatta con «usa chiave su automa» E «usa chiave con automa» (comprese le
    forme articolate). Le preposizioni fuori lista restano escluse."""
    def mondo():
        m = Mondo(meta={"stanza_iniziale": "qui"})
        m.stanze["qui"] = Stanza(id="qui", nome="Qui", desc="")
        m.oggetti["chiave"] = Oggetto(id="chiave", nome="chiave",
                                      nomi=["chiave"], posizione="inventario",
                                      props={"prendibile": True})
        m.oggetti["automa"] = Oggetto(id="automa", nome="automa",
                                      nomi=["automa"], posizione="qui",
                                      props={"scenario": True})
        m.verbi["usa"] = Verbo(id="usa", sinonimi=["usare"])
        m.regole.append(Regola(id="r_usa",
                               quando={"verbo": "usa", "oggetto": "chiave",
                                       "prep": ["su", "con"],
                                       "oggetto_indiretto": "automa"},
                               allora=[{"stampa": "Clic."}]))
        return m

    for frase in ("usa chiave su automa", "usa chiave con automa",
                  "usa chiave sull'automa"):
        mot = Motore(mondo())
        mot.avvia()
        assert "Clic." in mot.esegui(frase), frase
    mot = Motore(mondo())
    mot.avvia()
    assert "Clic." not in mot.esegui("usa chiave nell'automa")
    # retrocompatibilità: la stringa singola continua a funzionare
    m = mondo()
    m.regole[0].quando["prep"] = "su"
    mot = Motore(m)
    mot.avvia()
    assert "Clic." in mot.esegui("usa chiave su automa")


def test_prendi_tutto():
    """«prendi tutto» (o «tutti») raccoglie gli oggetti prendibili della
    stanza, ignora scenario e non prendibili, e ogni presa passa dalle
    regole dell'autore come un «prendi» singolo."""
    def mondo():
        m = Mondo(meta={"stanza_iniziale": "sala"})
        m.stanze["sala"] = Stanza(id="sala", nome="Sala", desc="")
        m.oggetti["chiave"] = Oggetto(id="chiave", nome="chiave",
                                      nomi=["chiave"], posizione="sala",
                                      props={"prendibile": True})
        m.oggetti["moneta"] = Oggetto(id="moneta", nome="moneta",
                                      nomi=["moneta"], posizione="sala",
                                      props={"prendibile": True})
        m.oggetti["statua"] = Oggetto(id="statua", nome="statua",
                                      nomi=["statua"], posizione="sala",
                                      props={"scenario": True,
                                             "prendibile": False})
        return m

    mot = Motore(mondo())
    mot.avvia()
    r = mot.esegui("prendi tutto")
    assert "Prendi chiave." in r and "Prendi moneta." in r
    assert "statua" not in r                      # scenario: nemmeno nominata
    assert mot.mondo.oggetti["chiave"].posizione == "inventario"
    assert mot.mondo.oggetti["moneta"].posizione == "inventario"
    assert mot.mondo.oggetti["statua"].posizione == "sala"
    assert "nulla da prendere" in mot.esegui("prendi tutto")

    # una regola dell'autore intercetta la presa singola anche dentro «tutto»
    m = mondo()
    m.regole.append(Regola(id="r_chiave",
                           quando={"verbo": "prendi", "oggetto": "chiave"},
                           allora=[{"stampa": "La chiave scotta!"}]))
    mot = Motore(m)
    mot.avvia()
    r = mot.esegui("prendi tutto")
    assert "La chiave scotta!" in r
    assert m.oggetti["chiave"].posizione == "sala"   # la regola non la sposta
    assert m.oggetti["moneta"].posizione == "inventario"

    # al buio non si vede cosa raccogliere; «tutto» vale solo per «prendi»
    m2 = mondo()
    m2.stanze["sala"].buia = True
    mot2 = Motore(m2)
    mot2.avvia()
    assert "buio" in mot2.esegui("prendi tutti").lower()
    mot3 = Motore(mondo())
    mot3.avvia()
    assert "tutto" in mot3.esegui("esamina tutto")


def test_prendi_tutto_contenitori_aperti():
    """«prendi tutto» raccoglie anche il contenuto dei contenitori aperti
    visibili nella stanza (pure annidati); ignora i contenitori chiusi e
    non svuota quelli portati nell'inventario."""
    def mondo():
        m = Mondo(meta={"stanza_iniziale": "sala"})
        m.stanze["sala"] = Stanza(id="sala", nome="Sala", desc="")
        m.oggetti["botola"] = Oggetto(id="botola", nome="botola",
                                      nomi=["botola"], posizione="sala",
                                      props={"scenario": True,
                                             "contenitore": True,
                                             "aperto": True})
        m.oggetti["libro"] = Oggetto(id="libro", nome="libro",
                                     nomi=["libro"], posizione="botola",
                                     props={"prendibile": True})
        m.oggetti["scatola"] = Oggetto(id="scatola", nome="scatola",
                                       nomi=["scatola"], posizione="botola",
                                       props={"prendibile": True,
                                              "contenitore": True,
                                              "aperto": True})
        m.oggetti["moneta"] = Oggetto(id="moneta", nome="moneta",
                                      nomi=["moneta"], posizione="scatola",
                                      props={"prendibile": True})
        m.oggetti["baule"] = Oggetto(id="baule", nome="baule",
                                     nomi=["baule"], posizione="sala",
                                     props={"scenario": True,
                                            "contenitore": True,
                                            "aperto": False})
        m.oggetti["gemma"] = Oggetto(id="gemma", nome="gemma",
                                     nomi=["gemma"], posizione="baule",
                                     props={"prendibile": True})
        m.oggetti["borsa"] = Oggetto(id="borsa", nome="borsa",
                                     nomi=["borsa"], posizione="inventario",
                                     props={"prendibile": True,
                                            "contenitore": True,
                                            "aperto": True})
        m.oggetti["mela"] = Oggetto(id="mela", nome="mela",
                                    nomi=["mela"], posizione="borsa",
                                    props={"prendibile": True})
        return m

    mot = Motore(mondo())
    mot.avvia()
    r = mot.esegui("prendi tutto")
    # dal contenitore aperto (e da quello annidato dentro di esso)
    assert "Prendi libro." in r and "Prendi moneta." in r
    assert mot.mondo.oggetti["libro"].posizione == "inventario"
    assert mot.mondo.oggetti["moneta"].posizione == "inventario"
    # il contenitore chiuso resta sigillato
    assert "gemma" not in r
    assert mot.mondo.oggetti["gemma"].posizione == "baule"
    # la borsa che porti con te non viene svuotata
    assert "mela" not in r
    assert mot.mondo.oggetti["mela"].posizione == "borsa"


def test_immagine_stanza_opzionale():
    """Il campo `immagine` della stanza è opzionale e retrocompatibile:
    sopravvive al round-trip su file, non compare nel JSON quando è vuoto,
    e le avventure esistenti (senza campo) continuano a caricarsi."""
    import json
    import tempfile
    from advcore import salva_mondo

    m = Mondo(meta={"titolo": "Con figure", "stanza_iniziale": "atrio"})
    m.stanze["atrio"] = Stanza(id="atrio", nome="Atrio", desc="",
                               immagine="atrio.png")
    m.stanze["cella"] = Stanza(id="cella", nome="Cella", desc="")

    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "figure.json"
        salva_mondo(m, f)
        dati = json.loads(f.read_text(encoding="utf-8"))
        assert dati["stanze"]["atrio"]["immagine"] == "atrio.png"
        assert "immagine" not in dati["stanze"]["cella"]     # niente rumore
        m2 = carica_mondo(f)
        assert m2.stanze["atrio"].immagine == "atrio.png"
        assert m2.stanze["cella"].immagine == ""

    # un'avventura esistente, senza campo, carica con immagine vuota
    m3 = carica_mondo("avventure/caverna.json")
    assert all(s.immagine == "" for s in m3.stanze.values())


def test_cambia_immagine_sostituisce_e_ripristina():
    """L'effetto cambia_immagine sostituisce l'illustrazione di una stanza
    a runtime (stanza.immagine_attuale), senza toccare il valore di default
    dichiarato dall'autore (stanza.immagine); un'immagine vuota ripristina
    il default."""
    m = Mondo(meta={"stanza_iniziale": "ingresso"})
    m.stanze["ingresso"] = Stanza(id="ingresso", nome="Ingresso", desc="",
                                  immagine="ingresso.png")
    m.oggetti["porta"] = Oggetto(id="porta", nome="porta", nomi=["porta"],
                                 posizione="ingresso", props={"contenitore": True,
                                                              "aperto": False})
    m.regole.append(Regola(
        id="r_apri", quando={"verbo": "apri", "oggetto": "porta"},
        allora=[{"cambia_immagine": "ingresso", "immagine": "ingresso_aperta.png"}]))
    m.regole.append(Regola(
        id="r_chiudi", quando={"verbo": "chiudi", "oggetto": "porta"},
        allora=[{"cambia_immagine": "ingresso", "immagine": ""}]))
    mot = Motore(m)
    mot.avvia()

    assert m.stanze["ingresso"].immagine_attuale == ""
    mot.esegui("apri porta")
    assert m.stanze["ingresso"].immagine_attuale == "ingresso_aperta.png"
    assert m.stanze["ingresso"].immagine == "ingresso.png"    # default intatto

    mot.esegui("chiudi porta")
    assert m.stanze["ingresso"].immagine_attuale == ""


def _mondo_nascondino():
    m = Mondo(meta={"stanza_iniziale": "studio"})
    m.stanze["studio"] = Stanza(id="studio", nome="Studio",
                                desc="Una scrivania polverosa.")
    m.oggetti["chiave"] = Oggetto(id="chiave", nome="chiave", nomi=["chiave"],
                                  posizione="studio",
                                  props={"prendibile": True, "nascosto": True})
    return m


def test_oggetto_nascosto_invisibile_e_non_prendibile():
    """Un oggetto «nascosto» non compare nella descrizione della stanza, non
    si può esaminare né prendere per nome (il parser lo tratta come
    inesistente, non diversamente da un oggetto che non c'è)."""
    m = _mondo_nascondino()
    mot = Motore(m)
    descrizione = mot.avvia()
    assert "chiave" not in descrizione.lower()
    assert "Non vedo nessun" in mot.esegui("esamina chiave")
    assert "Non vedo nessun" in mot.esegui("prendi chiave")
    assert m.oggetti["chiave"].posizione == "studio"


def test_mostra_oggetto_lo_rende_visibile_e_prendibile():
    """L'effetto mostra_oggetto rimuove nascosto: da quel momento l'oggetto
    compare nella stanza e si può esaminare/prendere normalmente."""
    m = _mondo_nascondino()
    m.regole.append(Regola(
        id="r_apri_cassetto",
        quando={"verbo": "apri", "oggetto": "scrivania"},
        allora=[{"mostra_oggetto": "chiave"}]))
    m.oggetti["scrivania"] = Oggetto(id="scrivania", nome="scrivania",
                                     nomi=["scrivania"], posizione="studio",
                                     props={"scenario": True})
    mot = Motore(m)
    mot.avvia()
    assert "Non vedo nessun" in mot.esegui("prendi chiave")

    mot.esegui("apri scrivania")
    assert m.oggetti["chiave"].props.get("nascosto") is False
    assert "chiave" in mot.esegui("guarda").lower()
    assert "Prendi chiave." in mot.esegui("prendi chiave")
    assert m.oggetti["chiave"].posizione == "inventario"


def test_nascondi_oggetto_lo_toglie_di_nuovo_di_mezzo():
    """nascondi_oggetto è il simmetrico di mostra_oggetto: rimette
    nascosto a vero su un oggetto in precedenza visibile."""
    m = Mondo(meta={"stanza_iniziale": "studio"})
    m.stanze["studio"] = Stanza(id="studio", nome="Studio", desc="")
    m.oggetti["moneta"] = Oggetto(id="moneta", nome="moneta", nomi=["moneta"],
                                  posizione="studio", props={"prendibile": True})
    from advcore.rules import esegui_effetti
    out = []
    esegui_effetti([{"nascondi_oggetto": "moneta"}], m, out)
    assert m.oggetti["moneta"].props["nascosto"] is True
    mot = Motore(m)
    mot.avvia()
    assert "Non vedo nessun" in mot.esegui("esamina moneta")


def test_prendi_tutto_ignora_oggetti_nascosti():
    """«prendi tutto» non deve raccogliere un oggetto nascosto: il
    giocatore non sa nemmeno che esiste finché non viene rivelato."""
    m = _mondo_nascondino()
    m.oggetti["moneta"] = Oggetto(id="moneta", nome="moneta", nomi=["moneta"],
                                  posizione="studio", props={"prendibile": True})
    mot = Motore(m)
    mot.avvia()
    r = mot.esegui("prendi tutto")
    assert "Prendi moneta." in r
    assert "chiave" not in r.lower()
    assert m.oggetti["chiave"].posizione == "studio"


def main() -> int:
    for nome, fn in sorted(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()
            print(f"  ok  {nome}")
    print("Tutti i test delle estensioni superati.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
