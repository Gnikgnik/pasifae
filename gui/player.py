# SPDX-License-Identifier: GPL-3.0-or-later
"""Player grafico (PySide6/Qt) per le avventure testuali.

È solo una *vista* sul motore: chiama Motore.esegui(stringa) -> stringa e
disegna il risultato. Look neutro, comparsa morbida del testo, storico dei
comandi e salvataggio/caricamento partita.

Uso:
    python gui/player.py [avventure/faro.json]
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
if str(RADICE) not in sys.path:
    sys.path.insert(0, str(RADICE))

# Da sorgente i dati stanno nella radice del progetto; impacchettato con
# PyInstaller stanno in una cartella temporanea (sys._MEIPASS).
RISORSE = Path(getattr(sys, "_MEIPASS", RADICE))


def _dir_salvataggi() -> str:
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else RADICE
    d = base / "salvataggi"
    d.mkdir(parents=True, exist_ok=True)
    return str(d)

from advcore import carica_mondo, Motore, salva_partita, carica_partita  # noqa: E402
from gui import tema  # noqa: E402

from PySide6.QtCore import Qt, QTimer  # noqa: E402
from PySide6.QtGui import QAction, QActionGroup, QFont  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QTextEdit, QVBoxLayout, QWidget,
)


class InputComando(QLineEdit):
    """Riga di comando con storico navigabile (frecce su/giù)."""

    def __init__(self):
        super().__init__()
        self.storico: list[str] = []
        self._i = 0

    def ricorda(self, testo: str):
        if testo and (not self.storico or self.storico[-1] != testo):
            self.storico.append(testo)
        self._i = len(self.storico)

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Up and self.storico:
            self._i = max(0, self._i - 1)
            self.setText(self.storico[self._i])
            return
        if ev.key() == Qt.Key_Down and self.storico:
            self._i = min(len(self.storico), self._i + 1)
            self.setText(self.storico[self._i] if self._i < len(self.storico) else "")
            return
        super().keyPressEvent(ev)


class Player(QMainWindow):
    def __init__(self, percorso: str | None = None):
        super().__init__()
        from gui import risorse
        self.setWindowIcon(risorse.icona_app())
        self.mondo = None
        self.motore = None
        self.percorso = None
        self.tema = "scuro"
        self.animazione = True
        self._voci: list[tuple[str, str]] = []
        # stato dell'animazione "telescrivente"
        self._anim = QTimer(self)
        self._anim.setInterval(22)
        self._anim.timeout.connect(self._anima_passo)
        self._anim_cuts: list[int] = []
        self._anim_step = 0

        self.setWindowTitle("Pasifae Play")
        self.resize(880, 660)
        self._costruisci_menu()

        centrale = QWidget()
        radice = QVBoxLayout(centrale)
        radice.setContentsMargins(0, 0, 0, 0)
        radice.setSpacing(0)

        self.titolo = QLabel(); self.titolo.setObjectName("titolo")
        self.stato = QLabel(); self.stato.setObjectName("stato")
        self.stato.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        testa = QFrame(); testa.setObjectName("barra")
        h = QHBoxLayout(testa)
        h.setContentsMargins(24, 14, 24, 14)
        h.addWidget(self.titolo); h.addStretch(1); h.addWidget(self.stato)
        radice.addWidget(testa)

        self.vista = QTextEdit(); self.vista.setObjectName("vista")
        self.vista.setReadOnly(True); self.vista.setFrameStyle(QFrame.NoFrame)
        radice.addWidget(self.vista, 1)

        riga = QFrame(); riga.setObjectName("barra_giu")
        hr = QHBoxLayout(riga)
        hr.setContentsMargins(24, 12, 24, 18); hr.setSpacing(12)
        prompt = QLabel("›"); prompt.setObjectName("prompt")
        self.input = InputComando(); self.input.setObjectName("input")
        self.input.setPlaceholderText("scrivi un comando e premi Invio…  (aiuto)")
        self.input.returnPressed.connect(self._invia)
        hr.addWidget(prompt); hr.addWidget(self.input, 1)
        radice.addWidget(riga)

        self.setCentralWidget(centrale)
        self._applica_tema()

        if percorso:
            self._apri_avventura(percorso)
        else:
            self._modo_blank()
        self.input.setFocus()

    # ---------- menu ----------

    def _costruisci_menu(self):
        barra = self.menuBar()

        mf = barra.addMenu("File")
        a_apri = QAction("Apri avventura…", self); a_apri.setShortcut("Ctrl+O")
        a_apri.triggered.connect(self._apri); mf.addAction(a_apri)
        mf.addSeparator()
        a_esci = QAction("Esci", self); a_esci.triggered.connect(self.close)
        mf.addAction(a_esci)

        m = barra.addMenu("Partita")
        self._azioni_partita = []
        for testo, slot, scorc in (("Salva partita…", self._salva, "Ctrl+S"),
                                   ("Carica partita…", self._carica, "Ctrl+L")):
            a = QAction(testo, self); a.setShortcut(scorc)
            a.triggered.connect(slot); m.addAction(a)
            self._azioni_partita.append(a)
        m.addSeparator()
        a_riavvia = QAction("Riavvia", self)
        a_riavvia.triggered.connect(self._riavvia); m.addAction(a_riavvia)
        self._azioni_partita.append(a_riavvia)

        v = barra.addMenu("Visualizza")
        gruppo = QActionGroup(self)
        for etichetta, chiave in (("Tema scuro", "scuro"), ("Tema chiaro", "chiaro")):
            a = QAction(etichetta, self, checkable=True)
            a.setChecked(chiave == self.tema)
            a.triggered.connect(lambda _=False, c=chiave: self._cambia_tema(c))
            gruppo.addAction(a); v.addAction(a)
        v.addSeparator()
        a_anim = QAction("Testo animato", self, checkable=True)
        a_anim.setChecked(self.animazione)
        a_anim.triggered.connect(lambda on: setattr(self, "animazione", on))
        v.addAction(a_anim)

        a = barra.addMenu("Aiuto")
        a_info = QAction("Informazioni", self)
        a_info.triggered.connect(self._informazioni); a.addAction(a_info)

    # ---------- apertura avventura ----------

    def _apri(self):
        base = str(RISORSE / "avventure")
        f, _ = QFileDialog.getOpenFileName(
            self, "Apri avventura", base, "Avventure (*.json)")
        if not f:
            return
        try:
            self._apri_avventura(f)
        except Exception as e:                       # noqa: BLE001
            QMessageBox.warning(self, "Apri avventura",
                                f"Impossibile aprire l'avventura:\n{e}")

    def _apri_avventura(self, percorso: str):
        mondo = carica_mondo(percorso)               # se fallisce, _apri lo segnala
        self.mondo = mondo
        self.motore = Motore(mondo)
        self.percorso = percorso
        self._anim_finisci()
        self._voci.clear()
        titolo = mondo.meta.get("titolo") or "Avventura"
        self.setWindowTitle(f"{titolo} — Pasifae")
        self._abilita_gioco(True)
        self.input.setPlaceholderText("scrivi un comando e premi Invio…  (aiuto)")
        self._mostra(self.motore.avvia(), "risposta")
        self._aggiorna_stato()
        self.input.setFocus()

    def _modo_blank(self):
        self.mondo = None
        self.motore = None
        self.percorso = None
        self._anim_finisci()
        self._voci = [("risposta",
                       "Nessuna avventura aperta.\n\n"
                       "Apri un'avventura da  File ▸ Apri avventura…  (Ctrl+O) "
                       "per cominciare a giocare.")]
        self.setWindowTitle("Pasifae Play")
        self.titolo.setText("Pasifae")
        self.stato.setText("")
        self._abilita_gioco(False)
        self._ridisegna()

    def _abilita_gioco(self, attivo: bool):
        self.input.setEnabled(attivo)
        for a in getattr(self, "_azioni_partita", []):
            a.setEnabled(attivo)
        if not attivo:
            self.input.setPlaceholderText(
                "apri un'avventura da  File ▸ Apri avventura…")

    def _informazioni(self):
        from gui import risorse
        risorse.mostra_informazioni(self, "Pasifae Play")

    # ---------- gioco ----------

    def _invia(self):
        if self.motore is None:
            return                       # nessuna avventura aperta
        if self._anim.isActive():
            self._anim_finisci()        # un Invio durante l'animazione la completa
        testo = self.input.text().strip()
        if not testo:
            return
        self.input.ricorda(testo)
        self.input.clear()
        self._mostra("› " + testo, "comando")
        risposta = self.motore.esegui(testo)
        if risposta:
            self._mostra(risposta, "risposta")
        self._aggiorna_stato()
        if self.mondo.finita:
            self.input.setPlaceholderText("— fine —   (Partita ▸ Riavvia)")

    def _riavvia(self):
        self._anim_finisci()
        self._voci.clear()
        self._mostra(self.motore.riavvia(), "risposta")
        self._aggiorna_stato()
        self.input.setPlaceholderText("scrivi un comando e premi Invio…  (aiuto)")
        self.input.setFocus()

    def _salva(self):
        cartella = _dir_salvataggi()
        f, _ = QFileDialog.getSaveFileName(self, "Salva partita", cartella,
                                           "Salvataggi (*.save *.json)")
        if f:
            salva_partita(self.mondo, f)
            self.statusBar().showMessage(f"Partita salvata in {f}", 4000)

    def _carica(self):
        cartella = _dir_salvataggi()
        f, _ = QFileDialog.getOpenFileName(self, "Carica partita", cartella,
                                           "Salvataggi (*.save *.json)")
        if not f:
            return
        carica_partita(self.mondo, f)
        self._anim_finisci()
        self._voci.clear()
        self._mostra("(partita caricata)\n\n" + self.motore._descrivi_stanza(), "risposta")
        self._aggiorna_stato()
        self.input.setFocus()

    # ---------- vista e animazione ----------

    def _mostra(self, testo: str, genere: str):
        self._voci.append((genere, testo))
        if genere == "risposta" and self.animazione and testo.strip():
            parti = re.findall(r"\S+\s*", testo)
            self._anim_cuts, acc = [], 0
            for p in parti:
                acc += len(p); self._anim_cuts.append(acc)
            self._anim_step = 0
            self._disegna_statico()
            self._anim.start()
        else:
            self._ridisegna()

    def _anima_passo(self):
        self._anim_step += 1
        if self._anim_step >= len(self._anim_cuts):
            self._anim_finisci()
        else:
            self._aggiorna_ultima_voce()

    def _anim_finisci(self):
        self._anim.stop()
        self._anim_cuts = []
        self._anim_step = 0
        self._ridisegna()

    def _blocco_html(self, genere: str, testo: str, p: dict) -> str:
        corpo = html.escape(testo).replace("\n", "<br>")
        stile = (f"font-family:{tema.FONT_TESTO}; font-size:16px; "
                 f"line-height:165%; ")
        if genere == "comando":
            return (f'<div style="{stile}color:{p["muto"]}; '
                    f'margin:2px 0 14px 0;"><i>{corpo}</i></div>')
        return (f'<div style="{stile}color:{p["testo"]}; '
                f'margin:0 0 16px 0;">{corpo}</div>')

    def _scorri_in_fondo(self):
        barra = self.vista.verticalScrollBar()
        barra.setValue(barra.maximum())

    def _ridisegna(self):
        """Ridisegna l'intera cronologia. Costa proporzionalmente alla sua
        lunghezza: usato solo per eventi rari (nuovo messaggio non animato,
        cambio tema, fine animazione), mai per-fotogramma."""
        p = tema.PALETTE[self.tema]
        ultimo = len(self._voci) - 1
        blocchi = []
        for i, (genere, testo) in enumerate(self._voci):
            if (i == ultimo and self._anim_cuts
                    and self._anim_step < len(self._anim_cuts)):
                testo = testo[:self._anim_cuts[self._anim_step]]
            blocchi.append(self._blocco_html(genere, testo, p))
        self.vista.setHtml("".join(blocchi))
        self._scorri_in_fondo()

    def _disegna_statico(self):
        """Ridisegna tutta la cronologia tranne l'ultima voce (quella che sta
        per animarsi) e memorizza il punto in cui inizia, cosicché i singoli
        fotogrammi dell'animazione tocchino solo quella voce e non l'intero
        documento (altrimenti il ridisegno rallenta con la partita e sotto
        Linux produce un fastidioso farfallio)."""
        p = tema.PALETTE[self.tema]
        blocchi = [self._blocco_html(g, t, p) for g, t in self._voci[:-1]]
        self.vista.setHtml("".join(blocchi))
        cursore = self.vista.textCursor()
        cursore.movePosition(cursore.MoveOperation.End)
        self._anim_anchor = cursore.position()
        self._aggiorna_ultima_voce()

    def _aggiorna_ultima_voce(self):
        p = tema.PALETTE[self.tema]
        genere, testo = self._voci[-1]
        if self._anim_cuts and self._anim_step < len(self._anim_cuts):
            testo = testo[:self._anim_cuts[self._anim_step]]
        cursore = self.vista.textCursor()
        cursore.setPosition(self._anim_anchor)
        cursore.movePosition(cursore.MoveOperation.End, cursore.MoveMode.KeepAnchor)
        cursore.removeSelectedText()
        cursore.insertHtml(self._blocco_html(genere, testo, p))
        self._scorri_in_fondo()

    def _aggiorna_stato(self):
        if self.mondo is None:
            self.titolo.setText("Pasifae"); self.stato.setText(""); return
        self.titolo.setText(self.mondo.meta.get("titolo", "Avventura"))
        self.stato.setText(
            f"punteggio {self.mondo.punteggio}    ·    turni {self.mondo.mosse}")

    # ---------- tema ----------

    def _cambia_tema(self, nome: str):
        self.tema = nome
        self._applica_tema()
        self._ridisegna()

    def _applica_tema(self):
        self.setStyleSheet(tema.qss(self.tema))


def _avventura_inclusa() -> str | None:
    """Se l'eseguibile è stato compilato con un'avventura allegata
    (Pasifae Editor ▸ Compila gioco), restituisce il suo percorso."""
    p = RISORSE / "avventura.json"
    return str(p) if p.exists() else None


def main():
    percorso = sys.argv[1] if len(sys.argv) > 1 else _avventura_inclusa()
    app = QApplication(sys.argv)
    app.setApplicationName("Pasifae")
    app.setApplicationDisplayName("Pasifae Play")
    from gui import risorse
    app.setWindowIcon(risorse.icona_app())
    app.setFont(QFont("Segoe UI", 10))
    Player(percorso).show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
