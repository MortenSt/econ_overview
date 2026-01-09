import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import io
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
    desc = str(description).lower()
    
    # 1. SJEKK BRUKERENS EGNE REGLER FØRST
    for keyword, category in custom_rules.items():
        if keyword.lower() in desc:
            return category

    # 2. STANDARD LOGIKK (FALLBACK)
    
    # INNTEKT
    if any(x in desc for x in ['lønn', 'lÃ¸nn', 'innskudd', 'renter', 'nav']):
        return 'Inntekt'
    
    # SPARING
    if any(x in desc for x in ['overføring mellom egne', 'morsom sparing', 'fondshandel', 'firi', 'aksjesparekont', 'dnb verdipapirservice', 'mobil overføring']):
        return 'Sparing & Overføring'

    # BOLIG
    if any(x in desc for x in ['leie', 'utleiemegleren', 'fjordkraft', 'strøm', 'efaktura', 'husleie', 'aneo', 'ropo', 'sameiet', 'world energy', 'movel']):
        return 'Bolig & Regninger'

    # --- NY: INKASSO OG PURRING (Høyeste prioritet av gjeld) ---
    # Her fanger vi opp ord som indikerer problemer/gebyrer
    if any(x in desc for x in ['purring', 'inkasso', 'intrum', 'lowell', 'namsmann', 'sileo', 'kredinor', 'sergel']):
        return 'Inkasso & Purring'

    # --- NY: FORBRUKSLÅN (Ordinær betjening) ---
    if any(x in desc for x in ['thorn', 'sambla', 'lån', 'avtalegiro', 'morrow bank', 'ikano', 'svea', 'resurs', 'bank norwegian', 'santander']):
        return 'Forbrukslån'

    # DAGLIGVARE
    if any(x in desc for x in ['meny', 'coop', 'rema', 'kiwi', 'joker', 'bunnepris', 'dagligvare']):
        return 'Mat & Drikke'

    # SHOPPING
    if any(x in desc for x in ['microsoft', 'apple', 'elkjøp', 'power', 'klær', 'steam', 'aljibe']):
        return 'Shopping & Tech'

    # TRANSPORT
    if any(x in desc for x in ['easypark', 'bensin', 'parkering', 'vy', 'ruter']):
        return 'Transport'
    
    # FRITID
    if any(x in desc for x in ['sats', 'netflix', 'spotify', 'restaurant', 'bar']):
        return 'Fritid & Abonnement'

    return 'Annet'

# --- HJELPEFUNKSJON FOR KOLONNER ---
def standardize_columns(df):
    col_map = {}
    for col in df.columns:
        c_lower = col.lower()
        if 'dato' in c_lower and 'rente' not in c_lower:
            col_map[col] = 'Date'
        elif 'forklaring' in c_lower or 'beskrivelse' in c_lower or 'tekst' in c_lower:
            col_map[col] = 'Description'
        elif 'ut' in c_lower and ('konto' in c_lower or 'beløp' in c_lower):
            col_map[col] = 'Out'
        elif 'inn' in c_lower and ('konto' in c_lower or 'beløp' in c_lower):
            col_map[col] = 'In'
            
    df.rename(columns=col_map, inplace=True)
    return df

# --- LASTE INN DATA FRA UPLOAD ---
@st.cache_data
def process_uploaded_files(uploaded_files, custom_rules):
    all_data = []
    
    for uploaded_file in uploaded_files:
        try:
            df = None
            uploaded_file.seek(0)
            if uploaded_file.name.lower().endswith('.txt'):
                df = pd.read_csv(uploaded_file, sep=';', encoding='latin1', on_bad_lines='skip')
            elif uploaded_file.name.lower().endswith('.csv'):
                df = pd.read_csv(uploaded_file, sep=',', encoding='utf-8')
            
            if df is not None:
                df.columns = [c.strip().replace('"', '') for c in df.columns]
                df = standardize_columns(df)
                all_data.append(df)
            
        except Exception as e:
            st.error(f"Feil ved lesing av {uploaded_file.name}: {e}")

    if not all_data:
        return pd.DataFrame()

    combined_df = pd.concat(all_data, ignore_index=True)
    
    for required_col in ['Out', 'In']:
        if required_col not in combined_df.columns:
            combined_df[required_col] = 0
    
    if 'Date' not in combined_df.columns:
         st.error("Kunne ikke finne datokolonnen i filene.")
         return pd.DataFrame()

    combined_df['Date'] = pd.to_datetime(combined_df['Date'], dayfirst=True, errors='coerce')
    
    for col in ['Out', 'In']:
        if combined_df[col].dtype == object:
            combined_df[col] = combined_df[col].astype(str).str.replace('"', '').str.replace(',', '.')
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
        uploaded_files = st.file_uploader("Velg filer", type=['txt', 'csv'], accept_multiple_files=True)
        
        st.divider()
        st.header("⚙️ Kategori-innstillinger")
        
        with st.expander("Legg til / Endre regler", expanded=False):
            with st.form("add_rule_form"):
                new_keyword = st.text_input("Tekst inneholder (f.eks. 'vipps')")
                new_category = st.selectbox("Sett til kategori", DEFAULT_CATEGORIES)
                submit_rule = st.form_submit_button("Lagre regel (Midlertidig)")
                
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
            st.warning("Ingen data.")
            return

        if df['Date'].dt.year.dropna().empty:
             st.error("Ingen gyldige årstall.")
             return

        st.sidebar.divider()
        all_years = sorted(df['Date'].dt.year.dropna().unique().astype(int))
        selected_year = st.sidebar.selectbox("Velg årstall", all_years, index=len(all_years)-1)
        
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
            monthly.index = monthly.index.astype(str)
            
            st.subheader("Inntekter og Utgifter")
            st.bar_chart(monthly, color=["#4ade80", "#f87171"]) # Grønn og Rød

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
                st.bar_chart(monthly_debt, color=[color_map.get(c, '#888888') for c in monthly_debt.columns])

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
            selected_categories = st.multiselect("Filtrer kategori", available_categories, default=available_categories)
            filtered_df = df_view[df_view['Category'].isin(selected_categories)]
            
            st.dataframe(filtered_df[['Date', 'Description', 'Category', 'In', 'Out']].sort_values('Date', ascending=False), use_container_width=True)
            
            csv = filtered_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Last ned CSV", csv, "transaksjoner.csv", "text/csv")

    else:
        st.info("👈 Last opp filer for å starte.")

if __name__ == "__main__":
    main()
