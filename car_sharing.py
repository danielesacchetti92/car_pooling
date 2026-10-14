# -*- coding: utf-8 -*-
"""
Created on Wed Oct 14 15:46:30 2026

@author: sacchettid
"""

import json
import os
from datetime import date
import pandas as pd
import streamlit as st

DATA_FILE = "carpool_data.json"


# Funzione per caricare i dati
def load_data():
  if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
      try:
        return json.load(f)
      except json.JSONDecodeError:
        return []
  return []


# Funzione per salvare i dati
def save_data(data):
  with open(DATA_FILE, "w") as f:
    json.dump(data, f, indent=4)


st.set_page_config(
    page_title="Car Pooling Manager", page_icon="🚗", layout="centered"
)

st.title("🚗 Gestione Car Pooling Lavoro")
st.write(
    "Tieni traccia dei passaggi giornalieri per capire chi guida e chi deve"
    " ricambiare il favore!"
)

# Caricamento dati esistenti
records = load_data()

# --- SEZIONE 1: AGGIUNGI NUOVO VIAGGIO ---
st.subheader("📝 Registra il viaggio di oggi")

with st.form("carpool_form"):
  col1, col2 = st.columns(2)
  with col1:
    viaggio_data = st.date_input("Data", value=date.today())
  with col2:
    autista = st.text_input("Chi ha guidato? (Nome)").strip()

  passeggeri_input = st.text_input(
      "Passeggeri a bordo (separa i nomi con la virgola, es: Marco, Luca,"
      " Anna)"
  ).strip()

  submit_button = st.form_submit_button(label="Registra Viaggio")

  if submit_button:
    if not autista:
      st.error("Inserisci il nome dell'autista!")
    else:
      # Pulisce la lista dei passeggeri
      passeggeri = [
          p.strip().capitalize()
          for p in passeggeri_input.split(",")
          if p.strip()
      ]

      nuovo_record = {
          "data": str(viaggio_data),
          "autista": autista.capitalize(),
          "passeggeri": passeggeri,
          "tot_passeggeri": len(passeggeri),
      }
      records.append(nuovo_record)
      save_data(records)
      st.success("Viaggio registrato con successo!")
      st.rerun()

# --- SEZIONE 2: BILANCIO E DEBITI INCROCIATI (Aggiornato) ---
st.markdown("---")
st.subheader("📊 Bilancio Incrociato (Chi deve passaggi a chi)")

if not records:
  st.info("Nessun viaggio registrato al momento. Inizia ad aggiungerne uno!")
else:
  # Raccogliamo tutti i partecipanti unici
  partecipanti = set()
  for r in records:
    partecipanti.add(r["autista"])
    for pas in r["passeggeri"]:
      partecipanti.add(pas)

  partecipanti = sorted(list(partecipanti))

  # Creiamo una matrice dei debiti: debiti[creditore][debitore] = quanti passaggi il debitore deve al creditore
  # Significa: quando A guida e porta B, B riceve un passaggio da A (quindi B deve un passaggio ad A)
  debiti = {p: {p2: 0 for p2 in partecipanti} for p in partecipanti}

  for r in records:
    aut = r["autista"]
    for pas in r["passeggeri"]:
      if aut != pas:  # Evitiamo auto-passaggi strani
        # Il passeggero 'pas' ha ricevuto un passaggio dall'autista 'aut'
        # Quindi 'pas' è in debito verso 'aut'
        debiti[aut][pas] += 1

  # Ora calcoliamo i saldi reciproci per pulire la visualizzazione (se A deve a B e B deve ad A, compensiamo)
  # Oppure creiamo una tabella di sintesi per ogni persona mostrando i singoli rapporti o il saldo netto verso gli altri.

  # Prepariamo una vista tabulare pulita per ogni persona:
  # Mostriamo quanto ogni persona deve agli altri o viceversa.
  st.markdown(
      "#### Tabella dei Debiti/Crediti (Righe = Chi deve, Colonne = A chi"
      " spetta il passaggio)"
  )

  # Costruiamo un DataFrame dove le righe sono i passeggeri/debitori e le colonne i creditori (o viceversa)
  # debiti_matrice[debitore][creditore]
  matrice_data = []
  for debitore in partecipanti:
    riga = {"Persona": debitore}
    for creditore in partecipanti:
      if debitore == creditore:
        riga[creditore] = "-"
      else:
        # Quanti passaggi 'debitore' deve a 'creditore'?
        # Sono i passaggi in cui 'creditore' ha guidato e 'debitore' era a bordo (debiti[creditore][debitore])
        # Meno il contrario (se il debitore ha scarrozzato il creditore)
        fatti_a_favore = debiti[debitore][creditore]  # quanto creditore deve a debitore
        dovuti = debiti[creditore][debitore]  # quanto debitore deve a creditore

        netto = dovuti - fatti_a_favore
        riga[creditore] = netto
    matrice_data.append(riga)

  df_matrice = pd.DataFrame(matrice_data)
  st.dataframe(df_matrice, use_container_width=True, hide_index=True)

  st.caption(
      "📖 **Come leggere la tabella:** Incrociando la riga di una persona con"
      " la colonna di un'altra, trovi quanti passaggi la persona in riga deve"
      " restituire alla persona in colonna. Se c'è un numero positivo, glieli"
      " devi; se è zero o negativo, siete pari o in credito."
  )


  # --- SEZIONE 3: STORICO VIAGGI ---
  with st.expander("📜 Visualizza lo storico completo dei viaggi"):
    df_history = pd.DataFrame(records)
    if not df_history.empty:
      # Riconvertiamo la lista passeggeri in stringa leggibile per la tabella
      df_history["passeggeri"] = df_history["passeggeri"].apply(
          lambda x: ", ".join(x)
      )
      st.dataframe(df_history, use_container_width=True, hide_index=True)

      # Pulsante per cancellare l'ultimo inserimento in caso di errore
      if st.button("Elimina l'ultimo viaggio inserito"):
        records.pop()
        save_data(records)
        st.success("Ultimo viaggio eliminato!")
        st.rerun()