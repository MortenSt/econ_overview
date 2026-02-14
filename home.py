import streamlit as st
import pandas as pd
import json
import os

# --- KONFIGURASJON ---
st.set_page_config(page_title="Økonomisk Oversikt", layout="wide", page_icon="💰")
RULE_FILE = "kategori_regler.json"

# --- STANDARD KATEGORIER ---
DEFAULT_CATEGORIES = [
    'Inntekt',
    'Bolig & Regninger',
    'Mat & Drikke',
    'Forbrukslån',        # NY
    'Inkasso & Purring',  # NY
    'Sparing & Overføring',
    'Shopping & Tech',
    'Transport',
    'Fritid & Abonnement',
    'Annet'
]

# --- HÅNDTERING AV BRUKERREGLER ---
def load_custom_rules():
    if os.path.exists(RULE_FILE):
        try:
            with open(RULE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_custom_rules(rules):
    with open(RULE_FILE, 'w', encoding='utf-8') as f:
        json.dump(rules, f, ensure_ascii=False, indent=4)

# --- KATEGORISERINGS-LOGIKK ---
def get_category(description, amount_out, custom_rules):
    # Konverterer til string og lowercase for trygg sammenligning
    desc = str(description).lower() if description else ""
    
    # 1. SJEKK BRUKERENS EGNE REGLER FØRST
    for keyword, category in custom_rules.items():
        if keyword.lower() in desc:
            return category

    # 2. STANDARD LOGIKK (FALLBACK)
    
    # INNTEKT
    if any(x in desc for x in ['lønn', 'løn', 'innskudd', 'renter', 'nav', 'trygd']):
        return 'Inntekt'
    
    # SPARING
    if any(x in desc for x in ['overføring mellom egne', 'morsom sparing', 'fondshandel', 'firi', 'aksjesparekont', 'dnb verdipapirservice', 'mobil overføring']):
        return 'Sparing & Overføring'

    # BOLIG
    if any(x in desc for x in ['leie', 'utleiemegleren', 'fjordkraft', 'strøm', 'efaktura', 'husleie', 'aneo', 'ropo', 'sameiet', 'world energy', 'movel', 'kommunale']):
        return 'Bolig & Regninger'

    # --- NY: INKASSO OG PURRING (Høyeste prioritet av gjeld) ---
    if any(x in desc for x in ['purring', 'inkasso', 'intrum', 'lowell', 'namsmann', 'sileo', 'kredinor', 'sergel', 'gjeldsregisteret']):
        return 'Inkasso & Purring'

    # --- NY: FORBRUKSLÅN (Ordinær betjening) ---
    if any(x in desc for x in ['thorn', 'sambla', 'lån', 'avtalegiro', 'morrow bank', 'ikano', 'svea', 'resurs', 'bank norwegian', 'santander']):
        return 'Forbrukslån'

    # DAGLIGVARE
    if any(x in desc for x in ['meny', 'coop', 'rema', 'kiwi', 'joker', 'bunnepris', 'dagligvare', 'oda.no']):
        return 'Mat & Drikke'

    # SHOPPING
    if any(x in desc for x in ['microsoft', 'apple', 'elkjøp', 'power', 'klær', 'steam', 'aljibe', 'komplett']):
        return 'Shopping & Tech'

    # TRANSPORT
    if any(x in desc for x in ['easypark', 'bensin', 'parkering', 'vy', 'ruter', 'bom', 'flytoget']):
        return 'Transport'
    
    # FRITID
    if any(x in desc for x in ['sats', 'netflix', 'spotify', 'restaurant', 'bar', 'vinmonopolet', 'hbo', 'disney']):
        return 'Fritid & Abonnement'

    return 'Annet'

# --- HJELPEFUNKSJON FOR KOLONNER ---
def standardize_columns(df):
    col_map = {}
    for col in df.columns:
        c_lower = col.lower()
        # Logikk for å finne riktige kolonner basert på vanlige bank-navn
        if 'dato' in c_lower and 'rente' not in c_lower:
            col_map[col] = 'Date'
        elif any(x in c_lower for x in ['forklaring', 'beskrivelse', 'tekst', 'transaksjonstype']):
            col_map[col] = 'Description'
        elif 'ut' in c_lower and ('konto' in c_lower or 'beløp' in c_lower):
            col_map[col] = 'Out'
        elif 'inn' in c_lower and ('konto' in c_lower or 'beløp' in c_lower):
            col_map[col] = 'In'
        # Fallback for banker som har én kolonne for beløp (negativt=ut, positivt=inn)
        elif 'beløp' in c_lower and 'ut' not in c_lower and 'inn' not in c_lower:
             col_map[col] = 'Amount_Single_Col'
            
    df.rename(columns=col_map, inplace=True)
    return df

# --- LASTE INN DATA FRA UPLOAD ---
@st.cache_data
def process_uploaded_files(uploaded_files, custom_rules):
    all_data = []
    
    for uploaded_file in uploaded_files:
        try:
            df = None
            uploaded_file.seek(0) # Reset file pointer
            
            # Prøver å lese filen. Sjekker både UTF-8 og Latin1 (for norske tegn)
            try:
                if uploaded_file.name.lower().endswith('.txt'):
                    df = pd.read_csv(uploaded_file, sep=';', encoding='latin1', on_bad_lines='skip')
                elif uploaded_file.name.lower().endswith('.csv'):
                    # Mange norske banker bruker latin1 for CSV også
                    try:
                        df = pd.read_csv(uploaded_file, sep=',', encoding='utf-8')
                    except UnicodeDecodeError:
                        uploaded_file.seek(0)
                        df = pd.read_csv(uploaded_file, sep=',', encoding='latin1')
                        
            except Exception as e:
                st.error(f"Kunne ikke lese {uploaded_file.name}. Sjekk filformatet.")
                continue
            
            if df is not None:
                # Rens kolonnenavn
                df.columns = [c.strip().replace('"', '') for c in df.columns]
                df = standardize_columns(df)
                all_data.append(df)
            
        except Exception as e:
            st.error(f"Kritisk feil ved lesing av {uploaded_file.name}: {e}")

    if not all_data:
        return pd.DataFrame()

    combined_df = pd.concat(all_data, ignore_index=True)
    
    # Håndter banker som kun har én kolonne 'Amount_Single_Col'
    if 'Amount_Single_Col' in combined_df.columns:
        # Rens tallformatet først
        combined_df['Amount_Single_Col'] = combined_df['Amount_Single_Col'].astype(str).str.replace('"', '').str.replace(' ', '').str.replace(',', '.')
        combined_df['Amount_Single_Col'] = pd.to_numeric(combined_df['Amount_Single_Col'], errors='coerce').fillna(0)
        
        # Splitt til In og Out
        combined_df['In'] = combined_df['Amount_Single_Col'].apply(lambda x: x if x > 0 else 0)
        combined_df['Out'] = combined_df['Amount_Single_Col'].apply(lambda x: abs(x) if x < 0 else 0)

    # Sikre at In og Out finnes
    for required_col in ['Out', 'In']:
        if required_col not in combined_df.columns:
            combined_df[required_col] = 0
    
    if 'Date' not in combined_df.columns:
         st.error("Kunne ikke finne datokolonnen i filene. Sjekk at filen har en kolonne som heter 'Dato' eller lignende.")
         return pd.DataFrame()

    combined_df['Date'] = pd.to_datetime(combined_df['Date'], dayfirst=True, errors='coerce')
    
    # --- VIKTIG RETTELSE: Tallformatering ---
    # Norske tall bruker ofte mellomrom som tusenskille (eks: "1 500,00").
    # Vi må fjerne mellomrom FØR vi bytter komma med punktum.
    for col in ['Out', 'In']:
        if combined_df[col].dtype == object:
            combined_df[col] = combined_df[col].astype(str).str.replace('"', '').str.replace(' ', '').str.replace(',', '.')
            combined_df[col] = pd.to_numeric(combined_df[col], errors='coerce').fillna(0)
        else:
            combined_df[col] = combined_df[col].fillna(0)
            
    if 'Description' in combined_df.columns:
        combined_df['Category'] = combined_df.apply(lambda row: get_category(row['Description'], row['Out'], custom_rules), axis=1)
    else:
        combined_df['Category'] = 'Ukjent'
        
    combined_df['Month'] = combined_df['Date'].dt.to_period('M')
    
    return combined_df

# --- HOVEDAPPLIKASJON ---
def main():
    st.title("📊 Økonomisk Analyse")
    
    custom_rules = load_custom_rules()

    # --- SIDEBAR ---
    with st.sidebar:
        st.header("Filopplasting")
        st.info("Last opp CSV eller TXT filer fra nettbanken din.")
        uploaded_files = st.file_uploader("Velg filer", type=['txt', 'csv'], accept_multiple_files=True)
        
        st.divider()
        st.header("⚙️ Kategori-innstillinger")
        
        with st.expander("Legg til / Endre regler", expanded=False):
            with st.form("add_rule_form"):
                new_keyword = st.text_input("Tekst inneholder (f.eks. 'vipps')")
                new_category = st.selectbox("Sett til kategori", DEFAULT_CATEGORIES)
                submit_rule = st.form_submit_button("Lagre regel")
                
                if submit_rule and new_keyword:
                    custom_rules[new_keyword.lower()] = new_category
                    save_custom_rules(custom_rules)
                    st.success(f"Regel lagret.")
                    st.rerun()

            st.write("---")
            json_str = json.dumps(custom_rules, indent=4, ensure_ascii=False)
            st.download_button("📥 Last ned regler (JSON)", json_str, "kategori_regler.json", "application/json")

    if uploaded_files:
        df = process_uploaded_files(uploaded_files, custom_rules)
        
        if df.empty:
            st.warning("Ingen lesbare data funnet. Sjekk filformatet.")
            return

        # Sjekk om vi har gyldige datoer
        valid_years = df['Date'].dt.year.dropna().unique()
        if len(valid_years) == 0:
             st.error("Ingen gyldige årstall funnet i dataene.")
             return

        st.sidebar.divider()
        all_years = sorted(valid_years.astype(int))
        
        # Safe selection logic
        index_default = len(all_years)-1 if len(all_years) > 0 else 0
        selected_year = st.sidebar.selectbox("Velg årstall", all_years, index=index_default)
        
        df_view = df[df['Date'].dt.year == selected_year].copy()

        # --- TABS FOR ORGANISERING ---
        tab_overview, tab_debt, tab_details = st.tabs(["Oversikt", "⚠️ Gjeldsanalyse", "Detaljer"])

        # --- FANE 1: OVERSIKT (Standard visning) ---
        with tab_overview:
            col1, col2, col3 = st.columns(3)
            total_in = df_view['In'].sum()
            total_out = df_view['Out'].sum()
            
            # KPI
            col1.metric("Total Inntekt", f"{total_in:,.0f} kr")
            col2.metric("Total Utgifter", f"{total_out:,.0f} kr")
            col3.metric("Balanse", f"{total_in - total_out:,.0f} kr", delta_color="normal")
            
            st.divider()
            
            # Grafer
            monthly = df_view.groupby('Month')[['In', 'Out']].sum()
            # Konverter til string for visning, men behold rekkefølgen
            monthly.index = monthly.index.astype(str)
            
            st.subheader("Inntekter og Utgifter")
            # Farger: Inntekt (Grønn), Utgift (Rød)
            # Obs: Streamlit mapper farger til kolonnene alfabetisk (In før Out)
            st.bar_chart(monthly, color=["#4ade80", "#f87171"])

        # --- FANE 2: GJELDSANALYSE (Fokusområde) ---
        with tab_debt:
            st.header(f"Gjeldsoversikt {selected_year}")
            
            # Filtrer kun gjeldsposter
            debt_categories = ['Forbrukslån', 'Inkasso & Purring']
            df_debt = df_view[df_view['Category'].isin(debt_categories)].copy()
            
            if df_debt.empty:
                st.success("Ingen transaksjoner funnet for Lån, Inkasso eller Purringer i år!")
            else:
                col_d1, col_d2 = st.columns(2)
                
                # Beregn totaler
                total_loan = df_debt[df_debt['Category'] == 'Forbrukslån']['Out'].sum()
                total_inkasso = df_debt[df_debt['Category'] == 'Inkasso & Purring']['Out'].sum()
                
                col_d1.metric("Ordinære Forbrukslån", f"{total_loan:,.0f} kr", help="Thorn, Morrow, Ikano osv.")
                col_d2.metric("Inkasso & Purringer", f"{total_inkasso:,.0f} kr", delta="-Unødvendig", delta_color="inverse", help="Intrum, Lowell, Purring...")

                st.divider()

                # Graf som viser utvikling av dårlig gjeld vs vanlig gjeld
                monthly_debt = df_debt.pivot_table(index='Month', columns='Category', values='Out', aggfunc='sum', fill_value=0)
                monthly_debt.index = monthly_debt.index.astype(str)
                
                st.subheader("Utvikling av gjeldskostnader")
                st.write("Røde søyler er purringer/inkasso – disse bør prioriteres først.")
                
                # Spesifiser farger: Inkasso = Rød, Lån = Oransje
                color_map = {'Inkasso & Purring': '#ff0000', 'Forbrukslån': '#ffa500'}
                # Denne listen genererer fargene i samme rekkefølge som kolonnene i dataframe
                colors = [color_map.get(c, '#888888') for c in monthly_debt.columns]
                
                st.bar_chart(monthly_debt, color=colors)

                # Detaljert tabell for Inkasso
                st.subheader("⚠️ Liste over Inkasso og Purringer")
                df_inkasso = df_debt[df_debt['Category'] == 'Inkasso & Purring']
                if not df_inkasso.empty:
                    st.dataframe(
                        df_inkasso[['Date', 'Description', 'Out']].sort_values('Date', ascending=False), 
                        use_container_width=True
                    )
                else:
                    st.success("Ingen inkasso eller purringer registrert.")

                # Detaljert tabell for Lån
                with st.expander("Se liste over ordinære lånebetalinger"):
                    st.dataframe(
                        df_debt[df_debt['Category'] == 'Forbrukslån'][['Date', 'Description', 'Out']].sort_values('Date', ascending=False), 
                        use_container_width=True
                    )

        # --- FANE 3: DETALJER (Tabell) ---
        with tab_details:
            st.subheader("Alle Transaksjoner")
            available_categories = sorted(df_view['Category'].unique())
            if available_categories:
                selected_categories = st.multiselect("Filtrer kategori", available_categories, default=available_categories)
                filtered_df = df_view[df_view['Category'].isin(selected_categories)]
            else:
                filtered_df = df_view
            
            st.dataframe(filtered_df[['Date', 'Description', 'Category', 'In', 'Out']].sort_values('Date', ascending=False), use_container_width=True)
            
            csv = filtered_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Last ned CSV", csv, "transaksjoner.csv", "text/csv")

    else:
        st.info("👈 Last opp filer for å starte.")

if __name__ == "__main__":
    main()
