# `advcore` — documentazione del modulo

> `advcore` è il **Pasifae Engine**: il motore su cui poggiano Pasifae Editor e
> Pasifae Play. «advcore» resta il nome tecnico del package Python.

`advcore` è il **nucleo del motore** di avventure testuali: la parte condivisa
fra editor e player. Non contiene interfaccia né I/O di gioco — riceve **stringhe**
e restituisce **stringhe**. Questo lo rende facile da testare e riusare: l'editor lo
usa per l'anteprima, il player per giocare, i test per verificare la logica.

```python
from advcore import carica_mondo, Motore

mondo = carica_mondo("avventure/faro.json")
motore = Motore(mondo)
print(motore.avvia())                 # intro + descrizione della prima stanza
print(motore.esegui("prendi lanterna"))
print(motore.esegui("nord"))
```

Principio cardine: **l'avventura è dati** (stanze, oggetti, regole — semplici
strutture) e il motore li interpreta. Le regole e i dialoghi sono dati editabili,
non codice.

---

## Struttura dei file

| File | Responsabilità |
|------|----------------|
| `model.py` | Le strutture dati del mondo (dataclass). *Cosa* esiste. |
| `engine.py` | Il `Motore`: esegue i comandi. *Cosa succede*. |
| `parser.py` | Analizza il testo del comando in un `ComandoParser`. |
| `rules.py` | Valuta le condizioni ed esegue gli effetti delle regole. |
| `testo.py` | Testo dinamico: interpolazione `{}` e frammenti `[]`. |
| `storage.py` | Carica/salva l'**avventura** in JSON. |
| `salvataggio.py` | Carica/salva lo **stato di una partita** (progressi). |
| `validazione.py` | Controlli statici dell'avventura (`valida`). |
| `mappa.py` | Mappa testuale ASCII (la versione grafica è nella GUI). |

Tutto ciò che serve di norma si importa direttamente da `advcore` (vedi
`__all__` in `__init__.py`). La versione del motore è in `advcore.__version__`.

---

## 1. Il modello dati — `model.py`

Tutte le entità sono `@dataclass` con valori di default: `Mondo()` crea un mondo
vuoto ma valido. Nessuna logica vive qui.

### Costanti

- `INVENTARIO = "inventario"` — posizione speciale: oggetto nell'inventario.
- `SCARTATO = "__scartato__"` — oggetto tolto dal gioco (importabile da
  `advcore.model`).

### `Stanza`

Un luogo dell'avventura.

| Campo | Tipo | Significato |
|-------|------|-------------|
| `id` | str | identificatore interno, fisso |
| `nome` | str | nome mostrato al giocatore |
| `desc` | str | descrizione (ammette testo dinamico) |
| `uscite` | dict | `direzione → id_stanza`, oppure `{"to": id, "se": flag, "bloccata": msg}` |
| `buia` | bool | richiede una luce per vedere |
| `visitata` | bool | impostata a runtime alla prima visita |

### `Oggetto`

Cose e personaggi. Il comportamento dipende dalle `props`.

| Campo | Tipo | Significato |
|-------|------|-------------|
| `id` | str | identificatore interno |
| `nome` | str | nome mostrato |
| `nomi` | list[str] | sostantivi riconosciuti dal parser |
| `aggettivi` | list[str] | aggettivi per disambiguare |
| `posizione` | str | id stanza · `INVENTARIO` · id contenitore · id png · `SCARTATO` |
| `props` | dict | proprietà (vedi sotto) |

Proprietà comuni in `props`: `prendibile`, `scenario`, `contenitore`, `aperto`,
`indossabile`, `png`, `luce` (`True` o nome di un flag), `desc`; per i nemici
`combattente`, `hp`, `attacco`, `difesa`, `intro_scontro`, `sconfitto` (lista di
effetti); per i png `saluto`, `stato_iniziale`, `dialogo` (lista di battute).

### `Verbo`

| Campo | Tipo | Significato |
|-------|------|-------------|
| `id` | str | forma canonica |
| `sinonimi` | list[str] | alias riconosciuti |
| `tipo` | str | `intransitivo` · `transitivo` · `ditransitivo` |
| `preposizioni` | list[str] | preposizioni ammesse |

### `Regola`

Il meccanismo «**quando → se → allora / altrimenti**».

| Campo | Tipo | Significato |
|-------|------|-------------|
| `id` | str | identificatore |
| `quando` | dict | innesco: `{verbo, oggetto, prep, oggetto_indiretto}` o `{evento: ...}` |
| `se` | list[dict] | condizioni (in **AND**; vedi `rules.py`) |
| `allora` | list[dict] | effetti se le condizioni sono vere |
| `altrimenti` | list[dict] | effetti se sono false |

### `Mondo`

Contenitore di tutto: definizione + stato runtime.

Definizione: `meta`, `flags`, `verbi`, `preposizioni`, `stanze`, `oggetti`,
`regole`. Stato runtime: `stanza_corrente`, `finita`, `messaggio_finale`,
`punteggio`, `mosse`, `conversazione`, `scontro`, `timer`.

`meta` può contenere `titolo`, `intro`, `autore`, `stanza_iniziale` e l'elenco dei
nomi di `timer` dichiarati.

**Metodi helper** (interrogano il mondo, non lo modificano):

- `oggetti_in(posizione) -> list[Oggetto]` — oggetti in quella posizione.
- `inventario() -> list[Oggetto]` — scorciatoia per `oggetti_in(INVENTARIO)`.
- `in_scope() -> list[Oggetto]` — oggetti nominabili ora: stanza corrente +
  inventario + contenuto dei contenitori **aperti** in scope.
- `luce_disponibile() -> bool` — c'è luce nella stanza corrente? (vero se non è
  buia, o se in scope c'è una sorgente di luce attiva).

---

## 2. Il motore — `engine.py`

### `class Motore`

Il cuore esecutivo. Senza I/O: ogni metodo pubblico ritorna la stringa da mostrare.

- `Motore(mondo)` — crea il motore su un `Mondo`. Imposta la stanza iniziale (da
  `meta["stanza_iniziale"]`), scatta un'istantanea dello stato iniziale (per il
  riavvio) e prepara la cronologia per l'annulla.
- `avvia() -> str` — testo iniziale: intestazione, intro e descrizione della
  stanza di partenza. Da chiamare una volta all'inizio.
- `esegui(comando) -> str` — esegue **un comando** del giocatore e ritorna la
  risposta. È il metodo principale del ciclo di gioco.
- `riavvia() -> str` — riporta il mondo allo stato iniziale e ritorna `avvia()`.

Tutto il resto è privato (prefisso `_`). In sintesi:

- **Ciclo del turno** (`_esegui_grezzo`): annulla → dialogo/scontro in corso →
  parsing → regole dell'autore → comportamento predefinito → eventi di fine turno.
- **Interpolazione**: `avvia`/`esegui` sono wrapper che applicano
  `rendi_testo` (testo dinamico) all'output grezzo.
- **Eventi e timer** (`_passo_eventi`, `_avanza_timer`): dopo ogni turno scattano
  le regole «a ogni turno», «ingresso», «scadenza timer»; i timer calano di uno.
  Un turno = un comando (l'annulla non conta); un timer avviato con `turni: k`
  scade *esattamente k turni dopo*; i timer sono sospesi durante dialoghi/scontri.
- **Regole** (`_prova_regole`, `_regola_corrisponde`): cerca una regola-comando che
  combaci; se le condizioni sono vere esegue `allora`, altrimenti `altrimenti`.
- **Comportamento predefinito** (`_predefinito` e i tanti `_h_*`): gestisce i verbi
  noti — guarda, esamina, prendi, lascia, inventario, apri, chiudi, metti, indossa,
  togli, usa, parla, attacca, aiuto, punteggio, e il movimento.
- **Dialoghi** (`_inizia_conversazione`, `_dialogo`): conversazioni a livelli con i
  png. **Combattimento** (`_combatti`, `_round_combat`, `_fuggi`): scontri a turni.
- **Movimento e descrizione** (`_muovi`, `_descrivi_stanza`, `_uscite_visibili`):
  gestisce uscite semplici e condizionate, buio e prima visita.

---

## 3. Il parser — `parser.py`

### `class ComandoParser`

Risultato dell'analisi di un comando (dataclass):

`raw`, `verbo`, `direzione`, `ogg_diretto`, `prep`, `ogg_indiretto`, `errore`
(messaggio se il comando non si capisce o è ambiguo).

### `class Parser`

- `Parser(mondo)` — costruisce le tabelle di sinonimi (verbi e preposizioni
  predefiniti + quelli dell'avventura).
- `analizza(testo) -> ComandoParser` — tokenizza, riconosce verbo/direzione,
  risolve gli oggetti nominati rispetto a `mondo.in_scope()` e segnala errori.

Vocabolari predefiniti utili: `VERBI_BUILTIN` (vai, guarda, esamina, prendi,
lascia, inventario, apri, chiudi, metti, indossa, togli, usa, parla, attacca,
difendi, fuggi, aiuto, annulla, punteggio), `PREP_BUILTIN` (in, su, con),
`DIREZIONI` / `DIREZIONI_CANONICHE` (nord, sud, est, ovest, su, giu, dentro,
fuori) e `RUMORE` (articoli e particelle ignorati).

---

## 4. Le regole — `rules.py`

Due funzioni pure operano sui dizionari di condizioni/effetti (così editor e
motore condividono lo stesso vocabolario).

- `valuta_condizioni(condizioni, mondo) -> bool` — vero se **tutte** le condizioni
  della lista sono soddisfatte (AND). I nodi logici permettono le altre
  combinazioni.
- `esegui_effetti(effetti, mondo, out)` — applica gli effetti in ordine,
  aggiungendo eventuali messaggi alla lista `out`.

### Vocabolario delle condizioni (campo `se`)

| Dizionario | Vera quando… |
|------------|--------------|
| `{flag, uguale}` | il flag è uguale al valore |
| `{flag, maggiore}` / `{flag, minore}` | confronto numerico `>` / `<` |
| `{flag, maggiore_uguale}` / `{flag, minore_uguale}` | confronto `≥` / `≤` |
| `{oggetto_in: [id, dove]}` | l'oggetto è in quel luogo |
| `{stanza_corrente: id}` | il giocatore è in quella stanza |
| `{stato_min: n}` | livello conversazione ≥ n |
| `{mosse_min: n}` | turni trascorsi ≥ n |
| `{non: cond}` | NON (nega una condizione) |
| `{oppure: [cond, ...]}` | almeno una vera (OR) |
| `{tutte: [cond, ...]}` | tutte vere (AND, per annidare) |

### Vocabolario degli effetti (campi `allora` / `altrimenti`)

| Dizionario | Effetto |
|------------|---------|
| `{set_flag, valore}` | imposta un flag |
| `{incrementa, di}` | aumenta un flag numerico |
| `{punti}` | aggiunge al punteggio |
| `{stampa}` | mostra un messaggio (con testo dinamico) |
| `{sposta_oggetto, a}` | sposta un oggetto in un luogo |
| `{scarta_oggetto[, stampa]}` | toglie un oggetto dal gioco |
| `{apri_oggetto}` / `{chiudi_oggetto}` | apre/chiude un contenitore (per aperture condizionate: la regola su `apri` scavalca il verbo predefinito) |
| `{teleporta}` | sposta il giocatore in un'altra stanza |
| `{vittoria}` / `{sconfitta}` | termina la partita |
| `{stato}` / `{avanza_stato}` | imposta/avanza il livello di conversazione |
| `{inizia_scontro}` | avvia un combattimento |
| `{avvia_timer, turni}` / `{ferma_timer}` | gestisce un timer |

---

## 5. Il testo dinamico — `testo.py`

- `rendi_testo(testo, mondo, extra=None) -> str` — applica al testo:
  - **interpolazione** `{nome}`: valore di un flag o speciale (`{punteggio}`,
    `{mosse}`, `{stanza}`); i booleani diventano «sì»/«no»; un nome sconosciuto
    resta `{nome}` (sicuro per il testo esistente);
  - **frammenti condizionati** `[flag: testo]`, `[flag: vero | falso]`,
    `[flag=valore: ...]`. Il token speciale `prima_volta` (passato dal motore in
    `extra`) consente una frase diversa alla prima visita di una stanza.

Il motore lo applica automaticamente all'output di `avvia`/`esegui`.

---

## 6. Persistenza

### Avventura — `storage.py`

Formato su disco: **JSON** leggibile e versionabile.

- `carica_mondo(percorso) -> Mondo`
- `salva_mondo(mondo, percorso) -> None`

### Partita (progressi) — `salvataggio.py`

Lo *stato di gioco* è separato dall'avventura.

- `stato_partita(mondo) -> dict` — estrae lo stato runtime serializzabile
  (stanza corrente, flag, punteggio, mosse, posizioni degli oggetti, timer…).
- `applica_stato(mondo, stato) -> None` — riapplica uno stato a un mondo appena
  caricato (in place).
- `salva_partita(mondo, percorso)` / `carica_partita(mondo, percorso) -> dict`.

Internamente `Motore` usa `stato_partita`/`applica_stato` anche per **annulla** e
**riavvia**.

---

## 7. Validazione — `validazione.py`

- `valida(mondo) -> list[Problema]` — controlli statici: stanza iniziale, uscite
  verso stanze inesistenti, posizioni non valide, riferimenti rotti in regole e
  dialoghi.
- `class Problema` — `gravita` (`errore`/`avviso`), `dove`, `messaggio`,
  `categoria`, `chiave` (per saltare all'entità).

> Nota: l'editor grafico usa una propria analisi più ricca (`gui/analisi.py`,
> con stanze irraggiungibili e «dove è usato»). `validazione.py` resta il
> controllo essenziale lato motore, indipendente dalla GUI.

---

## 8. Mappa — `mappa.py`

- `mappa_testuale(mondo) -> str` — disegna una mappa ASCII di stanze e
  collegamenti. (La mappa grafica interattiva è nella GUI, `gui/mappa.py`.)

---

## 9. Esempio: un ciclo di gioco minimo

```python
from advcore import carica_mondo, Motore

mondo = carica_mondo("avventure/caverna.json")
motore = Motore(mondo)
print(motore.avvia())

while not mondo.finita:
    comando = input("> ")
    print(motore.esegui(comando))
```

Il player e l'anteprima dell'editor non fanno altro che questo, aggiungendo
l'interfaccia attorno a `esegui`.

---

## 10. Estendere il motore

Le aggiunte tipiche sono **retrocompatibili** e seguono lo stesso schema:

- **Nuovo effetto**: aggiungi un ramo in `_esegui_uno` (`rules.py`) e la voce
  corrispondente nel catalogo dell'editor (`gui/regole.py`).
- **Nuova condizione**: aggiungi un ramo in `_valuta_una` (`rules.py`) e la voce
  nel catalogo dell'editor.
- **Nuovo verbo predefinito**: un metodo `_h_<verbo>` in `engine.py`, registrato
  nel dispatch di `_predefinito`, e l'eventuale sinonimo in `VERBI_BUILTIN`.

Regola d'oro del progetto: il motore evolve per aggiunte, mantenendo verde la
suite di test (`test_motore.py`, `test_testo.py`, …) e senza rompere le avventure
e i salvataggi esistenti.
