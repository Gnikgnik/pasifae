# Pasifae — versioni dell'interfaccia grafica (editor e player)

## 1.5.0
Pasifae Editor: nuova voce «Strumenti ▸ Compila gioco autonomo… (PyInstaller)».
Genera un eseguibile che apre direttamente l'avventura corrente, senza bisogno
di Pasifae installato. La build gira in un thread con finestra di avanzamento; il
player rileva l'avventura inclusa nel pacchetto e la avvia da solo.

## 1.4.0
Pasifae Play: voce «Aiuto ▸ Informazioni» con il logo (come nell'editor) e
**modalità blank** all'avvio senza avventura — il player parte vuoto e si apre
un'avventura da «File ▸ Apri avventura…» (Ctrl+O). Identità grafica Pasifae
(icona, titoli, dialogo Informazioni) in editor e player.

## 1.3.0
Condizioni più potenti nelle regole: casella «NON» per negare una condizione,
modalità «almeno una vera (OR)» oltre a «tutte vere (E)», e nuovi confronti
numerici sui flag (< , ≤ , ≥). Richiede motore advcore >= 1.11.0.

## 1.2.1
Suggerimenti (tooltip) sulla sintassi del testo dinamico nei campi di
descrizione e nei messaggi (richiede motore advcore >= 1.10.0).

## 1.2.0
Attrito di authoring ridotto: le voci di condizioni/effetti si modificano in
posizione (pulsante «modifica» o doppio clic), non solo aggiungi/rimuovi;
«Duplica» per stanze, oggetti e regole. Nuovo pannello «Problemi» (Ctrl+J) che
elenca dal vivo riferimenti rotti, uscite cieche, posizioni non valide e stanze
irraggiungibili, con doppio clic per andare all'elemento. Nuova voce «Dove è
usato…» per flag, oggetti e stanze. Corretta l'eliminazione delle regole. Aggiunta una suite di test
automatici dell'interfaccia (pytest-qt, test_gui.py) che blocca le regressioni.

## 1.1.0
Ricerca incrementale nelle tendine: digitando si filtrano le voci (corrispondenza
«contiene», non sensibile alle maiuscole); le tendine di oggetti, stanze, png e
verbi sono ora filtrabili e ordinate alfabeticamente. Nuova casella di filtro
sopra l'elenco «Elementi» per restringere stanze/oggetti/regole. Pensato per
avventure con molti elementi.

## 1.0.1
Nuovo effetto «scarta oggetto» disponibile nelle regole (richiede motore
advcore ≥ 1.9.0): toglie dal gioco un oggetto scarico/rovinato, con messaggio
opzionale. La posizione di un oggetto può ora essere anche un contenitore.

## 1.0.0
Prima versione numerata. Editor completo: stanze (id e nome distinti, uscite
semplici e condizionate), oggetti (proprietà, luce, combattimento, dialoghi a
livelli, esito di scontro), verbi, regole (inneschi comando/turno/ingresso/
timer, condizioni ed effetti), flag, metadati. Strumenti: prova giocabile,
mappa grafica, gestione timer. File: nuovo/apri/salva/salva con nome/chiudi con
conferma. Player con comparsa morbida del testo, storico comandi, salva/carica
partita. Tema scuro/chiaro condiviso.
