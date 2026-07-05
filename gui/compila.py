# SPDX-License-Identifier: GPL-3.0-or-later
"""Compilazione di un'avventura in un eseguibile autonomo (PyInstaller).

Genera un piccolo progetto di build (l'avventura come ``avventura.json`` + un
file ``.spec``) e invoca PyInstaller per produrre un eseguibile che apre
direttamente quell'avventura tramite Pasifae Play.

La logica è tenuta separata dalla GUI così da poter essere collaudata senza
interfaccia: l'editor si limita a chiamarla in un thread di lavoro.
"""
from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from advcore import salva_mondo

RADICE = Path(__file__).resolve().parent.parent


def disponibile() -> bool:
    """Vero se PyInstaller è importabile in questo interprete."""
    return importlib.util.find_spec("PyInstaller") is not None


def nome_sicuro(titolo: str | None) -> str:
    """Nome di file ammissibile a partire dal titolo dell'avventura."""
    base = re.sub(r"[^\w\-]+", "_", (titolo or "Avventura").strip()).strip("_")
    return base or "Avventura"


def _testo_spec(entry: Path, radice: Path, avv: Path, assets: Path,
                nome: str, icona: Path | None,
                immagini: list[Path] | None = None) -> str:
    icona_val = repr(str(icona)) if icona and icona.exists() else "None"
    # le illustrazioni delle stanze vanno alla radice del bundle, accanto ad
    # avventura.json: il player le risolve rispetto al JSON
    extra = "".join(f",\n           ({str(img)!r}, '.')"
                    for img in (immagini or []))
    return f"""# -*- mode: python ; coding: utf-8 -*-
# Generato da Pasifae Editor — compilazione di un'avventura autonoma.
import os

a = Analysis(
    [{str(entry)!r}],
    pathex=[{str(radice)!r}],
    binaries=[],
    datas=[({str(avv)!r}, '.'),
           ({str(assets)!r}, os.path.join('gui', 'assets')){extra}],
    hiddenimports=['advcore', 'gui'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name={nome!r},
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon={icona_val},
)
"""


def prepara(mondo, build_dir: str, radice: Path = RADICE,
            origine: str | None = None) -> tuple[str, str]:
    """Scrive ``avventura.json``, le illustrazioni e il ``.spec`` in *build_dir*.

    *origine* è il percorso del JSON dell'avventura in modifica: serve a
    risolvere le illustrazioni delle stanze (nomi file relativi al JSON), che
    vengono copiate nel progetto di build e impacchettate nell'eseguibile.
    Un'immagine riferita ma mancante viene saltata (il player la ignora).
    Ritorna ``(percorso_spec, nome_eseguibile)``.
    """
    build = Path(build_dir)
    build.mkdir(parents=True, exist_ok=True)
    avv = build / "avventura.json"
    salva_mondo(mondo, str(avv))
    immagini = _copia_immagini(mondo, build, origine)
    nome = nome_sicuro(mondo.meta.get("titolo"))
    entry = radice / "gui" / "player.py"
    assets = radice / "gui" / "assets"
    icona = radice / "gui" / "assets" / "pasifae.ico"
    spec = build / f"{nome}.spec"
    spec.write_text(_testo_spec(entry, radice, avv, assets, nome, icona,
                                immagini),
                    encoding="utf-8")
    return str(spec), nome


def _copia_immagini(mondo, build: Path, origine: str | None) -> list[Path]:
    """Copia in *build* le illustrazioni riferite dalle stanze e ne
    restituisce i percorsi copiati (solo quelle che esistono davvero)."""
    if not origine:
        return []
    base = Path(origine).resolve().parent
    copiate: list[Path] = []
    for nome_img in sorted({s.immagine for s in mondo.stanze.values()
                            if getattr(s, "immagine", "")}):
        src = base / nome_img
        if not src.is_file():
            continue
        dest = build / Path(nome_img).name
        shutil.copy2(src, dest)
        copiate.append(dest)
    return copiate


def comando(spec: str, dist: str, work: str) -> list[str]:
    """Comando per invocare PyInstaller con l'interprete corrente."""
    return [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm",
            "--distpath", dist, "--workpath", work, spec]


def compila(mondo, cartella_output: str, radice: Path = RADICE,
            log=None, origine: str | None = None) -> str:
    """Compila *mondo* in un eseguibile dentro *cartella_output*.

    Ritorna il percorso dell'eseguibile prodotto. Solleva ``RuntimeError`` in
    caso di problemi. La funzione è bloccante: chiamarla in un thread.
    """
    def _log(m: str) -> None:
        if log:
            log(m)

    if not disponibile():
        raise RuntimeError(
            "PyInstaller non è installato in questo ambiente.\n"
            "Installalo con:  pip install pyinstaller")

    out = Path(cartella_output)
    out.mkdir(parents=True, exist_ok=True)
    build_dir = Path(tempfile.mkdtemp(prefix="pasifae_build_"))
    dist = build_dir / "dist"
    work = build_dir / "work"
    try:
        spec, nome = prepara(mondo, str(build_dir), radice, origine=origine)
        _log(f"Preparazione di «{nome}»…")
        _log("Avvio di PyInstaller (può richiedere qualche minuto)…")
        proc = subprocess.run(
            comando(spec, str(dist), str(work)),
            cwd=str(build_dir), text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if proc.returncode != 0:
            coda = (proc.stdout or "").strip().splitlines()[-12:]
            _log("\n".join(coda))
            raise RuntimeError(
                "PyInstaller ha restituito un errore "
                f"(codice {proc.returncode}). Dettagli nel log.")
        prodotto = _trova_prodotto(dist, nome)
        if prodotto is None:
            raise RuntimeError("Eseguibile non trovato dopo la compilazione.")
        dest = out / prodotto.name
        if dest.exists():
            shutil.rmtree(dest) if dest.is_dir() else dest.unlink()
        shutil.move(str(prodotto), str(dest))
        _log(f"Fatto: {dest}")
        return str(dest)
    finally:
        shutil.rmtree(build_dir, ignore_errors=True)


def _trova_prodotto(dist: Path, nome: str) -> Path | None:
    """L'eseguibile (one-file) o la cartella (one-dir) prodotti da PyInstaller."""
    if not dist.exists():
        return None
    for cand in dist.iterdir():
        if cand.is_file() and cand.stem == nome:   # es. Nome  oppure  Nome.exe
            return cand
    d = dist / nome
    return d if d.is_dir() else None
