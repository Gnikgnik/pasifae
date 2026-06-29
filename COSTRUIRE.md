# Pasifae — costruire gli eseguibili (PyInstaller)

Trasforma player ed editor in eseguibili autonomi da doppio click, senza che chi
li usa debba installare Python.

## Preparazione (una volta)
Dentro l'ambiente virtuale del progetto:

    pip install pyinstaller

## Costruire
Dalla cartella del progetto (quella che contiene `player.spec`):

    pyinstaller player.spec
    pyinstaller editor.spec

Gli eseguibili finiti compaiono nella cartella `dist/`:
- `dist/Pasifae-Play`     (il player)
- `dist/Pasifae-Editor`   (l'editor)

Su Windows avranno estensione `.exe`; su macOS otterrai un `.app`.

## Compilare una singola avventura (dall'editor)

Per distribuire **una** avventura come gioco pronto all'uso non serve usare gli
spec a mano: apri l'avventura in **Pasifae Editor** e scegli
**Strumenti ▸ Compila gioco autonomo… (PyInstaller)**. L'editor crea un
eseguibile che, una volta avviato, apre direttamente quell'avventura — il
giocatore non deve installare nulla né conoscere Pasifae.

Sotto il cofano l'editor genera al volo un `.spec` che impacchetta Pasifae Play
insieme all'avventura corrente (inclusa come `avventura.json`); il player, quando
è impacchettato, rileva l'avventura inclusa e la avvia da solo. Vale la stessa
regola d'oro qui sotto: l'eseguibile è per il sistema operativo su cui lo
compili.

## ⚠️ Regola d'oro: niente cross-compilazione
PyInstaller produce un eseguibile **solo per il sistema su cui lo lanci**.
- il `.exe` di Windows va costruito **su Windows**;
- il `.app` di macOS va costruito **su macOS**;
- il binario Linux va costruito **su Linux**.
Vie pratiche per coprirli tutti: una macchina virtuale, un servizio di build
automatica (es. GitHub Actions), o il computer di un amico con quel sistema.

## Cose da sapere
- **Dimensioni**: il pacchetto include le librerie Qt, quindi è grande
  (tipicamente 100–200 MB). È il prezzo di "tutto incluso".
- **Avviso di sicurezza**: su Windows e macOS, un eseguibile non firmato mostra
  un avviso la prima volta ("apri comunque"). Si può firmare in seguito.
- **Avventure**: gli spec includono già la cartella `avventure/`. Per aggiungere
  nuove avventure a un eseguibile *senza* ricostruirlo, mettile in una cartella
  `avventure/` accanto all'eseguibile.
- **Salvataggi**: l'eseguibile scrive le partite salvate in una cartella
  `salvataggi/` accanto a sé.

## Primo collaudo consigliato
Costruisci e prova prima il binario per il *tuo* sistema (Linux), così verifichi
tutto il giro prima di affrontare gli altri sistemi operativi.
