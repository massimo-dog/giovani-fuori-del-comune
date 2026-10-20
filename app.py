"""Giovani fuori dal Comune: motore di ricerca dei giovani che vivono fuori dal Comune.

Una sola pagina: in alto la ricerca per paese e città, sotto i risultati.
Avvio:  streamlit run app.py
"""
from html import escape
from pathlib import Path

import streamlit as st
from packaging.version import Version

from comune import (barra_pagine, carica_profili, cerca, elenco_citta, elenco_nazioni, icona_pagina,
                    logo_uri, pagina_corrente, scorri_ai_risultati)

VERSIONE_MINIMA_STREAMLIT = "1.65"
PER_PAGINA = 10
LUNGHEZZA_ANTEPRIMA = 160
CHIAVE_PAGINA = "pagina"

st.set_page_config(page_title="Giovani fuori dal Comune", page_icon=icona_pagina(), layout="wide")

# Funzioni recenti di Streamlit: con una versione vecchia meglio un messaggio chiaro
if Version(st.__version__) < Version(VERSIONE_MINIMA_STREAMLIT):
    st.error(
        f"Questa app richiede Streamlit {VERSIONE_MINIMA_STREAMLIT} o successivo "
        f"(installato: {st.__version__}).\n\n"
        "Per aggiornarlo, apri il Terminale nella cartella dell'app ed esegui:\n\n"
        "`python3 -m pip install --upgrade -r requirements.txt`"
    )
    st.stop()

def a_testo_html(testo: str) -> str:
    return escape(testo).replace("\n", "<br>")


def motivazione_html(testo: str, indice: int) -> str:
    if not testo:
        return '<p class="motivazione vuota">Motivazione non indicata</p>'
    if len(testo) <= LUNGHEZZA_ANTEPRIMA:
        return f'<blockquote class="motivazione">{a_testo_html(testo)}</blockquote>'
    anteprima = testo[:LUNGHEZZA_ANTEPRIMA].rsplit(" ", 1)[0] + "…"
    ident = f"motivazione-{indice}"
    # Apri/chiudi senza JavaScript: la casella nascosta decide quale testo mostrare
    return (
        f'<input type="checkbox" class="apri" id="{ident}">'
        f'<blockquote class="motivazione anteprima">{escape(anteprima)}</blockquote>'
        f'<blockquote class="motivazione completa">{a_testo_html(testo)}</blockquote>'
        f'<label class="bottone" for="{ident}">'
        '<span class="apri-testo">Leggi tutto</span><span class="chiudi-testo">Riduci</span></label>'
    )


def scheda_html(profilo, indice: int) -> str:
    luogo = ", ".join(parte for parte in (profilo["citta"], profilo["nazione"]) if parte)
    return (
        '<article class="scheda">'
        f'<img class="foto" src="{profilo["foto_uri"]}" alt="Foto di {escape(profilo["nome_completo"])}">'
        '<div class="corpo">'
        f'<h2 class="nome">{escape(profilo["nome_completo"])}</h2>'
        f'<p class="luogo"><span class="pin"></span><span>{escape(luogo)}</span></p>'
        f"{motivazione_html(profilo['motivazione'], indice)}"
        "</div></article>"
    )


CONTATTO = (
    "Se desideri essere contattato dalla persona<br class=\"a-capo\"> che hai qui individuato<br class=\"a-capo\"> "
    "invia il nome e cognome a “PASSI” passi.salzano.robegano@gmail.com<br class=\"a-capo\"> "
    "precisando la tua identità e quando e come desideri essere contattato"
)

# --- Stile ---------------------------------------------------------------------
stile = (Path(__file__).parent / "stile.css").read_text(encoding="utf-8")
st.html(f"<style>{stile}</style>")

# --- Intestazione ----------------------------------------------------------------
LOGO = logo_uri()
st.html(
    '<header class="intestazione">'
    '<p class="introduzione">Questo è un progetto pensato<br class="a-capo"> '
    "per chi sta valutando un’esperienza di studio o lavoro fuori dal Veneto o all’estero.<br class=\"a-capo\"> "
    "Non è un invito a partire,<br class=\"a-capo\"> "
    "ma uno strumento per scegliere il futuro con maggiore consapevolezza.<br class=\"a-capo\"> "
    "Tutto ciò grazie all’aiuto di tanti amici<br class=\"a-capo\"> "
    "che questa esperienza la stanno già facendo.</p>"
    f'<img class="logo" src="{LOGO}" alt="Giovani fuori dal Comune">'
    '<h1 class="titolo">Scegli il paese o la città nella quale vorresti andare.</h1>'
    '<p class="sottotitolo">Ti saranno indicate le persone<br class="a-capo"> '
    "che già risiedono e lavorano lì<br class=\"a-capo\"> "
    "e che, se lo desideri, potranno contattarti.</p>"
    "</header>"
)

# --- Ricerca ---------------------------------------------------------------------
profili = carica_profili()


def nuova_ricerca(azzera_citta: bool = False) -> None:
    st.session_state[CHIAVE_PAGINA] = 1
    if azzera_citta:
        # Le città dipendono dal paese: quella scelta prima può non esistere nel nuovo paese
        st.session_state["citta"] = None


st.selectbox(
    "Paese estero", elenco_nazioni(profili), index=None, placeholder="Paese estero", key="paese",
    on_change=nuova_ricerca, args=(True,), label_visibility="collapsed",
)
st.selectbox(
    "Città", elenco_citta(profili, st.session_state.get("paese")), index=None, placeholder="Città",
    key="citta", on_change=nuova_ricerca, label_visibility="collapsed",
)

# --- Risultati -------------------------------------------------------------------
paese, citta = st.session_state.get("paese"), st.session_state.get("citta")
ricerca = (paese, citta)
nuova = ricerca != st.session_state.get("ultima_ricerca")
st.session_state["ultima_ricerca"] = ricerca

if paese or citta:
    trovati = cerca(profili, paese, citta)
    pagina, totale_pagine = pagina_corrente(len(trovati), PER_PAGINA, CHIAVE_PAGINA)
    blocco = trovati.iloc[(pagina - 1) * PER_PAGINA: pagina * PER_PAGINA]
    if trovati.empty:
        corpo = '<p class="nessun-risultato">Nessuna persona trovata per questa ricerca.</p>'
    else:
        corpo = f'<p class="contatto">{CONTATTO}</p><div class="pannello">' + "".join(
            scheda_html(profilo, indice) for indice, (_, profilo) in enumerate(blocco.iterrows())
        ) + "</div>"
    st.html(f'<section class="risultati" id="risultati">{corpo}</section>')
    barra_pagine(pagina, totale_pagine, CHIAVE_PAGINA)
    scorri_ai_risultati(CHIAVE_PAGINA, forza=nuova)

# --- Chiusura --------------------------------------------------------------------
st.html(f'<div class="chiusura"><img src="{LOGO}" alt="Giovani fuori dal Comune"></div>')
