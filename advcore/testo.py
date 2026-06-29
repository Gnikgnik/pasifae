# SPDX-License-Identifier: GPL-3.0-or-later
"""Testo dinamico per messaggi e descrizioni.

Due costrutti, utilizzabili in qualsiasi testo mostrato al giocatore (descrizioni
di stanze e oggetti, messaggi 'stampa', dialoghi, intro, messaggi finali):

  INTERPOLAZIONE   {nome}
      Sostituisce il valore di un flag, oppure di un valore speciale:
        {punteggio}  {mosse}  {stanza}  (nome della stanza corrente)
      I booleani diventano «sì»/«no». Un nome sconosciuto resta invariato,
      così un eventuale '{' nel testo normale non viene toccato.

  FRAMMENTO CONDIZIONATO   [nome: testo]   oppure   [nome: se vero | se falso]
      Mostra una parte di testo solo se la condizione è soddisfatta.
        [porta_aperta: La porta è spalancata.]
        [ha_chiave: Hai la chiave. | Ti manca qualcosa.]
        [monete=0: Sei al verde.]
        [prima_volta: Entri per la prima volta. | Sei già stato qui.]
      Senza «=valore» la condizione è vera se il flag è "acceso" (vero/diverso
      da zero). Con «=valore» è vera se il flag è uguale a quel valore.

Il testo viene interpolato al momento della stampa, quindi riflette sempre lo
stato corrente del gioco.
"""
from __future__ import annotations

import re

_INTERP = re.compile(r"\{([a-zA-Z_][\w]*)\}")
_COND = re.compile(
    r"\[([a-zA-Z_][\w]*)(?:=([^\]:|]*))?:\s*([^\]|]*?)(?:\|([^\]]*?))?\]")


def _coerci(testo: str):
    t = testo.strip()
    low = t.lower()
    if low in ("vero", "true", "sì", "si"):
        return True
    if low in ("falso", "false", "no"):
        return False
    if re.fullmatch(r"-?\d+", t):
        return int(t)
    return t


def _valore(nome: str, mondo, extra: dict):
    if extra and nome in extra:
        return extra[nome]
    if nome == "punteggio":
        return mondo.punteggio
    if nome == "mosse":
        return mondo.mosse
    if nome == "stanza":
        s = mondo.stanze.get(mondo.stanza_corrente)
        return s.nome if s else ""
    if nome in mondo.flags:
        return mondo.flags[nome]
    return None


def rendi_testo(testo: str, mondo, extra: dict | None = None) -> str:
    if not testo or ("{" not in testo and "[" not in testo):
        return testo

    def _cond(m):
        nome, val, a, b = m.group(1), m.group(2), m.group(3), m.group(4)
        attuale = _valore(nome, mondo, extra)
        if val is None:
            ok = bool(attuale)
        else:
            ok = (attuale == _coerci(val))
        return (a if ok else (b or "")).strip()

    testo = _COND.sub(_cond, testo)

    def _interp(m):
        v = _valore(m.group(1), mondo, extra)
        if v is None:
            return m.group(0)            # nome sconosciuto: lascia '{nome}'
        if isinstance(v, bool):
            return "sì" if v else "no"
        return str(v)

    return _INTERP.sub(_interp, testo)
