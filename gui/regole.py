# SPDX-License-Identifier: GPL-3.0-or-later
"""Dati e logica (senza Qt) per l'editor delle regole: cataloghi di condizioni
ed effetti, forma dei dizionari accettati dal motore, riassunti leggibili.

Tenere questo modulo privo di Qt lo rende testabile e fa da unica fonte di
verità sulle forme dei dati (allineata a advcore/rules.py).
"""
from __future__ import annotations

from advcore.parser import VERBI_BUILTIN

# ----- inneschi (campo «quando») -----
INNESCHI = [
    ("comando del giocatore", "comando"),
    ("a ogni turno", "turno"),
    ("ingresso in una stanza", "entra"),
    ("scadenza di un timer", "timer"),
]

# ----- cataloghi -----
TIPI_CONDIZIONE = [
    ("il flag è uguale a…", "flag_uguale"),
    ("il flag è maggiore di… (>)", "flag_maggiore"),
    ("il flag è minore di… (<)", "flag_minore"),
    ("il flag è almeno… (≥)", "flag_maggiore_uguale"),
    ("il flag è al più… (≤)", "flag_minore_uguale"),
    ("oggetto in un luogo", "oggetto_in"),
    ("stanza corrente", "stanza_corrente"),
    ("stato conversazione ≥ N", "stato_min"),
    ("turno (orologio) ≥ N", "mosse_min"),
]
TIPI_EFFETTO = [
    ("imposta flag", "set_flag"),
    ("incrementa flag", "incrementa"),
    ("assegna punti", "punti"),
    ("sposta oggetto", "sposta_oggetto"),
    ("scarta oggetto (scarico/rovinato)", "scarta_oggetto"),
    ("apri contenitore", "apri_oggetto"),
    ("chiudi contenitore", "chiudi_oggetto"),
    ("mostra oggetto nascosto", "mostra_oggetto"),
    ("nascondi oggetto", "nascondi_oggetto"),
    ("stampa testo", "stampa"),
    ("teleporta giocatore", "teleporta"),
    ("vittoria", "vittoria"),
    ("sconfitta", "sconfitta"),
    ("porta conversazione allo stato N", "stato"),
    ("avanza lo stato di N", "avanza_stato"),
    ("inizia scontro con png", "inizia_scontro"),
    ("avvia un timer", "avvia_timer"),
    ("ferma un timer", "ferma_timer"),
    ("avvia dialogo (saluto + battute)", "avvia_dialogo"),
]

# ----- campi per ciascun tipo: (id_campo, etichetta, genere_widget) -----
CAMPI = {
    # condizioni
    "flag_uguale": [("flag", "flag", "flag"), ("valore", "è uguale a", "valore")],
    "flag_maggiore": [("flag", "flag", "flag"), ("n", "è maggiore di", "intero")],
    "flag_minore": [("flag", "flag", "flag"), ("n", "è minore di", "intero")],
    "flag_maggiore_uguale": [("flag", "flag", "flag"), ("n", "è almeno (≥)", "intero")],
    "flag_minore_uguale": [("flag", "flag", "flag"), ("n", "è al più (≤)", "intero")],
    "oggetto_in": [("oggetto", "oggetto", "oggetto"), ("luogo", "si trova in", "luogo")],
    "stanza_corrente": [("stanza", "stanza", "stanza")],
    "stato_min": [("n", "stato conversazione ≥", "intero")],
    "mosse_min": [("n", "turno ≥", "intero")],
    # effetti
    "set_flag": [("flag", "flag", "flag"), ("valore", "al valore", "valore")],
    "incrementa": [("flag", "flag", "flag"), ("di", "di", "intero")],
    "punti": [("n", "punti", "intero")],
    "sposta_oggetto": [("oggetto", "oggetto", "oggetto"), ("a", "verso", "luogo")],
    "scarta_oggetto": [("oggetto", "oggetto", "oggetto"),
                       ("messaggio", "messaggio (facolt.)", "testo_lungo")],
    "apri_oggetto": [("oggetto", "contenitore", "contenitore")],
    "chiudi_oggetto": [("oggetto", "contenitore", "contenitore")],
    "mostra_oggetto": [("oggetto", "oggetto", "oggetto")],
    "nascondi_oggetto": [("oggetto", "oggetto", "oggetto")],
    "stampa": [("testo", "testo", "testo_lungo")],
    "teleporta": [("stanza", "verso la stanza", "stanza")],
    "vittoria": [("testo", "messaggio", "testo_lungo")],
    "sconfitta": [("testo", "messaggio", "testo_lungo")],
    "stato": [("n", "porta allo stato", "intero")],
    "avanza_stato": [("n", "avanza di", "intero")],
    "inizia_scontro": [("png", "con il png", "png")],
    "avvia_timer": [("nome", "nome timer", "timer"), ("turni", "fra (turni)", "intero")],
    "ferma_timer": [("nome", "nome timer", "timer")],
    # non "png": funziona su qualunque oggetto (un terminale non è un
    # personaggio, ma può avere un dialogo suo)
    "avvia_dialogo": [("oggetto", "apre il dialogo di", "oggetto")],
}

# ----- assemblaggio: valori {id_campo: valore} -> dizionario del motore -----
ASSEMBLA = {
    "flag_uguale": lambda v: {"flag": v["flag"], "uguale": v["valore"]},
    "flag_maggiore": lambda v: {"flag": v["flag"], "maggiore": v["n"]},
    "flag_minore": lambda v: {"flag": v["flag"], "minore": v["n"]},
    "flag_maggiore_uguale": lambda v: {"flag": v["flag"], "maggiore_uguale": v["n"]},
    "flag_minore_uguale": lambda v: {"flag": v["flag"], "minore_uguale": v["n"]},
    "oggetto_in": lambda v: {"oggetto_in": [v["oggetto"], v["luogo"]]},
    "stanza_corrente": lambda v: {"stanza_corrente": v["stanza"]},
    "stato_min": lambda v: {"stato_min": v["n"]},
    "mosse_min": lambda v: {"mosse_min": v["n"]},
    "set_flag": lambda v: {"set_flag": v["flag"], "valore": v["valore"]},
    "incrementa": lambda v: {"incrementa": v["flag"], "di": v["di"]},
    "punti": lambda v: {"punti": v["n"]},
    "sposta_oggetto": lambda v: {"sposta_oggetto": v["oggetto"], "a": v["a"]},
    "scarta_oggetto": lambda v: ({"scarta_oggetto": v["oggetto"]}
                                 | ({"stampa": v["messaggio"].strip()}
                                    if v.get("messaggio", "").strip() else {})),
    "apri_oggetto": lambda v: {"apri_oggetto": v["oggetto"]},
    "chiudi_oggetto": lambda v: {"chiudi_oggetto": v["oggetto"]},
    "mostra_oggetto": lambda v: {"mostra_oggetto": v["oggetto"]},
    "nascondi_oggetto": lambda v: {"nascondi_oggetto": v["oggetto"]},
    "stampa": lambda v: {"stampa": v["testo"]},
    "teleporta": lambda v: {"teleporta": v["stanza"]},
    "vittoria": lambda v: {"vittoria": v["testo"]},
    "sconfitta": lambda v: {"sconfitta": v["testo"]},
    "stato": lambda v: {"stato": v["n"]},
    "avanza_stato": lambda v: {"avanza_stato": v["n"]},
    "inizia_scontro": lambda v: {"inizia_scontro": v["png"]},
    "avvia_timer": lambda v: {"avvia_timer": v["nome"], "turni": v["turni"]},
    "ferma_timer": lambda v: {"ferma_timer": v["nome"]},
    "avvia_dialogo": lambda v: {"avvia_dialogo": v["oggetto"]},
}


def val_da_testo(s: str):
    """Interpreta il valore di un flag scritto a mano: vero/falso -> bool,
    cifre -> int, altrimenti stringa."""
    t = str(s).strip()
    basso = t.lower()
    if basso in ("vero", "true", "sì", "si"):
        return True
    if basso in ("falso", "false", "no"):
        return False
    try:
        return int(t)
    except ValueError:
        return t


def nomi_timer(mondo) -> list:
    """Tutti i nomi di timer noti nell'avventura: quelli dichiarati in
    meta['timer'] più quelli effettivamente usati (negli effetti avvia/ferma
    timer e negli inneschi-timer delle regole e dei dialoghi)."""
    nomi = set(mondo.meta.get("timer", []) or [])

    def scan(effetti):
        for e in effetti or []:
            if e.get("avvia_timer"):
                nomi.add(e["avvia_timer"])
            if e.get("ferma_timer"):
                nomi.add(e["ferma_timer"])

    for r in mondo.regole:
        if r.quando.get("evento") == "timer" and r.quando.get("timer"):
            nomi.add(r.quando["timer"])
        scan(r.allora)
        scan(r.altrimenti)
    for o in mondo.oggetti.values():
        for b in o.props.get("dialogo", []) or []:
            scan(b.get("allora"))
        scan(o.props.get("sconfitto"))
    return sorted(n for n in nomi if n)


def riferimenti_timer(mondo) -> dict:
    """Quante volte ciascun timer è usato (inneschi-timer + effetti avvia/ferma)."""
    conteggio = {}

    def scan(effetti):
        for e in effetti or []:
            for k in ("avvia_timer", "ferma_timer"):
                if e.get(k):
                    conteggio[e[k]] = conteggio.get(e[k], 0) + 1

    for r in mondo.regole:
        if r.quando.get("evento") == "timer" and r.quando.get("timer"):
            n = r.quando["timer"]
            conteggio[n] = conteggio.get(n, 0) + 1
        scan(r.allora)
        scan(r.altrimenti)
    for o in mondo.oggetti.values():
        for b in o.props.get("dialogo", []) or []:
            scan(b.get("allora"))
        scan(o.props.get("sconfitto"))
    return conteggio


def da_dict(voce: dict):
    """Inverso di ASSEMBLA: dato un dizionario condizione/effetto ritorna
    (tipo_key, {id_campo: valore}) per pre-compilare il dialogo in modifica."""
    e = voce
    # --- condizioni ---
    if "flag" in e and "uguale" in e:
        return "flag_uguale", {"flag": e["flag"], "valore": e["uguale"]}
    if "flag" in e and "maggiore" in e:
        return "flag_maggiore", {"flag": e["flag"], "n": e["maggiore"]}
    if "flag" in e and "minore" in e:
        return "flag_minore", {"flag": e["flag"], "n": e["minore"]}
    if "flag" in e and "maggiore_uguale" in e:
        return "flag_maggiore_uguale", {"flag": e["flag"], "n": e["maggiore_uguale"]}
    if "flag" in e and "minore_uguale" in e:
        return "flag_minore_uguale", {"flag": e["flag"], "n": e["minore_uguale"]}
    if "oggetto_in" in e:
        return "oggetto_in", {"oggetto": e["oggetto_in"][0], "luogo": e["oggetto_in"][1]}
    if "stanza_corrente" in e:
        return "stanza_corrente", {"stanza": e["stanza_corrente"]}
    if "stato_min" in e:
        return "stato_min", {"n": e["stato_min"]}
    if "mosse_min" in e:
        return "mosse_min", {"n": e["mosse_min"]}
    # --- effetti --- (scarta_oggetto prima di stampa: può contenerla)
    if "set_flag" in e:
        return "set_flag", {"flag": e["set_flag"], "valore": e.get("valore", True)}
    if "incrementa" in e:
        return "incrementa", {"flag": e["incrementa"], "di": e.get("di", 1)}
    if "punti" in e:
        return "punti", {"n": e["punti"]}
    if "sposta_oggetto" in e:
        return "sposta_oggetto", {"oggetto": e["sposta_oggetto"], "a": e.get("a")}
    if "scarta_oggetto" in e:
        return "scarta_oggetto", {"oggetto": e["scarta_oggetto"], "messaggio": e.get("stampa", "")}
    if "apri_oggetto" in e:
        return "apri_oggetto", {"oggetto": e["apri_oggetto"]}
    if "chiudi_oggetto" in e:
        return "chiudi_oggetto", {"oggetto": e["chiudi_oggetto"]}
    if "mostra_oggetto" in e:
        return "mostra_oggetto", {"oggetto": e["mostra_oggetto"]}
    if "nascondi_oggetto" in e:
        return "nascondi_oggetto", {"oggetto": e["nascondi_oggetto"]}
    if "stampa" in e:
        return "stampa", {"testo": e["stampa"]}
    if "teleporta" in e:
        return "teleporta", {"stanza": e["teleporta"]}
    if "vittoria" in e:
        return "vittoria", {"testo": e["vittoria"]}
    if "sconfitta" in e:
        return "sconfitta", {"testo": e["sconfitta"]}
    if "stato" in e:
        return "stato", {"n": e["stato"]}
    if "avanza_stato" in e:
        return "avanza_stato", {"n": e["avanza_stato"]}
    if "inizia_scontro" in e:
        return "inizia_scontro", {"png": e["inizia_scontro"]}
    if "avvia_timer" in e:
        return "avvia_timer", {"nome": e["avvia_timer"], "turni": e.get("turni", 1)}
    if "ferma_timer" in e:
        return "ferma_timer", {"nome": e["ferma_timer"]}
    if "avvia_dialogo" in e:
        return "avvia_dialogo", {"oggetto": e["avvia_dialogo"]}
    return None, {}


def opzioni(mondo) -> dict:
    contenitori = [oid for oid, o in mondo.oggetti.items() if o.props.get("contenitore")]
    luoghi = ["inventario", "stanza"] + list(mondo.stanze.keys()) + contenitori
    png = [oid for oid, o in mondo.oggetti.items() if o.props.get("png")]
    return {
        "flag": sorted(mondo.flags.keys()),
        "oggetto": list(mondo.oggetti.keys()),
        "contenitore": contenitori,
        "stanza": list(mondo.stanze.keys()),
        "luogo": luoghi,
        "png": png or list(mondo.oggetti.keys()),
        "verbo": list(mondo.verbi.keys()) + [v for v in VERBI_BUILTIN
                                             if v not in mondo.verbi],
        "timer": nomi_timer(mondo),
    }


# ----- riassunti leggibili -----

def riassunto_condizione(c: dict) -> str:
    if "non" in c:
        return "NON " + riassunto_condizione(c["non"])
    if "oppure" in c:
        return "almeno una di [" + " · ".join(
            riassunto_condizione(s) for s in c["oppure"]) + "]"
    if "tutte" in c:
        return "tutte di [" + " · ".join(
            riassunto_condizione(s) for s in c["tutte"]) + "]"
    if "flag" in c:
        if "uguale" in c:
            return f"flag «{c['flag']}» = {c['uguale']}"
        if "maggiore" in c:
            return f"flag «{c['flag']}» > {c['maggiore']}"
        if "minore" in c:
            return f"flag «{c['flag']}» < {c['minore']}"
        if "maggiore_uguale" in c:
            return f"flag «{c['flag']}» ≥ {c['maggiore_uguale']}"
        if "minore_uguale" in c:
            return f"flag «{c['flag']}» ≤ {c['minore_uguale']}"
        return f"flag «{c['flag']}» è vero"
    if "oggetto_in" in c:
        return f"«{c['oggetto_in'][0]}» si trova in «{c['oggetto_in'][1]}»"
    if "stanza_corrente" in c:
        return f"sei nella stanza «{c['stanza_corrente']}»"
    if "stato_min" in c:
        return f"stato conversazione ≥ {c['stato_min']}"
    if "mosse_min" in c:
        return f"turno ≥ {c['mosse_min']}"
    return "(condizione)"


def riassunto_effetto(e: dict) -> str:
    if "set_flag" in e:
        return f"imposta «{e['set_flag']}» = {e.get('valore')}"
    if "incrementa" in e:
        return f"incrementa «{e['incrementa']}» di {e.get('di', 1)}"
    if "punti" in e:
        return f"assegna {e['punti']} punti"
    if "sposta_oggetto" in e:
        return f"sposta «{e['sposta_oggetto']}» in «{e.get('a')}»"
    if "scarta_oggetto" in e:
        return f"scarta «{e['scarta_oggetto']}» (lo toglie dal gioco)"
    if "apri_oggetto" in e:
        return f"apre il contenitore «{e['apri_oggetto']}»"
    if "chiudi_oggetto" in e:
        return f"chiude il contenitore «{e['chiudi_oggetto']}»"
    if "mostra_oggetto" in e:
        return f"mostra «{e['mostra_oggetto']}» (lo rende visibile e prendibile)"
    if "nascondi_oggetto" in e:
        return f"nasconde «{e['nascondi_oggetto']}»"
    if "stampa" in e:
        return f"stampa: {e['stampa'][:40]}…" if len(e["stampa"]) > 40 else f"stampa: {e['stampa']}"
    if "teleporta" in e:
        return f"teleporta in «{e['teleporta']}»"
    if "vittoria" in e:
        return "vittoria"
    if "sconfitta" in e:
        return "sconfitta"
    if "stato" in e:
        return f"porta lo stato a {e['stato']}"
    if "avanza_stato" in e:
        return f"avanza lo stato di {e['avanza_stato']}"
    if "inizia_scontro" in e:
        return f"inizia scontro con «{e['inizia_scontro']}»"
    if "avvia_timer" in e:
        return f"avvia timer «{e['avvia_timer']}» (fra {e.get('turni', 1)})"
    if "ferma_timer" in e:
        return f"ferma timer «{e['ferma_timer']}»"
    if "avvia_dialogo" in e:
        return f"avvia il dialogo di «{e['avvia_dialogo']}»"
    return "(effetto)"


def quando_breve(q: dict) -> str:
    ev = q.get("evento")
    if ev == "turno":
        return "a ogni turno"
    if ev == "entra":
        return f"ingresso → {q.get('stanza', '?')}"
    if ev == "timer":
        return f"timer «{q.get('timer', '?')}» scaduto"
    pezzi = [q.get("verbo", "?")]
    for k in ("oggetto", "prep", "oggetto_indiretto"):
        if q.get(k):
            v = q[k]
            pezzi.append("/".join(v) if isinstance(v, list) else v)
    return "comando: " + " ".join(pezzi)
