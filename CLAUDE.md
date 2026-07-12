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
  movimento, dialoghi, combattimento, timer. Il congedo di un dialogo è
  `props["congedo"]` (fallback: `"Saluti «nome»."`, invariato).
- `parser.py` — verbo + preposizione + oggetto; sinonimi e direzioni.
- `rules.py` — valutazione condizioni (NON/OR/E, confronti) ed effetti;
  anche l'apertura dei dialoghi (`avvia_conversazione`,
  `battute_disponibili`, `menu_dialogo` — pura logica, nessun requisito
  di `props["png"]`), condivisa dal verbo builtin "parla" e dall'effetto
  di regola `avvia_dialogo` (apre il dialogo di un oggetto qualsiasi
  agganciandolo al verbo che l'autore preferisce, es. "usa" su un
  terminale: si usa, non si parla). La voce «0.» del menu dialogo è
  `props["etichetta_uscita"]` (fallback: `"saluta e vai"`, invariato).
- `testo.py` — testo dinamico: `{flag}` e frammenti `[flag: ...]`.
- `storage.py` — carica/salva l'avventura (JSON).
- `salvataggio.py` — salva/carica lo stato della partita.
- `validazione.py` — controlli statici (`valida -> list[Problema]`).
- `mappa.py` — mappa testuale (ASCII); anche `uscite_visibili(mondo, stanza)`,
  le uscite attualmente sbloccate come coppie (direzione, destinazione) —
  usata dalla mini-mappa del player, non solo dalla mappa ASCII.

**`gui/` — la suite grafica (PySide6/Qt), solo viste:**
- `editor.py` — Pasifae Editor (file grande, ~1850 righe; vedi insidie).
  Layout 2.1: splitter a tre colonne (categorie | elementi | dettaglio) più
  la **mappa in un `QDockWidget`** ancorato a destra (`dock_mappa`),
  ridimensionabile/richiudibile/flottante — toggle "Pannello mappa" nel menu
  Strumenti; da staccata, `topLevelChanged` le assegna i flag di finestra
  nativa (min/max/chiudi), altrimenti il `Qt::Tool` di default non mostra il
  pulsante di massimizza; le modifiche riallineano la mappa in modo differito
  (`_segna_modifica` → `QTimer.singleShot(0, _aggiorna_mappa)`).
- `player.py` — Pasifae Play. Splitter a tre colonne: illustrazione |
  trascrizione | mini-mappa (`self.mappa`, `MiniMappa`); quest'ultima si
  aggiorna in `_aggiorna_stato()` (come l'illustrazione) e si nasconde da
  sola sotto `Player.LARGHEZZA_MIN_MAPPA` (900px, vedi `resizeEvent`) per
  lasciare spazio alla lettura — indipendentemente dal toggle "Mappa" in
  Visualizza, che resta l'interruttore dell'utente.
- `mappa_player.py` — `MiniMappa`: mappa **di sola lettura** nel player
  (nessun drag, nessun menu contestuale). Un riquadro per ogni stanza
  visitata (evidenziata quella corrente), una linea fra due visitate
  collegate; verso una non ancora visitata, un trattino verso il bordo
  (direzioni cardinali) o un'etichetta "altre uscite: …" (su/giù/dentro/
  fuori) — mai un riquadro "?": niente fog-of-war, solo ciò che il
  giocatore già sa dal testo. I riquadri **non hanno dimensione fissa**:
  si ricalcolano a ogni `aggiorna()`/`resizeEvent` fra un minimo leggibile
  e un massimo (130–220px) per riempire il pannello disponibile in base a
  quante stanze sono visitate (griglia automatica, non le posizioni
  disegnate a mano nell'editor: quelle sono libere, incompatibili con
  celle uniformi). Griglia condivisa con l'editor via
  `gui.mappa._posizioni_griglia`.
- `regole.py` — costruzione/serializzazione regole nell'editor; catalogo
  degli effetti (`TIPI_EFFETTO`/`CAMPI`/`ASSEMBLA`/`da_dict`) allineato a
  `advcore/rules.py`, incluso `avvia_dialogo` (campo di tipo "oggetto",
  non "png": funziona su qualunque oggetto).
- `analisi.py` — riferimenti incrociati, "Dove è usato", problemi,
  catena dei puzzle (`catena_puzzle`).
- `catena.py` — finestra "Concatenazione dei puzzle" (albero dai finali).
- `anteprima.py` — finestra "Prova l'avventura" dentro l'editor.
- `mappa.py` — `PannelloMappa`, il piano di lavoro nel dock della mappa:
  stanze trascinabili (posizioni in `meta["editor"]["mappa"]`, il motore le
  ignora), clic → selezione nel dettaglio, uscite col trascinamento destro,
  nuova stanza dal canvas; API per l'editor: `aggiorna()`, `imposta_mondo()`,
  `imposta_tema()`, `evidenzia()`, `scollega()` (da chiamare prima della
  distruzione della finestra: GC sicuro).
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
- `oggetto.props` usa la chiave `"scenario"` (oggetto fisso, non raccoglibile,
  ma resta esaminabile/nominabile) e `"nascosto"` (invisibile e non
  nominabile finché una regola non lo rivela con `mostra_oggetto` — non è
  lo stesso concetto di `scenario`: quello è sempre lì, solo non elencato).
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
- **Qt/Wayland e QGraphicsScene** (lezioni del lavoro sulla mappa):
  su Linux il menu contestuale scatta alla *pressione* del destro — i gesti
  right-drag devono sopprimerlo; mai creare/rimuovere item della scena dentro
  `itemChange` (aggiornare solo la geometria); lasciar andare i riferimenti
  Python agli item *prima* di `scena.clear()` o della distruzione della
  finestra, altrimenti il GC crasha su wrapper di C++ già morto (firma:
  «Garbage-collecting, no Python frame»); menu e dialoghi da gesti della
  scena vanno aperti con `QTimer.singleShot(0, ...)`.

## Stato attuale
- `advcore` **1.19.0** · interfaccia `gui` **2.4.0** (oggetti nascosti,
  rivelabili con l'effetto `mostra_oggetto`; dialoghi apribili da
  qualunque verbo/oggetto con l'effetto `avvia_dialogo`, non solo dal
  "parla" sui png; congedo e voce di uscita del menu personalizzabili).
- Suite: **85 test GUI + 10 script**, tutti verdi.
- Documentazione: `README.md`, `advcore/DOCUMENTAZIONE.md`, `COSTRUIRE.md`,
  manuale d'uso (Word/PDF).

## Prossimi sviluppi

### Motore (`advcore`)
- **Priorità e "ferma qui" nelle regole**: poter ordinare le regole e fermare la
  catena dopo che una è scattata (evita effetti a cascata indesiderati). Aggiungi
  prima i test che descrivono l'ordine atteso.
- **Parser più ricco**: oggetti multipli ("prendi spada e scudo") e pronome
  "lo/la" riferito all'ultimo oggetto. (Fatti: "prendi tutto"/"tutti",
  abbreviazioni delle direzioni, preposizioni multiple nelle regole.)
- **Verbi personalizzati guidati da dati**: permettere all'autore di definire
  nuovi verbi con effetti, senza toccare il codice.
- **Stati dei contenitori e dei liquidi**: versare, riempire, mescolare — utile
  per enigmi più ricchi.
- **Dialoghi disaccoppiati da "parla"/png — FATTO (1.18.0, rifinito in
  1.18.1)**: un oggetto qualsiasi (non solo i personaggi) può avere
  saluto/battute/congedo e aprirli con qualunque verbo tramite l'effetto
  di regola `avvia_dialogo` — nato dal caso concreto di un terminale
  ("si usa", non "si parla", e "Saluti terminale" non ha senso). Anche
  la voce «0.» del menu ("saluta e vai") è personalizzabile
  (`props["etichetta_uscita"]`, 1.18.1: stesso problema del congedo,
  emerso testando l'avventura vera). Il verbo builtin "parla" non è
  cambiato: resta bloccato sui non-png.
- **Oggetti nascosti — FATTO (1.19.0)**: `props["nascosto"]` esclude un
  oggetto da `Mondo.in_scope()` (quindi dal parser, non solo dall'elenco
  della stanza) finché una regola non lo rivela con l'effetto
  `mostra_oggetto` (simmetrico: `nascondi_oggetto`). Diverso da
  `scenario`, che resta sempre esaminabile/nominabile.

### Editor / Player
- **Mappa come piano di lavoro — FATTO (2.0.0, rivisto in 2.1.0)**: stanze
  trascinabili (1.14.0), doppio clic → editor (1.15.0), uscite col
  trascinamento destro + nuova stanza dal canvas (1.16.0), mappa come widget
  centrale con i form a pannello di dettaglio (2.0.0); il layout a colonna
  fissa lasciava troppo poco spazio al form su schermi non ampi, quindi la
  mappa è passata a un `QDockWidget` ridimensionabile/richiudibile/flottante
  (2.1.0). Possibile rifinitura: evidenziare sulla mappa le uscite della
  stanza selezionata.
- **Mini-mappa nel player — FATTO (2.2.0)**: le stanze visitate compaiono
  via via in un pannello a destra (`gui/mappa_player.py`), con le uscite
  verso l'ignoto solo accennate (trattino o etichetta), mai svelate —
  vedi mappa dei moduli. Richiesta dall'utente dopo aver visto la mappa
  come piano di lavoro nell'editor.
- **Validazione più profonda**: avvisi su timer mai avviati, dialoghi senza
  uscita, oggetti irraggiungibili, finali non collegati.
- **Anteprima con "stato di gioco" ispezionabile**: pannello che mostra flag,
  inventario e timer durante la prova.
- **Esportazioni**: oltre all'eseguibile, una build "web" (il motore è già senza
  I/O: si presta a un front-end browser) e l'export della mappa come immagine.
- **Internazionalizzazione (i18n)**: estrarre le stringhe dell'interfaccia per
  aprire Pasifae anche al pubblico non italiano (vedi nota nel README).

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
