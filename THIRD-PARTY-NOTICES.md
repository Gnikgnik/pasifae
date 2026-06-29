# SPDX-License-Identifier: GPL-3.0-or-later
# Note sulle componenti di terze parti

Pasifae è distribuito sotto **GPL-3.0-or-later** (vedi `LICENSE`). Usa alcune
librerie di terze parti, ciascuna con la propria licenza. Questo file è
informativo; quando distribuisci Pasifae — o gli eseguibili creati con
«Compila gioco» — includi queste note e rispetta le rispettive condizioni.

## PySide6 / Qt — LGPL-3.0
L'interfaccia grafica usa **PySide6** (i binding Python ufficiali di **Qt**),
distribuito sotto **LGPL-3.0**. La LGPL è compatibile con la GPLv3.
Quando distribuisci un **eseguibile** che incorpora Qt (i binari di Pasifae o
quelli prodotti da «Compila gioco»), le condizioni LGPL richiedono in particolare
di: accludere le note di licenza di Qt, indicare chiaramente l'uso di Qt/PySide6,
e consentire all'utente la sostituzione della libreria Qt (relinking).
Riferimenti: https://doc.qt.io/qtforpython/licenses.html

## PyInstaller — GPL con eccezione
Lo strumento di packaging **PyInstaller** è rilasciato sotto GPL **con
un'eccezione** che consente di costruire e distribuire eseguibili **senza** che
la licenza di PyInstaller si propaghi all'applicazione impacchettata. Quindi
PyInstaller non impone vincoli aggiuntivi sui giochi compilati: per quelli vale
la licenza scelta da te per Pasifae e le note Qt qui sopra.
Riferimento: https://pyinstaller.org/en/stable/license.html

## urwid — LGPL-2.1
Il front-end da terminale (`edit.py`) usa **urwid**, sotto **LGPL-2.1**.
Riferimento: https://urwid.org/

---
Nota: questo riepilogo non è una consulenza legale. Per una distribuzione
pubblica, verifica i testi di licenza aggiornati delle dipendenze.
