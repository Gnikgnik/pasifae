# SPDX-License-Identifier: GPL-3.0-or-later
"""Caricamento e salvataggio del Mondo da/verso JSON.

Il formato su disco e' JSON puro (leggibile, versionabile con git). Qui si
traduce tra dizionari JSON e le dataclass di model.py. Editor e player usano
entrambi solo queste due funzioni: carica_mondo() e salva_mondo().
"""

from __future__ import annotations

import json
from pathlib import Path

from .model import Mondo, Stanza, Oggetto, Verbo, Regola


def carica_mondo(percorso: str | Path) -> Mondo:
    dati = json.loads(Path(percorso).read_text(encoding="utf-8"))
    return _da_dict(dati)


def salva_mondo(mondo: Mondo, percorso: str | Path) -> None:
    dati = _a_dict(mondo)
    Path(percorso).write_text(
        json.dumps(dati, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# --------- dict -> Mondo ---------

def _da_dict(d: dict) -> Mondo:
    verbi = {
        vid: Verbo(id=vid,
                   sinonimi=v.get("sinonimi", []),
                   tipo=v.get("tipo", "transitivo"),
                   preposizioni=v.get("preposizioni", []))
        for vid, v in d.get("verbi", {}).items()
    }
    stanze = {
        sid: Stanza(id=sid,
                    nome=s["nome"],
                    desc=s.get("desc", ""),
                    uscite=s.get("uscite", {}),
                    buia=s.get("buia", False))
        for sid, s in d.get("stanze", {}).items()
    }
    oggetti = {
        oid: Oggetto(id=oid,
                     nome=o["nome"],
                     nomi=o.get("nomi", []),
                     aggettivi=o.get("aggettivi", []),
                     posizione=o.get("posizione", ""),
                     props=o.get("props", {}))
        for oid, o in d.get("oggetti", {}).items()
    }
    regole = [
        Regola(id=r.get("id", f"regola_{i}"),
               quando=r.get("quando", {}),
               se=r.get("se", []),
               allora=r.get("allora", []),
               altrimenti=r.get("altrimenti", []))
        for i, r in enumerate(d.get("regole", []))
    ]
    meta = d.get("meta", {})
    mondo = Mondo(
        meta=meta,
        flags=dict(d.get("flags", {})),
        verbi=verbi,
        preposizioni=d.get("preposizioni", {}),
        stanze=stanze,
        oggetti=oggetti,
        regole=regole,
    )
    mondo.stanza_corrente = meta.get("stanza_iniziale", next(iter(stanze), ""))
    return mondo


# --------- Mondo -> dict ---------

def _a_dict(m: Mondo) -> dict:
    return {
        "meta": m.meta,
        "flags": m.flags,
        "verbi": {
            vid: {"sinonimi": v.sinonimi, "tipo": v.tipo,
                  "preposizioni": v.preposizioni}
            for vid, v in m.verbi.items()
        },
        "preposizioni": m.preposizioni,
        "stanze": {
            sid: {"nome": s.nome, "desc": s.desc,
                  "uscite": s.uscite, "buia": s.buia}
            for sid, s in m.stanze.items()
        },
        "oggetti": {
            oid: {"nome": o.nome, "nomi": o.nomi, "aggettivi": o.aggettivi,
                  "posizione": o.posizione, "props": o.props}
            for oid, o in m.oggetti.items()
        },
        "regole": [
            {"id": r.id, "quando": r.quando, "se": r.se,
             "allora": r.allora, "altrimenti": r.altrimenti}
            for r in m.regole
        ],
    }
