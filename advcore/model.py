# SPDX-License-Identifier: GPL-3.0-or-later
"""Modello dati condiviso tra editor e player.

Tutte le entita' del mondo sono semplici dataclass. Nessuna logica di gioco
vive qui: model.py descrive *cosa* esiste, non *cosa succede*. La logica sta
in rules.py ed engine.py, in modo che editor e player condividano le stesse
definizioni senza duplicarle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# Posizioni speciali (oltre agli id di stanza/oggetto):
INVENTARIO = "inventario"   # nell'inventario del giocatore
SCARTATO = "__scartato__"   # oggetto tolto dal gioco (non in alcuna stanza/contenitore)


@dataclass
class Stanza:
    id: str
    nome: str
    desc: str
    # direzione -> id stanza, oppure {"to": id, "se": nome_flag}
    uscite: dict[str, Any] = field(default_factory=dict)
    buia: bool = False          # richiede una sorgente di luce per vedere
    visitata: bool = False


@dataclass
class Oggetto:
    id: str
    nome: str                       # nome mostrato al giocatore
    nomi: list[str] = field(default_factory=list)        # sostantivi per il parser
    aggettivi: list[str] = field(default_factory=list)   # aggettivi disambiguanti
    posizione: str = ""             # id stanza | INVENTARIO | id oggetto contenitore
    props: dict[str, Any] = field(default_factory=dict)
    # props comuni: prendibile (bool), desc (str), luce (bool|str:nome_flag),
    #               contenitore (bool), statico (bool)


@dataclass
class Verbo:
    id: str
    sinonimi: list[str] = field(default_factory=list)
    tipo: str = "transitivo"        # intransitivo | transitivo | ditransitivo
    preposizioni: list[str] = field(default_factory=list)


@dataclass
class Regola:
    id: str
    quando: dict[str, Any] = field(default_factory=dict)   # {verbo, oggetto, prep, oggetto_indiretto}
    se: list[dict[str, Any]] = field(default_factory=list)        # condizioni (AND)
    allora: list[dict[str, Any]] = field(default_factory=list)    # effetti se condizioni vere
    altrimenti: list[dict[str, Any]] = field(default_factory=list)  # effetti se condizioni false


@dataclass
class Mondo:
    meta: dict[str, Any] = field(default_factory=dict)
    flags: dict[str, Any] = field(default_factory=dict)
    verbi: dict[str, Verbo] = field(default_factory=dict)
    preposizioni: dict[str, list[str]] = field(default_factory=dict)
    stanze: dict[str, Stanza] = field(default_factory=dict)
    oggetti: dict[str, Oggetto] = field(default_factory=dict)
    regole: list[Regola] = field(default_factory=list)

    # --- stato a runtime (non serializzato nello stato iniziale) ---
    stanza_corrente: str = ""
    finita: bool = False
    messaggio_finale: str = ""
    punteggio: int = 0
    mosse: int = 0
    conversazione: str = ""   # id del png con cui si sta parlando ("" = nessuno)
    scontro: str = ""         # id del png con cui si combatte ("" = nessuno)
    timer: dict[str, int] = field(default_factory=dict)  # nome -> turni rimanenti

    # ------- helper di interrogazione del mondo -------

    def oggetti_in(self, posizione: str) -> list[Oggetto]:
        """Tutti gli oggetti la cui posizione corrisponde (stanza, inventario, contenitore)."""
        return [o for o in self.oggetti.values() if o.posizione == posizione]

    def inventario(self) -> list[Oggetto]:
        return self.oggetti_in(INVENTARIO)

    def in_scope(self) -> list[Oggetto]:
        """Oggetti che il giocatore puo' nominare: stanza corrente + inventario
        + contenuto dei contenitori aperti in scope."""
        visti = self.oggetti_in(self.stanza_corrente) + self.inventario()
        # contenuto dei contenitori aperti gia' in scope
        aperti = [o for o in visti
                  if o.props.get("contenitore") and o.props.get("aperto")]
        for cont in aperti:
            visti = visti + self.oggetti_in(cont.id)
        return visti

    def luce_disponibile(self) -> bool:
        """C'e' luce nella stanza corrente? Vero se la stanza non e' buia,
        o se in scope c'e' una sorgente di luce attiva."""
        stanza = self.stanze[self.stanza_corrente]
        if not stanza.buia:
            return True
        for o in self.in_scope():
            luce = o.props.get("luce")
            if luce is True:
                return True
            if isinstance(luce, str) and self.flags.get(luce):
                return True
        return False
