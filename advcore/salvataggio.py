# SPDX-License-Identifier: GPL-3.0-or-later
"""Salvataggio e caricamento della partita.

Lo stato di una partita in corso e' gia' interamente contenuto nel Mondo: la
stanza corrente, i flag, la posizione di ogni oggetto, le stanze visitate e
l'eventuale fine partita. Qui si estrae quello stato in un piccolo dizionario
e lo si riapplica su un'avventura ricaricata da zero.

Un salvataggio NON contiene la definizione dell'avventura (stanze, regole,
testi): solo cio' che cambia giocando. Per riprendere una partita si ricarica
l'avventura originale con carica_mondo() e poi vi si applica il salvataggio.

Questo file fa I/O su file, come storage.py: il principio "motore senza I/O"
riguarda il ciclo di gioco (engine.py), non queste utilita' di supporto.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from .model import Mondo


def _stato_oggetto(o) -> dict:
    """Stato runtime di un oggetto: posizione e proprietà mutabili in gioco."""
    d = {"pos": o.posizione}
    if "aperto" in o.props:
        d["aperto"] = o.props["aperto"]
    if "indossato" in o.props:
        d["indossato"] = o.props["indossato"]
    return d


def stato_partita(mondo: Mondo) -> dict:
    """Estrae lo stato runtime del Mondo in un dizionario serializzabile."""
    return {
        "_tipo": "salvataggio_avventura",
        "avventura": mondo.meta.get("titolo", ""),
        "salvato": time.strftime("%Y-%m-%d %H:%M:%S"),
        "stanza_corrente": mondo.stanza_corrente,
        "finita": mondo.finita,
        "messaggio_finale": mondo.messaggio_finale,
        "punteggio": mondo.punteggio,
        "mosse": mondo.mosse,
        "scontro": mondo.scontro,
        "timer": dict(mondo.timer),
        "flags": dict(mondo.flags),
        "oggetti": {oid: _stato_oggetto(o) for oid, o in mondo.oggetti.items()},
        "visitate": [sid for sid, s in mondo.stanze.items() if s.visitata],
        "immagini": {sid: s.immagine_attuale for sid, s in mondo.stanze.items()
                    if s.immagine_attuale},
    }


def applica_stato(mondo: Mondo, stato: dict) -> None:
    """Riapplica uno stato salvato su un Mondo appena caricato (in place)."""
    mondo.stanza_corrente = stato.get("stanza_corrente", mondo.stanza_corrente)
    mondo.finita = stato.get("finita", False)
    mondo.messaggio_finale = stato.get("messaggio_finale", "")
    mondo.punteggio = stato.get("punteggio", 0)
    mondo.mosse = stato.get("mosse", 0)
    mondo.conversazione = ""
    mondo.scontro = stato.get("scontro", "")
    mondo.timer = dict(stato.get("timer", {}))
    mondo.flags = dict(stato.get("flags", mondo.flags))
    for oid, v in stato.get("oggetti", {}).items():
        if oid not in mondo.oggetti:
            continue
        o = mondo.oggetti[oid]
        if isinstance(v, str):                  # vecchio formato: solo posizione
            o.posizione = v
        else:
            o.posizione = v.get("pos", o.posizione)
            if "aperto" in v:
                o.props["aperto"] = v["aperto"]
            if "indossato" in v:
                o.props["indossato"] = v["indossato"]
    visitate = set(stato.get("visitate", []))
    for sid, s in mondo.stanze.items():
        s.visitata = sid in visitate
    immagini = stato.get("immagini", {})
    for sid, s in mondo.stanze.items():
        s.immagine_attuale = immagini.get(sid, "")


def salva_partita(mondo: Mondo, percorso: str | Path) -> None:
    p = Path(percorso)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(stato_partita(mondo), ensure_ascii=False, indent=2),
                 encoding="utf-8")


def carica_partita(mondo: Mondo, percorso: str | Path) -> dict:
    """Carica un salvataggio e lo applica al Mondo. Ritorna lo stato letto."""
    stato = json.loads(Path(percorso).read_text(encoding="utf-8"))
    applica_stato(mondo, stato)
    return stato
