import streamlit as st
import pandas as pd
import gspread
from gspread_dataframe import get_as_dataframe
from openpyxl import load_workbook
import io # Serve per il download del file

# --- 1. FUNZIONE PER CARICARE IL DB DA GOOGLE SHEETS ---
# Streamlit usa la cache per non ricaricare i dati ad ogni click
@st.cache_data(ttl=600) # ttl=600 -> ricarica i dati ogni 10 minuti
def carica_database_giocatori():
    print("Caricamento DB da Google Sheets...")
    try:
        # Usa i "Secrets" di Streamlit per autenticarsi
        creds = st.secrets["google_creds"]
        gc = gspread.service_account_from_dict(creds)

        # --- MODIFICA QUI ---
        # Apri il Google Sheet usando il suo NOME ESATTO
        sh = gc.open("db_giocatori")
        
        # Apri il foglio di lavoro (scheda) specifico, es. "db"
        worksheet = sh.worksheet("db")
        
        # Leggi i dati in un DataFrame pandas
        df_db = get_as_dataframe(worksheet)
        
        # --- Da qui è il tuo vecchio codice ---
        
        # Pulizia NOMI COLONNA: rimuovi spazi e rendi tutto MAIUSCOLO
        df_db.columns = df_db.columns.str.strip().str.upper()

        # Controllo colonne
        colonne_necessarie = ['COGNOME', 'NOME', 'MATRICOLA', 'ANNO', 'MESE', 'GIORNO']
        if not all(col in df_db.columns for col in colonne_necessarie):
            st.error(f"Errore DB: Colonne mancanti! Trovate: {list(df_db.columns)}")
            return None

        # Pulizia dati
        df_db['COGNOME'] = df_db['COGNOME'].str.strip()
        df_db['NOME'] = df_db['NOME'].str.strip()
        
        # Gestione date
        df_date = df_db[['ANNO', 'MESE', 'GIORNO']].rename(columns={
            'ANNO': 'year', 'MESE': 'month', 'GIORNO': 'day'
        })
        df_db['DOB'] = pd.to_datetime(df_date).dt.strftime('%d/%m/%Y')
        
        print("Caricamento DB completato.")
        return df_db
        
    except Exception as e:
        st.error(f"Errore nel caricamento del Google Sheet: {e}")
        print(f"Errore gspread: {e}")
        return None

# --- 2. INTERFACCIA STREAMLIT ---

# Autenticazione base (come da Proposta 3)
try:
    password_corretta = st.secrets["APP_PASSWORD"]
except:
    st.error("Password dell'app non impostata nei Secrets!")
    st.stop()

password = st.text_input("Inserisci password", type="password")
if password != password_corretta:
    st.error("Password errata")
    st.stop()

# --- Inizia l'app vera e propria ---
st.title("Compilatore Distinta 📝")

# Carica il database
df_db = carica_database_giocatori()

if df_db is None:
    st.warning("Database giocatori non caricato. Impossibile continuare.")
    st.stop()

st.success(f"Database giocatori caricato correttamente! ({len(df_db)} giocatori trovati)")

# --- Form per i campi extra ---
st.header("1. Dati Partita")
col1, col2 = st.columns(2)
with col1:
    squadra = st.text_input("Squadra", "FRAORE")
    gara = st.text_input("Gara", "LANGHIRANO - FRAORE")
with col2:
    data_partita = st.date_input("Data Partita")
    # ... (aggiungi altri campi se vuoi editarli, es. Dirigente)
    dirigente = st.text_input("Dirigente Accompagnatore", "M. ROSSI")


# --- Form per i giocatori ---
st.header("2. Giocatori Convocati")
cognomi_incollati = st.text_area("Incolla qui i COGNOMI (uno per riga):", height=250)
lista_cognomi = [name.strip().upper() for name in cognomi_incollati.split('\n') if name.strip()]

# Pulsante di generazione
if st.button("Genera Distinta Compilata", type="primary"):
    if not lista_cognomi:
        st.warning("Nessun cognome inserito.")
    elif len(lista_cognomi) > 20:
        st.warning("Max 20 giocatori. I successivi saranno ignorati.")
        lista_cognomi = lista_cognomi[:20]
    else:
        with st.spinner("Genero il file Excel..."):
            try:
                # Carica il TEMPLATE Excel (che è su GitHub insieme a app.py)
                workbook = load_workbook(filename="DISTINTA_DA_COMPILARE.xlsx")
                sheet = workbook["distinta"]

                # --- Scrive i dati della partita ---
                sheet['B8'] = squadra
                sheet['B7'] = gara
                sheet['E8'] = data_partita.strftime('%d/%m/%Y') # Formatta la data
                # ... (scrivi gli altri campi, es. Dirigente)
                # sheet['B32'] = dirigente # Esempio, cella inventata

                # --- Pulizia range giocatori ---
                for row in range(10, 30):
                    sheet[f'B{row}'], sheet[f'C{row}'], sheet[f'D{row}'] = None, None, None

                # --- Scrittura giocatori ---
                current_row = 10
                giocatori_non_trovati = []
                giocatori_ambigui = []

                for cognome_input in lista_cognomi:
                    risultati = df_db[df_db['COGNOME'].str.upper() == cognome_input]
                    
                    if len(risultati) == 1:
                        dati = risultati.iloc[0]
                        sheet[f'B{current_row}'] = f"{dati['COGNOME']} {dati['NOME']}"
                        sheet[f'C{current_row}'] = dati['MATRICOLA']
                        sheet[f'D{current_row}'] = dati['DOB']
                    elif len(risultati) > 1:
                        sheet[f'B{current_row}'] = cognome_input
                        sheet[f'C{current_row}'] = "AMBIGUO (Multiplo)"
                        giocatori_ambigui.append(cognome_input)
                    else:
                        sheet[f'B{current_row}'] = cognome_input
                        sheet[f'C{current_row}'] = "NON IN DB"
                        giocatori_non_trovati.append(cognome_input)
                    
                    current_row += 1

                # Salva il file in memoria
                file_in_memoria = io.BytesIO()
                workbook.save(file_in_memoria)
                file_in_memoria.seek(0) # Torna all'inizio del file

                st.success("Distinta generata con successo!")
                
                if giocatori_non_trovati:
                    st.warning(f"Attenzione: Giocatori non trovati nel DB: {', '.join(giocatori_non_trovati)}")
                if giocatori_ambigui:
                    st.error(f"ATTENZIONE: Cognomi ambigui (più giocatori trovati): {', '.join(giocatori_ambigui)}")

                # Pulsante Download
                st.download_button(
                    label="Scarica la Distinta Compilata (.xlsx)",
                    data=file_in_memoria,
                    file_name=f"DISTINTA_COMPILATA_{squadra}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            except Exception as e:
                st.error(f"Errore durante la generazione del file Excel:")
                st.exception(e) # Mostra l'errore completo