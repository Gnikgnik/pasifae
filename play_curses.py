# SPDX-License-Identifier: GPL-3.0-or-later
"""Player a tutto schermo basato su curses (ncurses).

Guscio attorno a advcore.Motore: tutta la logica di gioco vive nel motore,
qui si gestisce solo la presentazione a terminale. Caratteristiche:
  - barra del titolo e barra di stato
  - area di gioco scrollabile con a capo automatico (PgUp/PgDn, Home/End)
  - riga di comando con storico (frecce su/giu')
  - supporto al ridimensionamento del terminale e ai caratteri accentati

Uso:
    python3 play_curses.py avventure/caverna.json

La logica pura (Trascrizione, StoricoComandi) e' separata dalle chiamate
curses, cosi' e' testabile senza un terminale (vedi test_player.py).
"""

from __future__ import annotations

import curses
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from advcore import carica_mondo, Mondo, Motore, salva_partita, carica_partita
from advcore import __version__ as VERSIONE


def _percorso_salvataggio(nome: str):
    return Path("salvataggi") / f"{nome}.sav"


def _meta_partita(parti, mondo, motore) -> str:
    cmd = parti[0].lower()
    nome = parti[1].strip() if len(parti) > 1 else "partita"
    f = _percorso_salvataggio(nome)
    if cmd in ("salva", "save"):
        try:
            salva_partita(mondo, f)
            return f"Partita salvata in «{f}»."
        except Exception as e:                       # noqa: BLE001
            return f"Errore nel salvataggio: {e}"
    if not f.exists():
        return f"Nessun salvataggio «{f}»."
    try:
        carica_partita(mondo, f)
        return "Partita caricata.\n\n" + motore.esegui("guarda")
    except Exception as e:                           # noqa: BLE001
        return f"Errore nel caricamento: {e}"


# ===================== logica pura (testabile senza curses) =====================

class Trascrizione:
    """Storico del testo di gioco. Conserva i blocchi grezzi e li trasforma in
    righe gia' mandate a capo solo al momento del disegno, cosi' il
    ridimensionamento del terminale ri-avvolge tutto correttamente."""

    def __init__(self) -> None:
        self.blocchi: list[tuple[str, str]] = []   # (stile, testo)
        self.scroll = 0                            # righe scrollate in alto (0 = fondo)

    def aggiungi(self, testo: str, stile: str = "out") -> None:
        self.blocchi.append((stile, testo))
        self.scroll = 0                            # nuovo testo => torna al fondo

    def righe_display(self, larghezza: int) -> list[tuple[str, str]]:
        larghezza = max(1, larghezza)
        righe: list[tuple[str, str]] = []
        for stile, testo in self.blocchi:
            if stile == "cmd" and righe:
                righe.append(("out", ""))          # riga vuota tra un turno e l'altro
            for logica in testo.split("\n"):
                if logica == "":
                    righe.append((stile, ""))
                    continue
                for w in (textwrap.wrap(logica, width=larghezza) or [""]):
                    righe.append((stile, w))
        return righe

    def scorri_su(self, n: int) -> None:
        self.scroll += n

    def scorri_giu(self, n: int) -> None:
        self.scroll = max(0, self.scroll - n)

    def clamp(self, totale: int, visibili: int) -> None:
        self.scroll = max(0, min(self.scroll, max(0, totale - visibili)))


class StoricoComandi:
    """Storico dei comandi digitati, navigabile con su/giu'."""

    def __init__(self) -> None:
        self.voci: list[str] = []
        self.pos = 0          # indice corrente (== len(voci) => stai scrivendo di nuovo)
        self.bozza = ""       # testo non ancora inviato, conservato durante la navigazione

    def aggiungi(self, cmd: str) -> None:
        if cmd:
            self.voci.append(cmd)
        self.pos = len(self.voci)
        self.bozza = ""

    def precedente(self, corrente: str) -> str:
        if not self.voci:
            return corrente
        if self.pos == len(self.voci):
            self.bozza = corrente
        self.pos = max(0, self.pos - 1)
        return self.voci[self.pos]

    def successivo(self, corrente: str) -> str:
        if self.pos >= len(self.voci):
            return corrente
        self.pos += 1
        if self.pos == len(self.voci):
            return self.bozza
        return self.voci[self.pos]


# ===================== presentazione curses =====================

def _init_colori() -> None:
    if not curses.has_colors():
        return
    curses.start_color()
    try:
        curses.use_default_colors()
        sfondo = -1
    except curses.error:
        sfondo = curses.COLOR_BLACK
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)   # titolo
    curses.init_pair(2, curses.COLOR_CYAN, sfondo)               # comando
    curses.init_pair(3, curses.COLOR_YELLOW, sfondo)             # sistema


def _attr(stile: str) -> int:
    colori = curses.has_colors()
    if stile == "title":
        return (curses.color_pair(1) if colori else curses.A_REVERSE) | curses.A_BOLD
    if stile == "status":
        return curses.A_REVERSE
    if stile == "cmd":
        return (curses.color_pair(2) | curses.A_BOLD) if colori else curses.A_BOLD
    if stile == "sys":
        return (curses.color_pair(3)) if colori else curses.A_DIM
    if stile == "input":
        return curses.A_BOLD
    return curses.A_NORMAL


def _scrivi(stdscr, y: int, x: int, testo: str, attr: int = 0) -> None:
    """addstr difensivo: tronca alla larghezza e ignora gli errori di bordo."""
    h, w = stdscr.getmaxyx()
    if y < 0 or y >= h or x < 0 or x >= w:
        return
    testo = testo[: max(0, w - x)]
    try:
        stdscr.addstr(y, x, testo, attr)
    except curses.error:
        pass


def _render(stdscr, mondo: Mondo, trasc: Trascrizione, buffer: str) -> None:
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    if h < 4 or w < 12:
        _scrivi(stdscr, 0, 0, "Terminale troppo piccolo")
        stdscr.refresh()
        return

    # barra del titolo (versione del gioco accanto al titolo, motore a destra)
    nome = mondo.meta.get("titolo", "Avventura testuale")
    gv = mondo.meta.get("versione")
    titolo = " " + nome + (f"  (v{gv})" if gv else "") + " "
    marca = f"advcore v{VERSIONE} "
    barra = titolo.ljust(max(0, w - len(marca))) + marca
    _scrivi(stdscr, 0, 0, barra[:w], _attr("title"))

    # area di gioco
    area_alto = 1
    area_righe = h - 3
    righe = trasc.righe_display(w)
    trasc.clamp(len(righe), area_righe)
    totale = len(righe)
    if trasc.scroll == 0:
        inizio = max(0, totale - area_righe)
    else:
        inizio = max(0, totale - area_righe - trasc.scroll)
    for i, (stile, testo) in enumerate(righe[inizio:inizio + area_righe]):
        _scrivi(stdscr, area_alto + i, 0, testo, _attr(stile))

    # barra di stato
    if trasc.scroll > 0:
        stato = f" -- in alto di {trasc.scroll} righe · PgDn/End per tornare al fondo -- "
    else:
        stato = (" Invio: invia · frecce su/giu: storico · "
                 "PgUp/PgDn: scorri · 'fine' o Esc: esci ")
    _scrivi(stdscr, h - 2, 0, stato.ljust(w), _attr("status"))

    # riga di comando
    prompt = "> "
    _scrivi(stdscr, h - 1, 0, prompt, _attr("cmd"))
    # mostra solo la coda del buffer se piu' lungo della riga
    spazio = max(1, w - len(prompt) - 1)
    visibile = buffer[-spazio:]
    _scrivi(stdscr, h - 1, len(prompt), visibile, _attr("input"))
    cur_x = min(w - 1, len(prompt) + len(visibile))
    try:
        stdscr.move(h - 1, cur_x)
    except curses.error:
        pass
    stdscr.refresh()


def _ciclo(stdscr, mondo: Mondo) -> None:
    curses.curs_set(1)
    stdscr.keypad(True)
    _init_colori()

    motore = Motore(mondo)
    trasc = Trascrizione()
    storico = StoricoComandi()
    trasc.aggiungi(motore.avvia(), "out")
    trasc.aggiungi("(digita «aiuto» per i comandi · «salva»/«carica»/«riavvia» "
                   "per la partita)", "sys")
    buffer = ""

    def invia() -> bool:
        """Esegue il buffer come comando. Ritorna True se si deve uscire."""
        nonlocal buffer
        comando = buffer.strip()
        buffer = ""
        if not comando:
            return False
        if (not mondo.conversazione
                and comando.lower() in ("fine", "esci", "quit", "q")):
            return True
        # comandi che fanno I/O su file: salva/carica (non competono al motore)
        parti = comando.split(maxsplit=1)
        if parti[0].lower() in ("riavvia", "ricomincia", "restart"):
            trasc.blocchi.clear()
            trasc.scroll = 0
            trasc.aggiungi(motore.riavvia(), "out")
            return False
        if parti[0].lower() in ("salva", "save", "carica", "load"):
            trasc.aggiungi("> " + comando, "cmd")
            trasc.aggiungi(_meta_partita(parti, mondo, motore), "sys")
            return False
        storico.aggiungi(comando)
        trasc.aggiungi("> " + comando, "cmd")
        risposta = motore.esegui(comando)
        if risposta:
            trasc.aggiungi(risposta, "out")
        if mondo.finita:
            trasc.aggiungi("(premi un tasto per uscire)", "sys")
            _render(stdscr, mondo, trasc, "")
            stdscr.get_wch()
            return True
        return False

    while True:
        _render(stdscr, mondo, trasc, buffer)
        try:
            tasto = stdscr.get_wch()
        except KeyboardInterrupt:
            break
        except curses.error:
            continue

        # tasti normali (stringa di 1 carattere, anche accentati)
        if isinstance(tasto, str):
            if tasto in ("\n", "\r"):
                if invia():
                    break
            elif tasto in ("\x7f", "\b", "\x08"):     # backspace
                buffer = buffer[:-1]
            elif tasto == "\x1b":                      # Esc
                break
            elif tasto.isprintable():
                buffer += tasto
            continue

        # tasti speciali (interi)
        if tasto == curses.KEY_RESIZE:
            continue
        if tasto in (curses.KEY_ENTER,):
            if invia():
                break
        elif tasto == curses.KEY_BACKSPACE:
            buffer = buffer[:-1]
        elif tasto == curses.KEY_UP:
            buffer = storico.precedente(buffer)
        elif tasto == curses.KEY_DOWN:
            buffer = storico.successivo(buffer)
        elif tasto == curses.KEY_PPAGE:
            trasc.scorri_su(5)
        elif tasto == curses.KEY_NPAGE:
            trasc.scorri_giu(5)
        elif tasto == curses.KEY_HOME:
            trasc.scroll = 10 ** 9        # il clamp lo porta in cima
        elif tasto == curses.KEY_END:
            trasc.scroll = 0


def main() -> None:
    percorso = sys.argv[1] if len(sys.argv) > 1 else "avventure/caverna.json"
    mondo = carica_mondo(percorso)
    curses.wrapper(_ciclo, mondo)
    print("A presto.")


if __name__ == "__main__":
    main()
