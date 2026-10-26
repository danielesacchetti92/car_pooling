from datetime import date
import sqlite3
import pandas as pd
import streamlit as st

# Connessione al database SQLite locale
DB_FILE = "carpool.db"


def init_db():
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  # Tabella viaggi
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS viaggi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT,
            autista TEXT,
            passeggeri TEXT,
            tot_passeggeri INTEGER
        )
    """)
  # Tabella partecipanti (con alcuni colleghi di default come esempio)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS partecipanti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE
        )
    """)
  conn.commit()

  # Inseriamo qualche partecipante di default se la tabella è vuota
  cursor.execute("SELECT COUNT(*) FROM partecipanti")
  if cursor.fetchone()[0] == 0:
    default_users = ["Daniele", "Andrea", "Giacomo", "Miriam"]
    for u in default_users:
      cursor.execute(
          "INSERT OR IGNORE INTO partecipanti (nome) VALUES (?)", (u,)
      )
    conn.commit()

  conn.close()


init_db()

st.set_page_config(
    page_title="Car Pooling Manager", page_icon="🚗", layout="centered"
)

st.title("🚗 Gestione Car Pooling Lavoro")
st.write(
    "Gestisci i passaggi, i partecipanti e tieni traccia dei crediti in modo"
    " semplice!"
)


# Funzioni di utilità per il DB
def load_partecipanti():
  conn = sqlite3.connect(DB_FILE)
  df = pd.read_sql_query("SELECT nome FROM partecipanti", conn)
  conn.close()
  return sorted(df["nome"].tolist()) if not df.empty else []


def load_viaggi():
  conn = sqlite3.connect(DB_FILE)
  df = pd.read_sql_query("SELECT * FROM viaggi", conn)
  conn.close()
  return df


# --- SEZIONE 1: GESTIONE PARTECIPANTI (Aggiungi / Elimina persone) ---
with st.expander("👥 Gestisci il gruppo (Aggiungi / Rimuovi Colleghi)"):
  col_p1, col_p2 = st.columns(2)

  with col_p1:
    with st.form("add_user_form"):
      nuovo_membro = st.text_input("Aggiungi nuovo collega").strip()
      btn_add_user = st.form_submit_button("Aggiungi Persona")
      if btn_add_user and nuovo_membro:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        try:
          cursor.execute(
              "INSERT INTO partecipanti (nome) VALUES (?)",
              (nuovo_membro.capitalize(),),
          )
          conn.commit()
          st.success(f"'{nuovo_membro.capitalize()}' aggiunto con successo!")
          st.rerun()
        except sqlite3.IntegrityError:
          st.error("Questa persona esiste già!")
        finally:
          conn.close()

  with col_p2:
    lista_membri_corrente = load_partecipanti()
    with st.form("del_user_form"):
      membro_da_rimuovere = st.selectbox(
          "Rimuovi collega", lista_membri_corrente
      )
      btn_del_user = st.form_submit_button("Rimuovi Persona")
      if btn_del_user and membro_da_rimuovere:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM partecipanti WHERE nome = ?", (membro_da_rimuovere,)
        )
        conn.commit()
        conn.close()
        st.success(f"'{membro_da_rimuovere}' rimosso!")
        st.rerun()

# Ricarichiamo la lista aggiornata dei partecipanti
membri = load_partecipanti()

# --- SEZIONE 2: REGISTRATI UN NUOVO VIAGGIO ---
st.subheader("📝 Registra il viaggio di oggi")

if not membri:
  st.warning(
      "Aggiungi almeno un partecipante dal pannello sopra per registrare i"
      " viaggi!"
  )
else:
  with st.form("carpool_form"):
    col1, col2 = st.columns(2)
    with col1:
      viaggio_data = st.date_input("Data", value=date.today())
    with col2:
      autista = st.selectbox("Chi ha guidato?", membri)

    # I passeggeri si possono scegliere con una multiselect (escludendo l'autista)
    passeggeri_disponibili = [m for m in membri if m != autista]
    passeggeri_scelti = st.multiselect(
        "Passeggeri a bordo", passeggeri_disponibili
    )

    submit_button = st.form_submit_button(label="Registra Viaggio")

    if submit_button:
      conn = sqlite3.connect(DB_FILE)
      cursor = conn.cursor()
      passeggeri_str = ", ".join(passeggeri_scelti)
      cursor.execute(
          "INSERT INTO viaggi (data, autista, passeggeri, tot_passeggeri) VALUES"
          " (?, ?, ?, ?)",
          (
              str(viaggio_data),
              autista,
              passeggeri_str,
              len(passeggeri_scelti),
          ),
      )
      conn.commit()
      conn.close()
      st.success("Viaggio registrato con successo!")
      st.rerun()

# --- SEZIONE 3: BILANCIO E DEBITI INCROCIATI ---
st.markdown("---")
st.subheader("📊 Bilancio Incrociato (Chi deve passaggi a chi)")

df_records = load_viaggi()
records = []
if not df_records.empty:
  for _, row in df_records.iterrows():
    p_str = str(row["passeggeri"]) if pd.notna(row["passeggeri"]) else ""
    p_list = [p.strip() for p in p_str.split(",") if p.strip()]
    records.append({
        "id": row["id"],
        "data": str(row["data"]),
        "autista": str(row["autista"]).strip(),
        "passeggeri": p_list,
    })

if not records:
  st.info("Nessun viaggio registrato al momento.")
else:
  # Raccogliamo TUTTI i partecipanti unici (sia dai membri attivi che dai viaggi salvati)
  tutti_nomi = set(membri)
  for r in records:
    if r["autista"]:
      tutti_nomi.add(r["autista"])
    for pas in r["passeggeri"]:
      if pas:
        tutti_nomi.add(pas)

  partecipanti = sorted(list(tutti_nomi))
  
  # Inizializziamo il dizionario dei debiti in modo sicuro
  debiti = {p: {p2: 0 for p2 in partecipanti} for p in partecipanti}

  for r in records:
    aut = r["autista"]
    for pas in r["passeggeri"]:
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
            debiti[altro][utente_selezionato]
            - debiti[utente_selezionato][altro]
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
    st.dataframe(df_records, use_container_width=True, hide_index=True)

    # Menu a tendina per eliminare un viaggio specifico tramite il suo ID
    viaggi_ids = df_records["id"].tolist()
    if viaggi_ids:
      viaggio_da_eliminare = st.selectbox(
          "Seleziona l'ID del viaggio da eliminare in caso di errore:",
          viaggi_ids,
      )
      if st.button("Elimina Viaggio Selezionato"):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM viaggi WHERE id = ?", (viaggio_da_eliminare,))
        conn.commit()
        conn.close()
        st.success(f"Viaggio ID {viaggio_da_eliminare} eliminato con successo!")
        st.rerun()
