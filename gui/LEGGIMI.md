# Pasifae — interfaccia grafica (PySide6 / Qt)

Viste grafiche sul motore: non contengono logica di gioco, chiamano soltanto
`advcore`. Look neutro (tema scuro o chiaro), su Windows, macOS e Linux.

## Installazione
    pip install pyside6        # consigliato in un ambiente virtuale:
    #  python3 -m venv .venv && source .venv/bin/activate && pip install pyside6

## Player
    python gui/player.py [avventure/tutorial.json]
- Comparsa morbida del testo (a parole; un Invio la completa subito).
- Storico dei comandi con le frecce su/giù.
- Menu Partita: Salva (Ctrl+S) / Carica (Ctrl+L) partita, Riavvia.
- Menu Visualizza: tema scuro/chiaro, «Testo animato» on/off.

## Editor (completo)
    python gui/editor.py                 # parte in un ambiente vuoto
    python gui/editor.py avventure/caverna.json   # apre un'avventura
Tre pannelli: Categorie | Elementi | Dettaglio. Sono modificabili e salvabili
TUTTE le categorie, con creazione (+ Nuovo) ed eliminazione:
- Stanze (nome, descrizione, buio).
- Oggetti: anagrafica e proprietà; sorgente di luce; combattimento; e per i png
  lo stato iniziale, il saluto, le BATTUTE a livelli (con condizioni ed effetti)
  e l'ESITO ALLA SCONFITTA.
- Verbi, Flag iniziali, Metadati.
- Regole: selettore d'innesco (comando / ogni turno / ingresso / timer) e liste
  SE / ALLORA / ALTRIMENTI con un dialogo per ogni condizione/effetto.
Menu File: Nuovo, Apri, Salva (Ctrl+S), Salva con nome, Chiudi (chiede di
salvare se ci sono modifiche), Verifica riferimenti. Avviando senza un file si
parte da un'avventura vuota.
Menu Strumenti:
- «Prova l'avventura…» (Ctrl+P) — anteprima giocabile della versione corrente
  (anche con modifiche non salvate); gira su una copia, quindi i progressi della
  prova non alterano i dati in modifica.
- «Mappa dell'avventura…» (Ctrl+M) — disegno grafico di stanze, collegamenti
  (con senso e condizioni), personaggi e oggetti; con zoom, scorrimento ed
  esportazione in PNG.
- «Gestione timer…» — dichiara i nomi dei timer (riusabili dalle tendine) e
  vedi quanti usi ha ciascuno.
Menu Aiuto: «Informazioni…» mostra la versione dell'editor (vedi VERSIONI.md).
Nelle stanze e negli oggetti l'id (interno, fisso) e il nome (mostrato) sono
distinti: alla creazione vengono chiesti entrambi. I campi timer nelle regole e
negli effetti sono tendine (editabili).
La posizione di un oggetto può essere una stanza, l'inventario oppure un
oggetto contenitore (solo contenitori): nel gioco, aprendo ed esaminando il
contenitore se ne vede il contenuto.

Moduli: gui/tema.py (tema condiviso), gui/regole.py (cataloghi condizioni/effetti).

RICERCA E FILTRI (utili con avventure grandi):
- Tutte le tendine a scelta (oggetti, stanze, png, verbi, flag, timer, luoghi)
  sono filtrabili: digita una parte del nome e l'elenco si restringe
  (corrispondenza "contiene", non sensibile alle maiuscole). Le voci sono
  ordinate alfabeticamente.
- Sopra l'elenco "Elementi" c'è una casella di filtro per restringere
  rapidamente stanze, oggetti o regole per nome o id.

AUTHORING (avventure grandi):
- Le condizioni e gli effetti (SE/ALLORA) si modificano in posizione: pulsante
  "modifica" o doppio clic sulla voce.
- "Duplica" copia la stanza, l'oggetto o la regola selezionata.
- Strumenti > "Pannello problemi" (Ctrl+J): elenca dal vivo riferimenti rotti,
  uscite cieche, posizioni non valide e stanze irraggiungibili; doppio clic per
  saltare all'elemento.
- Strumenti > "Dove e' usato...": elenca dove un flag, un oggetto o una stanza
  (quello selezionato) sono usati nell'avventura.
- Strumenti > "Compila gioco autonomo... (PyInstaller)": crea un eseguibile che
  apre direttamente l'avventura corrente, da distribuire a chi non ha Pasifae.
  Richiede PyInstaller (`pip install pyinstaller`); la compilazione gira in
  sottofondo con una finestra di avanzamento e puo' richiedere qualche minuto.

TEST AUTOMATICI:
- I test della logica (motore, salvataggio, regole) si lanciano come script,
  es.  python3 test_motore.py
- I test dell'interfaccia usano pytest-qt:
    pip install -r requirements-dev.txt
    pytest test_gui.py            # oppure: python3 test_gui.py
  Coprono le regressioni note (crash al cambio innesco, Invio nell'anteprima,
  ordine di 'scarta oggetto', eliminazione regole) e i comportamenti chiave.

TESTO DINAMICO (nelle descrizioni e nei messaggi):
- {flag} inserisce il valore di un flag; valori speciali {punteggio},
  {mosse}, {stanza} (nome della stanza corrente).
- [flag: testo] mostra il testo solo se il flag e' vero; [flag: a | b]
  sceglie tra due varianti; [flag=valore: ...] confronta con un valore;
  [prima_volta: ...] vale solo alla prima visita della stanza.

CONDIZIONI (SE) PIU' POTENTI:
- Confronti sui flag numerici: uguale, maggiore (>), minore (<), almeno
  (>=), al piu' (<=).
- Casella «NON» in una condizione: la regola scatta se quella condizione
  e' FALSA.
- Modalita' delle condizioni: «tutte vere (E)» (predefinita) oppure
  «almeno una vera (O)» per combinare in OR.
