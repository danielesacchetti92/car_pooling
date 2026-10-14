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

# --- SEZIONE 2: BILANCIO E STATISTICHE (Aggiornato) ---
st.markdown("---")
st.subheader("📊 Bilancio dei Passaggi (Dare / Avere)")

if not records:
  st.info("Nessun viaggio registrato al momento. Inizia ad aggiungerne uno!")
else:
  # Raccogliamo tutti i partecipanti unici (sia autisti che passeggeri)
  partecipanti = set()
  for r in records:
    partecipanti.add(r["autista"])
    for pas in r["passeggeri"]:
      partecipanti.add(pas)

  partecipanti = sorted(list(partecipanti))

  # Inizializziamo una matrice o un dizionario dei debiti/crediti incrociati
  # matrix[A][B] = quanti passaggi A ha dato a B (cioè B deve ad A)
  # Per semplicità, calcoliamo un saldo netto per ogni persona:
  # Saldo = (Persone totali trasportate in tutti i tuoi viaggi) - (Totale passaggi in cui sei stato passeggero)

  statistiche = {
      p: {"guidate": 0, "passaggi_dati": 0, "passaggi_ricevuti": 0}
      for p in partecipanti
  }

  for r in records:
    aut = r["autista"]
    if aut in statistiche:
      statistiche[aut]["guidate"] += 1
      # Ogni passeggero a bordo riceve un passaggio dall'autista
      num_passeggeri = len(r["passeggeri"])
      statistiche[aut]["passaggi_dati"] += num_passeggeri

    for pas in r["passeggeri"]:
      if pas in statistiche:
        statistiche[pas]["passaggi_ricevuti"] += 1

  # Creiamo il DataFrame
  df_stats = pd.DataFrame.from_dict(statistiche, orient="index")
  df_stats.index.name = "Partecipante"
  df_stats.reset_index(inplace=True)

  # Il vero saldo: Passaggi dati (credito) - Passaggi ricevuti (debito)
  # Se guidi e porti 2 persone, i tuoi "passaggi_dati" aumentano di 2, facendo salire il tuo bilancio!
  df_stats["Saldo Netto"] = (
      df_stats["passaggi_dati"] - df_stats["passaggi_ricevuti"]
  )

  # Rinominiamo le colonne per renderle più leggibili
  df_stats = df_stats.rename(
      columns={
          "guidate": "Giornate guida",
          "passaggi_dati": "Passaggi offerti",
          "passaggi_ricevuti": "Passaggi ricevuti",
      }
  )

  st.dataframe(df_stats, use_container_width=True, hide_index=True)

  st.caption(
      "💡 **Legenda:** Un **Saldo Netto positivo** significa che hai offerto più"
      " passaggi di quanti ne hai ricevuti (sei in credito). Un **Saldo Netto"
      " negativo** significa che hai ricevuto più passaggi (sei in debito e"
      " ti tocca guidare!)."
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