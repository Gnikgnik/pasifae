# SPDX-License-Identifier: GPL-3.0-or-later
"""Player da riga di comando (stdin/stdout).

Guscio minimale attorno a advcore.Motore: legge una riga, la passa a
esegui(), stampa la risposta. Dimostra il principio "motore senza I/O" prima
di aggiungere il vero player ncurses. Uso:

    python3 play.py avventure/caverna.json
"""

import sys
from pathlib import Path

# permette di lanciare lo script da qualunque cartella
sys.path.insert(0, str(Path(__file__).resolve().parent))

from advcore import (carica_mondo, Motore, salva_partita, carica_partita)
from advcore import __version__ as VERSIONE


def _percorso_salvataggio(nome: str) -> Path:
    return Path("salvataggi") / f"{nome}.sav"


def _gestisci_meta(riga: str, mondo, motore) -> str | None:
    """Intercetta i comandi che fanno I/O su file (salva/carica), che non
    competono al motore. Ritorna un messaggio se gestito, altrimenti None."""
    parti = riga.split(maxsplit=1)
    cmd = parti[0].lower()
    nome = parti[1].strip() if len(parti) > 1 else "partita"
    if cmd in ("salva", "save"):
        f = _percorso_salvataggio(nome)
        try:
            salva_partita(mondo, f)
            return f"Partita salvata in «{f}»."
        except Exception as e:                       # noqa: BLE001
            return f"Errore nel salvataggio: {e}"
    if cmd in ("carica", "load"):
        f = _percorso_salvataggio(nome)
        if not f.exists():
            return f"Nessun salvataggio «{f}»."
        try:
            carica_partita(mondo, f)
            return "Partita caricata.\n\n" + motore.esegui("guarda")
        except Exception as e:                       # noqa: BLE001
            return f"Errore nel caricamento: {e}"
    if cmd in ("riavvia", "ricomincia", "restart"):
        return "Partita riavviata.\n\n" + motore.riavvia()
    return None


def main() -> None:
    percorso = sys.argv[1] if len(sys.argv) > 1 else "avventure/caverna.json"
    mondo = carica_mondo(percorso)
    motore = Motore(mondo)

    riga = f"Pasifae · motore advcore v{VERSIONE}"
    gv = mondo.meta.get("versione")
    if gv:
        riga += f"  ·  gioco v{gv}"
    print(riga)
    print(motore.avvia())
    print()
    print("(digita 'aiuto' per l'elenco dei comandi · "
          "'salva [nome]' / 'carica [nome]' / 'riavvia' per la partita · "
          "'fine' per uscire)")

    while True:
        try:
            riga = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nA presto.")
            break
        if not riga:
            continue
        if not mondo.conversazione and riga.lower() in ("fine", "esci", "quit", "q"):
            print("A presto.")
            break

        meta = _gestisci_meta(riga, mondo, motore)
        if meta is not None:
            print(meta)
            continue

        print(motore.esegui(riga))

        if mondo.finita:
            print("\n--- Partita conclusa ---")
            break


if __name__ == "__main__":
    main()
