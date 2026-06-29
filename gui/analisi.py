# SPDX-License-Identifier: GPL-3.0-or-later
"""Analisi statica dell'avventura (pura, senza Qt).

- analizza_problemi(mondo): elenco di problemi navigabili (riferimenti rotti,
  stanze irraggiungibili, posizioni non valide, ...).
- usi_di(mondo, genere, chiave): «dove è usato» un flag, un oggetto o una stanza.

Ogni voce restituita ha la forma:
    {"testo": str, "categoria": str, "chiave": str|int, "grave": bool}
dove (categoria, chiave) permettono all'editor di navigare all'elemento.
"""
from __future__ import annotations

from advcore.model import SCARTATO


def _sorgenti(mondo):
    """Genera (contesto, categoria, chiave, tipo, voce) per ogni condizione/effetto
    presente in regole, dialoghi ed esiti di scontro."""
    for i, r in enumerate(mondo.regole):
        eti = r.id or i
        for c in r.se or []:
            yield (f"regola «{eti}» · SE", "Regole", i, "cond", c)
        for e in r.allora or []:
            yield (f"regola «{eti}» · ALLORA", "Regole", i, "eff", e)
        for e in r.altrimenti or []:
            yield (f"regola «{eti}» · ALTRIMENTI", "Regole", i, "eff", e)
    for oid, o in mondo.oggetti.items():
        for b in o.props.get("dialogo", []) or []:
            for c in b.get("se", []) or []:
                yield (f"dialogo di «{oid}»", "Oggetti", oid, "cond", c)
            for e in b.get("allora", []) or []:
                yield (f"dialogo di «{oid}»", "Oggetti", oid, "eff", e)
        for e in o.props.get("sconfitto", []) or []:
            yield (f"sconfitta di «{oid}»", "Oggetti", oid, "eff", e)


def _flag_riferiti(v: dict) -> set:
    """Flag referenziati da una condizione/effetto (ricorsivo sui nodi logici)."""
    if "non" in v:
        return _flag_riferiti(v["non"])
    if "oppure" in v or "tutte" in v:
        f = set()
        for s in v.get("oppure") or v.get("tutte") or []:
            f |= _flag_riferiti(s)
        return f
    f = set()
    for k in ("flag", "set_flag", "incrementa"):
        if v.get(k):
            f.add(v[k])
    return f


def _luoghi_validi(mondo):
    # una posizione è valida se è una stanza, l'inventario, lo "scarto", il
    # segnaposto "stanza" (= stanza corrente), oppure un QUALSIASI oggetto
    # esistente: un oggetto può stare in un contenitore o essere tenuto da un png.
    return set(mondo.stanze) | {"inventario", "stanza", SCARTATO} | set(mondo.oggetti)


# --------------------------------------------------------------------------- #
#  PROBLEMI
# --------------------------------------------------------------------------- #

def analizza_problemi(mondo) -> list:
    P = []

    def agg(testo, cat, chiave, grave=True):
        P.append({"testo": testo, "categoria": cat, "chiave": chiave, "grave": grave})

    stanze = set(mondo.stanze)
    oggetti = set(mondo.oggetti)
    png = {oid for oid, o in mondo.oggetti.items() if o.props.get("png")}
    luoghi = _luoghi_validi(mondo)

    if not stanze:
        agg("L'avventura non ha nessuna stanza.", "Stanze", None)
        return P

    # stanza iniziale
    init = mondo.meta.get("stanza_iniziale")
    if not init:
        agg("Manca la stanza iniziale (Metadati).", "Metadati", "__meta__")
    elif init not in stanze:
        agg(f"La stanza iniziale «{init}» non esiste.", "Metadati", "__meta__")

    # uscite
    for sid, s in mondo.stanze.items():
        for direz, u in s.uscite.items():
            dest = u.get("to") if isinstance(u, dict) else u
            if dest not in stanze:
                agg(f"Stanza «{sid}»: l'uscita «{direz}» porta a «{dest}», inesistente.",
                    "Stanze", sid)

    # posizione oggetti
    for oid, o in mondo.oggetti.items():
        if o.posizione and o.posizione not in luoghi:
            agg(f"Oggetto «{oid}»: posizione «{o.posizione}» non valida.", "Oggetti", oid)

    # riferimenti in regole / dialoghi
    for contesto, cat, chiave, tipo, v in _sorgenti(mondo):
        for genere, rif in _riferimenti(v):
            if genere == "oggetto" and rif not in oggetti:
                agg(f"{contesto}: oggetto «{rif}» inesistente.", cat, chiave)
            elif genere == "stanza" and rif not in stanze:
                agg(f"{contesto}: stanza «{rif}» inesistente.", cat, chiave)
            elif genere == "png" and rif not in png:
                agg(f"{contesto}: «{rif}» non è un personaggio valido.", cat, chiave)
            elif genere == "luogo" and rif not in luoghi:
                agg(f"{contesto}: luogo «{rif}» non valido.", cat, chiave)

    # inneschi delle regole
    for i, r in enumerate(mondo.regole):
        q = r.quando
        if q.get("evento") == "entra" and q.get("stanza") not in stanze:
            agg(f"Regola «{r.id or i}»: ingresso in «{q.get('stanza')}», stanza inesistente.",
                "Regole", i)
        if q.get("evento") == "timer" and not q.get("timer"):
            agg(f"Regola «{r.id or i}»: innesco «timer» senza nome.", "Regole", i, grave=False)
        if q.get("oggetto") and q["oggetto"] not in oggetti:
            agg(f"Regola «{r.id or i}»: comando con oggetto «{q['oggetto']}» inesistente.",
                "Regole", i)
        if q.get("oggetto_indiretto") and q["oggetto_indiretto"] not in oggetti:
            agg(f"Regola «{r.id or i}»: oggetto indiretto «{q['oggetto_indiretto']}» inesistente.",
                "Regole", i)

    # stanze irraggiungibili (via uscite o teleport) dalla iniziale
    if init in stanze:
        raggiunte = _raggiungibili(mondo, init)
        for sid in stanze - raggiunte:
            agg(f"Stanza «{sid}» irraggiungibile dalla stanza iniziale.",
                "Stanze", sid, grave=False)

    return P


def _riferimenti(v: dict):
    """(genere, id) referenziati da una condizione o un effetto (ricorsivo sui
    nodi logici non/oppure/tutte)."""
    if "non" in v:
        return _riferimenti(v["non"])
    if "oppure" in v or "tutte" in v:
        out = []
        for s in v.get("oppure") or v.get("tutte") or []:
            out += _riferimenti(s)
        return out
    out = []
    if "oggetto_in" in v:
        out.append(("oggetto", v["oggetto_in"][0]))
        out.append(("luogo", v["oggetto_in"][1]))
    if "stanza_corrente" in v:
        out.append(("stanza", v["stanza_corrente"]))
    if "sposta_oggetto" in v:
        out.append(("oggetto", v["sposta_oggetto"]))
        if v.get("a"):
            out.append(("luogo", v["a"]))
    if "scarta_oggetto" in v:
        out.append(("oggetto", v["scarta_oggetto"]))
    if "teleporta" in v:
        out.append(("stanza", v["teleporta"]))
    if "inizia_scontro" in v:
        out.append(("png", v["inizia_scontro"]))
    return out


def _raggiungibili(mondo, init) -> set:
    # roots: iniziale + tutte le destinazioni di teleport
    roots = {init}
    for _, _, _, tipo, v in _sorgenti(mondo):
        if tipo == "eff" and v.get("teleporta") in mondo.stanze:
            roots.add(v["teleporta"])
    visti = set()
    pila = list(roots)
    while pila:
        sid = pila.pop()
        if sid in visti or sid not in mondo.stanze:
            continue
        visti.add(sid)
        for u in mondo.stanze[sid].uscite.values():
            dest = u.get("to") if isinstance(u, dict) else u
            if dest in mondo.stanze and dest not in visti:
                pila.append(dest)
    return visti


# --------------------------------------------------------------------------- #
#  RICERCA TRASVERSALE: «dove è usato?»
# --------------------------------------------------------------------------- #

def usi_di(mondo, genere: str, chiave: str) -> list:
    """genere: 'flag' | 'oggetto' | 'stanza'. Ritorna l'elenco degli usi."""
    U = []

    def agg(testo, cat, ch):
        U.append({"testo": testo, "categoria": cat, "chiave": ch, "grave": False})

    if genere == "flag":
        if mondo.flags.get(chiave) is not None or chiave in mondo.flags:
            agg(f"dichiarato nei Flag iniziali (= {mondo.flags.get(chiave)})",
                "Flag iniziali", chiave)
        for sid, s in mondo.stanze.items():
            for direz, u in s.uscite.items():
                if isinstance(u, dict) and u.get("se") == chiave:
                    agg(f"stanza «{sid}»: sblocca l'uscita «{direz}»", "Stanze", sid)
        for oid, o in mondo.oggetti.items():
            if o.props.get("luce") == chiave:
                agg(f"oggetto «{oid}»: fa luce se «{chiave}»", "Oggetti", oid)
        for contesto, cat, ch, tipo, v in _sorgenti(mondo):
            if chiave in _flag_riferiti(v):
                agg(contesto, cat, ch)

    elif genere == "oggetto":
        for oid, o in mondo.oggetti.items():
            if o.posizione == chiave:
                agg(f"oggetto «{oid}» si trova qui dentro", "Oggetti", oid)
        for i, r in enumerate(mondo.regole):
            q = r.quando
            if q.get("oggetto") == chiave or q.get("oggetto_indiretto") == chiave:
                agg(f"regola «{r.id or i}»: nel comando", "Regole", i)
        for contesto, cat, ch, tipo, v in _sorgenti(mondo):
            refs = [rif for g, rif in _riferimenti(v) if g in ("oggetto", "png")]
            if chiave in refs:
                agg(contesto, cat, ch)

    elif genere == "stanza":
        if mondo.meta.get("stanza_iniziale") == chiave:
            agg("è la stanza iniziale", "Metadati", "__meta__")
        for sid, s in mondo.stanze.items():
            for direz, u in s.uscite.items():
                dest = u.get("to") if isinstance(u, dict) else u
                if dest == chiave:
                    agg(f"stanza «{sid}»: ci arriva con «{direz}»", "Stanze", sid)
        for oid, o in mondo.oggetti.items():
            if o.posizione == chiave:
                agg(f"oggetto «{oid}» si trova qui", "Oggetti", oid)
        for i, r in enumerate(mondo.regole):
            q = r.quando
            if q.get("evento") == "entra" and q.get("stanza") == chiave:
                agg(f"regola «{r.id or i}»: innesco all'ingresso", "Regole", i)
        for contesto, cat, ch, tipo, v in _sorgenti(mondo):
            refs = [rif for g, rif in _riferimenti(v) if g in ("stanza", "luogo")]
            if chiave in refs:
                agg(contesto, cat, ch)

    return U
