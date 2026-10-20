"""Funzioni di supporto dell'app: caricamento dati e foto dall'Excel, logo, paginazione."""
import base64
import io
import math
from pathlib import Path

import pandas as pd
import streamlit as st
from openpyxl import load_workbook
from PIL import Image, ImageDraw, ImageFont, ImageOps

CARTELLA = Path(__file__).resolve().parent
EXCEL = CARTELLA / "questionario.xlsx"
# LOGO_OK.png con il bianco reso trasparente, per poterlo appoggiare sullo sfondo colorato
LOGO = CARTELLA / "logo_trasparente.png"


def _miniatura(dati: bytes, lato: int = 400) -> bytes:
    """Ritaglio quadrato e leggero della foto: alcune originali superano 1 MB."""
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(dati)))
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        sfondo = Image.new("RGB", img.size, "white")
        sfondo.paste(img, mask=img.getchannel("A"))
        img = sfondo
    else:
        img = img.convert("RGB")
    # Centratura spostata verso l'alto, dove di solito sta il volto
    img = ImageOps.fit(img, (lato, lato), centering=(0.5, 0.35))
    buffer = io.BytesIO()
    img.save(buffer, "JPEG", quality=85)
    return buffer.getvalue()


def _segnaposto(iniziali: str, lato: int = 400) -> bytes:
    """Immagine con le iniziali, per chi non ha caricato la foto."""
    img = Image.new("RGB", (lato, lato), "#d9dee8")
    disegno = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=lato // 3)
    disegno.text((lato / 2, lato / 2), iniziali, fill="#5b6478", font=font, anchor="mm")
    buffer = io.BytesIO()
    img.save(buffer, "JPEG", quality=85)
    return buffer.getvalue()


def _testo(valore) -> str:
    return "" if pd.isna(valore) else str(valore).strip()


@st.cache_data(show_spinner="Caricamento profili…")
def _carica(percorso: str, modificato: float) -> pd.DataFrame:
    df = pd.read_excel(percorso)
    df.columns = df.columns.str.strip()

    # Le foto non sono dentro le celle: sono immagini appoggiate sopra la colonna "Foto",
    # ancorate alla riga del profilo (riga 0 = intestazione, riga 1 = primo profilo).
    foglio = load_workbook(percorso).active
    intestazioni = [_testo(cella.value) for cella in foglio[1]]
    colonna_foto = intestazioni.index("Foto")
    foto_per_riga = {}
    for immagine in foglio._images:
        ancora = getattr(immagine.anchor, "_from", None)
        if ancora is not None and ancora.col == colonna_foto:
            foto_per_riga[ancora.row - 1] = _miniatura(immagine._data())

    # Solo i dati da mostrare: email, telefono e difficoltà non vengono nemmeno caricati
    profili = []
    for indice, riga in df.iterrows():
        parti = _testo(riga["Cognome e Nome"]).split()
        if not parti:
            continue
        # Nel modulo il campo è "Cognome Nome": la prima parola è il cognome
        cognome, nome = parti[0], " ".join(parti[1:])
        foto = foto_per_riga.get(indice) or _segnaposto((nome[:1] + cognome[:1]).upper())
        profili.append({
            "nome": nome,
            "cognome": cognome,
            "nome_completo": f"{nome} {cognome}".strip(),
            "nazione": " ".join(_testo(riga["Nazione"]).split()) or "Non indicata",
            "citta": " ".join(_testo(riga["Città"]).split()),
            "motivazione": _testo(riga["Motivazione"]),
            "foto_uri": "data:image/jpeg;base64," + base64.b64encode(foto).decode(),
        })

    return (
        pd.DataFrame(profili)
        .sort_values(["nazione", "cognome", "nome"], key=lambda colonna: colonna.str.lower())
        .reset_index(drop=True)
    )


def carica_profili() -> pd.DataFrame:
    # La data di modifica fa ricaricare la cache quando l'Excel viene aggiornato
    return _carica(str(EXCEL), EXCEL.stat().st_mtime)


def elenco_nazioni(profili: pd.DataFrame) -> list[str]:
    """Solo le nazioni presenti nei dati, dalla più scelta alla meno scelta."""
    conteggi = profili["nazione"].value_counts()
    return sorted(conteggi.index, key=lambda nazione: (-conteggi[nazione], nazione.lower()))


def elenco_citta(profili: pd.DataFrame, nazione: str | None) -> list[str]:
    """Città presenti nei dati, ristrette alla nazione scelta (se c'è), in ordine alfabetico."""
    if nazione:
        profili = profili[profili["nazione"] == nazione]
    return sorted({citta for citta in profili["citta"] if citta}, key=str.lower)


def cerca(profili: pd.DataFrame, nazione: str | None, citta: str | None) -> pd.DataFrame:
    """Profili della nazione e/o della città scelte (con entrambe valgono entrambe)."""
    if nazione:
        profili = profili[profili["nazione"] == nazione]
    if citta:
        profili = profili[profili["citta"].str.lower() == citta.lower()]
    return profili


@st.cache_data
def _data_uri(percorso: str, modificato: float, tipo: str) -> str:
    return f"data:{tipo};base64," + base64.b64encode(Path(percorso).read_bytes()).decode()


def logo_uri() -> str:
    return _data_uri(str(LOGO), LOGO.stat().st_mtime, "image/png")


@st.cache_data
def _icona(percorso: str, modificato: float) -> Image.Image:
    """Quadrato col mappamondo del logo, per l'icona della scheda del browser."""
    logo = Image.open(percorso).convert("RGBA")
    return logo.crop((640, 0, 1045, 405))


def icona_pagina() -> Image.Image:
    return _icona(str(LOGO), LOGO.stat().st_mtime)


# --- Paginazione ---------------------------------------------------------------

def pagina_corrente(totale_elementi: int, per_pagina: int, chiave: str) -> tuple[int, int]:
    totale_pagine = max(1, math.ceil(totale_elementi / per_pagina))
    pagina = min(max(1, st.session_state.get(chiave, 1)), totale_pagine)
    st.session_state[chiave] = pagina
    return pagina, totale_pagine


def _vai_a_pagina(chiave: str, pagina: int) -> None:
    st.session_state[chiave] = pagina
    st.session_state[f"{chiave}_scorri"] = True


def scorri_ai_risultati(chiave: str, forza: bool = False) -> None:
    """Porta in vista l'inizio dei risultati dopo una nuova ricerca o un cambio pagina."""
    if st.session_state.pop(f"{chiave}_scorri", False) or forza:
        st.html(
            "<script>"
            "setTimeout(() => {"
            "const r = window.parent.document.getElementById('risultati');"
            "if (r) r.scrollIntoView({behavior: 'smooth', block: 'start'});"
            "}, 150);"
            "</script>",
            unsafe_allow_javascript=True,
        )


def barra_pagine(pagina: int, totale_pagine: int, chiave: str) -> None:
    if totale_pagine <= 1:
        return
    prima = max(1, min(pagina - 3, totale_pagine - 6))
    numeri = list(range(prima, min(totale_pagine, prima + 6) + 1))
    _, *colonne, _ = st.columns([4] + [1] * (len(numeri) + 2) + [4])
    colonne[0].button("‹", key=f"{chiave}_prec", disabled=pagina == 1, help="Pagina precedente",
                      on_click=_vai_a_pagina, args=(chiave, pagina - 1))
    for colonna, numero in zip(colonne[1:-1], numeri):
        colonna.button(str(numero), key=f"{chiave}_n{numero}",
                       type="primary" if numero == pagina else "tertiary",
                       on_click=_vai_a_pagina, args=(chiave, numero))
    colonne[-1].button("›", key=f"{chiave}_succ", disabled=pagina == totale_pagine, help="Pagina successiva",
                       on_click=_vai_a_pagina, args=(chiave, pagina + 1))
