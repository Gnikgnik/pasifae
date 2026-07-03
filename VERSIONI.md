# Pasifae — cronologia delle versioni

## gui 1.8.0
Rifinitura tipografica del player. **Gerarchia nella trascrizione**: il titolo
del gioco appare grande e senza i «==» decorativi, il nome della stanza spicca
in grassetto nel colore accento, la riga «Uscite: …» è in tono muto (la
classificazione usa le convenzioni testuali del motore e i nomi delle stanze
del mondo caricato — il motore non cambia). **Accento per avventura**: il
campo opzionale «colore» nei metadati (es. `#c8a04a`, anche dall'editor) tinge
titolo, prompt, cornice dell'input e intestazioni. **Carattere con grazie**:
opzione in Visualizza per il corpo del racconto, ricordata tra le sessioni.
La barra di stato mostra anche la **stanza corrente**.


## gui 1.7.0
Lettura più comoda nel player. La trascrizione sta in una **colonna centrata**
di larghezza fissa (~75 caratteri): su finestre larghe il testo non si stende
più da bordo a bordo. La **dimensione del testo si regola** da Visualizza
(Testo più grande/più piccolo, Ctrl+«+»/Ctrl+«-», Ctrl+0 per tornare al
normale, o Ctrl+rotella sulla trascrizione) e viene **ricordata tra le
sessioni**. La riga di comando è ora in una **cornice** che si accende col
colore accento quando ha il fuoco.


## gui 1.6.0
«Prova da…» nell'editor: per le avventure lunghe la prova può partire da un
punto scelto invece che dall'inizio. Un dialogo (Strumenti ▸ Prova da…,
Ctrl+Maiusc+P, o clic destro su una stanza ▸ «Prova da questa stanza…»)
permette di scegliere stanza di partenza, oggetti già nell'inventario e flag
da impostare (compresi quelli che nascono solo durante il gioco). «Riavvia»
nell'anteprima torna al punto scelto, non all'inizio. Nuova funzione
`analisi.flag_noti()` che elenca tutti i flag citati dall'avventura.


## gui 1.5.2
Due correzioni al player, regressioni del fix del farfallio (gui 1.5.1):
durante l'animazione la risposta si fondeva con la riga del comando
(«› guardaBIBLIOTECA…»), e a fine animazione la vista poteva fermarsi
sopra il fondo, nascondendo l'ultima riga stampata (lo scorrimento usava
la corsa *stimata* della scrollbar, prima che il layout vero arrivasse).


## advcore 1.11.0
Condizioni più espressive: confronti numerici `<`, `≤`, `≥` (oltre a `=` e
`>`) e operatori logici — `non` (negazione), `oppure` (almeno una vera, OR) e
`tutte` (per annidare). La lista `se` resta in AND; gli altri casi si esprimono
con questi nodi.


## advcore 1.10.0
Testo dinamico nei messaggi e nelle descrizioni: interpolazione `{flag}` (e
`{punteggio}`/`{mosse}`/`{stanza}`) e frammenti condizionati `[flag: testo]` /
`[flag: vero | falso]` / `[flag=valore: ...]`. Il token speciale `prima_volta`
permette una frase diversa alla prima visita di una stanza.


## advcore 1.9.0
Nuovo effetto «scarta oggetto» (scarta_oggetto): toglie dal gioco un oggetto
scarico o rovinato, con messaggio opzionale. Utile allo scadere di un timer
(torce che si spengono, batterie esaurite, cibo che marcisce).


Il progetto segue il **versionamento semantico**: `MAJOR.MINOR.PATCH`.

- **PATCH** (es. 1.0.0 → 1.0.1): correzioni di bug e piccole rifiniture, senza
  nuove funzioni e senza rompere nulla.
- **MINOR** (es. 1.0.0 → 1.1.0): nuove funzionalità retrocompatibili (le
  avventure e i salvataggi esistenti continuano a funzionare).
- **MAJOR** (es. 1.0.0 → 2.0.0): cambiamenti incompatibili, per esempio una
  modifica al formato del file `.json` che impedisce di aprire avventure vecchie.

La versione corrente è definita in un solo punto, `advcore/__init__.py`
(`__version__`), ed è mostrata nell'intestazione dell'editor e all'avvio dei
player.

> Regola di lavoro: **ogni modifica al progetto incrementa la versione** e
> aggiunge una voce qui sotto, in cima.

---

## 1.8.0 — Orologio dei turni e architettura a eventi (+ annulla)

Il cambiamento più profondo finora: il mondo non è più solo reattivo ai comandi,
ma **scorre nel tempo**. Dopo ogni turno il motore esegue un «passo eventi» che dà
al mondo autonomia, riusando lo stesso vocabolario di condizioni ed effetti.

- **Regole-evento.** Oltre all'innesco «comando del giocatore», una regola può
  ora scattare per:
  - **ogni turno** (`{"evento": "turno"}`) — il classico daemon: una torcia che si
    consuma, un'atmosfera che cambia, un veleno che agisce;
  - **ingresso in una stanza** (`{"evento": "entra", "stanza": id}`) — agguati,
    descrizioni che cambiano, trigger d'arrivo;
  - **scadenza di un timer** (`{"evento": "timer", "timer": nome}`).
- **Orologio dei turni.** Nuova condizione **«turno ≥ N»** (`mosse_min`) per
  eventi a tempo assoluto.
- **Timer.** Nuovi effetti **«avvia un timer»** (`avvia_timer`, con `turni`) e
  **«ferma un timer»** (`ferma_timer`): conti alla rovescia (la miccia, l'arrivo
  della guardia, l'ossigeno che finisce). Un timer avviato durante un turno scade
  esattamente dopo il numero di turni indicato.
- **Annulla (undo).** Nuovo comando **`annulla`** (sinonimi `undo`, `disfa`):
  ripristina lo stato prima dell'ultimo turno — eventi e timer compresi. Nasce
  quasi gratis dall'architettura a istantanee del motore.
- **Salvataggi.** I timer viaggiano nel salvataggio e si azzerano col riavvio.
- **Editor.** Il form della regola ha un selettore **«innesco»** (comando / ogni
  turno / ingresso stanza / timer); nuova condizione «turno ≥ N» e nuovi effetti
  timer nei cataloghi; l'elenco regole mostra l'innesco-evento.
- **Determinismo.** Le regole-evento sono valutate in ordine di dichiarazione, una
  volta per turno; nessuna rientranza.
- Nuova avventura d'esempio **`tutorial.json`** («Il Meccanismo del Tempo»): un
  breve tutorial che insegna i comandi base e mostra orologio, evento d'ingresso,
  timer con conto alla rovescia e annulla.

---

## 1.7.0 — Incolla da sorgenti esterne; verbi di sistema marcati ovunque

- **Nuova funzione**: l'editor ora supporta l'**incolla da sorgenti esterne**
  (bracketed paste). Un blocco di testo copiato da Word o da un altro programma
  viene inserito in un colpo solo nel campo a fuoco, con gli a-capo preservati
  nei campi multiriga (e convertiti in spazi in quelli a riga singola). Utile per
  travasare nell'editor un'avventura scritta altrove senza riscriverla. Richiede
  un terminale che supporti l'incolla (praticamente tutti quelli moderni).
- **Bugfix**: nell'elenco e nel selettore dei verbi, un verbo **di sistema**
  ridichiarato dall'avventura (es. «apri», «usa») non era marcato come tale. Ora
  ogni verbo di sistema è sempre indicato: «predefinito (esteso)» se l'avventura
  lo estende con sinonimi propri, «predefinito (sola lettura)» se è fornito solo
  dal motore.

---

## 1.6.0 — Stato di conversazione e scontro minimale

Due nuovi modi, intrecciati, per rendere più ricca l'interazione con i png.

- **Stato di conversazione (dialoghi a livelli).** Ogni png ha un livello di
  conversazione (prop opzionale `stato_iniziale`, default 0). Nuova condizione
  «stato conversazione ≥ N» per mostrare una battuta solo a un certo livello, e
  nuovi effetti «porta allo stato N» / «avanza di N» per farlo salire. Così la
  conversazione si approfondisce a tappe. Tutto vive nelle liste `se`/`allora`
  che già esistono; lo stato è memorizzato in un flag riservato e si salva da sé.
- **Scontro minimale (combattimento).** Una modalità a turni deterministica,
  gemella della conversazione. Un png può essere `combattente` con `hp`,
  `attacco`, `difesa`, `fuga` e un `intro_scontro`; l'esito alla sconfitta è una
  **lista di effetti standard** (`sconfitto`: bottino, flag, messaggi…). Verbi
  di combattimento `attacca`/`difendi`/`fuggi`; lo scontro si avvia col nuovo
  effetto «inizia scontro» (da una regola o da una battuta di dialogo) oppure
  con «attacca <png>». PF del giocatore nei flag `pg_hp`/`pg_attacco`/`pg_difesa`.
- **Editor.** Nuove voci nei cataloghi di condizioni ed effetti; nel form
  dell'oggetto la sezione «Combattimento» (statistiche) e un editor «Esito alla
  sconfitta» che riusa l'editor degli effetti.
- **Salvataggi.** Lo stato dello scontro e i PF viaggiano nel salvataggio.
- Nuova avventura d'esempio `duello.json`: un dialogo a livelli che può sfociare
  in duello, il cui esito apre la cripta.

---

## 1.5.1 — Correzione: l'abbreviazione «e» per est

- **Bugfix**: l'abbreviazione «e» (est) veniva scartata dal parser perché «e»
  è anche nella lista delle parole-rumore (la congiunzione). Ora un token che è
  una direzione viene sempre mantenuto, così «e» muove a est come «n», «s», «o»
  e «w» fanno per le rispettive direzioni. Le altre parole-rumore (articoli,
  particelle) restano scartate.

---

## 1.5.0 — Messaggio personalizzato per le uscite bloccate

- **Nuova funzione**: nell'editor delle uscite, ogni uscita condizionata ha ora
  il campo «se bloccata, mostra:» per personalizzare il testo che appare quando
  il passaggio è ancora sbarrato (prima il motore usava solo il generico «Quella
  via è bloccata.»).
- **Bugfix**: l'editor non perde più un messaggio di blocco (`bloccata`) già
  presente nel file quando si risalva la stanza; ora viene caricato, mostrato e
  riscritto correttamente.

---

## 1.4.0 — Verbi predefiniti ispezionabili nell'editor

- **Nuova funzione**: nell'elenco «Verbi» ora compaiono anche i **verbi
  predefiniti** del motore (marcati «predefinito · sola lettura»). Aprendoli si
  vede id e sinonimi, con una nota: sono forniti dal motore e non si modificano
  da qui (per cambiarne il comportamento si usa una regola). Prima erano
  invisibili nell'editor.
- I verbi predefiniti compaiono ora anche nel **selettore del verbo** delle
  regole: così si può scegliere «apri», «usa», «esamina»… come innesco senza
  doverli ridichiarare (completa la correzione del validatore della 1.0.1).

---

## 1.3.0 — Frase di presenza degli oggetti

- **Nuova funzione**: ogni oggetto può avere una **«frase in stanza»**
  (`props.in_stanza`), una frase mostrata nella descrizione della stanza
  *finché l'oggetto è lì*, che sparisce automaticamente quando viene preso o
  spostato. Più elegante del nudo elenco «Qui vedi: …», e soprattutto non più
  stantia: risolve l'incongruenza per cui la prosa fissa continuava a nominare
  oggetti già raccolti. Gli oggetti senza questa frase restano nell'elenco
  automatico come prima.
- L'editor dell'oggetto ha il nuovo campo «frase in stanza». Aggiornata
  l'avventura d'esempio «Il Faro» (cucina): la prosa fissa ora descrive solo la
  scena, lanterna e fiammiferi usano la frase di presenza (gioco v1.0.1).

---

## 1.2.0 — Versione del gioco e direzioni a selettore

- **Metadati**: nuovo campo **«versione del gioco»** (in `meta.versione`), la
  versione dell'avventura decisa dall'autore, distinta da quella del motore.
  Viene mostrata nei player accanto al titolo (es. «gioco v1.0.0»).
- **Direzioni a selettore**: la direzione di un'uscita non si digita più a mano
  ma si sceglie da un menu (nord/sud/est/ovest/su/giù/dentro/fuori), le uniche
  che il parser riconosce. Elimina i refusi che creavano uscite irraggiungibili.
  Con questo, in una riga di uscita **tutti e tre** i riferimenti (direzione,
  destinazione, flag) sono ormai selettori: niente più testo libero per le
  entità a insieme chiuso.

---

## 1.1.0 — I flag si scelgono, non si digitano

- **Nuova funzione**: ovunque nell'editor si faccia riferimento a un flag
  (condizioni, effetti «imposta/incrementa flag», campo «flag luce» di un
  oggetto, «se flag» di un'uscita) ora c'è un **selettore a comparsa** che
  elenca i flag già dichiarati, invece di un campo da digitare a mano. Elimina
  alla radice i disallineamenti da refuso (es. un flag impostato da una regola
  ma scritto in modo diverso nella proprietà luce).
- Il selettore include l'opzione **«nuovo flag…»**: la si sceglie, si digita il
  nome una volta sola e il flag viene **auto-dichiarato** tra quelli iniziali
  (così resta sempre allineato). Aggiunto un piccolo prompt di testo a comparsa.

---

## 1.0.1 — Correzione del validatore

- **Bugfix**: la «Verifica» non segnala più come «verbo inesistente» i verbi
  **predefiniti** (apri, esamina, usa, prendi, ...) usati nelle regole ma non
  dichiarati esplicitamente. Prima un'avventura corretta poteva mostrare falsi
  errori. Aggiunta un'avventura di esempio più ampia: `avventure/faro.json`.

---

## 1.0.0 — Prima release completa

Stato maturo e coerente: motore ricco, due player, editor visuale completo,
salvataggi, validazione, dialoghi, mappa. Questa versione formalizza tutto il
lavoro svolto finora e introduce il tracciamento delle versioni.

Contenuto della 1.0.0 (rispetto alla 0.9.0):

- **Mappa testuale dell'avventura** (`advcore/mappa.py`, voce «Mappa»
  nell'editor): le stanze sono disegnate come riquadri ASCII collegati seguendo
  le uscite cardinali, con il conteggio degli oggetti in ciascuna e, sotto, la
  distribuzione completa degli oggetti, i collegamenti non cardinali
  (su/giù/dentro/fuori) e le stanze non posizionabili.
- **Navigazione con Tab**: nell'editor, Tab e Shift+Tab spostano il fuoco come
  le frecce Giù/Su (prima urwid li ignorava). Le frecce continuano a funzionare.
- Tracciamento delle versioni: `__version__` in `advcore`, mostrato in editor e
  player; questo file di cronologia.

---

## Cronologia precedente (tappe di sviluppo)

Le versioni dalla 0.1.0 alla 0.9.0 ricostruiscono, a posteriori, le tappe con
cui il progetto è cresciuto.

### 0.9.0 — Rifiniture e comodità
- Comando di gioco **`aiuto`** (elenca i comandi) e **`riavvia`** (ripristina lo
  stato iniziale; il motore ne fa un'istantanea alla creazione).
- Editor: **ricerca globale** (per id/nome/testo su stanze, oggetti, verbi,
  regole) e **duplicazione** di stanze, oggetti, verbi e regole con id univoco.

### 0.8.0 — Editor di dialoghi
- Dal form di un oggetto, «Modifica dialogo» costruisce saluto e battute (con
  condizioni ed effetti, riusando gli editor delle regole) senza toccare il JSON.

### 0.7.0 — Personaggi e combinazioni
- Personaggi (png) con dialoghi a menu (battute con `se`/`allora` e «una volta»).
- Oggetti combinabili: «usa X con Y», con corrispondenza simmetrica.

### 0.6.0 — Estensioni del motore
- Contenitori (apri/chiudi, metti X in Y), indumenti (indossa/togli),
  punteggio e conteggio mosse, verbi predefiniti sempre disponibili.

### 0.5.0 — Validazione dei riferimenti
- `advcore/validazione.py` e schermata «Verifica»: errori (riferimenti rotti) e
  avvisi (flag mai impostati, ecc.), cliccabili per saltare all'entità.

### 0.4.0 — Salvataggio della partita
- `advcore/salvataggio.py`; comandi `salva`/`carica` nei player.

### 0.3.0 — Editor urwid
- `edit.py`: editor visuale a schermo intero per costruire l'avventura.

### 0.2.0 — Player a tutto schermo
- `play_curses.py`: player ncurses con trascrizione e storico dei comandi.

### 0.1.0 — Nucleo e player base
- `advcore` (modello, storage JSON, parser, regole, motore) e `play.py` (CLI).
- Il principio cardine: il motore è senza I/O — `Motore.esegui(str) -> str`.
