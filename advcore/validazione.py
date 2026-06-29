# SPDX-License-Identifier: GPL-3.0-or-later
"""Validazione del Mondo: trova riferimenti rotti e incongruenze.

E' logica a livello di modello (nessuna interfaccia), quindi vive in advcore ed
e' testabile senza terminale. L'editor la usa per la schermata "Verifica"; in
prospettiva potrebbe usarla anche uno strumento da riga di comando.

Distingue due gravita':
  - "errore": riferimento strutturalmente rotto (es. un'uscita verso una stanza
    che non esiste). Il gioco quasi certamente si comportera' male.
  - "avviso": situazione sospetta ma forse voluta (es. un flag letto ma mai
    inizializzato, o un oggetto dentro qualcosa non marcato come contenitore).
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import Mondo
from .parser import PREP_BUILTIN, VERBI_BUILTIN


@dataclass
class Problema:
    gravita: str           # "errore" | "avviso"
    dove: str              # posizione leggibile del problema
    messaggio: str         # descrizione
    categoria: str = ""    # "stanza" | "oggetto" | "verbo" | "regola" | "meta"
    chiave: object = None  # id (o indice di regola) per saltare all'entita'


def _loc_valida(loc, mondo: Mondo) -> bool:
    """Una destinazione/posizione e' valida se e' l'inventario, la stanza
    corrente, una stanza esistente o un oggetto esistente (contenitore)."""
    return (loc in ("inventario", "stanza")
            or loc in mondo.stanze or loc in mondo.oggetti)


def _flag_noti(mondo: Mondo) -> set[str]:
    """Flag dichiarati all'inizio o impostati da un qualsiasi effetto
    (regole e dialoghi)."""
    noti = set(mondo.flags.keys())
    blocchi = [list(r.allora) + list(r.altrimenti) for r in mondo.regole]
    for o in mondo.oggetti.values():
        for b in o.props.get("dialogo", []):
            blocchi.append(b.get("allora", []))
    for effetti in blocchi:
        for eff in effetti:
            if "set_flag" in eff:
                noti.add(eff["set_flag"])
            if "incrementa" in eff:
                noti.add(eff["incrementa"])
    return noti


def _valida_condizioni(condizioni, dove, categoria, chiave, mondo, noti, p):
    for c in condizioni:
        if "oggetto_in" in c:
            rif = list(c["oggetto_in"]) + [None, None]
            oid, luogo = rif[0], rif[1]
            if oid not in mondo.oggetti:
                p.append(Problema("errore", dove,
                                  f"condizione: oggetto «{oid}» inesistente",
                                  categoria, chiave))
            if not _loc_valida(luogo, mondo):
                p.append(Problema("errore", dove,
                                  f"condizione: luogo «{luogo}» non valido",
                                  categoria, chiave))
        elif "stanza_corrente" in c:
            if c["stanza_corrente"] not in mondo.stanze:
                p.append(Problema("errore", dove,
                                  f"condizione: stanza «{c['stanza_corrente']}» "
                                  "inesistente", categoria, chiave))
        elif "flag" in c and c["flag"] not in noti:
            p.append(Problema("avviso", dove,
                              f"condizione: legge il flag «{c['flag']}» "
                              "mai impostato", categoria, chiave))


def _valida_effetti(effetti, dove, categoria, chiave, mondo, p):
    for eff in effetti:
        if "sposta_oggetto" in eff:
            if eff["sposta_oggetto"] not in mondo.oggetti:
                p.append(Problema("errore", dove,
                                  f"effetto: sposta l'oggetto "
                                  f"«{eff['sposta_oggetto']}» inesistente",
                                  categoria, chiave))
            if not _loc_valida(eff.get("a"), mondo):
                p.append(Problema("errore", dove,
                                  f"effetto: destinazione «{eff.get('a')}» "
                                  "non valida", categoria, chiave))
        elif "teleporta" in eff and eff["teleporta"] not in mondo.stanze:
            p.append(Problema("errore", dove,
                              f"effetto: teleporta nella stanza "
                              f"«{eff['teleporta']}» inesistente", categoria, chiave))


def valida(mondo: Mondo) -> list[Problema]:
    """Analizza il mondo e restituisce la lista dei problemi (errori prima)."""
    p: list[Problema] = []
    noti = _flag_noti(mondo)

    # --- metadati ---
    si = mondo.meta.get("stanza_iniziale")
    if not si or si not in mondo.stanze:
        p.append(Problema("errore", "metadati · stanza iniziale",
                          f"la stanza iniziale «{si or '(vuota)'}» non esiste",
                          "meta", None))

    # --- stanze e uscite ---
    for sid, s in mondo.stanze.items():
        for direzione, u in s.uscite.items():
            if isinstance(u, dict):
                dest = u.get("to")
                flag = u.get("se")
                if flag and flag not in noti:
                    p.append(Problema(
                        "avviso", f"stanza «{sid}» · uscita «{direzione}»",
                        f"dipende dal flag «{flag}», mai inizializzato né impostato",
                        "stanza", sid))
            else:
                dest = u
            if not dest or dest not in mondo.stanze:
                p.append(Problema(
                    "errore", f"stanza «{sid}» · uscita «{direzione}»",
                    f"punta alla stanza «{dest or '(vuota)'}» che non esiste",
                    "stanza", sid))

    # --- oggetti ---
    for oid, o in mondo.oggetti.items():
        pos = o.posizione
        if not pos:
            p.append(Problema("avviso", f"oggetto «{oid}»",
                              "non ha una posizione: non comparirà da nessuna parte",
                              "oggetto", oid))
        elif pos == oid:
            p.append(Problema("errore", f"oggetto «{oid}»",
                              "è contenuto in se stesso", "oggetto", oid))
        elif not _loc_valida(pos, mondo):
            p.append(Problema("errore", f"oggetto «{oid}»",
                              f"si trova in «{pos}», che non è una stanza, "
                              "l'inventario o un oggetto", "oggetto", oid))
        elif pos in mondo.oggetti and not (
                mondo.oggetti[pos].props.get("contenitore")
                or mondo.oggetti[pos].props.get("png")):
            p.append(Problema("avviso", f"oggetto «{oid}»",
                              f"è dentro «{pos}», che non è marcato come contenitore",
                              "oggetto", oid))

    # --- verbi: parole usate da piu' verbi (parser ambiguo) ---
    mappa: dict[str, list[str]] = {}
    for vid, v in mondo.verbi.items():
        for parola in [vid] + list(v.sinonimi):
            mappa.setdefault(parola, []).append(vid)
    for parola, verbi in mappa.items():
        univoci = sorted(set(verbi))
        if len(univoci) > 1:
            p.append(Problema("avviso", f"verbi · «{parola}»",
                              f"la parola è usata da più verbi: {', '.join(univoci)}",
                              "verbo", univoci[0]))

    # --- regole ---
    for i, r in enumerate(mondo.regole):
        dove = f"regola [{i}] «{r.id or '?'}»"
        q = r.quando
        evento = q.get("evento")
        if evento:
            if evento not in ("turno", "entra", "timer"):
                p.append(Problema("errore", dove,
                                  f"innesco-evento «{evento}» sconosciuto", "regola", i))
            if evento == "entra" and q.get("stanza") not in mondo.stanze:
                p.append(Problema("errore", dove,
                                  "l'evento «ingresso» non indica una stanza valida",
                                  "regola", i))
            if evento == "timer" and not q.get("timer"):
                p.append(Problema("errore", dove,
                                  "l'evento «timer» non indica il nome del timer",
                                  "regola", i))
        else:
            verbo = q.get("verbo")
            if not verbo:
                p.append(Problema("errore", dove, "non ha un verbo di innesco",
                                  "regola", i))
            elif verbo not in mondo.verbi and verbo not in VERBI_BUILTIN:
                p.append(Problema("errore", dove,
                                  f"usa il verbo «{verbo}» che non esiste", "regola", i))
            for campo in ("oggetto", "oggetto_indiretto"):
                val = q.get(campo)
                if val and val not in mondo.oggetti:
                    p.append(Problema("errore", dove,
                                      f"l'innesco riferisce l'oggetto «{val}» inesistente",
                                      "regola", i))
            prep = q.get("prep")
            if prep and prep not in mondo.preposizioni and prep not in PREP_BUILTIN:
                p.append(Problema("avviso", dove,
                                  f"usa la preposizione «{prep}» non dichiarata",
                                  "regola", i))

        _valida_condizioni(r.se, dove, "regola", i, mondo, noti, p)
        _valida_effetti(list(r.allora) + list(r.altrimenti),
                        dove, "regola", i, mondo, p)

    # --- dialoghi dei personaggi ---
    for oid, o in mondo.oggetti.items():
        dlg = o.props.get("dialogo", [])
        if dlg and not o.props.get("png"):
            p.append(Problema("avviso", f"oggetto «{oid}»",
                              "ha un dialogo ma non è marcato come png",
                              "oggetto", oid))
        for j, b in enumerate(dlg):
            dove = f"dialogo «{oid}» · battuta [{j}]"
            if not b.get("etichetta") or not b.get("testo"):
                p.append(Problema("avviso", dove,
                                  "manca «etichetta» o «testo»", "oggetto", oid))
            _valida_condizioni(b.get("se", []), dove, "oggetto", oid, mondo, noti, p)
            _valida_effetti(b.get("allora", []), dove, "oggetto", oid, mondo, p)

    p.sort(key=lambda x: 0 if x.gravita == "errore" else 1)
    return p
