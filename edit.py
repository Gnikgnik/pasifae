# SPDX-License-Identifier: GPL-3.0-or-later
"""Editor visuale (urwid) per le avventure del motore advcore.

Permette di creare e modificare, senza scrivere JSON a mano:
  - la mappa (stanze e uscite, anche condizionate da flag)
  - gli oggetti e le loro proprieta'
  - i verbi del parser (sinonimi, tipo, preposizioni)
  - i flag iniziali e i metadati dell'avventura
  - le regole di interazione (innesco -> condizioni -> effetti)

In piu' offre un'ANTEPRIMA di gioco integrata che riusa lo stesso motore del
player: una conferma diretta che editor e runtime parlano lo stesso formato.

Uso:
    python3 edit.py [avventure/caverna.json]

Se il file non esiste viene creata una nuova avventura vuota in quel percorso.

Note di architettura:
  - Ogni schermata e' una *funzione costruttrice* (zero argomenti) registrata
    sullo stack di navigazione. Tornando indietro o ricaricando si ri-invoca
    la costruttrice, quindi le modifiche ai dati si riflettono da sole.
  - Le scelte su insiemi chiusi (stanza, oggetto, verbo, ...) usano un
    selettore a comparsa (overlay), per non digitare id a mano.
  - La logica pura (parsing valori, conversioni) e' separata e testabile.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import urwid

sys.path.insert(0, str(Path(__file__).resolve().parent))

from advcore import (carica_mondo, salva_mondo, Mondo, Motore,
                     Stanza, Oggetto, Verbo, Regola, valida, mappa_testuale)
from advcore import __version__ as VERSIONE
from advcore import storage as _storage
from advcore.parser import DIREZIONI_CANONICHE, VERBI_BUILTIN


# ===================== logica pura (testabile senza urwid) =====================

def parse_valore(s: str):
    """Converte una stringa nel tipo piu' adatto: bool, int, altrimenti str."""
    t = s.strip()
    if t.lower() in ("true", "vero", "si", "sì"):
        return True
    if t.lower() in ("false", "falso", "no"):
        return False
    try:
        return int(t)
    except ValueError:
        return t


def csv_a_lista(s: str) -> list[str]:
    return [p.strip() for p in s.split(",") if p.strip()]


def lista_a_csv(lst: list[str]) -> str:
    return ", ".join(lst or [])


def clona_mondo(m: Mondo) -> Mondo:
    """Copia profonda del mondo (via round-trip del formato di salvataggio)."""
    return _storage._da_dict(json.loads(
        json.dumps(_storage._a_dict(m), ensure_ascii=False)))


def riassunto_condizione(c: dict) -> str:
    if "flag" in c:
        if "uguale" in c:
            return f"flag «{c['flag']}» == {c['uguale']!r}"
        if "maggiore" in c:
            return f"flag «{c['flag']}» > {c['maggiore']}"
        return f"flag «{c['flag']}» è vero"
    if "oggetto_in" in c:
        oid, dove = c["oggetto_in"]
        return f"«{oid}» si trova in «{dove}»"
    if "stanza_corrente" in c:
        return f"sei nella stanza «{c['stanza_corrente']}»"
    if "stato_min" in c:
        return f"stato conversazione ≥ {c['stato_min']}"
    if "mosse_min" in c:
        return f"turno ≥ {c['mosse_min']}"
    return "(condizione sconosciuta)"


def riassunto_effetto(e: dict) -> str:
    if "set_flag" in e:
        return f"imposta flag «{e['set_flag']}» = {e.get('valore', True)!r}"
    if "incrementa" in e:
        return f"incrementa «{e['incrementa']}» di {e.get('di', 1)}"
    if "punti" in e:
        return f"assegna {e.get('punti', 0)} punti"
    if "sposta_oggetto" in e:
        return f"sposta «{e['sposta_oggetto']}» in «{e.get('a', '?')}»"
    if "stampa" in e:
        testo = e["stampa"]
        return f"stampa: {testo[:40]}{'…' if len(testo) > 40 else ''}"
    if "teleporta" in e:
        return f"teleporta il giocatore in «{e['teleporta']}»"
    if "vittoria" in e:
        return "VITTORIA"
    if "sconfitta" in e:
        return "SCONFITTA"
    if "stato" in e:
        return f"porta la conversazione allo stato {e['stato']}"
    if "avanza_stato" in e:
        return f"avanza lo stato di {e.get('avanza_stato', 1)}"
    if "inizia_scontro" in e:
        return f"inizia scontro con «{e['inizia_scontro']}»"
    if "avvia_timer" in e:
        return f"avvia il timer «{e['avvia_timer']}» (fra {e.get('turni', 1)} turni)"
    if "ferma_timer" in e:
        return f"ferma il timer «{e['ferma_timer']}»"
    return "(effetto sconosciuto)"


def quando_breve(q: dict) -> str:
    ev = q.get("evento")
    if ev == "turno":
        return "ogni turno"
    if ev == "entra":
        return f"ingresso → {q.get('stanza', '?')}"
    if ev == "timer":
        return f"timer «{q.get('timer', '?')}» scaduto"
    return f"{q.get('verbo', '?')} {q.get('oggetto', '')}".strip()


TIPI_CONDIZIONE = [
    ("flag (confronto)", "flag"),
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
    ("stampa testo", "stampa"),
    ("teleporta giocatore", "teleporta"),
    ("vittoria", "vittoria"),
    ("sconfitta", "sconfitta"),
    ("porta la conversazione allo stato N", "stato"),
    ("avanza lo stato di N", "avanza_stato"),
    ("inizia scontro con png", "inizia_scontro"),
    ("avvia un timer", "avvia_timer"),
    ("ferma un timer", "ferma_timer"),
]


def tipo_condizione(c: dict) -> str:
    for _, t in TIPI_CONDIZIONE:
        if t == "flag" and "flag" in c:
            return "flag"
        if t in c:
            return t
    return "flag"


def tipo_effetto(e: dict) -> str:
    for _, t in TIPI_EFFETTO:
        if t in e:
            return t
    return "stampa"


# ===================== widget di supporto =====================

class CampoScelta(urwid.WidgetWrap):
    """Bottone che apre un selettore a comparsa per scegliere un valore da un
    insieme chiuso. Mostra «etichetta: valore» e, opzionalmente, scrive la
    scelta in un dizionario (write-through)."""

    def __init__(self, app, etichetta, valore, opzioni_fn,
                 segnaposto="(scegli)", on_change=None):
        self.app = app
        self.etichetta = etichetta
        self.valore = valore
        self.opzioni_fn = opzioni_fn
        self.segnaposto = segnaposto
        self.on_change = on_change
        self._bottone = urwid.Button(self._label(), self._apri)
        super().__init__(urwid.AttrMap(self._bottone, "campo", "campo_f"))

    def _label(self) -> str:
        v = self.valore
        mostra = self.segnaposto if v in (None, "") else str(v)
        return f"{self.etichetta}: {mostra}"

    def _apri(self, _btn):
        self.app.scegli(self.etichetta, self.opzioni_fn(), self._scelto)

    def _scelto(self, valore):
        self.valore = valore
        self._bottone.set_label(self._label())
        if self.on_change:
            self.on_change(valore)

    def get(self):
        return self.valore


NUOVO_FLAG = "\x00nuovo_flag"


class CampoFlag(CampoScelta):
    """Selettore di flag: si sceglie tra i flag già dichiarati, evitando i
    refusi. Include l'opzione «nuovo flag…» per crearne uno al volo, che viene
    auto-dichiarato (così resta allineato e niente più nomi scritti a mano)."""

    def _scelto(self, valore):
        if valore == NUOVO_FLAG:
            self.app.chiedi_testo("Nome del nuovo flag", "", self._nuovo)
            return
        super()._scelto(valore)

    def _nuovo(self, nome):
        nome = (nome or "").strip()
        if not nome:
            return
        if nome not in self.app.mondo.flags:
            self.app.mondo.flags[nome] = False      # auto-dichiarazione
            self.app._segna_modifica()
        super()._scelto(nome)


class ListBoxTab(urwid.ListBox):
    """ListBox in cui Tab e Shift+Tab spostano il fuoco come Giù e Su,
    saltando le voci non selezionabili (con ritorno a capo)."""

    def keypress(self, size, key):
        if key in ("tab", "shift tab"):
            self._sposta(+1 if key == "tab" else -1)
            return None
        return super().keypress(size, key)

    def _sposta(self, direz):
        corpo = self.body
        n = len(corpo)
        if n == 0:
            return
        try:
            i = self.focus_position
        except Exception:                       # nessun fuoco corrente
            i = 0
        for _ in range(n):
            i = (i + direz) % n
            if corpo[i].selectable():
                self.set_focus(i, "above" if direz > 0 else "below")
                self._invalidate()
                return


class RigaScroll(urwid.Text):
    """Riga di testo selezionabile: permette di scorrere un blocco di testo
    (es. la mappa) con le frecce/Tab senza che la riga catturi i tasti."""

    _selectable = True

    def keypress(self, size, key):
        return key                              # non consuma: la ListBox scorre


# ===================== applicazione editor =====================

PALETTE = [
    ("titolo",    "white,bold",      "dark blue"),
    ("piede",     "black",           "light gray"),
    ("campo",     "light gray",      "black"),
    ("campo_f",   "black",           "light cyan"),
    ("etichetta", "yellow",          "black"),
    ("sezione",   "light cyan,bold", "black"),
    ("errore",    "light red,bold",  "black"),
    ("ok",        "light green,bold","black"),
    ("cmd",       "light cyan",      "black"),
]


def _trova_edit(widget):
    """Scende la catena del fuoco fino al primo urwid.Edit a fuoco (per sapere
    dove inserire il testo incollato). Restituisce None se non ce n'è uno."""
    w = widget
    for _ in range(80):
        if w is None:
            return None
        try:
            w = getattr(w, "base_widget", w)   # togli eventuali decorazioni
        except Exception:
            return None
        if isinstance(w, urwid.Edit):
            return w
        try:
            f = w.focus
        except Exception:
            return None
        if f is None or f is w:
            return None
        w = f
    return None


class EditorApp:
    def __init__(self, mondo: Mondo, percorso: str):
        self.mondo = mondo
        self.percorso = percorso
        self.modificato = False
        self.stack: list[tuple] = []      # (costruttrice, titolo)
        self._harvest = None              # raccolta campi prima di un ricarica
        self._in_paste = False            # incolla da sorgente esterna in corso
        self._paste_buf: list[str] = []

        self.header = urwid.AttrMap(urwid.Text(""), "titolo")
        self.piede = urwid.AttrMap(urwid.Text(""), "piede")
        self.frame = urwid.Frame(urwid.SolidFill(" "),
                                 header=self.header, footer=self.piede)
        self.loop = None

    # ---------- avvio e navigazione ----------

    def run(self):
        self.push(self.vista_home, "")
        self.loop = urwid.MainLoop(self.frame, PALETTE,
                                   unhandled_input=self._tasto_globale,
                                   input_filter=self._filtro_input)
        # abilita l'incolla dal terminale (bracketed paste) appena lo schermo è pronto
        self.loop.set_alarm_in(0, lambda *_: self._abilita_incolla())
        try:
            self.loop.run()
        finally:
            import sys
            try:
                sys.stdout.write("\x1b[?2004l")   # disabilita bracketed paste
                sys.stdout.flush()
            except Exception:
                pass

    # ---------- incolla da sorgenti esterne (bracketed paste) ----------

    def _abilita_incolla(self):
        try:
            self.loop.screen.write("\x1b[?2004h")
            self.loop.screen.flush()
        except Exception:
            pass

    def _filtro_input(self, keys, raw):
        """Intercetta il testo incollato (tra «begin paste» e «end paste») e lo
        inserisce in blocco nel campo a fuoco, così righe e caratteri non
        vengono interpretati come comandi di navigazione."""
        if not self._in_paste and not any(
                k in ("begin paste", "end paste") for k in keys):
            return keys
        passanti = []
        for k in keys:
            if k == "begin paste":
                self._in_paste = True
                self._paste_buf = []
            elif k == "end paste":
                self._in_paste = False
                self._incolla("".join(self._paste_buf))
                self._paste_buf = []
            elif self._in_paste:
                if k == "enter":
                    self._paste_buf.append("\n")
                elif k == "tab":
                    self._paste_buf.append("\t")
                elif isinstance(k, str) and len(k) == 1 and k.isprintable():
                    self._paste_buf.append(k)
                # gli altri tasti durante l'incolla vengono ignorati
            else:
                passanti.append(k)
        return passanti

    def _incolla(self, testo):
        if not testo:
            return
        e = _trova_edit(self.loop.widget if self.loop else None)
        if e is None:
            return
        if not getattr(e, "multiline", False):
            testo = testo.replace("\n", " ").replace("\t", " ")
        e.insert_text(testo)
        self._segna_modifica()

    def push(self, costruttrice, titolo):
        self._harvest = None
        self.stack.append((costruttrice, titolo))
        self._mostra()

    def indietro(self, *_):
        if len(self.stack) > 1:
            self._harvest = None
            self.stack.pop()
            self._mostra()

    def ricarica(self):
        self._harvest = None
        self._mostra()

    def _mostra(self):
        costruttrice, titolo = self.stack[-1]
        corpo = costruttrice()
        self.frame.body = corpo
        marchio = " *" if self.modificato else ""
        self.header.original_widget.set_text(
            f" {titolo}{marchio}   [{self.percorso}]   · Pasifae · advcore v{VERSIONE}")
        self.piede.original_widget.set_text(
            " Frecce/Tab: muovi · Invio: seleziona/modifica · Esc: indietro")

    def _tasto_globale(self, tasto):
        if isinstance(tasto, str) and tasto == "esc":
            # se c'e' un overlay (selettore) aperto, chiudilo
            if self.loop and self.loop.widget is not self.frame:
                self.loop.widget = self.frame
            else:
                self.indietro()

    def messaggio(self, testo, attr="ok"):
        self.piede.original_widget.set_text(("  " + testo))
        self.piede.set_attr_map({None: attr})

    def _segna_modifica(self):
        self.modificato = True

    # ---------- selettore a comparsa ----------

    def scegli(self, titolo, opzioni, on_scelto):
        righe = []
        for etichetta, valore in opzioni:
            righe.append(self._bottone(
                etichetta, lambda b, v=valore: self._chiudi_e(on_scelto, v)))
        righe.append(urwid.Divider())
        righe.append(self._bottone("Annulla", lambda b: self._chiudi()))
        lb = ListBoxTab(urwid.SimpleFocusListWalker(righe))
        box = urwid.LineBox(lb, title=titolo)
        self.loop.widget = urwid.Overlay(
            box, self.frame, align="center", width=("relative", 70),
            valign="middle", height=("relative", 70))

    def _chiudi(self):
        self.loop.widget = self.frame

    def _chiudi_e(self, cb, valore):
        self.loop.widget = self.frame
        cb(valore)

    def chiedi_testo(self, titolo, valore, on_ok):
        """Piccolo prompt a comparsa per inserire una stringa (es. il nome di
        un nuovo flag)."""
        e = urwid.Edit("", valore or "")
        righe = [urwid.AttrMap(e, "campo", "campo_f"), urwid.Divider(),
                 self._azioni([("OK", lambda b: self._chiudi_e(on_ok, e.edit_text)),
                               ("Annulla", lambda b: self._chiudi())])]
        lb = ListBoxTab(urwid.SimpleFocusListWalker(righe))
        box = urwid.LineBox(lb, title=titolo)
        self.loop.widget = urwid.Overlay(
            box, self.frame, align="center", width=("relative", 60),
            valign="middle", height=("relative", 30))

    # ---------- costruttori di widget ----------

    def _bottone(self, etichetta, on_press, dati=None):
        b = urwid.Button(etichetta, on_press, dati)
        return urwid.AttrMap(b, "campo", "campo_f")

    def _edit(self, caption, testo, multiline=False):
        e = urwid.Edit(("etichetta", caption), testo or "", multiline=multiline)
        return urwid.AttrMap(e, "campo", "campo_f"), e

    def _check(self, etichetta, stato):
        c = urwid.CheckBox(etichetta, state=bool(stato))
        return urwid.AttrMap(c, "campo", "campo_f"), c

    def _listbox(self, righe):
        return ListBoxTab(urwid.SimpleFocusListWalker(righe))

    def _azioni(self, voci):
        """Riga di bottoni d'azione: voci = [(etichetta, callback), ...]."""
        cols = [self._bottone(et, cb) for et, cb in voci]
        return urwid.Columns(cols, dividechars=2)

    # ---------- opzioni per i selettori ----------

    def opz_stanze(self, nessuno=False):
        o = [(f"{sid} — {s.nome}", sid) for sid, s in self.mondo.stanze.items()]
        return ([("(nessuna)", None)] + o) if nessuno else o

    def opz_oggetti(self, nessuno=False):
        o = [(f"{oid} — {ob.nome}", oid) for oid, ob in self.mondo.oggetti.items()]
        return ([("(nessuno)", None)] + o) if nessuno else o

    def opz_flag(self, vuoto=False):
        opz = [(n, n) for n in sorted(self.mondo.flags.keys())]
        if vuoto:
            opz = [("(nessuno)", "")] + opz
        opz.append(("« nuovo flag… »", NUOVO_FLAG))
        return opz

    def _campo_flag(self, etichetta, valore, vuoto=False):
        seg = "(nessuno)" if vuoto else "(scegli)"
        return CampoFlag(self, etichetta, valore or "",
                         lambda: self.opz_flag(vuoto), segnaposto=seg)

    def opz_verbi(self, nessuno=False):
        o = []
        for vid in self.mondo.verbi:
            marca = "  · predefinito" if vid in VERBI_BUILTIN else ""
            o.append((f"{vid}{marca}", vid))
        o += [(f"{vid}  · predefinito", vid) for vid in VERBI_BUILTIN
              if vid not in self.mondo.verbi]
        return ([("(nessuno)", None)] + o) if nessuno else o

    def opz_prep(self, nessuno=True):
        o = [(p, p) for p in self.mondo.preposizioni]
        return ([("(nessuna)", None)] + o) if nessuno else o

    def opz_luoghi(self):
        """Destinazioni valide per posizione/sposta: stanze + inventario + contenitori."""
        o = [("inventario", "inventario"), ("stanza corrente", "stanza")]
        o += [(f"stanza: {sid}", sid) for sid in self.mondo.stanze]
        o += [(f"dentro: {oid}", oid) for oid in self.mondo.oggetti]
        return o

    def opz_direzioni(self):
        etich = {"su": "su (salita)", "giu": "giù (discesa)"}
        return [(etich.get(d, d), d) for d in DIREZIONI_CANONICHE]

    # =================== SCHERMATE ===================

    def vista_home(self):
        m = self.mondo
        problemi = valida(m)
        n_err = sum(1 for x in problemi if x.gravita == "errore")
        n_avv = len(problemi) - n_err
        et_verifica = f"» Verifica riferimenti  ({n_err} errori, {n_avv} avvisi)"
        righe = [
            urwid.Text(("sezione", f"  {m.meta.get('titolo', 'Avventura senza titolo')}")),
            urwid.Divider(),
            self._bottone(f"Stanze ............ {len(m.stanze)}",
                          lambda b: self.push(self.vista_stanze, "Stanze")),
            self._bottone(f"Oggetti ........... {len(m.oggetti)}",
                          lambda b: self.push(self.vista_oggetti, "Oggetti")),
            self._bottone(f"Verbi ............. {len(m.verbi)}",
                          lambda b: self.push(self.vista_verbi, "Verbi")),
            self._bottone(f"Regole ............ {len(m.regole)}",
                          lambda b: self.push(self.vista_regole, "Regole")),
            self._bottone(f"Flag iniziali ..... {len(m.flags)}",
                          lambda b: self.push(self.vista_flag, "Flag iniziali")),
            self._bottone("Metadati avventura",
                          lambda b: self.push(self.vista_meta, "Metadati")),
            urwid.Divider(),
            self._bottone(et_verifica,
                          lambda b: self.push(self.vista_verifica, "Verifica")),
            self._bottone("» Cerca",
                          lambda b: self.push(self.vista_cerca, "Cerca")),
            self._bottone("» Mappa dell'avventura",
                          lambda b: self.push(self.vista_mappa, "Mappa")),
            self._bottone("» Anteprima di gioco",
                          lambda b: self.push(self.vista_anteprima, "Anteprima")),
            self._bottone("» Salva su file", lambda b: self.azione_salva()),
            self._bottone("» Esci", lambda b: self.azione_esci()),
        ]
        return self._listbox(righe)

    # ---------- verifica dei riferimenti ----------

    def vista_verifica(self):
        problemi = valida(self.mondo)
        righe = [urwid.Text(("sezione", "  Verifica riferimenti")),
                 urwid.Text(("etichetta",
                             "  Invio su un problema per aprire l'entità")),
                 urwid.Divider()]
        if not problemi:
            righe.append(urwid.Text(("ok", "  Nessun problema rilevato. ✓")))
        for pr in problemi:
            attr = "errore" if pr.gravita == "errore" else "etichetta"
            etichetta = f"[{pr.gravita}] {pr.dove}: {pr.messaggio}"
            if pr.categoria:
                righe.append(self._bottone(
                    etichetta, lambda b, p=pr: self._vai_problema(p)))
            else:
                righe.append(urwid.Text((attr, "  " + etichetta)))
        righe += [urwid.Divider(), self._bottone("< indietro", self.indietro)]
        return self._listbox(righe)

    def _vai_entita(self, categoria, chiave):
        if categoria == "stanza" and chiave in self.mondo.stanze:
            self._lav_stanza_id = None
            self.push(lambda: self.form_stanza(chiave), f"Stanza: {chiave}")
        elif categoria == "oggetto" and chiave in self.mondo.oggetti:
            self.push(lambda: self.form_oggetto(chiave), f"Oggetto: {chiave}")
        elif categoria == "verbo" and chiave in self.mondo.verbi:
            self.push(lambda: self.form_verbo(chiave), f"Verbo: {chiave}")
        elif categoria == "regola" and isinstance(chiave, int) \
                and 0 <= chiave < len(self.mondo.regole):
            self.apri_regola(chiave)
        elif categoria == "meta":
            self.push(self.vista_meta, "Metadati")

    def _vai_problema(self, pr):
        self._vai_entita(pr.categoria, pr.chiave)

    # ---------- mappa testuale ----------

    def vista_mappa(self):
        testo = mappa_testuale(self.mondo)
        righe = [urwid.Text(("sezione", "  Mappa dell'avventura")),
                 urwid.Text(("etichetta",
                             "  scorri con frecce o Tab · Esc per tornare")),
                 urwid.Divider()]
        for ln in testo.split("\n"):
            righe.append(RigaScroll(ln if ln else " ", wrap="clip"))
        righe += [urwid.Divider(), self._bottone("< indietro", self.indietro)]
        return self._listbox(righe)

    # ---------- ricerca globale ----------

    def _cerca(self, q: str):
        q = q.lower().strip()
        ris = []
        if not q:
            return ris
        for sid, s in self.mondo.stanze.items():
            if q in sid.lower() or q in s.nome.lower() or q in (s.desc or "").lower():
                ris.append((f"stanza · {sid} — {s.nome}", "stanza", sid))
        for oid, o in self.mondo.oggetti.items():
            campi = [oid, o.nome] + list(o.nomi) + [o.props.get("desc", "")]
            if any(q in str(x).lower() for x in campi):
                ris.append((f"oggetto · {oid} — {o.nome}", "oggetto", oid))
        for vid, v in self.mondo.verbi.items():
            if q in vid.lower() or any(q in s.lower() for s in v.sinonimi):
                ris.append((f"verbo · {vid}", "verbo", vid))
        for i, r in enumerate(self.mondo.regole):
            testo = f"{r.id} {r.quando.get('verbo', '')} {r.quando.get('oggetto', '')}"
            if q in testo.lower():
                ris.append((f"regola [{i}] · {r.id or '?'}", "regola", i))
        return ris

    def vista_cerca(self):
        q = getattr(self, "_query", "")
        w_q, e_q = self._edit("cerca (id, nome, testo): ", q)
        self._harvest = lambda: setattr(self, "_query", e_q.edit_text)
        righe = [urwid.Text(("sezione", "  Cerca")), urwid.Divider(), w_q,
                 self._bottone("cerca", lambda b: self._fai_cerca(e_q)),
                 urwid.Divider()]
        risultati = self._cerca(q)
        if q and not risultati:
            righe.append(urwid.Text(("etichetta", "  Nessun risultato.")))
        elif risultati:
            righe.append(urwid.Text(("etichetta",
                                     f"  {len(risultati)} risultati:")))
        for et, cat, chiave in risultati:
            righe.append(self._bottone(
                et, lambda b, c=cat, k=chiave: self._vai_entita(c, k)))
        righe += [urwid.Divider(), self._bottone("< indietro", self.indietro)]
        return self._listbox(righe)

    def _fai_cerca(self, e_q):
        self._query = e_q.edit_text
        self.ricarica()

    # ---------- duplicazione ----------

    @staticmethod
    def _nuovo_id(base, esistenti) -> str:
        cand = f"{base}_copia"
        n = 2
        while cand in esistenti:
            cand = f"{base}_copia{n}"
            n += 1
        return cand

    def _duplica_stanza(self, sid):
        s = self.mondo.stanze[sid]
        nid = self._nuovo_id(sid, self.mondo.stanze)
        self.mondo.stanze[nid] = Stanza(
            id=nid, nome=f"{s.nome} (copia)", desc=s.desc,
            uscite=copy.deepcopy(s.uscite), buia=s.buia)
        self._segna_modifica()
        self._lav_stanza_id = None
        self.push(lambda: self.form_stanza(nid), f"Stanza: {nid}")

    def _duplica_oggetto(self, oid):
        o = self.mondo.oggetti[oid]
        nid = self._nuovo_id(oid, self.mondo.oggetti)
        self.mondo.oggetti[nid] = Oggetto(
            id=nid, nome=f"{o.nome} (copia)", nomi=list(o.nomi),
            aggettivi=list(o.aggettivi), posizione=o.posizione,
            props=copy.deepcopy(o.props))
        self._segna_modifica()
        self.push(lambda: self.form_oggetto(nid), f"Oggetto: {nid}")

    def _duplica_verbo(self, vid):
        v = self.mondo.verbi[vid]
        nid = self._nuovo_id(vid, self.mondo.verbi)
        self.mondo.verbi[nid] = Verbo(
            id=nid, sinonimi=list(v.sinonimi), tipo=v.tipo,
            preposizioni=list(v.preposizioni))
        self._segna_modifica()
        self.push(lambda: self.form_verbo(nid), f"Verbo: {nid}")

    def _duplica_regola(self):
        if self._harvest:
            self._harvest()
        r = self._reg
        nuova = Regola(id=f"{r['id'] or 'regola'}_copia",
                       quando=copy.deepcopy(r["quando"]),
                       se=copy.deepcopy(r["se"]),
                       allora=copy.deepcopy(r["allora"]),
                       altrimenti=copy.deepcopy(r["altrimenti"]))
        self.mondo.regole.append(nuova)
        self._segna_modifica()
        self.apri_regola(len(self.mondo.regole) - 1)

    # ---------- liste generiche ----------


    def vista_lista(self, titolo, elementi, on_apri, on_nuovo):
        righe = [urwid.Text(("sezione", f"  {titolo}")), urwid.Divider()]
        for etichetta, chiave in elementi:
            righe.append(self._bottone(etichetta,
                                       lambda b, k=chiave: on_apri(k)))
        righe.append(urwid.Divider())
        righe.append(self._bottone("+ nuovo", lambda b: on_nuovo()))
        righe.append(self._bottone("< indietro", self.indietro))
        return self._listbox(righe)

    def vista_stanze(self):
        elementi = [(f"{sid} — {s.nome}", sid)
                    for sid, s in self.mondo.stanze.items()]
        return self.vista_lista("Stanze", elementi,
                                lambda k: self.push(lambda: self.form_stanza(k),
                                                    f"Stanza: {k}"),
                                lambda: self.push(lambda: self.form_stanza(None),
                                                  "Nuova stanza"))

    def vista_oggetti(self):
        elementi = [(f"{oid} — {o.nome}", oid)
                    for oid, o in self.mondo.oggetti.items()]
        return self.vista_lista("Oggetti", elementi,
                                lambda k: self.push(lambda: self.form_oggetto(k),
                                                    f"Oggetto: {k}"),
                                lambda: self.push(lambda: self.form_oggetto(None),
                                                  "Nuovo oggetto"))

    def vista_verbi(self):
        elementi = []
        for vid in self.mondo.verbi:
            marca = "  · predefinito (esteso)" if vid in VERBI_BUILTIN else ""
            elementi.append((f"{vid}{marca}", vid))
        elementi += [(f"{vid}  · predefinito (sola lettura)", vid)
                     for vid in VERBI_BUILTIN if vid not in self.mondo.verbi]
        return self.vista_lista("Verbi", elementi,
                                lambda k: self.push(lambda: self.form_verbo(k),
                                                    f"Verbo: {k}"),
                                lambda: self.push(lambda: self.form_verbo(None),
                                                  "Nuovo verbo"))

    def vista_regole(self):
        elementi = [(f"[{i}] {r.id or '(senza id)'} — {quando_breve(r.quando)}", i)
                    for i, r in enumerate(self.mondo.regole)]
        return self.vista_lista("Regole", elementi,
                                lambda k: self.apri_regola(k),
                                lambda: self.apri_regola(None))

    # ---------- form: STANZA ----------

    def form_stanza(self, sid):
        nuova = sid is None
        s = self.mondo.stanze.get(sid) if not nuova else None
        if not hasattr(self, "_lav_stanza_id") or self._lav_stanza_id != sid:
            # inizializza la copia di lavoro la prima volta che si apre
            self._lav_stanza_id = sid
            self._lav_uscite = []
            if s:
                for direzione, u in s.uscite.items():
                    if isinstance(u, dict):
                        self._lav_uscite.append(
                            {"dir": direzione, "to": u.get("to", ""),
                             "se": u.get("se", ""),
                             "bloccata": u.get("bloccata", "")})
                    else:
                        self._lav_uscite.append(
                            {"dir": direzione, "to": u, "se": "", "bloccata": ""})

        c = {}
        w_id, c["id"] = self._edit("id: ", sid or "")
        w_nome, c["nome"] = self._edit("nome: ", s.nome if s else "")
        w_desc, c["desc"] = self._edit("descrizione:\n", s.desc if s else "",
                                       multiline=True)
        w_buia, c["buia"] = self._check("stanza buia (serve una luce)",
                                        s.buia if s else False)

        righe = [urwid.Text(("sezione", "  Stanza")), urwid.Divider()]
        righe.append(w_id if nuova else urwid.Text(("etichetta", f"id: {sid}")))
        righe += [w_nome, w_desc, w_buia, urwid.Divider(),
                  urwid.Text(("sezione", "  Uscite"))]

        for i, u in enumerate(self._lav_uscite):
            sel_dir = CampoScelta(self, "dir", u["dir"], self.opz_direzioni,
                                  segnaposto="(scegli)")
            sel_to = CampoScelta(self, "verso", u["to"],
                                 lambda: self.opz_stanze())
            sel_se = self._campo_flag("se flag", u["se"], vuoto=True)
            w_bloc, e_bloc = self._edit(
                "   se bloccata, mostra: ", u.get("bloccata", ""))
            # registra i widget per la raccolta
            u["_w"] = (sel_dir, sel_to, sel_se, e_bloc)
            righe.append(urwid.Columns([
                ("weight", 2, sel_dir), ("weight", 3, sel_to),
                ("weight", 3, sel_se),
                ("weight", 2, self._bottone(
                    "rimuovi", lambda b, idx=i: self._uscita_rimuovi(idx))),
            ], dividechars=1))
            righe.append(w_bloc)

        righe.append(self._bottone("+ aggiungi uscita",
                                   lambda b: self._uscita_aggiungi()))
        righe.append(urwid.Divider())

        def harvest():
            for u in self._lav_uscite:
                sel_dir, sel_to, sel_se, e_bloc = u["_w"]
                u["dir"] = sel_dir.get() or ""
                u["to"] = sel_to.get()
                u["se"] = sel_se.get() or ""
                u["bloccata"] = e_bloc.edit_text.strip()
        self._harvest = harvest

        azioni = [("Salva", lambda b: self._salva_stanza(c, nuova))]
        if not nuova:
            azioni.append(("Elimina", lambda b: self._elimina_stanza(sid)))
            azioni.append(("Duplica", lambda b: self._duplica_stanza(sid)))
        azioni.append(("Indietro", self.indietro))
        righe.append(self._azioni(azioni))
        return self._listbox(righe)

    def _uscita_aggiungi(self):
        if self._harvest:
            self._harvest()
        self._lav_uscite.append({"dir": "", "to": None, "se": "", "bloccata": ""})
        self.ricarica()

    def _uscita_rimuovi(self, idx):
        if self._harvest:
            self._harvest()
        if 0 <= idx < len(self._lav_uscite):
            del self._lav_uscite[idx]
        self.ricarica()

    def _uscite_da_lav(self) -> dict:
        uscite = {}
        for u in self._lav_uscite:
            d = u["dir"].strip()
            if not d or not u["to"]:
                continue
            if u["se"]:
                ex = {"to": u["to"], "se": u["se"]}
                if u.get("bloccata"):
                    ex["bloccata"] = u["bloccata"]
                uscite[d] = ex
            else:
                uscite[d] = u["to"]
        return uscite

    def _salva_stanza(self, c, nuova):
        if self._harvest:
            self._harvest()
        sid = c["id"].edit_text.strip()
        if not sid:
            return self.messaggio("L'id non puo' essere vuoto.", "errore")
        if nuova and sid in self.mondo.stanze:
            return self.messaggio(f"Esiste gia' una stanza «{sid}».", "errore")
        uscite = self._uscite_da_lav()
        self.mondo.stanze[sid] = Stanza(
            id=sid, nome=c["nome"].edit_text.strip(),
            desc=c["desc"].edit_text, uscite=uscite,
            buia=c["buia"].state)
        if not self.mondo.meta.get("stanza_iniziale"):
            self.mondo.meta["stanza_iniziale"] = sid
        self._lav_stanza_id = None
        self._segna_modifica()
        self.indietro()

    def _elimina_stanza(self, sid):
        self.mondo.stanze.pop(sid, None)
        self._lav_stanza_id = None
        self._segna_modifica()
        self.indietro()

    # ---------- form: OGGETTO ----------

    def form_oggetto(self, oid):
        nuovo = oid is None
        o = self.mondo.oggetti.get(oid) if not nuovo else None
        props = dict(o.props) if o else {}

        c = {}
        w_id, c["id"] = self._edit("id: ", oid or "")
        w_nome, c["nome"] = self._edit("nome: ", o.nome if o else "")
        w_nomi, c["nomi"] = self._edit("sostantivi (csv): ",
                                       lista_a_csv(o.nomi) if o else "")
        w_agg, c["aggettivi"] = self._edit("aggettivi (csv): ",
                                           lista_a_csv(o.aggettivi) if o else "")
        c["posizione"] = CampoScelta(self, "posizione",
                                     o.posizione if o else None,
                                     self.opz_luoghi)
        w_desc, c["desc"] = self._edit("descrizione:\n",
                                       props.get("desc", ""), multiline=True)
        w_frase, c["in_stanza"] = self._edit(
            "frase in stanza (mostrata finché è qui):\n",
            props.get("in_stanza", ""), multiline=True)
        w_prend, c["prendibile"] = self._check("prendibile",
                                               props.get("prendibile"))
        w_scen, c["scenario"] = self._check(
            "scenario (non elencato tra gli oggetti)", props.get("scenario"))
        w_cont, c["contenitore"] = self._check("contenitore",
                                               props.get("contenitore"))
        w_apt, c["aperto"] = self._check("aperto (se contenitore)",
                                         props.get("aperto"))
        w_ind, c["indossabile"] = self._check("indossabile",
                                              props.get("indossabile"))
        w_png, c["png"] = self._check("personaggio (png)", props.get("png"))
        # combattimento
        w_comb, c["combattente"] = self._check("combattente (affrontabile in scontro)",
                                               props.get("combattente"))
        w_hp, c["hp"] = self._edit("  PF (hp): ", str(props.get("hp", 10)))
        w_att, c["attacco"] = self._edit("  attacco: ", str(props.get("attacco", 3)))
        w_dif, c["difesa"] = self._edit("  difesa: ", str(props.get("difesa", 1)))
        w_fuga, c["fuga"] = self._check(
            "  il giocatore può fuggire", props.get("fuga", True))
        w_intro, c["intro_scontro"] = self._edit(
            "  intro dello scontro:\n", props.get("intro_scontro", ""),
            multiline=True)
        # luce: assente | sempre | flag
        luce = props.get("luce")
        w_luce, c["luce_on"] = self._check("e' una sorgente di luce",
                                           luce is not None)
        c["luce_flag"] = self._campo_flag(
            "  flag luce (nessuno = sempre accesa)",
            luce if isinstance(luce, str) else "", vuoto=True)
        # proprietà non gestite dai campi (es. dialogo): conservate
        c["_props_orig"] = props
        n_battute = len(props.get("dialogo", []))

        righe = [urwid.Text(("sezione", "  Oggetto")), urwid.Divider()]
        righe.append(w_id if nuovo else urwid.Text(("etichetta", f"id: {oid}")))
        righe += [w_nome, w_nomi, w_agg, c["posizione"], w_desc, w_frase,
                  urwid.Divider(), urwid.Text(("sezione", "  Proprietà")),
                  w_prend, w_scen, w_cont, w_apt, w_ind, w_png,
                  w_luce, c["luce_flag"], urwid.Divider(),
                  urwid.Text(("sezione", "  Combattimento")),
                  w_comb, w_hp, w_att, w_dif, w_fuga, w_intro, urwid.Divider()]
        if not nuovo:
            righe.append(self._bottone(
                f"» Modifica dialogo  ({n_battute} battute)",
                lambda b: self._apri_dialogo_da_oggetto(c, oid)))
            n_sconf = len(props.get("sconfitto", []))
            righe.append(self._bottone(
                f"» Esito alla sconfitta  ({n_sconf} effetti)",
                lambda b: self._apri_sconfitto_da_oggetto(c, oid)))
        else:
            righe.append(urwid.Text(("etichetta",
                "  (salva l'oggetto per modificarne dialogo ed esito scontro)")))
        righe.append(urwid.Divider())
        azioni = [("Salva", lambda b: self._salva_oggetto(c, nuovo))]
        if not nuovo:
            azioni.append(("Elimina", lambda b: self._elimina_oggetto(oid)))
            azioni.append(("Duplica", lambda b: self._duplica_oggetto(oid)))
        azioni.append(("Indietro", self.indietro))
        righe.append(self._azioni(azioni))
        return self._listbox(righe)

    def _props_da_form(self, c) -> dict:
        # parti dai props originali per conservare quelli non gestiti dal form
        # (es. dialogo, saluto), poi sovrascrivi gli interruttori noti
        props = dict(c.get("_props_orig", {}))
        for chiave in ("prendibile", "scenario", "contenitore", "aperto",
                       "indossabile", "png"):
            if c[chiave].state:
                props[chiave] = True
            else:
                props.pop(chiave, None)
        desc = c["desc"].edit_text.strip()
        if desc:
            props["desc"] = desc
        else:
            props.pop("desc", None)
        frase = c["in_stanza"].edit_text.strip()
        if frase:
            props["in_stanza"] = frase
        else:
            props.pop("in_stanza", None)
        if c["luce_on"].state:
            flag = (c["luce_flag"].get() or "").strip()
            props["luce"] = flag if flag else True
        else:
            props.pop("luce", None)
        # combattimento
        if c["combattente"].state:
            props["combattente"] = True
            for chiave in ("hp", "attacco", "difesa"):
                try:
                    props[chiave] = int(c[chiave].edit_text)
                except ValueError:
                    props[chiave] = 0
            if not c["fuga"].state:           # default = fuggibile; salva solo il divieto
                props["fuga"] = False
            else:
                props.pop("fuga", None)
            intro = c["intro_scontro"].edit_text.strip()
            if intro:
                props["intro_scontro"] = intro
            else:
                props.pop("intro_scontro", None)
        else:
            for chiave in ("combattente", "hp", "attacco", "difesa", "fuga",
                           "intro_scontro"):
                props.pop(chiave, None)
        return props

    def _salva_oggetto(self, c, nuovo):
        oid = c["id"].edit_text.strip()
        if not oid:
            return self.messaggio("L'id non puo' essere vuoto.", "errore")
        if nuovo and oid in self.mondo.oggetti:
            return self.messaggio(f"Esiste gia' un oggetto «{oid}».", "errore")
        self.mondo.oggetti[oid] = Oggetto(
            id=oid, nome=c["nome"].edit_text.strip(),
            nomi=csv_a_lista(c["nomi"].edit_text),
            aggettivi=csv_a_lista(c["aggettivi"].edit_text),
            posizione=c["posizione"].get() or "", props=self._props_da_form(c))
        self._segna_modifica()
        self.indietro()

    def _applica_oggetto(self, c, oid):
        """Scrive i campi correnti sull'oggetto esistente senza uscire dal form
        (usato prima di aprire l'editor del dialogo)."""
        o = self.mondo.oggetti[oid]
        o.nome = c["nome"].edit_text.strip()
        o.nomi = csv_a_lista(c["nomi"].edit_text)
        o.aggettivi = csv_a_lista(c["aggettivi"].edit_text)
        o.posizione = c["posizione"].get() or ""
        o.props = self._props_da_form(c)
        self._segna_modifica()

    def _apri_dialogo_da_oggetto(self, c, oid):
        self._applica_oggetto(c, oid)
        self._dlg_oid = None          # rilegge il dialogo dall'oggetto aggiornato
        self.push(lambda: self.vista_dialogo(oid), f"Dialogo: {oid}")

    def _apri_sconfitto_da_oggetto(self, c, oid):
        self._applica_oggetto(c, oid)
        self.push(lambda: self.vista_sconfitto(oid), f"Esito: {oid}")

    def vista_sconfitto(self, oid):
        o = self.mondo.oggetti[oid]
        o.props.setdefault("sconfitto", [])
        self._reg = o.props          # riuso self._reg per la lista di effetti
        righe = [urwid.Text(("sezione", f"  Esito alla sconfitta di «{oid}»")),
                 urwid.Divider(),
                 urwid.Text("Effetti eseguiti quando il giocatore lo sconfigge"),
                 urwid.Text("(bottino con «sposta oggetto», flag, messaggi…)."),
                 urwid.Divider()]
        righe += self._righe_voci(o.props["sconfitto"], "effetto", "sconfitto")
        righe.append(self._bottone(
            "+ aggiungi effetto", lambda x: self._aggiungi_effetto("sconfitto")))
        righe += [urwid.Divider(),
                  self._azioni([("Fatto", lambda b: self._chiudi_sconfitto(oid))])]
        return self._listbox(righe)

    def _chiudi_sconfitto(self, oid):
        o = self.mondo.oggetti[oid]
        if not o.props.get("sconfitto"):
            o.props.pop("sconfitto", None)
        self._segna_modifica()
        self.indietro()

    def _elimina_oggetto(self, oid):
        self.mondo.oggetti.pop(oid, None)
        self._segna_modifica()
        self.indietro()

    # ---------- editor dei dialoghi (riusa condizioni/effetti delle regole) ----------

    def vista_dialogo(self, oid):
        if getattr(self, "_dlg_oid", None) != oid:
            o = self.mondo.oggetti[oid]
            self._dlg_oid = oid
            self._dlg = {"saluto": o.props.get("saluto", ""),
                         "battute": copy.deepcopy(o.props.get("dialogo", []))}
        d = self._dlg
        w_sal, e_sal = self._edit("saluto (frase d'apertura):\n",
                                  d["saluto"], multiline=True)

        righe = [urwid.Text(("sezione", f"  Dialogo di «{oid}»")), urwid.Divider(),
                 w_sal, urwid.Divider(),
                 urwid.Text(("sezione", "  Battute (voci del menu)"))]
        for i, b in enumerate(d["battute"]):
            et = b.get("etichetta") or "(senza etichetta)"
            marca = " · una volta" if b.get("una_volta") else ""
            righe.append(urwid.Columns([
                ("weight", 5, self._bottone(
                    f"{et}{marca}", lambda btn, idx=i: self._apri_battuta(idx))),
                ("weight", 1, self._bottone(
                    "rimuovi", lambda btn, idx=i: self._rimuovi_battuta(idx))),
            ], dividechars=1))

        self._harvest = lambda: d.__setitem__("saluto", e_sal.edit_text)

        righe += [self._bottone("+ aggiungi battuta",
                                lambda b: self._apri_battuta(None)),
                  urwid.Divider(),
                  self._azioni([("Salva dialogo",
                                 lambda b: self._salva_dialogo(oid)),
                                ("Indietro", self.indietro)])]
        return self._listbox(righe)

    def _apri_battuta(self, idx):
        if self._harvest:
            self._harvest()                 # conserva il saluto in corso
        if idx is None:
            self._battuta_idx = None
            self._reg = {"etichetta": "", "testo": "", "una_volta": False,
                         "se": [], "allora": []}
        else:
            self._battuta_idx = idx
            b = self._dlg["battute"][idx]
            b.setdefault("se", [])
            b.setdefault("allora", [])
            b.setdefault("una_volta", False)
            self._reg = b                   # riuso self._reg per condizioni/effetti
        self.push(self.form_battuta, "Battuta")

    def _rimuovi_battuta(self, idx):
        if self._harvest:
            self._harvest()
        del self._dlg["battute"][idx]
        self.ricarica()

    def _salva_dialogo(self, oid):
        if self._harvest:
            self._harvest()
        o = self.mondo.oggetti[oid]
        saluto = self._dlg["saluto"].strip()
        if saluto:
            o.props["saluto"] = saluto
        else:
            o.props.pop("saluto", None)
        if self._dlg["battute"]:
            o.props["dialogo"] = self._dlg["battute"]
            o.props["png"] = True           # con un dialogo è un personaggio
        else:
            o.props.pop("dialogo", None)
        self._dlg_oid = None
        self._segna_modifica()
        self.indietro()

    def form_battuta(self):
        b = self._reg
        w_et, e_et = self._edit("etichetta (voce del menu): ",
                                b.get("etichetta", ""))
        w_te, e_te = self._edit("testo (cosa dice il png):\n",
                                b.get("testo", ""), multiline=True)
        w_uv, c_uv = self._check("disponibile una sola volta",
                                 b.get("una_volta"))

        def harvest():
            b["etichetta"] = e_et.edit_text.strip()
            b["testo"] = e_te.edit_text
            b["una_volta"] = c_uv.state
        self._harvest = harvest

        righe = [urwid.Text(("sezione", "  Battuta")), urwid.Divider(),
                 w_et, w_te, w_uv, urwid.Divider(),
                 urwid.Text(("sezione", "  SE (condizioni per mostrarla)"))]
        righe += self._righe_voci(b["se"], "condizione")
        righe.append(self._bottone("+ aggiungi condizione",
                                   lambda x: self._aggiungi_condizione()))
        righe += [urwid.Divider(),
                  urwid.Text(("sezione", "  ALLORA (effetti quando scelta)"))]
        righe += self._righe_voci(b["allora"], "effetto", "allora")
        righe.append(self._bottone("+ aggiungi effetto",
                                   lambda x: self._aggiungi_effetto("allora")))
        righe += [urwid.Divider(),
                  self._azioni([("Salva battuta",
                                 lambda x: self._salva_battuta()),
                                ("Indietro", self.indietro)])]
        return self._listbox(righe)

    def _salva_battuta(self):
        if self._harvest:
            self._harvest()
        b = self._reg
        if not b.get("etichetta"):
            return self.messaggio("Serve un'etichetta per la battuta.", "errore")
        if not b.get("testo"):
            return self.messaggio("Serve un testo per la battuta.", "errore")
        if self._battuta_idx is None:
            self._dlg["battute"].append(b)
        self.indietro()

    # ---------- form: VERBO ----------

    def form_verbo(self, vid):
        nuovo = vid is None
        # verbo predefinito (del motore): ispezionabile ma non modificabile
        if not nuovo and vid not in self.mondo.verbi and vid in VERBI_BUILTIN:
            return self._form_verbo_predefinito(vid)
        v = self.mondo.verbi.get(vid) if not nuovo else None
        c = {}
        w_id, c["id"] = self._edit("id: ", vid or "")
        w_sin, c["sinonimi"] = self._edit("sinonimi (csv): ",
                                          lista_a_csv(v.sinonimi) if v else "")
        c["tipo"] = CampoScelta(
            self, "tipo", v.tipo if v else "transitivo",
            lambda: [("intransitivo", "intransitivo"),
                     ("transitivo", "transitivo"),
                     ("ditransitivo", "ditransitivo")])
        w_prep, c["preposizioni"] = self._edit(
            "preposizioni (csv): ", lista_a_csv(v.preposizioni) if v else "")

        righe = [urwid.Text(("sezione", "  Verbo")), urwid.Divider()]
        righe.append(w_id if nuovo else urwid.Text(("etichetta", f"id: {vid}")))
        if not nuovo and vid in VERBI_BUILTIN:
            righe.append(urwid.Text(("etichetta",
                "  (estende un verbo predefinito del motore: qui aggiungi sinonimi)")))
        righe += [w_sin, c["tipo"], w_prep, urwid.Divider()]
        azioni = [("Salva", lambda b: self._salva_verbo(c, nuovo))]
        if not nuovo:
            azioni.append(("Elimina", lambda b: self._elimina_verbo(vid)))
            azioni.append(("Duplica", lambda b: self._duplica_verbo(vid)))
        azioni.append(("Indietro", self.indietro))
        righe.append(self._azioni(azioni))
        return self._listbox(righe)

    def _form_verbo_predefinito(self, vid):
        sinonimi = VERBI_BUILTIN.get(vid, [])
        righe = [
            urwid.Text(("sezione", f"  Verbo predefinito: {vid}")),
            urwid.Divider(),
            urwid.Text(("etichetta", f"id: {vid}")),
            urwid.Text("sinonimi: " +
                       (", ".join(sinonimi) if sinonimi else "(nessuno)")),
            urwid.Divider(),
            urwid.Text("Questo verbo è fornito dal motore: è sempre disponibile"),
            urwid.Text("in gioco e non si modifica da qui. Per cambiarne il"),
            urwid.Text("comportamento su un oggetto, scrivi una regola che lo"),
            urwid.Text("inneschi (le regole hanno la precedenza)."),
            urwid.Divider(),
            self._azioni([("Indietro", self.indietro)]),
        ]
        return self._listbox(righe)

    def _salva_verbo(self, c, nuovo):
        vid = c["id"].edit_text.strip()
        if not vid:
            return self.messaggio("L'id non puo' essere vuoto.", "errore")
        if nuovo and vid in self.mondo.verbi:
            return self.messaggio(f"Esiste gia' un verbo «{vid}».", "errore")
        self.mondo.verbi[vid] = Verbo(
            id=vid, sinonimi=csv_a_lista(c["sinonimi"].edit_text),
            tipo=c["tipo"].get(),
            preposizioni=csv_a_lista(c["preposizioni"].edit_text))
        self._segna_modifica()
        self.indietro()

    def _elimina_verbo(self, vid):
        self.mondo.verbi.pop(vid, None)
        self._segna_modifica()
        self.indietro()

    # ---------- form: FLAG ----------

    def vista_flag(self):
        if not hasattr(self, "_lav_flag") or self._lav_flag is None:
            self._lav_flag = [[k, str(v)] for k, v in self.mondo.flags.items()]
        righe = [urwid.Text(("sezione", "  Flag iniziali")),
                 urwid.Text(("etichetta",
                             "  valori: true/false oppure numeri o testo")),
                 urwid.Divider()]
        campi = []
        for i, (nome, val) in enumerate(self._lav_flag):
            w_n, e_n = self._edit("nome: ", nome)
            w_v, e_v = self._edit("valore: ", val)
            campi.append((e_n, e_v))
            righe.append(urwid.Columns([
                ("weight", 3, w_n), ("weight", 3, w_v),
                ("weight", 2, self._bottone(
                    "rimuovi", lambda b, idx=i: self._flag_rimuovi(idx))),
            ], dividechars=1))

        def harvest():
            self._lav_flag = [[e_n.edit_text.strip(), e_v.edit_text]
                              for e_n, e_v in campi]
        self._harvest = harvest

        righe += [self._bottone("+ aggiungi flag",
                                lambda b: self._flag_aggiungi()),
                  urwid.Divider(),
                  self._azioni([("Salva", lambda b: self._salva_flag()),
                                ("Indietro", self.indietro)])]
        return self._listbox(righe)

    def _flag_aggiungi(self):
        if self._harvest:
            self._harvest()
        self._lav_flag.append(["", "false"])
        self.ricarica()

    def _flag_rimuovi(self, idx):
        if self._harvest:
            self._harvest()
        if 0 <= idx < len(self._lav_flag):
            del self._lav_flag[idx]
        self.ricarica()

    def _salva_flag(self):
        if self._harvest:
            self._harvest()
        nuovi = {}
        for nome, val in self._lav_flag:
            if nome:
                nuovi[nome] = parse_valore(val)
        self.mondo.flags = nuovi
        self._lav_flag = None
        self._segna_modifica()
        self.indietro()

    # ---------- form: METADATI ----------

    def vista_meta(self):
        m = self.mondo.meta
        c = {}
        w_tit, c["titolo"] = self._edit("titolo: ", m.get("titolo", ""))
        w_aut, c["autore"] = self._edit("autore: ", m.get("autore", ""))
        w_ver, c["versione"] = self._edit("versione del gioco: ",
                                          m.get("versione", "1.0.0"))
        w_intro, c["intro"] = self._edit("intro:\n", m.get("intro", ""),
                                         multiline=True)
        c["stanza_iniziale"] = CampoScelta(
            self, "stanza iniziale", m.get("stanza_iniziale"),
            lambda: self.opz_stanze())
        righe = [urwid.Text(("sezione", "  Metadati")), urwid.Divider(),
                 w_tit, w_aut, w_ver, w_intro, c["stanza_iniziale"],
                 urwid.Divider(),
                 self._azioni([("Salva", lambda b: self._salva_meta(c)),
                               ("Indietro", self.indietro)])]
        return self._listbox(righe)

    def _salva_meta(self, c):
        self.mondo.meta["titolo"] = c["titolo"].edit_text.strip()
        self.mondo.meta["autore"] = c["autore"].edit_text.strip()
        versione = c["versione"].edit_text.strip()
        if versione:
            self.mondo.meta["versione"] = versione
        else:
            self.mondo.meta.pop("versione", None)
        self.mondo.meta["intro"] = c["intro"].edit_text.strip()
        if c["stanza_iniziale"].get():
            self.mondo.meta["stanza_iniziale"] = c["stanza_iniziale"].get()
        self._segna_modifica()
        self.indietro()

    # ---------- form: REGOLA ----------

    def apri_regola(self, idx):
        if idx is None:
            self._reg_idx = None
            self._reg = {"id": "", "quando": {}, "se": [],
                         "allora": [], "altrimenti": []}
        else:
            r = self.mondo.regole[idx]
            self._reg_idx = idx
            self._reg = {"id": r.id, "quando": copy.deepcopy(r.quando),
                         "se": copy.deepcopy(r.se),
                         "allora": copy.deepcopy(r.allora),
                         "altrimenti": copy.deepcopy(r.altrimenti)}
        self.push(self.form_regola, "Regola")

    def form_regola(self):
        reg = self._reg
        q = reg["quando"]
        w_id, e_id = self._edit("id regola: ", reg["id"])
        self._reg_e_id = e_id

        # conserva l'id (e l'eventuale nome del timer) quando si naviga
        def _harvest_regola():
            reg["id"] = e_id.edit_text.strip()
            if getattr(self, "_reg_timer_edit", None) is not None:
                q["timer"] = self._reg_timer_edit.edit_text.strip()
        self._harvest = _harvest_regola

        innesco = q.get("evento") or "comando"
        sel_innesco = CampoScelta(
            self, "innesco", innesco,
            lambda: [("comando del giocatore", "comando"),
                     ("a ogni turno", "turno"),
                     ("ingresso in una stanza", "entra"),
                     ("scadenza di un timer", "timer")],
            on_change=lambda v: self._cambia_innesco(q, v))

        righe = [urwid.Text(("sezione", "  Regola")), urwid.Divider(), w_id,
                 urwid.Divider(), urwid.Text(("sezione", "  QUANDO (innesco)")),
                 sel_innesco]
        self._reg_timer_edit = None
        if innesco == "comando":
            sel_v = CampoScelta(self, "verbo", q.get("verbo"), self.opz_verbi,
                                on_change=lambda v: q.__setitem__("verbo", v))
            sel_o = CampoScelta(self, "oggetto", q.get("oggetto"),
                                lambda: self.opz_oggetti(nessuno=True),
                                segnaposto="(nessuno)",
                                on_change=lambda v: self._reg_set(q, "oggetto", v))
            sel_p = CampoScelta(self, "preposizione", q.get("prep"),
                                lambda: self.opz_prep(nessuno=True),
                                segnaposto="(nessuna)",
                                on_change=lambda v: self._reg_set(q, "prep", v))
            sel_oi = CampoScelta(self, "oggetto indiretto",
                                 q.get("oggetto_indiretto"),
                                 lambda: self.opz_oggetti(nessuno=True),
                                 segnaposto="(nessuno)",
                                 on_change=lambda v: self._reg_set(
                                     q, "oggetto_indiretto", v))
            righe += [sel_v, sel_o, sel_p, sel_oi]
        elif innesco == "turno":
            righe.append(urwid.Text("  La regola è valutata dopo ogni turno."))
        elif innesco == "entra":
            sel_s = CampoScelta(self, "stanza", q.get("stanza"),
                                lambda: self.opz_stanze(),
                                on_change=lambda v: self._reg_set(q, "stanza", v))
            righe += [urwid.Text("  Scatta quando il giocatore entra nella stanza:"),
                      sel_s]
        elif innesco == "timer":
            w_t, e_t = self._edit("nome del timer: ", q.get("timer", ""))
            self._reg_timer_edit = e_t
            righe += [urwid.Text("  Scatta quando scade un timer con questo nome:"),
                      w_t]
        righe += [urwid.Divider(),
                  urwid.Text(("sezione", "  SE (condizioni, tutte vere)"))]
        righe += self._righe_voci(reg["se"], "condizione")
        righe.append(self._bottone("+ aggiungi condizione",
                                   lambda b: self._aggiungi_condizione()))

        righe += [urwid.Divider(),
                  urwid.Text(("sezione", "  ALLORA (se vere)"))]
        righe += self._righe_voci(reg["allora"], "effetto", "allora")
        righe.append(self._bottone(
            "+ aggiungi effetto",
            lambda b: self._aggiungi_effetto("allora")))

        righe += [urwid.Divider(),
                  urwid.Text(("sezione", "  ALTRIMENTI (se false)"))]
        righe += self._righe_voci(reg["altrimenti"], "effetto", "altrimenti")
        righe.append(self._bottone(
            "+ aggiungi effetto",
            lambda b: self._aggiungi_effetto("altrimenti")))

        azioni = [("Salva regola", lambda b: self._salva_regola())]
        if self._reg_idx is not None:
            azioni.append(("Elimina", lambda b: self._elimina_regola()))
            azioni.append(("Duplica", lambda b: self._duplica_regola()))
        azioni.append(("Indietro", self.indietro))
        righe += [urwid.Divider(), self._azioni(azioni)]
        return self._listbox(righe)

    def _reg_set(self, d, chiave, valore):
        if valore is None:
            d.pop(chiave, None)
        else:
            d[chiave] = valore

    def _cambia_innesco(self, q, v):
        # conserva l'id digitato, poi azzera il «quando» e imposta la forma scelta
        if getattr(self, "_reg_e_id", None) is not None:
            self._reg["id"] = self._reg_e_id.edit_text.strip()
        q.clear()
        if v != "comando":
            q["evento"] = v
        self._reg_timer_edit = None
        self.ricarica()

    def _righe_voci(self, voci, genere, lista=None):
        """Righe (riassunto + rimuovi) per condizioni/effetti."""
        out = []
        for i, v in enumerate(voci):
            testo = (riassunto_condizione(v) if genere == "condizione"
                     else riassunto_effetto(v))
            if genere == "condizione":
                apri = lambda b, idx=i: self._modifica_condizione(idx)
                rim = lambda b, idx=i: self._rimuovi_condizione(idx)
            else:
                apri = lambda b, idx=i, l=lista: self._modifica_effetto(l, idx)
                rim = lambda b, idx=i, l=lista: self._rimuovi_effetto(l, idx)
            out.append(urwid.Columns([
                ("weight", 5, self._bottone(testo, apri)),
                ("weight", 1, self._bottone("rimuovi", rim)),
            ], dividechars=1))
        return out

    # --- regola: salvataggio/eliminazione ---

    def _salva_regola(self):
        reg = self._reg
        reg["id"] = self._reg_e_id.edit_text.strip() or f"regola_{len(self.mondo.regole)}"
        q = reg["quando"]
        if getattr(self, "_reg_timer_edit", None) is not None:
            q["timer"] = self._reg_timer_edit.edit_text.strip()
        ev = q.get("evento")
        if ev == "entra" and not q.get("stanza"):
            return self.messaggio("Scegli la stanza d'ingresso.", "errore")
        if ev == "timer" and not q.get("timer"):
            return self.messaggio("Indica il nome del timer.", "errore")
        if not ev and not q.get("verbo"):
            return self.messaggio(
                "La regola deve avere un verbo o un innesco-evento.", "errore")
        nuova = Regola(id=reg["id"], quando=q, se=reg["se"],
                       allora=reg["allora"], altrimenti=reg["altrimenti"])
        if self._reg_idx is None:
            self.mondo.regole.append(nuova)
        else:
            self.mondo.regole[self._reg_idx] = nuova
        self._segna_modifica()
        self.indietro()

    def _elimina_regola(self):
        if self._reg_idx is not None:
            del self.mondo.regole[self._reg_idx]
            self._segna_modifica()
        self.indietro()

    # --- regola: condizioni ---

    def _aggiungi_condizione(self):
        if self._harvest:
            self._harvest()
        self.scegli("Tipo di condizione", TIPI_CONDIZIONE,
                    lambda t: self.push(lambda: self.form_condizione(t, None),
                                        "Condizione"))

    def _modifica_condizione(self, idx):
        if self._harvest:
            self._harvest()
        t = tipo_condizione(self._reg["se"][idx])
        self.push(lambda: self.form_condizione(t, idx), "Condizione")

    def _rimuovi_condizione(self, idx):
        if self._harvest:
            self._harvest()
        del self._reg["se"][idx]
        self.ricarica()

    def form_condizione(self, tipo, idx):
        corrente = self._reg["se"][idx] if idx is not None else {}
        c = {}
        righe = [urwid.Text(("sezione", f"  Condizione: {tipo}")), urwid.Divider()]
        if tipo == "flag":
            c["flag"] = self._campo_flag("flag", corrente.get("flag", ""))
            op = ("uguale" if "uguale" in corrente
                  else "maggiore" if "maggiore" in corrente else "vero")
            c["op"] = CampoScelta(self, "operatore", op,
                                  lambda: [("è uguale a", "uguale"),
                                           ("è maggiore di", "maggiore"),
                                           ("è vero", "vero")])
            val = (corrente.get("uguale") if "uguale" in corrente
                   else corrente.get("maggiore", ""))
            w_v, c["valore"] = self._edit("valore: ", str(val) if val != "" else "")
            righe += [c["flag"], c["op"], w_v]
        elif tipo == "oggetto_in":
            o = corrente.get("oggetto_in", [None, None])
            c["oggetto"] = CampoScelta(self, "oggetto", o[0], self.opz_oggetti)
            c["dove"] = CampoScelta(self, "si trova in", o[1], self.opz_luoghi)
            righe += [c["oggetto"], c["dove"]]
        elif tipo == "stanza_corrente":
            c["stanza"] = CampoScelta(self, "stanza",
                                      corrente.get("stanza_corrente"),
                                      lambda: self.opz_stanze())
            righe += [c["stanza"]]
        elif tipo == "stato_min":
            w_n, c["stato_min"] = self._edit(
                "stato minimo (numero): ", str(corrente.get("stato_min", 1)))
            righe += [urwid.Text("Vera se la conversazione col png ha raggiunto"),
                      urwid.Text("almeno questo livello."), w_n]
        elif tipo == "mosse_min":
            w_n, c["mosse_min"] = self._edit(
                "turno minimo (numero): ", str(corrente.get("mosse_min", 1)))
            righe += [urwid.Text("Vera quando l'orologio dei turni ha raggiunto"),
                      urwid.Text("almeno questo valore (1 = dopo il primo turno)."), w_n]
        righe += [urwid.Divider(),
                  self._azioni([
                      ("Salva", lambda b: self._salva_condizione(tipo, idx, c)),
                      ("Indietro", self.indietro)])]
        return self._listbox(righe)

    def _salva_condizione(self, tipo, idx, c):
        if tipo == "flag":
            nome = c["flag"].get()
            if not nome:
                return self.messaggio("Scegli il flag.", "errore")
            op = c["op"].get()
            d = {"flag": nome}
            if op == "uguale":
                d["uguale"] = parse_valore(c["valore"].edit_text)
            elif op == "maggiore":
                try:
                    d["maggiore"] = int(c["valore"].edit_text)
                except ValueError:
                    return self.messaggio("«maggiore» richiede un numero.", "errore")
            cond = d
        elif tipo == "oggetto_in":
            if not c["oggetto"].get() or not c["dove"].get():
                return self.messaggio("Scegli oggetto e luogo.", "errore")
            cond = {"oggetto_in": [c["oggetto"].get(), c["dove"].get()]}
        elif tipo == "stato_min":
            try:
                cond = {"stato_min": int(c["stato_min"].edit_text)}
            except ValueError:
                return self.messaggio("Lo stato richiede un numero.", "errore")
        elif tipo == "mosse_min":
            try:
                cond = {"mosse_min": int(c["mosse_min"].edit_text)}
            except ValueError:
                return self.messaggio("Il turno richiede un numero.", "errore")
        else:
            if not c["stanza"].get():
                return self.messaggio("Scegli la stanza.", "errore")
            cond = {"stanza_corrente": c["stanza"].get()}
        if idx is None:
            self._reg["se"].append(cond)
        else:
            self._reg["se"][idx] = cond
        self.indietro()

    # --- regola: effetti ---

    def _aggiungi_effetto(self, lista):
        if self._harvest:
            self._harvest()
        self.scegli("Tipo di effetto", TIPI_EFFETTO,
                    lambda t: self.push(
                        lambda: self.form_effetto(lista, t, None), "Effetto"))

    def _modifica_effetto(self, lista, idx):
        if self._harvest:
            self._harvest()
        t = tipo_effetto(self._reg[lista][idx])
        self.push(lambda: self.form_effetto(lista, t, idx), "Effetto")

    def _rimuovi_effetto(self, lista, idx):
        if self._harvest:
            self._harvest()
        del self._reg[lista][idx]
        self.ricarica()

    def form_effetto(self, lista, tipo, idx):
        corrente = self._reg[lista][idx] if idx is not None else {}
        c = {}
        righe = [urwid.Text(("sezione", f"  Effetto: {tipo}")), urwid.Divider()]
        if tipo == "set_flag":
            c["flag"] = self._campo_flag("flag", corrente.get("set_flag", ""))
            w_v, c["valore"] = self._edit("valore: ",
                                          str(corrente.get("valore", "true")))
            righe += [c["flag"], w_v]
        elif tipo == "incrementa":
            c["flag"] = self._campo_flag("flag", corrente.get("incrementa", ""))
            w_v, c["di"] = self._edit("di: ", str(corrente.get("di", 1)))
            righe += [c["flag"], w_v]
        elif tipo == "punti":
            w_p, c["punti"] = self._edit("punti: ", str(corrente.get("punti", 0)))
            righe += [w_p]
        elif tipo == "sposta_oggetto":
            c["oggetto"] = CampoScelta(self, "oggetto",
                                       corrente.get("sposta_oggetto"),
                                       self.opz_oggetti)
            c["a"] = CampoScelta(self, "verso", corrente.get("a"),
                                 self.opz_luoghi)
            righe += [c["oggetto"], c["a"]]
        elif tipo == "stampa":
            w_t, c["testo"] = self._edit("testo:\n", corrente.get("stampa", ""),
                                         multiline=True)
            righe += [w_t]
        elif tipo == "teleporta":
            c["stanza"] = CampoScelta(self, "stanza",
                                      corrente.get("teleporta"),
                                      lambda: self.opz_stanze())
            righe += [c["stanza"]]
        elif tipo in ("vittoria", "sconfitta"):
            w_t, c["testo"] = self._edit("messaggio:\n", corrente.get(tipo, ""),
                                         multiline=True)
            righe += [w_t]
        elif tipo == "stato":
            w_n, c["stato"] = self._edit(
                "stato (numero): ", str(corrente.get("stato", 1)))
            righe += [urwid.Text("Imposta il livello di conversazione del png."),
                      w_n]
        elif tipo == "avanza_stato":
            w_n, c["avanza_stato"] = self._edit(
                "avanza di (numero): ", str(corrente.get("avanza_stato", 1)))
            righe += [w_n]
        elif tipo == "inizia_scontro":
            c["inizia_scontro"] = CampoScelta(
                self, "png combattente", corrente.get("inizia_scontro"),
                self.opz_oggetti)
            righe += [c["inizia_scontro"]]
        elif tipo == "avvia_timer":
            w_n, c["avvia_timer"] = self._edit(
                "nome del timer: ", corrente.get("avvia_timer", ""))
            w_t, c["turni"] = self._edit(
                "turni (numero): ", str(corrente.get("turni", 1)))
            righe += [urwid.Text("Scade dopo il numero indicato di turni e fa"),
                      urwid.Text("scattare le regole-evento «timer» con questo nome."),
                      w_n, w_t]
        elif tipo == "ferma_timer":
            w_n, c["ferma_timer"] = self._edit(
                "nome del timer: ", corrente.get("ferma_timer", ""))
            righe += [urwid.Text("Annulla un timer in corso con questo nome."), w_n]
        righe += [urwid.Divider(),
                  self._azioni([
                      ("Salva",
                       lambda b: self._salva_effetto(lista, tipo, idx, c)),
                      ("Indietro", self.indietro)])]
        return self._listbox(righe)

    def _salva_effetto(self, lista, tipo, idx, c):
        if tipo == "set_flag":
            nome = c["flag"].get()
            if not nome:
                return self.messaggio("Scegli il flag.", "errore")
            eff = {"set_flag": nome, "valore": parse_valore(c["valore"].edit_text)}
        elif tipo == "incrementa":
            nome = c["flag"].get()
            if not nome:
                return self.messaggio("Scegli il flag.", "errore")
            try:
                di = int(c["di"].edit_text)
            except ValueError:
                return self.messaggio("«di» richiede un numero.", "errore")
            eff = {"incrementa": nome, "di": di}
        elif tipo == "punti":
            try:
                eff = {"punti": int(c["punti"].edit_text)}
            except ValueError:
                return self.messaggio("«punti» richiede un numero.", "errore")
        elif tipo == "sposta_oggetto":
            if not c["oggetto"].get() or not c["a"].get():
                return self.messaggio("Scegli oggetto e destinazione.", "errore")
            eff = {"sposta_oggetto": c["oggetto"].get(), "a": c["a"].get()}
        elif tipo == "stampa":
            eff = {"stampa": c["testo"].edit_text.strip()}
        elif tipo == "teleporta":
            if not c["stanza"].get():
                return self.messaggio("Scegli la stanza.", "errore")
            eff = {"teleporta": c["stanza"].get()}
        elif tipo == "stato":
            try:
                eff = {"stato": int(c["stato"].edit_text)}
            except ValueError:
                return self.messaggio("Lo stato richiede un numero.", "errore")
        elif tipo == "avanza_stato":
            try:
                eff = {"avanza_stato": int(c["avanza_stato"].edit_text)}
            except ValueError:
                return self.messaggio("«avanza» richiede un numero.", "errore")
        elif tipo == "inizia_scontro":
            if not c["inizia_scontro"].get():
                return self.messaggio("Scegli il png.", "errore")
            eff = {"inizia_scontro": c["inizia_scontro"].get()}
        elif tipo == "avvia_timer":
            nome = c["avvia_timer"].edit_text.strip()
            if not nome:
                return self.messaggio("Dai un nome al timer.", "errore")
            try:
                turni = int(c["turni"].edit_text)
            except ValueError:
                return self.messaggio("«turni» richiede un numero.", "errore")
            eff = {"avvia_timer": nome, "turni": turni}
        elif tipo == "ferma_timer":
            nome = c["ferma_timer"].edit_text.strip()
            if not nome:
                return self.messaggio("Indica il timer da fermare.", "errore")
            eff = {"ferma_timer": nome}
        else:
            eff = {tipo: c["testo"].edit_text.strip()}
        if idx is None:
            self._reg[lista].append(eff)
        else:
            self._reg[lista][idx] = eff
        self.indietro()

    # ---------- ANTEPRIMA ----------

    def vista_anteprima(self):
        mondo = clona_mondo(self.mondo)
        motore = Motore(mondo)
        walker = urwid.SimpleListWalker([])

        def stampa(testo, attr=None):
            for riga in testo.split("\n"):
                walker.append(urwid.Text((attr, riga) if attr else riga))
            walker.set_focus(len(walker) - 1)

        def invio(testo):
            testo = testo.strip()
            if not testo:
                return
            stampa("> " + testo, "cmd")
            stampa(motore.esegui(testo))
            if mondo.finita:
                stampa("(partita conclusa — Esc per tornare all'editor)", "ok")

        stampa(motore.avvia())
        riga = _RigaComando(invio)
        corpo = urwid.Frame(urwid.ListBox(walker),
                            footer=urwid.AttrMap(riga, "campo", "campo_f"))
        corpo.focus_position = "footer"
        return corpo

    # ---------- file e uscita ----------

    def azione_salva(self):
        try:
            salva_mondo(self.mondo, self.percorso)
            self.modificato = False
            n_err = sum(1 for x in valida(self.mondo) if x.gravita == "errore")
            if n_err:
                self.messaggio(f"Salvato in {self.percorso} — attenzione: "
                               f"{n_err} riferimenti rotti (vedi «Verifica»)",
                               "errore")
            else:
                self.messaggio(f"Salvato in {self.percorso}", "ok")
        except Exception as e:                       # noqa: BLE001
            self.messaggio(f"Errore nel salvataggio: {e}", "errore")

    def azione_esci(self):
        raise urwid.ExitMainLoop()


class _RigaComando(urwid.Edit):
    """Riga di comando dell'anteprima: invia il testo su Invio."""

    def __init__(self, on_invio):
        super().__init__("> ")
        self._on_invio = on_invio

    def keypress(self, size, key):
        if key == "enter":
            testo = self.edit_text
            self.set_edit_text("")
            self._on_invio(testo)
            return None
        return super().keypress(size, key)


def _mondo_vuoto() -> Mondo:
    m = Mondo(meta={"titolo": "Nuova avventura", "stanza_iniziale": "inizio"})
    m.stanze["inizio"] = Stanza(id="inizio", nome="Punto di partenza",
                                desc="Una stanza vuota, tutta da scrivere.")
    for vid, sin, tipo in [
        ("vai", ["va"], "intransitivo"),
        ("guarda", ["osserva", "l"], "intransitivo"),
        ("esamina", ["x"], "transitivo"),
        ("prendi", ["raccogli"], "transitivo"),
        ("lascia", ["posa"], "transitivo"),
        ("inventario", ["i"], "intransitivo"),
    ]:
        m.verbi[vid] = Verbo(id=vid, sinonimi=sin, tipo=tipo)
    return m


def main():
    percorso = sys.argv[1] if len(sys.argv) > 1 else "avventure/caverna.json"
    if Path(percorso).exists():
        mondo = carica_mondo(percorso)
    else:
        mondo = _mondo_vuoto()
    EditorApp(mondo, percorso).run()
    print(f"Editor chiuso. (ricorda di salvare: {percorso})")


if __name__ == "__main__":
    main()
