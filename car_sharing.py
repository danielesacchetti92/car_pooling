from datetime import date
import pandas as pd
import streamlit as st
from streamlit_gsheets import GSheetsConnection

st.set_page_config(
    page_title="Car Pooling Manager", page_icon="🚗", layout="centered"
)

st.title("🚗 Gestione Car Pooling Lavoro")
st.write(
    "Tieni traccia dei passaggi giornalieri e del bilancio incrociato tra"
    " colleghi!"
)

# Connessione a Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)


# Funzione per caricare i dati dal foglio
def load_data():
  try:
    df = conn.read(ttl=0)  # ttl=0 per non usare la cache e leggere dati sempre freschi
    df = df.dropna(how="all")  # rimuove righe completamente vuote
    return df
  except Exception as e:
    return pd.DataFrame(
        columns=["data", "autista", "passeggeri", "tot_passeggeri"]
    )


df_records = load_data()

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
      passeggeri_list = [
          p.strip().capitalize()
          for p in passeggeri_input.split(",")
          if p.strip()
      ]
      passeggeri_str = ", ".join(passeggeri_list)

      nuova_riga = pd.DataFrame([{
          "data": str(viaggio_data),
          "autista": autista.capitalize(),
          "passeggeri": passeggeri_str,
          "tot_passeggeri": len(passeggeri_list),
      }])

      df_aggiornato = pd.concat([df_records, nuova_riga], ignore_index=True)
      conn.update(data=df_aggiornato)

      st.success("Viaggio salvato con successo su Google Sheets!")
      st.rerun()

# Convertiamo i dati in formato lista di record per i calcoli del bilancio
records = []
if not df_records.empty:
  for _, row in df_records.iterrows():
    p_str = str(row["passeggeri"]) if pd.notna(row["passeggeri"]) else ""
    p_list = [p.strip() for p in p_str.split(",") if p.strip()]
    records.append({
        "data": str(row["data"]),
        "autista": str(row["autista"]).strip(),
        "passeggeri": p_list,
    })

# --- SEZIONE 2: BILANCIO E DEBITI INCROCIATI ---
st.markdown("---")
st.subheader("📊 Bilancio Incrociato (Chi deve passaggi a chi)")

if not records:
  st.info("Nessun viaggio registrato al momento. Inizia ad aggiungerne uno!")
else:
  partecipanti = set()
  for r in records:
    if r["autista"]:
      partecipanti.add(r["autista"])
    for pas in r["passeggeri"]:
      if pas:
        partecipanti.add(pas)

  partecipanti = sorted(list(partecipanti))
  debiti = {p: {p2: 0 for p2 in partecipanti} for p in partecipanti}

  for r in records:
    aut = r["autista"]
    for pas in r["passeggeri"]:
      if aut and pas and aut != pas:
        debiti[aut][pas] += 1

  st.markdown(
      "#### Tabella dei Debiti/Crediti (Righe = Chi deve, Colonne = A chi"
      " spetta il passaggio)"
  )

  matrice_data = []
  for debitore in partecipanti:
    riga = {"Persona": debitore}
    for creditore in partecipanti:
      if debitore == creditore:
        riga[creditore] = "-"
      else:
        fatti_a_favore = debiti[debitore][creditore]
        dovuti = debiti[creditore][debitore]
        netto = dovuti - fatti_a_favore
        riga[creditore] = netto
    matrice_data.append(riga)

  df_matrice = pd.DataFrame(matrice_data)
  st.dataframe(df_matrice, use_container_width=True, hide_index=True)

  # Dettaglio personale
  st.markdown("#### 🔍 Dettaglio per singolo utente")
  utente_selezionato = st.selectbox(
      "Seleziona un partecipante per vedere la sua situazione:", partecipanti
  )

  if utente_selezionato:
    dettagli_personali = []
    for altro in partecipanti:
      if altro != utente_selezionato:
        dovuti_da_te = debiti[altro][utente_selezionato] - debiti[utente_selezionato][altro]
        if dovuti_da_te > 0:
          dettagli_personali.append(f"👉 Devi **{dovuti_da_te}** passaggi a **{altro}**")
        elif dovuti_da_te < 0:
          dettagli_personali.append(f"👍 **{altro}** ti deve **{-dovuti_da_te}** passaggi")

    if dettagli_personali:
      for d in dettagli_personali:
        st.write(d)
    else:
      st.write("✨ Siete perfettamente in pari con tutti!")

  with st.expander("📜 Visualizza lo storico completo"):
    st.dataframe(df_records, use_container_width=True, hide_index=True)


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
