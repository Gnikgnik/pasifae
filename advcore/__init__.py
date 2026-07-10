# SPDX-License-Identifier: GPL-3.0-or-later
"""advcore — nucleo condiviso del motore di avventure testuali.

Editor e player importano da qui. Non contiene I/O di interfaccia: il motore
prende stringhe e restituisce stringhe.
"""

__version__ = "1.18.0"

from .model import Mondo, Stanza, Oggetto, Verbo, Regola, INVENTARIO
from .storage import carica_mondo, salva_mondo
from .salvataggio import (stato_partita, applica_stato,
                          salva_partita, carica_partita)
from .validazione import valida, Problema
from .mappa import mappa_testuale, uscite_visibili
from .parser import Parser, ComandoParser
from .engine import Motore

__all__ = [
    "Mondo", "Stanza", "Oggetto", "Verbo", "Regola", "INVENTARIO",
    "carica_mondo", "salva_mondo",
    "stato_partita", "applica_stato", "salva_partita", "carica_partita",
    "valida", "Problema", "mappa_testuale", "uscite_visibili",
    "Parser", "ComandoParser",
    "Motore",
]
