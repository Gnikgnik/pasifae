# SPDX-License-Identifier: GPL-3.0-or-later
"""Riassunti testuali in sola lettura per le categorie dell'editor non ancora
modificabili graficamente (oggetti, verbi, regole, flag)."""
from __future__ import annotations


def _quando(q: dict) -> str:
    ev = q.get("evento")
    if ev == "turno":
        return "a ogni turno"
    if ev == "entra":
        return f"all'ingresso in «{q.get('stanza', '?')}»"
    if ev == "timer":
        return f"alla scadenza del timer «{q.get('timer', '?')}»"
    pezzi = [q.get("verbo", "?")]
    if q.get("oggetto"):
        pezzi.append(q["oggetto"])
    if q.get("prep"):
        p = q["prep"]
        pezzi.append("/".join(p) if isinstance(p, list) else p)
    if q.get("oggetto_indiretto"):
        pezzi.append(q["oggetto_indiretto"])
    return "comando: " + " ".join(pezzi)


def riassunto(mondo, categoria: str, chiave) -> str:
    if categoria == "Oggetti":
        o = mondo.oggetti[chiave]
        props = o.props or {}
        attivi = [k for k, v in props.items() if v is True]
        righe = [f"id:           {o.id}",
                 f"nome:         {o.nome}",
                 f"posizione:    {o.posizione}",
                 f"sostantivi:   {', '.join(o.nomi)}"]
        if props.get("desc"):
            righe.append(f"esamina:      {props['desc']}")
        if props.get("in_stanza"):
            righe.append(f"in stanza:    {props['in_stanza']}")
        if attivi:
            righe.append(f"proprietà:    {', '.join(attivi)}")
        if props.get("png"):
            dlg = props.get("dialogo", [])
            righe.append(f"personaggio:  sì, {len(dlg)} battute")
        if props.get("combattente"):
            righe.append(f"combattente:  hp {props.get('hp')}, "
                         f"att {props.get('attacco')}, dif {props.get('difesa')}")
        return "\n".join(righe)

    if categoria == "Verbi":
        v = mondo.verbi[chiave]
        righe = [f"id:           {v.id}",
                 f"sinonimi:     {', '.join(v.sinonimi) or '(nessuno)'}",
                 f"tipo:         {v.tipo}"]
        if v.preposizioni:
            righe.append(f"preposizioni: {', '.join(v.preposizioni)}")
        return "\n".join(righe)

    if categoria == "Regole":
        r = mondo.regole[chiave]
        righe = [f"id:        {r.id or '(senza id)'}",
                 f"quando:    {_quando(r.quando)}",
                 f"se:        {len(r.se)} condizioni",
                 f"allora:    {len(r.allora)} effetti"]
        if r.altrimenti:
            righe.append(f"altrimenti: {len(r.altrimenti)} effetti")
        return "\n".join(righe)

    if categoria == "Flag iniziali":
        return f"{chiave} = {mondo.flags[chiave]}"

    return "(nessun dettaglio)"
