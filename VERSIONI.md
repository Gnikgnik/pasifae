# Pasifae — cronologia delle versioni

## gui 2.5.0
Due cambiamenti nell'editor:
- **"Gestione timer…" lascia il menu Strumenti**: i timer sono ora una
  categoria della colonna a sinistra (fra "Flag iniziali" e "Metadati"),
  con +Nuovo/Elimina come i flag — la vecchia finestra `DialogoTimer`
  è stata rimossa, sostituita dalla stessa lista/dettaglio delle altre
  categorie.
- **Illustrazione di una stanza condizionabile**: nel catalogo degli
  effetti delle regole, nuova voce **"cambia illustrazione di una
  stanza"** (`cambia_immagine`): sostituisce l'immagine mostrata per una
  stanza a runtime (un'immagine vuota ripristina il default). Impacchettata
  automaticamente anche in "Compila gioco autonomo" e controllata dal
  pannello problemi (riferimento a stanza inesistente, file mancante) come
  l'illustrazione di default. Vedi advcore 1.20.0.

## gui 2.4.0
Nuovo checkbox **nascosto** nel form Oggetto (accanto a scenario):
un oggetto nascosto non compare nella descrizione della stanza né nel
contenuto di un contenitore aperto, e il giocatore non può esaminarlo
o prenderlo per nome finché resta tale — non solo "non elencato" come
scenario, ma proprio irraggiungibile. Nel catalogo degli effetti delle
regole, nuove voci **"mostra oggetto nascosto"** / **"nascondi
oggetto"** (`mostra_oggetto`/`nascondi_oggetto`) per rivelarlo o
nasconderlo di nuovo. Vedi advcore 1.19.0.

## gui 2.3.1
Nel form Oggetto, nuovo campo **voce «0.» del menu dialogo** (accanto a
«congedo»): personalizza l'etichetta della riga di uscita nel menu
delle battute (default «saluta e vai», anche questo senza senso su un
terminale). Vedi advcore 1.18.1.

## gui 2.3.0
Nell'editor, il form Oggetto guadagna il campo **congedo**, accanto a
«saluto»: personalizza il messaggio di chiusura di un dialogo (vuoto =
resta «Saluti «nome»»). Nel catalogo degli effetti delle regole, nuova
voce **"avvia dialogo (saluto + battute)"** (`avvia_dialogo`): apre il
dialogo di un oggetto qualsiasi — non serve spuntare "personaggio (png)"
— agganciandolo al verbo che si preferisce tramite una regola dell'autore.
Pensato per oggetti come un terminale, che si "usano" e non si
"parlano". Vedi advcore 1.18.0.

## gui 2.2.0
Mini-mappa nel Pasifae Player: una terza colonna a destra (dopo
illustrazione e trascrizione) che si popola via via che si esplora
l'avventura. Sola lettura — nessun drag, nessun menu contestuale, solo
`PannelloImmagine`-style — mostra un riquadro per ogni stanza già
visitata (evidenziata quella corrente), una linea per ogni collegamento
fra due stanze visitate. Dalle stanze visitate, le uscite verso
l'ignoto restano un breve trattino verso il bordo per le direzioni
cardinali, o un'etichetta "altre uscite: …" per quelle non cardinali
(su/giù/dentro/fuori): indicano che di là si può andare, senza
svelarne nome o contenuto — le uscite condizionate non ancora
sbloccate restano del tutto invisibili. I riquadri non hanno una
dimensione fissa: si ridimensionano da soli fra un minimo leggibile e un
massimo (130–220px) per riempire lo spazio del pannello in base a quante
stanze sono visitate in quel momento — poche stanze restano comode e
centrate, molte si stringono fino al minimo e poi si scorrono. Nuovo
toggle "Mappa" nel menu Visualizza; sotto `Player.LARGHEZZA_MIN_MAPPA`
(900px) la mappa lascia il posto alla colonna di lettura, che resta la
priorità su finestre strette. Nuovo modulo `gui/mappa_player.py`; la
griglia automatica (`_posizioni_griglia`) è stata estratta a livello di
modulo in `gui/mappa.py` per essere condivisa con l'editor.

## gui 2.1.0
La mappa lascia la colonna fissa dello splitter e diventa un **pannello
dock** (`QDockWidget`, ancorato a destra di default): ridimensionabile,
richiudibile e anche flottante fuori dalla finestra principale. Con il
dock chiuso, categorie/elementi/dettaglio recuperano tutto lo spazio: il
layout a quattro colonne fisse della 2.0.0 lasciava troppo poco margine al
form di modifica su schermi non ampi. Nuovo toggle "Pannello mappa" nel
menu Strumenti (Ctrl+Shift+M); "Adatta la mappa" ed "Esporta la mappa come
PNG" restano invariati. Da staccata, la finestra della mappa ha i pulsanti
nativi di minimizza/massimizza/chiudi (il `Qt::Tool` di default non li
mostra): a tutto schermo senza doverla ridimensionare a mano.


## gui 2.0.0
Il ribaltone della direzione «mappa come piano di lavoro»: layout a quattro
pannelli (categorie | elementi | **mappa** | dettaglio). Un clic su un nodo
seleziona la stanza nel dettaglio, la selezione nella lista evidenzia il
nodo; ogni modifica riallinea la mappa in modo differito
(`QTimer.singleShot`, mai dentro i gestori della scena) e una stanza nata
dalla mappa entra subito nella lista degli elementi. `FinestraMappa` non
serve più: Ctrl+M adatta la vista, l'export PNG resta nel menu Strumenti.


## gui 1.16.3
**Bugfix**: su Linux il menu contestuale scattava alla *pressione* del
destro, subito dopo il gesto che avvia un collegamento fra stanze — la
linea provvisoria sotto il cursore ingannava `itemAt`, così si apriva
sempre «Nuova stanza» invece del menu delle uscite o del trascinamento.
Ora, durante un collegamento, il menu del canvas è soppresso e il nodo si
cerca fra tutti gli item nel punto.


## gui 1.16.2
**Bugfix**: bonificato un segfault in garbage collection («Garbage-
collecting, no Python frame») nella mappa. I collegamenti non vengono più
distrutti e ricreati a ogni pixel di trascinamento (item persistenti, si
aggiorna solo la geometria); i riferimenti Python agli item vengono
lasciati andare *prima* che `scena.clear()` o la chiusura della finestra
eliminino il lato C++; anche i dialoghi della nuova stanza sono differiti
fuori dal menu contestuale.


## gui 1.16.1
**Bugfix**: su Wayland, aprire un `QMenu` o un dialogo modale dentro
`mouseReleaseEvent` — col grab del mouse della scena ancora attivo —
falliva il grabbing dei popup e poteva mandare in segfault l'editor. Il
menu delle uscite e il dialogo «Nuova uscita» ora si aprono con
`QTimer.singleShot(0, ...)`, a evento concluso e grab rilasciato.


## gui 1.16.0
Quarto passo della «mappa come piano di lavoro»: trascinando col tasto
destro da una stanza all'altra si crea un'uscita (dialogo con le sole
direzioni libere e ritorno opzionale); il clic destro fermo su una stanza
elenca le uscite da eliminare; il clic destro sul vuoto crea una stanza
nel punto scelto. L'editor riallinea la lista degli elementi alla
chiusura della mappa.


## gui 1.15.0
Terzo passo della «mappa come piano di lavoro»: doppio clic su un
riquadro seleziona la stanza nel form dell'editor (come già nella
Concatenazione dei puzzle). Legenda aggiornata.


## gui 1.14.0
Secondo passo della «mappa come piano di lavoro»: i riquadri delle stanze
si trascinano, i collegamenti seguono in tempo reale (retta se libera,
curva se attraversa un riquadro), la disposizione vive in
`meta["editor"]["mappa"]` — il motore la ignora e `storage` la conserva
senza modifiche. «Riordina» torna al layout automatico.


## gui 1.13.0
Nuova finestra **«Concatenazione dei puzzle»** (menu Strumenti): mostra ad
albero, a ritroso dai finali, la catena dei passi — regole, dialoghi,
esiti di scontro e uscite condizionate, con requisiti e produttori;
doppio clic per navigare all'elemento. Le condizioni «flag uguale a
falso» non concatenano (chiedono l'assenza del progresso).


## gui 1.12.0
Il pannello illustrazione del player passa da una striscia con tetto a
240px a una **colonna a tutta altezza** in uno splitter orizzontale:
immagine molto più grande, larghezza regolabile e ricordata tra le
sessioni. La stessa colonna arriva anche nella finestra «Prova
l'avventura» (l'anteprima nell'editor resta in modalità striscia).


## gui 1.11.0
Nel form della regola il campo preposizione dell'innesco accetta più voci
separate da virgola («su, con»): una sola regola scatta con «usa chiave
su automa» e «usa chiave con automa». I riassunti mostrano «su/con»; una
voce sola resta stringa semplice.


## gui 1.10.0
**Illustrazioni di stanza**: nel form della stanza il campo
«illustrazione» (Sfoglia… copia il file scelto accanto al JSON per la
portabilità dell'avventura, Togli lo sgancia senza cancellarlo, la
duplicazione della stanza la porta con sé); il player e la finestra
«Prova l'avventura» la mostrano in un pannello dedicato
(`gui/immagine.py`, interruttore in Visualizza, ricordato tra le
sessioni); «Compila gioco autonomo» impacchetta le immagini riferite
nell'eseguibile; «Verifica» avvisa se un'illustrazione non è accanto al
JSON.


## gui 1.9.1
**Bugfix**: il dialogo «Salva partita» non imponeva un'estensione — un
nome come «lab1» creava un file senza suffisso che «Carica partita» (filtro
`*.save *.json`) non mostrava più. Ora il player aggiunge `.save` quando
manca, e il filtro di caricamento include i `.sav` dei player da terminale
e la voce «Tutti i file» per i salvataggi nati senza estensione.


## gui 1.9.0
Nel catalogo degli effetti, voci per i nuovi `apri_oggetto`/`chiudi_oggetto`
del motore (advcore 1.12.0), con selettore dei soli contenitori; aggiornati
i riferimenti incrociati.


## advcore 1.20.0
**Illustrazione di stanza sostituibile a runtime**: nuovo campo
`Stanza.immagine_attuale` (non nei dati statici dell'avventura, solo
nello stato di gioco — persiste nei salvataggi come `visitate`) e nuovo
effetto di regola `{"cambia_immagine": id_stanza, "immagine": nome_file}`:
un'illustrazione vuota ripristina il default dichiarato dall'autore
(`Stanza.immagine`, mai toccato). La logica di apertura dialogo/mostra
oggetto ecc. sceglie sempre `immagine_attuale or immagine`; l'effetto
non richiede che la stanza cambiata sia quella corrente.


## advcore 1.19.0
**Oggetti nascosti**: `props["nascosto"]` toglie un oggetto dalla vista
del giocatore — non compare nella descrizione della stanza né nel
contenuto di un contenitore aperto, e `Mondo.in_scope()` (usato dal
parser per risolvere i nomi) lo esclude, quindi «esamina»/«prendi» su
di lui rispondono come per un oggetto che non esiste («Non vedo nessun
"X" qui.»), non solo «non elencato» — quella era già la funzione di
`scenario`. Ignorato anche da «prendi tutto». Due nuovi effetti di
regola: `{"mostra_oggetto": id}` lo rivela (`nascosto = False`),
`{"nascondi_oggetto": id}` lo rinasconde. Pensato per un oggetto che
il giocatore deve prima scoprire (aprendo un cassetto, spostando un
quadro) prima di poterci interagire.


## advcore 1.18.1
**`props["etichetta_uscita"]`**: personalizza la voce «0.» del menu di
dialogo (`menu_dialogo` in `advcore/rules.py`), per default `"saluta e
vai"` — invariato senza la prop. Emerso testando l'avventura con il
terminale (1.18.0): il congedo era personalizzabile, ma la riga del
menu che lo introduce no.


## advcore 1.18.0
Dialoghi disaccoppiati dal verbo "parla" e dal ruolo di "personaggio":
- **`props["congedo"]`**: personalizza il messaggio di chiusura di un
  dialogo (per default, invariato, `"Saluti «nome»."`). Utile per un
  oggetto che non è un personaggio — un terminale, per cui salutare non
  ha senso.
- **Nuovo effetto di regola `{"avvia_dialogo": id_oggetto}`**: apre il
  dialogo (saluto + battute) di un oggetto qualunque, non solo dei png.
  Una regola dell'autore può agganciarlo a qualsiasi verbo — es. "usa
  terminale" invece di "parla con terminale", perché un terminale si usa,
  non si parla. La logica di apertura (`avvia_conversazione`,
  `battute_disponibili`, `menu_dialogo`) è stata estratta da `Motore` a
  funzioni pure in `advcore/rules.py`, condivise dal verbo builtin
  "parla" e dal nuovo effetto — nessun cambiamento al comportamento
  esistente di "parla" (resta bloccato sui non-png). Vedi gui 2.3.0 per
  il supporto nell'editor.


## advcore 1.17.0
Nuova funzione pura `uscite_visibili(mondo, stanza)` in `advcore/mappa.py`
(esportata da `advcore`): le uscite attualmente sbloccate di una stanza
(le condizionate non ancora sbloccate restano fuori) come coppie
(direzione, id_destinazione) — duplica il filtro di
`Motore._uscite_visibili`, ma restituisce anche la destinazione, non solo
l'etichetta, per poter disegnare i collegamenti sulla mappa. Nata per la
mini-mappa del player (gui 2.2.0); nessun cambiamento al comportamento
esistente.


## advcore 1.16.1
Motore: **«prendi tutto»** ora comprende anche il contenuto dei contenitori
aperti visibili nella stanza, annidati compresi (l'inventario e ciò che
contiene restano esclusi). Emerso nel playtest de «Il labirinto»: i tre
libri nella botola andavano presi uno a uno.


## advcore 1.16.0
Nuovo quantificatore **«tutto»/«tutti»** riconosciuto dal parser: il motore
lo espande in prese singole della stanza, ognuna passando dalle regole
dell'autore (gli enigmi che intercettano «prendi <oggetto>» restano
validi). Scenario e non prendibili sono ignorati in silenzio; al buio
serve una luce; con gli altri verbi «tutto» risponde con un messaggio.


## advcore 1.15.0
Nell'innesco a comando di una regola, ogni campo (in particolare la
preposizione) ammette ora **una lista di alternative** — «uno qualsiasi di
questi» — così una sola regola scatta sia con «usa chiave su automa» sia
con «usa chiave con automa». Le stringhe singole restano valide
(retrocompatibile).


## advcore 1.14.0
Nuovo campo opzionale **«immagine»** sulla Stanza: nome file relativo al
JSON dell'avventura. Il motore lo ignora — lo usano le interfacce — ed è
assente dal JSON quando vuoto, così le avventure e i salvataggi esistenti
restano validi.


## advcore 1.13.0
Il comando **«aiuto»** ora elenca solo le sezioni che l'avventura rende
utili (contenitori, indumenti, personaggi, combattenti, punteggio) o per
cui una regola risponde a quel verbo; i verbi ad hoc dichiarati
dall'autore compaiono in una riga «speciali». Vale sia per Pasifae Play
sia per la prova nell'editor.


## advcore 1.12.1
Il parser ora riconosce tutte le **preposizioni articolate** di «in» e
«su» («metti sasso nello zaino», «nell'astuccio», «sulle mensole»): le
forme articolate mancanti dividevano male il comando.


## advcore 1.12.0
Nuovi effetti **`apri_oggetto`/`chiudi_oggetto`**: una regola su
«apri»/«chiudi» che scavalca il verbo predefinito ora può anche commutare
`props["aperto"]`, rendendo possibile il pattern «apribile solo se…»
(serrature, chiavi) sui contenitori condizionati.


## advcore 1.11.1
**Bugfix**: `Mondo.in_scope()` non vedeva un oggetto dentro un contenitore
aperto a sua volta dentro un altro contenitore aperto (es. lente in
calamaio in scrivania) — l'espansione del contenuto si fermava a un solo
livello. Ora è ricorsiva.


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
