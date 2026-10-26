from datetime import date
import json
import os
from github import Github
import pandas as pd
import streamlit as st

# Configurazione GitHub Secrets
if "GITHUB_TOKEN" in st.secrets:
  GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
  REPO_NAME = st.secrets["GITHUB_REPO"]
  JSON_FILENAME = st.secrets.get("JSON_FILENAME", "viaggi.json")
else:
  GITHUB_TOKEN = None
  REPO_NAME = None
  JSON_FILENAME = "viaggi.json"


def load_data_from_github():
  default_data = {
      "partecipanti": ["Andrea s.", "Jack", "Miriam", "Sacco"],
      "viaggi": [],
  }
  if GITHUB_TOKEN and REPO_NAME:
    try:
      g = Github(GITHUB_TOKEN)
      repo = g.get_repo(REPO_NAME)
      file_content = repo.get_contents(JSON_FILENAME)
      data = json.loads(file_content.decoded_content.decode("utf-8"))
      if isinstance(data, dict):
        if "partecipanti" not in data:
          data["partecipanti"] = default_data["partecipanti"]
        if "viaggi" not in data:
          data["viaggi"] = []
        return data
      else:
        return default_data
    except Exception:
      return default_data
  else:
    if os.path.exists(JSON_FILENAME):
      try:
        with open(JSON_FILENAME, "r", encoding="utf-8") as f:
          data = json.load(f)
          if isinstance(data, dict):
            return data
      except Exception:
        pass
    return default_data


def save_data_to_github(data_dict):
  json_string = json.dumps(data_dict, ensure_ascii=False, indent=4)
  if GITHUB_TOKEN and REPO_NAME:
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)
    try:
      file_content = repo.get_contents(JSON_FILENAME)
      repo.update_file(
          file_content.path,
          "Aggiornamento dati car pooling da Streamlit",
          json_string,
          file_content.sha,
      )
    except Exception:
      repo.create_file(
          JSON_FILENAME, "Creazione file dati car pooling", json_string
      )
  else:
    with open(JSON_FILENAME, "w", encoding="utf-8") as f:
      f.write(json_string)


# Carichiamo i dati all'avvio
db_data = load_data_from_github()
membri = db_data.get("partecipanti", [])
raw_viaggi = db_data.get("viaggi", [])

st.set_page_config(
    page_title="Car Pooling Manager", page_icon="🚗", layout="centered"
)

st.title("🚗 Gestione Car Pooling Lavoro")
st.write(
    "Dati salvati in modo sicuro su GitHub: sempre persistenti e modificabili!"
)

# --- SEZIONE 1: GESTIONE PARTECIPANTI (STAND ALONE NELL'EXPANDER) ---
with st.expander("👥 Gestisci il gruppo (Aggiungi / Rimuovi Colleghi)"):
  col_p1, col_p2 = st.columns(2)

  with col_p1:
    with st.form("add_user_form"):
      nuovo_membro = st.text_input("Aggiungi nuovo collega").strip()
      btn_add_user = st.form_submit_button("Aggiungi Persona")
      if btn_add_user and nuovo_membro:
        nome_cap = nuovo_membro.capitalize()
        if nome_cap not in membri:
          membri.append(nome_cap)
          db_data["partecipanti"] = membri
          save_data_to_github(db_data)
          st.success(f"'{nome_cap}' aggiunto con successo!")
          st.rerun()
        else:
          st.error("Questa persona esiste già!")

  with col_p2:
    with st.form("del_user_form"):
      membro_da_rimuovere = st.selectbox("Rimuovi collega", membri)
      btn_del_user = st.form_submit_button("Rimuovi Persona")
      if btn_del_user and membro_da_rimuovere:
        if membro_da_rimuovere in membri:
          membri.remove(membro_da_rimuovere)
          db_data["partecipanti"] = membri
          save_data_to_github(db_data)
          st.success(f"'{membro_da_rimuovere}' rimosso!")
          st.rerun()

st.markdown("---")

# --- SEZIONE 2: REGISTRA NUOVO VIAGGIO (STAND ALONE FUORI DALL'EXPANDER) ---
st.subheader("📝 Registra il viaggio di oggi")

if not membri:
  st.warning("Aggiungi almeno un partecipante dal pannello sopra!")
else:
  with st.form("carpool_form"):
    col1, col2 = st.columns(2)
    with col1:
      viaggio_data = st.date_input("Data", value=date.today())
    with col2:
      autista = st.selectbox("Chi ha guidato?", membri)

    passeggeri_disponibili = [m for m in membri if m != autista]
    passeggeri_scelti = st.multiselect(
        "Passeggeri a bordo", passeggeri_disponibili
    )

    submit_button = st.form_submit_button(label="Registra Viaggio")

    if submit_button:
      nuovo_id = (
          max([v.get("id", 0) for v in raw_viaggi], default=0) + 1
      )
      nuovo_viaggio = {
          "id": nuovo_id,
          "data": str(viaggio_data),
          "autista": autista,
          "passeggeri": passeggeri_scelti,
      }
      raw_viaggi.append(nuovo_viaggio)
      db_data["viaggi"] = raw_viaggi
      save_data_to_github(db_data)
      st.success("Viaggio registrato e salvato su GitHub!")
      st.rerun()


# --- SEZIONE 3: BILANCIO E DEBITI INCROCIATI ---
st.markdown("---")
st.subheader("📊 Bilancio Incrociato (Chi deve passaggi a chi)")

if not raw_viaggi:
  st.info("Nessun viaggio registrato al momento.")
else:
  tutti_nomi = set(membri)
  for r in raw_viaggi:
    if r.get("autista"):
      tutti_nomi.add(r["autista"])
    for pas in r.get("passeggeri", []):
      if pas:
        tutti_nomi.add(pas)

  partecipanti = sorted(list(tutti_nomi))
  debiti = {p: {p2: 0 for p2 in partecipanti} for p in partecipanti}

  for r in raw_viaggi:
    aut = r.get("autista")
    for pas in r.get("passeggeri", []):
      if aut and pas and aut != pas:
        if aut in debiti and pas in debiti[aut]:
          debiti[aut][pas] += 1

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
        dovuti_da_te = (
            debiti[altro].get(utente_selezionato, 0)
            - debiti[utente_selezionato].get(altro, 0)
        )
        if dovuti_da_te > 0:
          dettagli_personali.append(
              f"👉 Devi **{dovuti_da_te}** passaggi a **{altro}**"
          )
        elif dovuti_da_te < 0:
          dettagli_personali.append(
              f"👍 **{altro}** ti deve **{-dovuti_da_te}** passaggi"
          )

    if dettagli_personali:
      for d in dettagli_personali:
        st.write(d)
    else:
      st.write("✨ Siete perfettamente in pari con tutti!")

  # --- SEZIONE 4: STORICO ED ELIMINAZIONE VIAGGI ---
  st.markdown("---")
  with st.expander("📜 Storico Viaggi ed Eliminazione"):
    df_storico = pd.DataFrame([
        {
            "ID": v.get("id"),
            "Data": v.get("data"),
            "Autista": v.get("autista"),
            "Passeggeri": ", ".join(v.get("passeggeri", [])),
        }
        for v in raw_viaggi
    ])
    st.dataframe(df_storico, use_container_width=True, hide_index=True)

    viaggi_ids = [v.get("id") for v in raw_viaggi]
    if viaggi_ids:
      viaggio_da_eliminare = st.selectbox(
          "Seleziona l'ID del viaggio da eliminare in caso di errore:",
          viaggi_ids,
      )
      if st.button("Elimina Viaggio Selezionato"):
        raw_viaggi = [v for v in raw_viaggi if v.get("id") != viaggio_da_eliminare]
        db_data["viaggi"] = raw_viaggi
        save_data_to_github(db_data)
        st.success(f"Viaggio ID {viaggio_da_eliminare} eliminato con successo!")
        st.rerun()
