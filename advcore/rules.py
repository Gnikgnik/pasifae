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
  {"stampa": testo}
  {"teleporta": id_stanza}
  {"vittoria": testo} / {"sconfitta": testo}
  {"stato": n}                            porta il livello di conversazione del png a n
  {"avanza_stato": n}                     aumenta il livello di conversazione di n (default 1)
  {"inizia_scontro": id_png}              avvia un combattimento con il png
  {"avvia_timer": nome, "turni": k}        avvia un timer che scade fra k turni
  {"ferma_timer": nome}                    annulla un timer in corso
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
