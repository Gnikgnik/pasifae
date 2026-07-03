# CLAUDE.md — guida per lavorare a Pasifae

Questo file è un promemoria per l'assistente. Leggilo a ogni avvio: contiene le
regole, i comandi e le insidie del progetto. Seguile invece di reinventarle.

## In una riga
**Pasifae** è una suite per creare e giocare avventure testuali: un motore
(`advcore`) senza interfaccia, e due front-end grafici (Pasifae Editor e Pasifae
Play) più due da terminale.

## Lingua
Rispondi e commenta **in italiano**. I nomi di classi, funzioni e variabili sono
in italiano: mantieni questa convenzione. `advcore` è il nome tecnico del package;
**"Pasifae"** è il marchio rivolto all'utente.

## Principio cardine (non violarlo)
Il motore è **senza I/O**: `Motore.esegui(stringa) -> stringa`. Non sa nulla di
schermo, file o rete. Le interfacce (GUI e terminale) sono **solo viste** sottili
sopra il motore. Avventure, regole e dialoghi sono **dati** (JSON), non codice.
Qualunque logica di gioco va nel motore o nei dati, mai nell'interfaccia.

## Regole del progetto
- **Prima il test, poi la correzione.** Quando emerge un bug, aggiungi prima il
  test che lo cattura (fallisce), poi correggi finché passa.
- Il motore evolve per **aggiunte retrocompatibili**: le avventure esistenti
  devono continuare a funzionare e i salvataggi a caricarsi.
- **La suite resta sempre verde** prima di considerare conclusa una modifica.
- Modifiche **a piccoli passi**, una cosa alla volta, con commit chiari.

## Ambiente e comandi
```bash
# ambiente
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # esecuzione
pip install -r requirements-dev.txt       # test (pytest, pytest-qt)

# avvio (interfaccia grafica)
python3 -m gui.editor [avventura.json]    # Pasifae Editor
python3 -m gui.player [avventura.json]    # Pasifae Play  (senza argomento: modalità blank)

# avvio (terminale)
python3 edit.py [avventura.json]          # editor urwid
python3 play.py  avventura.json           # player a riga di comando

# test — l'intera suite (headless serve QT_QPA_PLATFORM=offscreen)
QT_QPA_PLATFORM=offscreen pytest -q
# solo i test del motore (niente Qt):
python3 test_motore.py
```
Avventure di esempio in `avventure/`: `caverna`, `faro`, `duello`, `tutorial`.

## Mappa dei moduli
**`advcore/` — il motore (niente I/O):**
- `model.py` — dataclass del mondo: Mondo, Stanza, Oggetto, Verbo, Regola.
- `engine.py` — `Motore`: parser + applicazione regole + verbi predefiniti,
  movimento, dialoghi, combattimento, timer.
- `parser.py` — verbo + preposizione + oggetto; sinonimi e direzioni.
- `rules.py` — valutazione condizioni (NON/OR/E, confronti) ed effetti.
- `testo.py` — testo dinamico: `{flag}` e frammenti `[flag: ...]`.
- `storage.py` — carica/salva l'avventura (JSON).
- `salvataggio.py` — salva/carica lo stato della partita.
- `validazione.py` — controlli statici (`valida -> list[Problema]`).
- `mappa.py` — mappa testuale (ASCII).

**`gui/` — la suite grafica (PySide6/Qt), solo viste:**
- `editor.py` — Pasifae Editor (file grande, ~1650 righe; vedi insidie).
- `player.py` — Pasifae Play.
- `regole.py` — costruzione/serializzazione regole nell'editor.
- `analisi.py` — riferimenti incrociati, "Dove è usato", problemi.
- `anteprima.py` — finestra "Prova l'avventura" dentro l'editor.
- `mappa.py` — mappa visuale.
- `tema.py` — temi chiaro/scuro.
- `risorse.py` — icona, loghi, dialogo "Informazioni" condiviso.
- `compila.py` — logica pura per "Compila gioco autonomo" (PyInstaller).
- `editor_riassunti.py` — riepiloghi testuali degli elementi.
- `assets/` — icona e loghi Pasifae.

**Radice:** `edit.py` (editor urwid), `play.py` / `play_curses.py` (player CLI),
`test_*.py` (suite), `editor.spec` / `player.spec` (build PyInstaller).

## Convenzioni di codice
- Ogni elemento ha **id** (stabile, per i riferimenti) e **nome** (mostrato).
  Non confonderli: le regole e le uscite puntano agli id.
- In testa a ogni sorgente c'è `# SPDX-License-Identifier: GPL-3.0-or-later`
  (licenza **GPLv3**, vedi `LICENSE`). Mantienilo sui nuovi file.
- `oggetto.props` usa la chiave `"scenario"` (oggetto fisso, non raccoglibile).
- Costanti utili: `INVENTARIO = "inventario"`, `SCARTATO = "__scartato__"`.

## Insidie note
- **`gui/editor.py` è grande**: quando lo modifichi, sii chirurgico — indica con
  precisione la sezione da toccare e rivedi sempre il diff.
- **Test GUI headless**: richiedono `QT_QPA_PLATFORM=offscreen`. Per catturare uno
  screenshot di un widget: `widget.grab().save(path)` (filtra dallo stderr la riga
  "propagateSizeHints").
- **Non committare** artefatti: `__pycache__/`, `.pytest_cache/`, `build/`,
  `dist/`, `salvataggi/`, `.venv/` (vedi `.gitignore`).
- **urwid 4.x**: l'editor da terminale è provato su urwid 4; su versioni più
  vecchie alcune API differiscono.
- **PyInstaller**: la build impacchetta Qt; è lenta (~1 min) e pesante (~80 MB),
  e l'eseguibile vale solo per il sistema operativo su cui lo compili.

## Stato attuale
- `advcore` **1.11.1** · interfaccia `gui` **1.5.2**.
- Suite: **39 test GUI + 10 script**, tutti verdi.
- Documentazione: `README.md`, `advcore/DOCUMENTAZIONE.md`, `COSTRUIRE.md`,
  manuale d'uso (Word/PDF), e il progetto dell'avventura "SOTTO ARES".

## Prossimi sviluppi

### Motore (`advcore`)
- **Priorità e "ferma qui" nelle regole**: poter ordinare le regole e fermare la
  catena dopo che una è scattata (evita effetti a cascata indesiderati). Aggiungi
  prima i test che descrivono l'ordine atteso.
- **Parser più ricco**: gestione di "tutto"/"tutti", oggetti multipli ("prendi
  spada e scudo"), pronome "lo/la" riferito all'ultimo oggetto, abbreviazioni
  delle direzioni (n/s/e/o).
- **Verbi personalizzati guidati da dati**: permettere all'autore di definire
  nuovi verbi con effetti, senza toccare il codice.
- **Stati dei contenitori e dei liquidi**: versare, riempire, mescolare — utile
  per enigmi più ricchi (anche per SOTTO ARES: bombole, reattore).

### Editor / Player
- **Validazione più profonda**: avvisi su timer mai avviati, dialoghi senza
  uscita, oggetti irraggiungibili, finali non collegati.
- **Anteprima con "stato di gioco" ispezionabile**: pannello che mostra flag,
  inventario e timer durante la prova.
- **Esportazioni**: oltre all'eseguibile, una build "web" (il motore è già senza
  I/O: si presta a un front-end browser) e l'export della mappa come immagine.
- **Internazionalizzazione (i18n)**: estrarre le stringhe dell'interfaccia per
  aprire Pasifae anche al pubblico non italiano (vedi nota nel README).

### Avventura "SOTTO ARES"
- Costruire il **JSON** a partire da `SOTTO-ARES-progetto.md` (18 stanze, PNG,
  timer, finali). Procedere per zone: prima la superficie, poi il livello tecnico,
  poi sotto la crosta, provando nel player dopo ogni zona.
- Primo passo concreto consigliato: la stanza `discesa` con l'uscita **condizionata
  alla tuta** verso `airlock`, e il relativo messaggio di rifiuto.
- Usare l'appendice "Mappa delle stanze e direzioni" del documento come traccia
  delle uscite (sono già tutte definite e reciproche).

### Qualità e distribuzione
- **`git` + commit piccoli** come canale di revisione (questo file e `.gitignore`
  sono il punto di partenza).
- Spezzare gradualmente `gui/editor.py` in moduli più piccoli, **un blocco alla
  volta e a suite verde**.
- Pubblicazione del repository con la **GPLv3** (GitHub riconosce la licenza dal
  file `LICENSE`).

## Licenza
Pasifae è software libero sotto **GPL-3.0-or-later**. Copyright (C) 2026
Vito Antonio Raimondi. Vedi `LICENSE` e `THIRD-PARTY-NOTICES.md`.
