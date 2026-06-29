# SPDX-License-Identifier: GPL-3.0-or-later
"""Mappa testuale (ASCII) dell'avventura.

Dispone le stanze su una griglia seguendo le uscite cardinali
(nord/sud/est/ovest), le disegna come riquadri collegati da linee, e indica
quanti oggetti contiene ciascuna. Sotto la griglia elenca la distribuzione
degli oggetti, i collegamenti non cardinali (su/giù/dentro/fuori o incroci) e
le eventuali stanze non posizionabili.

È logica di modello pura: nessuna interfaccia, quindi testabile senza
terminale e riusabile (editor, eventuale comando «mappa» nel player...).
"""

from __future__ import annotations

from .model import Mondo

_CARD = {"nord": (0, -1), "sud": (0, 1), "est": (1, 0), "ovest": (-1, 0)}
_WI = 13          # larghezza interna del riquadro
_GAPX = 3         # spazio orizzontale tra riquadri
_GAPY = 2         # righe verticali tra riquadri


def _destinazione(uscita):
    return uscita["to"] if isinstance(uscita, dict) else uscita


def _layout(mondo: Mondo):
    """Assegna coordinate (x,y) alle stanze via BFS sulle uscite cardinali.
    Ritorna (coord, isolate)."""
    if not mondo.stanze:
        return {}, []
    start = mondo.meta.get("stanza_iniziale")
    if start not in mondo.stanze:
        start = next(iter(mondo.stanze))
    coord = {start: (0, 0)}
    occupato = {(0, 0): start}
    coda = [start]
    while coda:
        sid = coda.pop(0)
        x, y = coord[sid]
        for direz, u in mondo.stanze[sid].uscite.items():
            t = _destinazione(u)
            if t not in mondo.stanze or direz not in _CARD or t in coord:
                continue
            dx, dy = _CARD[direz]
            cella = (x + dx, y + dy)
            if cella not in occupato:
                coord[t] = cella
                occupato[cella] = t
                coda.append(t)
    isolate = [s for s in mondo.stanze if s not in coord]
    return coord, isolate


def _oggetti_in(mondo: Mondo, sid: str):
    return [o for o in mondo.oggetti.values() if o.posizione == sid]


def mappa_testuale(mondo: Mondo) -> str:
    if not mondo.stanze:
        return "(nessuna stanza: crea almeno una stanza)"

    coord, isolate = _layout(mondo)
    start = mondo.meta.get("stanza_iniziale")

    xs = [p[0] for p in coord.values()]
    ys = [p[1] for p in coord.values()]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    cols, rows = maxx - minx + 1, maxy - miny + 1

    cellw = _WI + 2                       # larghezza riquadro coi bordi
    width = cols * cellw + (cols - 1) * _GAPX
    height = rows * 3 + (rows - 1) * _GAPY
    canvas = [[" "] * width for _ in range(height)]

    def stampa(cx, cy, s):
        for k, ch in enumerate(s):
            if 0 <= cy < height and 0 <= cx + k < width:
                canvas[cy][cx + k] = ch

    px = {}                               # sid -> (cx, cy) angolo in alto a sx
    for sid, (x, y) in coord.items():
        cx = (x - minx) * (cellw + _GAPX)
        cy = (y - miny) * (3 + _GAPY)
        px[sid] = (cx, cy)
        nome = (mondo.stanze[sid].nome or sid)
        if sid == start:
            nome = "*" + nome              # segna la stanza iniziale
        nome = nome[:_WI - 1]
        n = len(_oggetti_in(mondo, sid))
        marca = f"#{n}" if n else ""
        interno = (" " + nome).ljust(_WI)
        if marca:
            interno = interno[:_WI - len(marca) - 1] + " " + marca
        stampa(cx, cy, "+" + "-" * _WI + "+")
        stampa(cx, cy + 1, "|" + interno[:_WI] + "|")
        stampa(cx, cy + 2, "+" + "-" * _WI + "+")

    extra = []                            # collegamenti non disegnati
    for sid, (x, y) in coord.items():
        cx, cy = px[sid]
        for direz, u in mondo.stanze[sid].uscite.items():
            t = _destinazione(u)
            if t not in mondo.stanze:
                continue
            if direz in _CARD and t in coord:
                dx, dy = _CARD[direz]
                if coord[t] == (x + dx, y + dy):     # adiacente: disegna
                    if direz == "est":
                        for g in range(_GAPX):
                            stampa(cx + cellw + g, cy + 1, "-")
                    elif direz == "ovest":
                        for g in range(_GAPX):
                            stampa(cx - 1 - g, cy + 1, "-")
                    elif direz == "sud":
                        for g in range(_GAPY):
                            stampa(cx + cellw // 2, cy + 3 + g, "|")
                    elif direz == "nord":
                        for g in range(_GAPY):
                            stampa(cx + cellw // 2, cy - 1 - g, "|")
                    continue
            extra.append((sid, direz, t))            # non cardinale o incrocio

    righe = [l.rstrip() for l in ("".join(r) for r in canvas)]

    out = ["MAPPA   (* = stanza iniziale,  #n = oggetti nella stanza)", ""]
    out += righe

    # distribuzione degli oggetti
    out += ["", "Oggetti per stanza:"]
    qualcosa = False
    for sid in list(coord) + isolate:
        oggetti = _oggetti_in(mondo, sid)
        if oggetti:
            qualcosa = True
            nomi = ", ".join(
                ("@" + o.nome if o.props.get("png") else o.nome) for o in oggetti)
            out.append(f"  {sid}: {nomi}")
    if not qualcosa:
        out.append("  (nessun oggetto posizionato nelle stanze)")
    out.append("  (@ = personaggio)")

    if extra:
        out += ["", "Collegamenti non sulla griglia (su/giù/dentro/fuori o incroci):"]
        for sid, direz, t in extra:
            out.append(f"  {sid}  --{direz}-->  {t}")

    if isolate:
        out += ["", "Stanze non collegate alla griglia:"]
        out.append("  " + ", ".join(isolate))

    return "\n".join(out)
