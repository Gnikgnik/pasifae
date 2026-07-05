# SPDX-License-Identifier: GPL-3.0-or-later
"""Parser verbo + (oggetto diretto) + (preposizione + oggetto indiretto).

Pipeline:
  1. normalizza  -> minuscole, via la punteggiatura
  2. tokenizza   -> lista di parole
  3. pulisci     -> scarta articoli e parole-rumore
  4. verbo       -> mappa il primo token sul verbo canonico (via sinonimi)
  5. preposizione-> se presente, spezza in [diretto] [prep] [indiretto]
  6. risolvi     -> i gruppi nominali contro gli oggetti in scope

Il risultato e' un ComandoParser, una struttura pulita che engine.py confronta
con le regole e poi con gli handler predefiniti.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .model import Mondo, Oggetto


# Verbi sempre riconosciuti dal parser, anche se l'autore non li dichiara.
# L'autore puo' comunque estenderli dichiarando lo stesso id con altri sinonimi.
VERBI_BUILTIN = {
    "vai": ["va", "muoviti", "cammina"],
    "guarda": ["osserva", "guardare"],
    "esamina": ["x", "ispeziona", "esaminare"],
    "prendi": ["raccogli", "afferra", "prendere"],
    "lascia": ["posa", "molla", "lasciare"],
    "inventario": ["i", "inv"],
    "apri": ["aprire"],
    "chiudi": ["chiudere"],
    "metti": ["inserisci", "infila", "mettere"],
    "indossa": ["vesti", "indossare"],
    "togli": ["sfila", "togliere"],
    "usa": ["utilizza", "adopera", "usare"],
    "parla": ["parlare", "chiacchiera", "dì"],
    "attacca": ["attaccare", "colpisci", "combatti", "aggredisci"],
    "difendi": ["difenditi", "para", "guardia"],
    "fuggi": ["scappa", "ritirati", "fuga"],
    "aiuto": ["help", "comandi", "aiutami"],
    "annulla": ["undo", "disfa"],
    "punteggio": ["punti", "score"],
}

# Preposizioni sempre riconosciute (l'autore puo' estenderle).
PREP_BUILTIN = {
    "in": ["dentro", "nella", "nel", "nello", "nell", "nelle", "negli", "in"],
    "su": ["sopra", "sulla", "sul", "sullo", "sull", "sulle", "sugli", "su"],
    "con": ["con"],
}


# Parole ignorate (articoli, particelle). Restano fuori dalla risoluzione.
RUMORE = {
    "il", "lo", "la", "i", "gli", "le", "l",
    "un", "uno", "una", "del", "dello", "della", "dei", "degli", "delle",
    "al", "allo", "alla", "ai", "agli", "alle",
    "a", "di", "da", "the", "and", "e",
}

# Direzioni canoniche e loro sinonimi/abbreviazioni.
DIREZIONI = {
    "nord": "nord", "n": "nord",
    "sud": "sud", "s": "sud",
    "est": "est", "e": "est",
    "ovest": "ovest", "o": "ovest", "w": "ovest",
    "su": "su", "alto": "su", "sopra": "su",
    "giu": "giu", "giù": "giu", "basso": "giu", "sotto": "giu",
    "dentro": "dentro", "entra": "dentro",
    "fuori": "fuori", "esci": "fuori",
}

# Valori canonici in ordine: le uniche direzioni valide per un'uscita
# (l'editor le offre come selettore; la validazione vi si appoggia).
DIREZIONI_CANONICHE = ["nord", "sud", "est", "ovest", "su", "giu",
                       "dentro", "fuori"]


@dataclass
class ComandoParser:
    raw: str
    verbo: str | None = None
    direzione: str | None = None
    ogg_diretto: str | None = None      # id oggetto risolto
    prep: str | None = None             # preposizione canonica
    ogg_indiretto: str | None = None    # id oggetto risolto
    tutto: bool = False                 # oggetto diretto = «tutto»/«tutti»
    errore: str | None = None           # messaggio se non si capisce / ambiguo


class Parser:
    def __init__(self, mondo: Mondo):
        self.mondo = mondo
        # parti dai verbi predefiniti, poi estendili con quelli dell'avventura
        self._sinonimo_verbo: dict[str, str] = {}
        for vid, sinonimi in VERBI_BUILTIN.items():
            self._sinonimo_verbo[vid] = vid
            for s in sinonimi:
                self._sinonimo_verbo[s] = vid
        for vid, v in mondo.verbi.items():
            self._sinonimo_verbo[vid] = vid
            for s in v.sinonimi:
                self._sinonimo_verbo[s] = vid
        # preposizione: predefinite + quelle dell'avventura
        self._sinonimo_prep: dict[str, str] = {}
        for canon, varianti in PREP_BUILTIN.items():
            self._sinonimo_prep[canon] = canon
            for w in varianti:
                self._sinonimo_prep[w] = canon
        for canon, varianti in mondo.preposizioni.items():
            self._sinonimo_prep[canon] = canon
            for w in varianti:
                self._sinonimo_prep[w] = canon

    def analizza(self, testo: str) -> ComandoParser:
        cmd = ComandoParser(raw=testo)
        token = self._tokenizza(testo)
        if not token:
            cmd.errore = "Non ho capito."
            return cmd

        # direzione "secca" (es. "nord", "n") = movimento
        if len(token) == 1 and token[0] in DIREZIONI:
            cmd.verbo = "vai"
            cmd.direzione = DIREZIONI[token[0]]
            return cmd

        # primo token = verbo
        primo = token[0]
        if primo not in self._sinonimo_verbo:
            cmd.errore = f"Non conosco il verbo \"{primo}\"."
            return cmd
        cmd.verbo = self._sinonimo_verbo[primo]
        resto = token[1:]

        # "vai nord" / "vai dentro"
        if cmd.verbo == "vai":
            if resto and resto[0] in DIREZIONI:
                cmd.direzione = DIREZIONI[resto[0]]
            else:
                cmd.errore = "Vai dove?"
            return cmd

        # cerca una preposizione che spezzi diretto / indiretto
        idx_prep = next((i for i, t in enumerate(resto)
                         if t in self._sinonimo_prep), None)
        if idx_prep is None:
            frase_diretto, frase_indiretto = resto, []
        else:
            cmd.prep = self._sinonimo_prep[resto[idx_prep]]
            frase_diretto = resto[:idx_prep]
            frase_indiretto = resto[idx_prep + 1:]

        # «tutto»/«tutti» come oggetto diretto: non è un oggetto da risolvere,
        # è un quantificatore che il motore espande (es. «prendi tutto»)
        if frase_diretto and all(t in ("tutto", "tutti") for t in frase_diretto):
            cmd.tutto = True
            frase_diretto = []

        # risolvi i gruppi nominali contro gli oggetti in scope
        if frase_diretto:
            oid, err = self._risolvi(frase_diretto)
            if err:
                cmd.errore = err
                return cmd
            cmd.ogg_diretto = oid
        if frase_indiretto:
            oid, err = self._risolvi(frase_indiretto)
            if err:
                cmd.errore = err
                return cmd
            cmd.ogg_indiretto = oid
        return cmd

    # ------- interni -------

    def _tokenizza(self, testo: str) -> list[str]:
        pulito = "".join(c.lower() if c.isalnum() or c.isspace() else " "
                         for c in testo)
        # una parola-rumore va comunque tenuta se è una direzione: altrimenti
        # «e» (abbreviazione di est) verrebbe scartato come congiunzione.
        return [t for t in pulito.split()
                if t and (t not in RUMORE or t in DIREZIONI)]

    def _risolvi(self, parole: list[str]) -> tuple[str | None, str | None]:
        """Trova l'oggetto in scope che corrisponde al gruppo nominale.
        Ritorna (id, None) se unico, (None, messaggio) se assente/ambiguo."""
        scope = self.mondo.in_scope()
        candidati: list[Oggetto] = []
        for o in scope:
            nomi = {n.lower() for n in (o.nomi or [o.nome])}
            if any(p in nomi for p in parole):
                candidati.append(o)

        if not candidati:
            termine = " ".join(parole)
            return None, f"Non vedo nessun \"{termine}\" qui."

        if len(candidati) > 1:
            # prova a disambiguare con gli aggettivi presenti nel comando
            agg = set(parole)
            filtrati = [o for o in candidati
                        if agg & {a.lower() for a in o.aggettivi}]
            if len(filtrati) == 1:
                return filtrati[0].id, None
            nomi = ", ".join(o.nome for o in candidati)
            return None, f"Quale intendi: {nomi}?"

        return candidati[0].id, None
