# SPDX-License-Identifier: GPL-3.0-or-later
"""Tema grafico condiviso tra player ed editor.

Due palette neutre (scuro / chiaro), pensate per qualsiasi genere di avventura,
e un foglio di stile (QSS) che le applica in modo coerente alle due finestre.
"""
from __future__ import annotations

# tipografia: una sans di sistema, comoda da leggere su tutti gli OS
FONT_TESTO = "'Segoe UI', 'Helvetica Neue', 'Cantarell', system-ui, sans-serif"
FONT_UI = FONT_TESTO
# alternativa "da libro" per il corpo del racconto nel player
FONT_TESTO_GRAZIE = "'Georgia', 'Liberation Serif', 'DejaVu Serif', serif"

PALETTE = {
    "scuro": {
        "bg": "#1b1e24", "sup": "#232730", "barra": "#20242c",
        "testo": "#d9dce3", "muto": "#888e9a", "accento": "#7fa8d8",
        "bordo": "#2d323c", "sel": "#30425a", "ombra": "#15171c",
    },
    "chiaro": {
        "bg": "#f4f1ea", "sup": "#ffffff", "barra": "#ece8df",
        "testo": "#2b2a27", "muto": "#8a857b", "accento": "#4f6f9e",
        "bordo": "#ddd8cd", "sel": "#d6e2f1", "ombra": "#e3ded3",
    },
}


def qss(nome: str = "scuro") -> str:
    p = PALETTE.get(nome, PALETTE["scuro"])
    return f"""
    * {{ font-family: {FONT_UI}; }}
    QWidget {{ background: {p['bg']}; color: {p['testo']}; }}

    /* barre superiori/inferiori e intestazioni */
    #barra {{ background: {p['barra']}; border-bottom: 1px solid {p['bordo']}; }}
    #barra_giu {{ background: {p['barra']}; border-top: 1px solid {p['bordo']}; }}
    #titolo {{ color: {p['testo']}; font-size: 14px; font-weight: 600;
               letter-spacing: 1px; }}
    #stato {{ color: {p['muto']}; font-size: 12px; letter-spacing: 1px; }}
    #sezione {{ color: {p['muto']}; font-size: 11px; font-weight: 600;
                letter-spacing: 2px; }}

    /* trascrizione del player */
    #vista {{ background: {p['bg']}; border: none; padding: 20px 26px;
              selection-background-color: {p['sel']}; }}

    /* riga di comando */
    #prompt {{ color: {p['accento']}; font-size: 16px; font-weight: 700; }}
    #input {{ background: transparent; border: none; color: {p['testo']};
              font-size: 15px; padding: 2px 0; }}
    #cornice_input {{ background: {p['sup']}; border: 1px solid {p['bordo']};
                      border-radius: 9px; }}
    #cornice_input[fuoco="true"] {{ border: 1px solid {p['accento']}; }}

    /* menu */
    QMenuBar {{ background: {p['barra']}; color: {p['testo']};
                border-bottom: 1px solid {p['bordo']}; }}
    QMenuBar::item {{ background: transparent; padding: 6px 12px; }}
    QMenuBar::item:selected {{ background: {p['sel']}; }}
    QMenu {{ background: {p['sup']}; color: {p['testo']};
             border: 1px solid {p['bordo']}; }}
    QMenu::item {{ padding: 6px 24px; }}
    QMenu::item:selected {{ background: {p['sel']}; }}

    /* liste e pannelli dell'editor */
    QListWidget {{ background: {p['sup']}; border: 1px solid {p['bordo']};
                   border-radius: 6px; padding: 4px; outline: none; }}
    QListWidget::item {{ padding: 7px 10px; border-radius: 4px; }}
    QListWidget::item:selected {{ background: {p['sel']}; color: {p['testo']}; }}
    QListWidget::item:hover {{ background: {p['barra']}; }}

    QLineEdit, QPlainTextEdit, QTextEdit#campo {{
        background: {p['sup']}; color: {p['testo']};
        border: 1px solid {p['bordo']}; border-radius: 6px; padding: 7px 9px;
        selection-background-color: {p['sel']}; }}
    QLineEdit:focus, QPlainTextEdit:focus {{ border: 1px solid {p['accento']}; }}

    QLabel#campetto {{ color: {p['muto']}; font-size: 12px; }}

    QPushButton {{ background: {p['sup']}; color: {p['testo']};
                   border: 1px solid {p['bordo']}; border-radius: 6px;
                   padding: 7px 16px; }}
    QPushButton:hover {{ border: 1px solid {p['accento']}; }}
    QPushButton:pressed {{ background: {p['sel']}; }}
    QPushButton#primario {{ background: {p['accento']}; color: {p['bg']};
                            border: none; font-weight: 600; }}
    QPushButton#primario:hover {{ background: {p['testo']}; }}

    QCheckBox {{ spacing: 8px; }}
    QSplitter::handle {{ background: {p['bordo']}; }}

    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px; }}
    QScrollBar::handle:vertical {{ background: {p['bordo']}; border-radius: 5px;
                                   min-height: 30px; }}
    QScrollBar::handle:vertical:hover {{ background: {p['accento']}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 4px; }}
    QScrollBar::handle:horizontal {{ background: {p['bordo']}; border-radius: 5px;
                                     min-width: 30px; }}
    """
