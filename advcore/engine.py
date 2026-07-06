# SPDX-License-Identifier: GPL-3.0-or-later
"""Il motore di gioco. Senza I/O: prende una stringa di comando e restituisce
una stringa di risposta, mutando lo stato del Mondo.

Questa scelta e' il cardine dell'architettura: il motore non sa nulla di
curses o di terminali. Il player ncurses e l'editor (per l'anteprima) sono
gusci sottili attorno a Motore.esegui(). Lo stesso motore e' testabile senza
interfaccia e riusabile (web, bot, ...).

Ordine di risoluzione di un comando:
  1. parsing
  2. movimento (verbo "vai")
  3. regole dell'autore  (possono sovrascrivere qualsiasi verbo)
  4. handler predefiniti  (guarda, esamina, prendi, lascia, inventario)
"""

from __future__ import annotations

from dataclasses import replace

from .model import Mondo, INVENTARIO
from .parser import Parser, ComandoParser, VERBI_BUILTIN
from .rules import valuta_condizioni, esegui_effetti
from .salvataggio import stato_partita, applica_stato
from .testo import rendi_testo


# Direzione canonica -> testo mostrato nelle uscite
ETICHETTA_DIR = {
    "nord": "nord", "sud": "sud", "est": "est", "ovest": "ovest",
    "su": "su", "giu": "giù", "dentro": "dentro", "fuori": "fuori",
}


class Motore:
    def __init__(self, mondo: Mondo):
        self.mondo = mondo
        self.parser = Parser(mondo)
        if not mondo.stanza_corrente:
            mondo.stanza_corrente = (mondo.meta.get("stanza_iniziale")
                                     or next(iter(mondo.stanze), ""))
        # istantanea dello stato iniziale, per il riavvio della partita
        self._stato_iniziale = stato_partita(mondo)
        self._storia: list[dict] = []     # istantanee per l'annulla (undo)
        self._prima_volta = False          # contesto per il testo dinamico

    def riavvia(self) -> str:
        """Riporta la partita allo stato iniziale e restituisce l'apertura."""
        applica_stato(self.mondo, self._stato_iniziale)
        self.mondo.finita = False
        self.mondo.messaggio_finale = ""
        self.mondo.conversazione = ""
        self.mondo.punteggio = 0
        self.mondo.mosse = 0
        self.mondo.timer = {}
        self._storia = []
        for s in self.mondo.stanze.values():
            s.visitata = False
        return self.avvia()

    # ------- ciclo principale -------

    def avvia(self) -> str:
        self._prima_volta = False
        grezzo = self._avvia_grezzo()
        return rendi_testo(grezzo, self.mondo, {"prima_volta": self._prima_volta})

    def _avvia_grezzo(self) -> str:
        """Testo iniziale: intestazione + descrizione della stanza di partenza."""
        m = self.mondo
        intro = m.meta.get("intro", "")
        testa = []
        if m.meta.get("titolo"):
            testa.append(f"== {m.meta['titolo']} ==")
        if intro:
            testa.append(intro)
        testa.append(self._descrivi_stanza(prima_volta=True))
        return "\n\n".join(t for t in testa if t)

    def esegui(self, comando: str) -> str:
        self._prima_volta = False
        grezzo = self._esegui_grezzo(comando)
        return rendi_testo(grezzo, self.mondo, {"prima_volta": self._prima_volta})

    def _esegui_grezzo(self, comando: str) -> str:
        """Esegue un comando e restituisce il testo di risposta."""
        if self.mondo.finita:
            return "La partita e' finita. (digita 'riavvia' nel player)"

        # se si sta parlando con un png, l'input è una scelta di dialogo
        if self.mondo.conversazione:
            return self._dialogo(comando)

        # se è in corso uno scontro, l'input è un'azione di combattimento
        if self.mondo.scontro:
            return self._combatti(comando)

        cmd = self.parser.analizza(comando)
        if cmd.errore:
            return cmd.errore

        # annulla: ripristina lo stato prima dell'ultimo turno (non è un turno)
        if cmd.verbo == "annulla":
            return self._annulla()

        # istantanea PRIMA del turno, per poterlo annullare
        self._storia.append(stato_partita(self.mondo))
        if len(self._storia) > 100:
            self._storia.pop(0)

        self.mondo.mosse += 1
        pre_timer = set(self.mondo.timer)
        stanza_prima = self.mondo.stanza_corrente

        # comandi meta gestiti direttamente
        if cmd.verbo == "vai":
            risposta = self._muovi(cmd.direzione)
        elif cmd.tutto:
            risposta = (self._prendi_tutto() if cmd.verbo == "prendi"
                        else "Puoi usare \"tutto\" solo con \"prendi\".")
        else:
            rr = self._prova_regole(cmd)               # 1) regole dell'autore
            risposta = rr if rr is not None else self._predefinito(cmd)  # 2) builtin

        # 3) passo eventi (orologio + regole-evento), solo se restiamo "liberi"
        if not (self.mondo.conversazione or self.mondo.scontro or self.mondo.finita):
            extra = self._passo_eventi(stanza_prima, pre_timer)
            if extra:
                risposta = (risposta + "\n" + extra) if risposta else extra
        return risposta

    def _annulla(self) -> str:
        if not self._storia:
            return "Non c'è nulla da annullare."
        applica_stato(self.mondo, self._storia.pop())
        return "Hai annullato l'ultimo turno.\n\n" + self._descrivi_stanza()

    # ------- architettura a eventi (orologio dei turni) -------

    def _passo_eventi(self, stanza_prima: str, pre_timer: set) -> str:
        """Dopo ogni turno: scala i timer e valuta le regole-evento in ordine."""
        out: list[str] = []
        entrato = (self.mondo.stanza_corrente
                   if self.mondo.stanza_corrente != stanza_prima else None)
        scaduti = self._avanza_timer(pre_timer)
        for r in self.mondo.regole:
            if not r.quando.get("evento"):
                continue
            if not self._evento_corrisponde(r.quando, entrato, scaduti):
                continue
            if valuta_condizioni(r.se, self.mondo):
                esegui_effetti(r.allora, self.mondo, out)
            else:
                esegui_effetti(r.altrimenti, self.mondo, out)
            if self.mondo.finita:
                break
        return "\n".join(out)

    def _avanza_timer(self, pre_timer: set) -> list[str]:
        """Scala i timer esistenti prima di questo turno; restituisce gli scaduti.
        Un timer avviato durante il turno non scala nello stesso turno."""
        scaduti = []
        for nome in list(self.mondo.timer):
            if nome not in pre_timer:
                continue
            self.mondo.timer[nome] -= 1
            if self.mondo.timer[nome] <= 0:
                del self.mondo.timer[nome]
                scaduti.append(nome)
        return scaduti

    @staticmethod
    def _evento_corrisponde(quando: dict, entrato, scaduti: list) -> bool:
        ev = quando.get("evento")
        if ev == "turno":
            return True
        if ev == "entra":
            return entrato is not None and quando.get("stanza") == entrato
        if ev == "timer":
            return quando.get("timer") in scaduti
        return False

    # ------- regole -------

    def _prova_regole(self, cmd: ComandoParser) -> str | None:
        # per "usa X con Y" prova anche la combinazione invertita (Y con X)
        candidati = [cmd]
        if cmd.verbo == "usa" and cmd.prep and cmd.ogg_indiretto:
            candidati.append(replace(cmd, ogg_diretto=cmd.ogg_indiretto,
                                     ogg_indiretto=cmd.ogg_diretto))
        for r in self.mondo.regole:
            if r.quando.get("evento"):     # le regole-evento non rispondono ai comandi
                continue
            for cc in candidati:
                if self._regola_corrisponde(r.quando, cc):
                    out: list[str] = []
                    if valuta_condizioni(r.se, self.mondo):
                        esegui_effetti(r.allora, self.mondo, out)
                    else:
                        esegui_effetti(r.altrimenti, self.mondo, out)
                    return "\n".join(out) if out else ""
        return None

    @staticmethod
    def _regola_corrisponde(quando: dict, cmd: ComandoParser) -> bool:
        if quando.get("verbo") != cmd.verbo:
            return False
        for campo, attr in (("oggetto", "ogg_diretto"),
                            ("prep", "prep"),
                            ("oggetto_indiretto", "ogg_indiretto")):
            if campo not in quando:
                continue                    # campo assente = jolly
            atteso = quando[campo]
            valore = getattr(cmd, attr)
            # una lista vale "una qualsiasi di queste" (es. prep: [su, con])
            if isinstance(atteso, (list, tuple)):
                if valore not in atteso:
                    return False
            elif atteso != valore:
                return False
        return True

    # ------- handler predefiniti -------

    def _predefinito(self, cmd: ComandoParser) -> str:
        handler = {
            "guarda": self._h_guarda,
            "esamina": self._h_esamina,
            "prendi": self._h_prendi,
            "lascia": self._h_lascia,
            "inventario": self._h_inventario,
            "apri": self._h_apri,
            "chiudi": self._h_chiudi,
            "metti": self._h_metti,
            "indossa": self._h_indossa,
            "togli": self._h_togli,
            "usa": self._h_usa,
            "parla": self._h_parla,
            "attacca": self._h_attacca,
            "aiuto": self._h_aiuto,
            "punteggio": self._h_punteggio,
        }.get(cmd.verbo)
        if handler is None:
            return "Non puoi farlo."
        return handler(cmd)

    def _h_guarda(self, cmd: ComandoParser) -> str:
        if cmd.ogg_diretto:
            return self._h_esamina(cmd)
        return self._descrivi_stanza()

    def _h_esamina(self, cmd: ComandoParser) -> str:
        if not self.mondo.luce_disponibile():
            return "E' troppo buio per vedere."
        if not cmd.ogg_diretto:
            return "Esamina cosa?"
        o = self.mondo.oggetti[cmd.ogg_diretto]
        testo = o.props.get("desc") or f"Un {o.nome}, niente di speciale."
        if o.props.get("contenitore"):
            if o.props.get("aperto"):
                dentro = self.mondo.oggetti_in(o.id)
                if dentro:
                    testo += (" Contiene: "
                              + ", ".join(c.nome for c in dentro) + ".")
                else:
                    testo += " È vuoto."
            else:
                testo += " È chiuso."
        return testo

    def _h_prendi(self, cmd: ComandoParser) -> str:
        if not cmd.ogg_diretto:
            return "Prendi cosa?"
        o = self.mondo.oggetti[cmd.ogg_diretto]
        if o.posizione == INVENTARIO:
            return f"Hai gia' {o.nome}."
        if not o.props.get("prendibile"):
            return f"Non puoi prendere {o.nome}."
        o.posizione = INVENTARIO
        return f"Prendi {o.nome}."

    def _prendi_tutto(self) -> str:
        """«prendi tutto»: prova a prendere, uno per uno, gli oggetti
        prendibili visibili nella stanza, compreso il contenuto dei
        contenitori aperti (anche annidati). L'inventario e ciò che
        contiene restano fuori. Ogni presa passa dalle regole
        dell'autore come un «prendi» singolo, così gli enigmi che
        intercettano la presa restano validi. Scenario e oggetti non
        prendibili vengono ignorati in silenzio."""
        if not self.mondo.luce_disponibile():
            return "E' troppo buio per vedere cosa c'e' da prendere."
        visibili = list(self.mondo.oggetti_in(self.mondo.stanza_corrente))
        da_espandere = list(visibili)
        while da_espandere:
            o = da_espandere.pop()
            if o.props.get("contenitore") and o.props.get("aperto"):
                contenuto = self.mondo.oggetti_in(o.id)
                visibili += contenuto
                da_espandere.extend(contenuto)
        candidati = [o for o in visibili if o.props.get("prendibile")]
        if not candidati:
            return "Non c'e' nulla da prendere qui."
        righe = []
        for o in candidati:
            cmd = ComandoParser(raw=f"prendi {o.nome}", verbo="prendi",
                                ogg_diretto=o.id)
            rr = self._prova_regole(cmd)
            r = rr if rr is not None else self._predefinito(cmd)
            if r:
                righe.append(r)
            if self.mondo.finita:      # una regola può chiudere la partita
                break
        return "\n".join(righe)

    def _h_lascia(self, cmd: ComandoParser) -> str:
        if not cmd.ogg_diretto:
            return "Lascia cosa?"
        o = self.mondo.oggetti[cmd.ogg_diretto]
        if o.posizione != INVENTARIO:
            return f"Non hai {o.nome}."
        o.posizione = self.mondo.stanza_corrente
        return f"Lasci {o.nome}."

    def _h_inventario(self, cmd: ComandoParser) -> str:
        inv = self.mondo.inventario()
        if not inv:
            return "Non porti nulla."
        righe = []
        for o in inv:
            suffisso = " (indosso)" if o.props.get("indossato") else ""
            righe.append(f"  - {o.nome}{suffisso}")
        return "Porti con te:\n" + "\n".join(righe)

    def _h_apri(self, cmd: ComandoParser) -> str:
        if not cmd.ogg_diretto:
            return "Apri cosa?"
        o = self.mondo.oggetti[cmd.ogg_diretto]
        if not o.props.get("contenitore"):
            return f"{o.nome.capitalize()} non si apre."
        if o.props.get("aperto"):
            return f"{o.nome.capitalize()} è già aperto."
        o.props["aperto"] = True
        dentro = self.mondo.oggetti_in(o.id)
        if dentro:
            return (f"Apri {o.nome}. Contiene: "
                    + ", ".join(c.nome for c in dentro) + ".")
        return f"Apri {o.nome}. È vuoto."

    def _h_chiudi(self, cmd: ComandoParser) -> str:
        if not cmd.ogg_diretto:
            return "Chiudi cosa?"
        o = self.mondo.oggetti[cmd.ogg_diretto]
        if not o.props.get("contenitore"):
            return f"{o.nome.capitalize()} non si chiude."
        if not o.props.get("aperto"):
            return f"{o.nome.capitalize()} è già chiuso."
        o.props["aperto"] = False
        return f"Chiudi {o.nome}."

    def _h_metti(self, cmd: ComandoParser) -> str:
        if not cmd.ogg_diretto:
            return "Metti cosa?"
        o = self.mondo.oggetti[cmd.ogg_diretto]
        if not cmd.ogg_indiretto:
            return f"Dove vuoi mettere {o.nome}?"
        cont = self.mondo.oggetti[cmd.ogg_indiretto]
        if o.posizione != INVENTARIO:
            return f"Prima devi avere {o.nome}."
        if not cont.props.get("contenitore"):
            return f"Non puoi metterci nulla, in {cont.nome}."
        if not cont.props.get("aperto"):
            return f"{cont.nome.capitalize()} è chiuso."
        o.posizione = cont.id
        return f"Metti {o.nome} in {cont.nome}."

    def _h_indossa(self, cmd: ComandoParser) -> str:
        if not cmd.ogg_diretto:
            return "Indossa cosa?"
        o = self.mondo.oggetti[cmd.ogg_diretto]
        if o.posizione != INVENTARIO:
            return f"Non hai {o.nome}."
        if not o.props.get("indossabile"):
            return f"Non puoi indossare {o.nome}."
        if o.props.get("indossato"):
            return f"Indossi già {o.nome}."
        o.props["indossato"] = True
        return f"Indossi {o.nome}."

    def _h_togli(self, cmd: ComandoParser) -> str:
        if not cmd.ogg_diretto:
            return "Togli cosa?"
        o = self.mondo.oggetti[cmd.ogg_diretto]
        if not o.props.get("indossato"):
            return f"Non indossi {o.nome}."
        o.props["indossato"] = False
        return f"Ti togli {o.nome}."

    def _h_punteggio(self, cmd: ComandoParser) -> str:
        return (f"Punteggio: {self.mondo.punteggio} "
                f"in {self.mondo.mosse} mosse.")

    def _h_aiuto(self, cmd: ComandoParser) -> str:
        """Elenca solo i comandi che questa avventura usa davvero: le sezioni
        compaiono se il mondo contiene ciò che le rende utili (contenitori,
        indumenti, personaggi, ...) o se una regola risponde a quel verbo."""
        m = self.mondo
        props = {k for o in m.oggetti.values()
                 for k, v in o.props.items() if v}
        verbi_regole = {r.quando.get("verbo") for r in m.regole
                        if r.quando.get("verbo") and not r.quando.get("evento")}
        righe = [
            "  muoverti:     nord/sud/est/ovest, su/giù (o «vai <direzione>»)",
            "  osservare:    guarda, esamina <oggetto>",
        ]
        if "prendibile" in props or {"prendi", "lascia"} & verbi_regole:
            righe.append("  oggetti:      prendi/lascia <oggetto>, "
                         "prendi tutto, inventario")
        if "contenitore" in props or {"apri", "chiudi", "metti"} & verbi_regole:
            righe.append("  contenitori:  apri/chiudi <oggetto>, "
                         "metti <oggetto> in <contenitore>")
        if "indossabile" in props or {"indossa", "togli"} & verbi_regole:
            righe.append("  indumenti:    indossa/togli <oggetto>")
        interagire = []
        if "usa" in verbi_regole:
            interagire.append("usa <oggetto> con <oggetto>")
        if "png" in props or "parla" in verbi_regole:
            interagire.append("parla con <personaggio>")
        if interagire:
            righe.append("  interagire:   " + ", ".join(interagire))
        if "combattente" in props or "attacca" in verbi_regole:
            righe.append("  combattere:   attacca <personaggio> "
                         "(poi: attacca, difendi, fuggi)")
        speciali = [v for vid, v in m.verbi.items() if vid not in VERBI_BUILTIN]
        if speciali:
            righe.append("  speciali:     "
                         + ", ".join(self._firma_verbo(v) for v in speciali))
        partita = ["salva [nome]", "carica [nome]", "riavvia", "fine"]
        if self._usa_punteggio():
            partita.insert(0, "punteggio")
        righe.append("  partita:      " + ", ".join(partita))
        return "Comandi che puoi usare:\n" + "\n".join(righe)

    @staticmethod
    def _firma_verbo(v) -> str:
        """Come mostrare un verbo ad hoc nell'aiuto, secondo il suo tipo."""
        if v.tipo == "intransitivo":
            return v.id
        if v.tipo == "ditransitivo":
            prep = v.preposizioni[0] if v.preposizioni else "con"
            return f"{v.id} <oggetto> {prep} <oggetto>"
        return f"{v.id} <oggetto>"

    def _usa_punteggio(self) -> bool:
        """Vero se da qualche parte (regole, dialoghi, esiti degli scontri)
        c'e' un effetto che assegna punti."""
        def cerca(x) -> bool:
            if isinstance(x, dict):
                return "punti" in x or any(cerca(v) for v in x.values())
            if isinstance(x, list):
                return any(cerca(v) for v in x)
            return False
        return (any(cerca(r.allora) or cerca(r.altrimenti)
                    for r in self.mondo.regole)
                or any(cerca(o.props) for o in self.mondo.oggetti.values()))

    def _h_usa(self, cmd: ComandoParser) -> str:
        # le combinazioni vere sono regole "usa ... con ..." (provate prima)
        if not cmd.ogg_diretto:
            return "Usa cosa?"
        if cmd.ogg_indiretto:
            return "Non succede nulla di utile."
        return "Non sai bene come usarlo."

    # ------- personaggi e dialoghi -------

    def _h_parla(self, cmd: ComandoParser) -> str:
        target = cmd.ogg_indiretto or cmd.ogg_diretto
        if not target:
            return "Con chi vuoi parlare?"
        o = self.mondo.oggetti[target]
        if not o.props.get("png"):
            return f"{o.nome.capitalize()} non è il tipo da fare conversazione."
        return self._inizia_conversazione(o)

    def _battute_disponibili(self, o):
        """Battute attualmente selezionabili: (indice, battuta)."""
        disp = []
        for i, b in enumerate(o.props.get("dialogo", [])):
            if b.get("una_volta") and self.mondo.flags.get(f"__dlg_{o.id}_{i}"):
                continue
            if not valuta_condizioni(b.get("se", []), self.mondo):
                continue
            disp.append((i, b))
        return disp

    def _menu_dialogo(self, o) -> str:
        righe = []
        for n, (_i, b) in enumerate(self._battute_disponibili(o), start=1):
            righe.append(f"  {n}. {b['etichetta']}")
        righe.append("  0. (saluta e vai)")
        return "\n".join(righe)

    def _inizia_conversazione(self, o) -> str:
        parti = []
        if o.props.get("saluto"):
            parti.append(o.props["saluto"])
        # imposto il png corrente PRIMA di filtrare le battute, così le
        # condizioni/effetti di stato sanno con chi si sta parlando
        self.mondo.conversazione = o.id
        if not self._battute_disponibili(o):
            self.mondo.conversazione = ""
            return "\n".join(parti + [f"{o.nome.capitalize()} non ha nulla da dirti."])
        parti.append(self._menu_dialogo(o))
        parti.append("(scegli un numero)")
        return "\n".join(parti)

    def _dialogo(self, comando: str) -> str:
        o = self.mondo.oggetti.get(self.mondo.conversazione)
        if o is None:
            self.mondo.conversazione = ""
            return "..."
        s = comando.strip().lower()
        if s in ("0", "esci", "basta", "addio", "arrivederci", "ciao",
                 "stop", "fine", "vai"):
            self.mondo.conversazione = ""
            return f"Saluti {o.nome}."
        if not s.isdigit():
            return ("Sei in conversazione con " + o.nome
                    + ". Scegli il numero di un argomento, oppure «esci».\n"
                    + self._menu_dialogo(o))
        disp = self._battute_disponibili(o)
        n = int(s)
        if n < 1 or n > len(disp):
            return "Non c'è quell'argomento.\n" + self._menu_dialogo(o)
        i, b = disp[n - 1]
        out = [b["testo"]]
        esegui_effetti(b.get("allora", []), self.mondo, out)
        if b.get("una_volta"):
            self.mondo.flags[f"__dlg_{o.id}_{i}"] = True
        if self.mondo.finita:
            self.mondo.conversazione = ""
            return "\n".join(out)
        if self.mondo.scontro:            # una battuta ha avviato un combattimento
            self.mondo.conversazione = ""
            return "\n".join(out)
        if self._battute_disponibili(o):
            out.append(self._menu_dialogo(o))
        else:
            self.mondo.conversazione = ""
            out.append(f"Non hai altro da chiedere. Saluti {o.nome}.")
        return "\n".join(out)

    # ------- combattimento (minimale, deterministico) -------

    def _h_attacca(self, cmd: ComandoParser) -> str:
        target = cmd.ogg_indiretto or cmd.ogg_diretto
        if not target:
            return "Attacca chi?"
        o = self.mondo.oggetti.get(target)
        if o is None:
            return "Non vedo chi attaccare."
        if not o.props.get("combattente"):
            return f"Attaccare {o.nome} non ha molto senso."
        out: list[str] = []
        esegui_effetti([{"inizia_scontro": target}], self.mondo, out)
        out.append(self._prompt_scontro(o))
        return "\n".join(out)

    def _prompt_scontro(self, o) -> str:
        npc_hp = self.mondo.flags.get(f"__hp_{o.id}", o.props.get("hp", 1))
        pg_hp = self.mondo.flags.get("pg_hp", 20)
        return (f"[Scontro con {o.nome} — PF nemico {max(0, npc_hp)}, "
                f"tuoi PF {max(0, pg_hp)}]  Azioni: attacca, difendi, fuggi.")

    def _combatti(self, comando: str) -> str:
        o = self.mondo.oggetti.get(self.mondo.scontro)
        if o is None:
            self.mondo.scontro = ""
            return "Lo scontro si interrompe."
        azione = (comando.strip().lower().split() or [""])[0]
        if azione in ("attacca", "attacco", "colpisci", "combatti"):
            return self._round_combat(o, "attacca")
        if azione in ("difendi", "difenditi", "para", "guardia"):
            return self._round_combat(o, "difendi")
        if azione in ("fuggi", "scappa", "ritirati", "fuga"):
            return self._fuggi(o)
        if azione in ("stato", "situazione", "pf"):
            return self._prompt_scontro(o)
        return ("Sei nel mezzo di uno scontro con " + o.nome
                + ".\n" + self._prompt_scontro(o))

    def _round_combat(self, o, azione: str) -> str:
        pg_hp = self.mondo.flags.get("pg_hp", 20)
        pg_att = self.mondo.flags.get("pg_attacco", 5)
        pg_dif = self.mondo.flags.get("pg_difesa", 1)
        npc_hp = self.mondo.flags.get(f"__hp_{o.id}", o.props.get("hp", 1))
        npc_att = o.props.get("attacco", 1)
        npc_dif = o.props.get("difesa", 0)
        out: list[str] = []

        dif_eff = pg_dif
        if azione == "attacca":
            danno = max(1, pg_att - npc_dif)
            npc_hp -= danno
            out.append(f"Colpisci {o.nome}: {danno} danni "
                       f"(PF {o.nome}: {max(0, npc_hp)}).")
        else:  # difendi
            dif_eff = pg_dif * 2
            out.append("Ti metti in guardia: il prossimo colpo sarà attutito.")

        # png sconfitto: esegue l'esito (effetti standard) e chiude lo scontro
        if npc_hp <= 0:
            self.mondo.flags[f"__hp_{o.id}"] = 0
            self.mondo.scontro = ""
            out.append(f"{o.nome.capitalize()} è sconfitto!")
            esegui_effetti(o.props.get("sconfitto", []), self.mondo, out)
            return "\n".join(out)
        self.mondo.flags[f"__hp_{o.id}"] = npc_hp

        # contrattacco del png
        danno_npc = max(1, npc_att - dif_eff)
        pg_hp -= danno_npc
        self.mondo.flags["pg_hp"] = pg_hp
        out.append(f"{o.nome.capitalize()} ti colpisce: {danno_npc} danni "
                   f"(tuoi PF: {max(0, pg_hp)}).")
        if pg_hp <= 0:
            self.mondo.scontro = ""
            self.mondo.finita = True
            self.mondo.messaggio_finale = o.props.get(
                "uccisione", f"{o.nome.capitalize()} ti ha sopraffatto. Sei caduto.")
            out.append(self.mondo.messaggio_finale)
        return "\n".join(out)

    def _fuggi(self, o) -> str:
        if o.props.get("fuga") is False:
            return f"Non puoi fuggire da {o.nome}: devi affrontarlo."
        self.mondo.scontro = ""
        return f"Ti sganci e fuggi da {o.nome}."

    # ------- movimento -------

    def _muovi(self, direzione: str | None) -> str:
        if not direzione:
            return "Vai dove?"
        stanza = self.mondo.stanze[self.mondo.stanza_corrente]
        uscita = stanza.uscite.get(direzione)
        if uscita is None:
            return "Non puoi andare in quella direzione."

        # uscita semplice (id) oppure condizionata ({"to": id, "se": flag})
        if isinstance(uscita, dict):
            flag = uscita.get("se")
            if flag and not self.mondo.flags.get(flag):
                return uscita.get("bloccata", "Quella via e' bloccata.")
            dest = uscita["to"]
        else:
            dest = uscita

        if dest not in self.mondo.stanze:
            return "Quella via non porta da nessuna parte."
        self.mondo.stanza_corrente = dest
        prima = not self.mondo.stanze[dest].visitata
        return self._descrivi_stanza(prima_volta=prima)

    # ------- descrizione della stanza -------

    def _descrivi_stanza(self, prima_volta: bool = False) -> str:
        m = self.mondo
        self._prima_volta = prima_volta    # per i frammenti [prima_volta: ...]
        stanza = m.stanze[m.stanza_corrente]
        stanza.visitata = True

        if not m.luce_disponibile():
            return "E' buio pesto. Non vedi nulla. Ti servirebbe una luce."

        parti = [stanza.nome.upper(), stanza.desc]

        oggetti = [o for o in m.oggetti_in(stanza.id)
                   if not o.props.get("scenario")]
        # oggetti con una "frase di presenza" propria: la mostrano finché sono
        # qui (e sparisce quando vengono presi); gli altri vanno nell'elenco
        with_frase = [o for o in oggetti if o.props.get("in_stanza")]
        senza_frase = [o for o in oggetti if not o.props.get("in_stanza")]
        for o in with_frase:
            parti.append(o.props["in_stanza"])
        if senza_frase:
            elenco = ", ".join(o.nome for o in senza_frase)
            parti.append(f"Qui vedi: {elenco}.")

        uscite = self._uscite_visibili(stanza)
        if uscite:
            parti.append("Uscite: " + ", ".join(uscite) + ".")

        return "\n".join(p for p in parti if p)

    def _uscite_visibili(self, stanza) -> list[str]:
        visibili = []
        for direzione, uscita in stanza.uscite.items():
            etichetta = ETICHETTA_DIR.get(direzione, direzione)
            # un'uscita condizionata non ancora sbloccata resta nascosta
            if isinstance(uscita, dict):
                flag = uscita.get("se")
                if flag and not self.mondo.flags.get(flag):
                    continue
            visibili.append(etichetta)
        return visibili
