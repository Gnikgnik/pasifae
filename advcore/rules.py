# SPDX-License-Identifier: GPL-3.0-or-later
"""Valutazione delle condizioni ed esecuzione degli effetti delle regole.

Una regola e' dati puri: condizioni (AND) sui flag e sullo stato del mondo, ed
effetti che modificano flag, spostano oggetti, stampano testo o muovono il
giocatore. Tutto qui e' editabile dall'editor senza scrivere codice Python.

Vocabolario delle CONDIZIONI (campo "se"):
  {"flag": nome, "uguale": valore}        flag == valore
  {"flag": nome, "maggiore": n}           flag (numerico) > n
  {"flag": nome, "minore": n}             flag (numerico) < n
  {"flag": nome, "maggiore_uguale": n}    flag (numerico) >= n
  {"flag": nome, "minore_uguale": n}      flag (numerico) <= n
  {"oggetto_in": [id_oggetto, dove]}      dove: "inventario" | "stanza" | id stanza/contenitore
  {"stanza_corrente": id_stanza}          il giocatore e' in quella stanza
  {"stato_min": n}                        livello di conversazione del png corrente >= n
  {"mosse_min": n}                         numero di turni trascorsi >= n
  {"non": cond}                            NON (nega una condizione)
  {"oppure": [cond, ...]}                  almeno una vera (OR)
  {"tutte": [cond, ...]}                   tutte vere (AND, per annidare)
La lista "se" e' valutata in AND; usa "oppure"/"non" per le altre combinazioni.

Vocabolario degli EFFETTI (campi "allora"/"altrimenti"):
  {"set_flag": nome, "valore": v}
  {"incrementa": nome, "di": n}
  {"punti": n}                            aggiunge n al punteggio
  {"sposta_oggetto": id, "a": dove}       dove: "inventario" | id stanza/contenitore
  {"scarta_oggetto": id}                  toglie l'oggetto dal gioco (scarico/rovinato)
  {"apri_oggetto": id}                    apre un contenitore (props["aperto"] = True)
  {"chiudi_oggetto": id}                  chiude un contenitore (props["aperto"] = False)
  {"mostra_oggetto": id}                  rivela un oggetto nascosto (props["nascosto"] = False)
  {"nascondi_oggetto": id}                nasconde un oggetto (props["nascosto"] = True)
  {"stampa": testo}
  {"teleporta": id_stanza}
  {"vittoria": testo} / {"sconfitta": testo}
  {"stato": n}                            porta il livello di conversazione del png a n
  {"avanza_stato": n}                     aumenta il livello di conversazione di n (default 1)
  {"inizia_scontro": id_png}              avvia un combattimento con il png
  {"avvia_timer": nome, "turni": k}        avvia un timer che scade fra k turni
  {"ferma_timer": nome}                    annulla un timer in corso
  {"avvia_dialogo": id_oggetto}            apre il dialogo (saluto + battute)
                                           dell'oggetto — come il verbo builtin
                                           "parla", ma agganciabile a qualunque
                                           verbo/oggetto tramite una regola
                                           dell'autore (non richiede props["png"])
  {"cambia_immagine": id_stanza, "immagine": nome_file}
                                           sostituisce l'illustrazione della
                                           stanza a runtime; "immagine" vuota
                                           (o assente) ripristina il default
                                           dichiarato dall'autore
"""

from __future__ import annotations

from .model import Mondo, INVENTARIO, SCARTATO


def valuta_condizioni(condizioni: list[dict], mondo: Mondo) -> bool:
    """Vero se TUTTE le condizioni sono soddisfatte (AND)."""
    return all(_valuta_una(c, mondo) for c in condizioni)


def esegui_effetti(effetti: list[dict], mondo: Mondo, out: list[str]) -> None:
    """Esegue gli effetti in ordine, accumulando il testo in `out`."""
    for e in effetti:
        _esegui_uno(e, mondo, out)


# ------- condizioni -------

def _valuta_una(c: dict, mondo: Mondo) -> bool:
    if "non" in c:
        return not _valuta_una(c["non"], mondo)
    if "oppure" in c:
        return any(_valuta_una(s, mondo) for s in c["oppure"])
    if "tutte" in c:
        return all(_valuta_una(s, mondo) for s in c["tutte"])
    if "flag" in c:
        valore = mondo.flags.get(c["flag"])
        if "uguale" in c:
            return valore == c["uguale"]
        num = isinstance(valore, (int, float))
        if "maggiore" in c:
            return num and valore > c["maggiore"]
        if "minore" in c:
            return num and valore < c["minore"]
        if "maggiore_uguale" in c:
            return num and valore >= c["maggiore_uguale"]
        if "minore_uguale" in c:
            return num and valore <= c["minore_uguale"]
        return bool(valore)
    if "oggetto_in" in c:
        oid, dove = c["oggetto_in"]
        ogg = mondo.oggetti.get(oid)
        if ogg is None:
            return False
        if dove == "stanza":
            return ogg.posizione == mondo.stanza_corrente
        return ogg.posizione == dove
    if "stanza_corrente" in c:
        return mondo.stanza_corrente == c["stanza_corrente"]
    if "stato_min" in c:
        return _stato_conversazione(mondo) >= c["stato_min"]
    if "mosse_min" in c:
        return mondo.mosse >= c["mosse_min"]
    return False


def battute_disponibili(mondo: Mondo, o) -> list[tuple[int, dict]]:
    """Battute di un dialogo attualmente selezionabili: (indice, battuta).

    Pura logica di modello (condiviso da Motore._battute_disponibili e
    dall'effetto avvia_dialogo): non richiede che l'oggetto sia un png."""
    disp = []
    for i, b in enumerate(o.props.get("dialogo", [])):
        if b.get("una_volta") and mondo.flags.get(f"__dlg_{o.id}_{i}"):
            continue
        if not valuta_condizioni(b.get("se", []), mondo):
            continue
        disp.append((i, b))
    return disp


def menu_dialogo(mondo: Mondo, o) -> str:
    righe = []
    for n, (_i, b) in enumerate(battute_disponibili(mondo, o), start=1):
        righe.append(f"  {n}. {b['etichetta']}")
    etichetta_uscita = o.props.get("etichetta_uscita") or "saluta e vai"
    righe.append(f"  0. ({etichetta_uscita})")
    return "\n".join(righe)


def avvia_conversazione(mondo: Mondo, o) -> str:
    """Apre il dialogo di un oggetto: saluto (se presente) + primo menu, o
    chiusura immediata se non ci sono battute disponibili. Condivisa dal
    verbo builtin "parla" e dall'effetto di regola "avvia_dialogo", così
    un autore può agganciare l'apertura del dialogo a un verbo qualsiasi
    (es. "usa" su un terminale, che non è un personaggio/png)."""
    parti = []
    if o.props.get("saluto"):
        parti.append(o.props["saluto"])
    # imposto l'oggetto corrente PRIMA di filtrare le battute, così le
    # condizioni/effetti di stato sanno con chi/cosa si sta interagendo
    mondo.conversazione = o.id
    if not battute_disponibili(mondo, o):
        mondo.conversazione = ""
        parti.append(f"{o.nome.capitalize()} non ha nulla da dirti.")
        return "\n".join(parti)
    parti.append(menu_dialogo(mondo, o))
    parti.append("(scegli un numero)")
    return "\n".join(parti)


def _stato_conversazione(mondo: Mondo) -> int:
    """Livello di conversazione del png con cui si sta parlando.

    È memorizzato in un flag riservato __stato_<png>; il valore di partenza
    è la prop opzionale `stato_iniziale` del png (0 se assente).
    """
    npc = mondo.conversazione
    base = 0
    o = mondo.oggetti.get(npc)
    if o is not None:
        base = o.props.get("stato_iniziale", 0)
    val = mondo.flags.get(f"__stato_{npc}", base)
    return val if isinstance(val, (int, float)) else 0


# ------- effetti -------

def _esegui_uno(e: dict, mondo: Mondo, out: list[str]) -> None:
    if "set_flag" in e:
        mondo.flags[e["set_flag"]] = e.get("valore", True)
    elif "incrementa" in e:
        nome = e["incrementa"]
        mondo.flags[nome] = mondo.flags.get(nome, 0) + e.get("di", 1)
    elif "punti" in e:
        mondo.punteggio += e.get("punti", 0)
    elif "sposta_oggetto" in e:
        ogg = mondo.oggetti.get(e["sposta_oggetto"])
        if ogg is not None:
            dest = e["a"]
            ogg.posizione = INVENTARIO if dest == "inventario" else dest
    elif "apri_oggetto" in e or "chiudi_oggetto" in e:
        # solo sui contenitori: apre/chiude commutando props["aperto"]
        oid = e.get("apri_oggetto") or e.get("chiudi_oggetto")
        ogg = mondo.oggetti.get(oid)
        if ogg is not None and ogg.props.get("contenitore"):
            ogg.props["aperto"] = "apri_oggetto" in e
    elif "mostra_oggetto" in e or "nascondi_oggetto" in e:
        # su qualunque oggetto: commuta props["nascosto"]
        oid = e.get("mostra_oggetto") or e.get("nascondi_oggetto")
        ogg = mondo.oggetti.get(oid)
        if ogg is not None:
            ogg.props["nascosto"] = "nascondi_oggetto" in e
    elif "scarta_oggetto" in e:
        ogg = mondo.oggetti.get(e["scarta_oggetto"])
        if ogg is not None:
            ogg.posizione = SCARTATO
        if e.get("stampa"):
            out.append(e["stampa"])
    elif "stampa" in e:
        out.append(e["stampa"])
    elif "teleporta" in e:
        if e["teleporta"] in mondo.stanze:
            mondo.stanza_corrente = e["teleporta"]
    elif "vittoria" in e:
        mondo.finita = True
        mondo.messaggio_finale = e.get("vittoria", "Hai vinto!")
        out.append(mondo.messaggio_finale)
    elif "sconfitta" in e:
        mondo.finita = True
        mondo.messaggio_finale = e.get("sconfitta", "Hai perso.")
        out.append(mondo.messaggio_finale)
    elif "stato" in e:
        mondo.flags[f"__stato_{mondo.conversazione}"] = e["stato"]
    elif "avanza_stato" in e:
        npc = mondo.conversazione
        mondo.flags[f"__stato_{npc}"] = _stato_conversazione(mondo) + e.get("avanza_stato", 1)
    elif "inizia_scontro" in e:
        npc = e["inizia_scontro"]
        o = mondo.oggetti.get(npc)
        if o is not None:
            mondo.scontro = npc
            mondo.flags[f"__hp_{npc}"] = o.props.get("hp", 1)
            mondo.flags.setdefault("pg_hp", 20)
            mondo.flags.setdefault("pg_attacco", 5)
            mondo.flags.setdefault("pg_difesa", 1)
            out.append(o.props.get("intro_scontro",
                                   f"{o.nome.capitalize()} ti affronta!"))
    elif "avvia_timer" in e:
        mondo.timer[e["avvia_timer"]] = int(e.get("turni", 1))
    elif "ferma_timer" in e:
        mondo.timer.pop(e["ferma_timer"], None)
    elif "avvia_dialogo" in e:
        o = mondo.oggetti.get(e["avvia_dialogo"])
        if o is not None:
            out.append(avvia_conversazione(mondo, o))
    elif "cambia_immagine" in e:
        st = mondo.stanze.get(e["cambia_immagine"])
        if st is not None:
            st.immagine_attuale = e.get("immagine", "")
