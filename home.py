import streamlit as st
import pandas as pd
import json
import os

# --- KONFIGURASJON ---
st.set_page_config(page_title="Kontantstrøm & Økonomi", layout="wide", page_icon="📈")
RULE_FILE = "kategori_regler.json"

# --- STANDARD KATEGORIER ---
DEFAULT_CATEGORIES = [
    'Inntekt',
    'Bolig & Regninger',
    'Mat & Drikke',
    'Forbrukslån',        
    'Inkasso & Purring',  
    'Sparing & Overføring',
    'Shopping & Tech',
    'Transport',
    'Fritid & Abonnement',
    'Annet'
]

# --- KONTO-TYPER ---
ACCOUNT_TYPES = [
    "Brukskonto",
    "Regningskonto",
    "Sparekonto",
    "Kredittkort",
    "Annet"
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
    desc = str(description).lower() if description else ""
    
    # 1. SJEKK BRUKERENS EGNE REGLER FØRST
    for keyword, category in custom_rules.items():
        if keyword.lower() in desc:
            return category

    # 2. STANDARD LOGIKK (FALLBACK)
    if any(x in desc for x in ['lønn', 'løn', 'innskudd', 'renter', 'nav', 'trygd']):
        return 'Inntekt'
    
    if any(x in desc for x in ['overføring mellom egne', 'morsom sparing', 'fondshandel', 'firi', 'aksjesparekont', 'dnb verdipapirservice', 'mobil overføring', 'sparing']):
        return 'Sparing & Overføring'

    if any(x in desc for x in ['leie', 'utleiemegleren', 'fjordkraft', 'strøm', 'efaktura', 'husleie', 'aneo', 'ropo', 'sameiet', 'world energy', 'movel', 'kommunale', 'forsikring']):
        return 'Bolig & Regninger'

    if any(x in desc for x in ['purring', 'inkasso', 'intrum', 'lowell', 'namsmann', 'sileo', 'kredinor', 'sergel', 'gjeldsregisteret']):
        return 'Inkasso & Purring'

    if any(x in desc for x in ['thorn', 'sambla', 'lån', 'avtalegiro', 'morrow bank', 'ikano', 'svea', 'resurs', 'bank norwegian', 'santander', 'facit']):
        return 'Forbrukslån'

    if any(x in desc for x in ['meny', 'coop', 'rema', 'kiwi', 'joker', 'bunnepris', 'dagligvare', 'oda.no', 'bunnepris']):
        return 'Mat & Drikke'

    if any(x in desc for x in ['microsoft', 'apple', 'elkjøp', 'power', 'klær', 'steam', 'aljibe', 'komplett', 'vipps']):
        return 'Shopping & Tech'

    if any(x in desc for x in ['easypark', 'bensin', 'parkering', 'vy', 'ruter', 'bom', 'flytoget', 'taxi']):
        return 'Transport'
    
    if any(x in desc for x in ['sats', 'netflix', 'spotify', 'restaurant', 'bar', 'vinmonopolet', 'hbo', 'disney', 'kino']):
        return 'Fritid & Abonnement'

    return 'Annet'

# --- HJELPEFUNKSJON FOR KOLONNER ---
def standardize_columns(df):
    col_map = {}
    for col in df.columns:
        c_lower = col.lower()
        if 'dato' in c_lower and 'rente' not in c_lower:
            col_map[col] = 'Date'
        elif any(x in c_lower for x in ['forklaring', 'beskrivelse', 'tekst', 'transaksjonstype']):
            col_map[col] = 'Description'
        elif 'ut' in c_lower and ('konto' in c_lower or 'beløp' in c_lower):
            col_map[col] = 'Out'
        elif 'inn' in c_lower and ('konto' in c_lower or 'beløp' in c_lower):
            col_map[col] = 'In'
        elif 'beløp' in c_lower and 'ut' not in c_lower and 'inn' not in c_lower:
             col_map[col] = 'Amount_Single_Col'
            
    df.rename(columns=col_map, inplace=True)
    return df

# --- LASTE INN DATA FRA UPLOAD ---
def process_uploaded_files(uploaded_files, custom_rules, file_mapping):
    all_data = []
    
    for uploaded_file in uploaded_files:
        try:
            df = None
            uploaded_file.seek(0)
            
            # Prøv å lese filen (UTF-8 først, så Latin1)
            try:
                if uploaded_file.name.lower().endswith('.txt'):
                    df = pd.read_csv(uploaded_file, sep=';', encoding='latin1', on_bad_lines='skip')
                elif uploaded_file.name.lower().endswith('.csv'):
                    try:
                        df = pd.read_csv(uploaded_file, sep=',', encoding='utf-8')
                    except UnicodeDecodeError:
                        uploaded_file.seek(0)
                        df = pd.read_csv(uploaded_file, sep=';', encoding='latin1')
            except Exception:
                continue 
            
            if df is not None:
                # Rens kolonnenavn
                df.columns = [c.strip().replace('"', '') for c in df.columns]
                df = standardize_columns(df)
                
                # Legg til konto-navn
                assigned_account = file_mapping.get(uploaded_file.name, "Ukjent")
                df['Account'] = assigned_account
                
                all_data.append(df)
            
        except Exception as e:
            st.error(f"Feil med fil {uploaded_file.name}: {e}")

    if not all_data:
        return pd.DataFrame()

    combined_df = pd.concat(all_data, ignore_index=True)
    
    # Håndter 'Amount_Single_Col' (hvis filen har én kolonne for beløp)
    if 'Amount_Single_Col' in combined_df.columns:
        combined_df['Amount_Single_Col'] = combined_df['Amount_Single_Col'].astype(str).str.replace('"', '').str.replace(' ', '').str.replace(',', '.')
        combined_df['Amount_Single_Col'] = pd.to_numeric(combined_df['Amount_Single_Col'], errors='coerce').fillna(0)
        combined_df['In'] = combined_df['Amount_Single_Col'].apply(lambda x: x if x > 0 else 0)
        combined_df['Out'] = combined_df['Amount_Single_Col'].apply(lambda x: abs(x) if x < 0 else 0)

    for required_col in ['Out', 'In']:
        if required_col not in combined_df.columns:
            combined_df[required_col] = 0
    
    if 'Date' not in combined_df.columns:
         return pd.DataFrame()

    combined_df['Date'] = pd.to_datetime(combined_df['Date'], dayfirst=True, errors='coerce')
    
    # Rens tall (fjerner mellomrom, bytter komma til punktum)
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
    st.title("📊 Økonomisk Oversikt & Kontantstrøm")
    
    custom_rules = load_custom_rules()

    # --- SIDEBAR ---
    with st.sidebar:
        st.header("1. Last opp filer")
        uploaded_files = st.file_uploader("Last opp CSV/TXT fra banken", type=['txt', 'csv'], accept_multiple_files=True)
        
        file_mapping = {}
        
        # --- KONTO-VELGER ---
        if uploaded_files:
            st.write("---")
            st.header("2. Velg kontoer")
            st.info("Hvilken konto tilhører hver fil?")
            for f in uploaded_files:
                account = st.selectbox(
                    f"Fil: {f.name}", 
                    ACCOUNT_TYPES, 
                    key=f.name
                )
                file_mapping[f.name] = account
        
        st.write("---")
        with st.expander("⚙️ Endre kategorier", expanded=False):
            with st.form("add_rule_form"):
                new_keyword = st.text_input("Tekst inneholder (f.eks. 'vipps')")
                new_category = st.selectbox("Kategori", DEFAULT_CATEGORIES)
                submit_rule = st.form_submit_button("Lagre regel")
                if submit_rule and new_keyword:
                    custom_rules[new_keyword.lower()] = new_category
                    save_custom_rules(custom_rules)
                    st.success("Lagret!")
                    st.rerun()
            
            # Last ned regler-knapp
            json_str = json.dumps(custom_rules, indent=4, ensure_ascii=False)
            st.download_button("📥 Last ned regler", json_str, "kategori_regler.json", "application/json")

    if uploaded_files:
        # Prosesser filer
        df = process_uploaded_files(uploaded_files, custom_rules, file_mapping)
        
        if df.empty or df['Date'].dt.year.dropna().empty:
            st.warning("Ingen gyldige data funnet. Sjekk filformatet.")
            return

        st.sidebar.divider()
        all_years = sorted(df['Date'].dt.year.dropna().unique().astype(int))
        # Velg siste år som standard
        selected_year = st.sidebar.selectbox("Velg årstall", all_years, index=len(all_years)-1)
        
        df_view = df[df['Date'].dt.year == selected_year].copy()

        # --- TABS ---
        tab_overview, tab_debt, tab_details = st.tabs(["Oversikt", "⚠️ Gjeld & Lån", "Detaljer"])

        # --- FANE 1: OVERSIKT ---
        with tab_overview:
            st.subheader(f"Status for {selected_year}")
            
            # KPIer
            col1, col2, col3 = st.columns(3)
            total_in = df_view['In'].sum()
            total_out = df_view['Out'].sum()
            resultat = total_in - total_out
            
            col1.metric("Inn", f"{total_in:,.0f} kr")
            col2.metric("Ut", f"{total_out:,.0f} kr")
            col3.metric("Resultat", f"{resultat:,.0f} kr", delta_color="normal")
            
            st.divider()
            
            # Oversikt per konto (Tabell)
            st.subheader("Fordeling per konto")
            account_summary = df_view.groupby('Account')[['In', 'Out']].sum()
            account_summary['Netto'] = account_summary['In'] - account_summary['Out']
            st.dataframe(account_summary.style.format("{:,.0f} kr"), use_container_width=True)
            
            st.divider()

            # --- NY GRAF: KONTANTSTRØM (LIKVIDITET) ---
            st.subheader("🌊 Kontantstrøm: Saldo-utvikling")
            st.caption(f"Viser hvordan pengene har flyttet seg gjennom {selected_year} (akkumulert). Går linjen nedover, bruker du mer enn du tjener i den perioden.")
            
            # Sorter kronologisk
            df_liq = df_view.sort_values('Date').copy()
            # Beregn netto per transaksjon
            df_liq['Netto'] = df_liq['In'] - df_liq['Out']
            # Grupper per dag og summer
            daily_flow = df_liq.groupby('Date')['Netto'].sum()
            # Beregn løpende sum (Cumulative Sum)
            cumulative_balance = daily_flow.cumsum()
            
            st.line_chart(cumulative_balance)

            # --- MÅNEDLIG SØYLER ---
            st.divider()
            st.subheader("Inntekter vs Utgifter (Månedlig)")
            monthly = df_view.groupby('Month')[['In', 'Out']].sum()
            monthly.index = monthly.index.astype(str)
            st.bar_chart(monthly, color=["#4ade80", "#f87171"]) # Grønn og Rød

        # --- FANE 2: GJELD ---
        with tab_debt:
            st.header("Gjeldsoversikt")
            debt_cats = ['Forbrukslån', 'Inkasso & Purring']
            df_debt = df_view[df_view['Category'].isin(debt_cats)].copy()
            
            if not df_debt.empty:
                col_d1, col_d2 = st.columns(2)
                lån_sum = df_debt[df_debt['Category'] == 'Forbrukslån']['Out'].sum()
                inkasso_sum = df_debt[df_debt['Category'] == 'Inkasso & Purring']['Out'].sum()
                
                col_d1.metric("Ordinære Lån/Kreditt", f"{lån_sum:,.0f} kr")
                col_d2.metric("Inkasso & Purring", f"{inkasso_sum:,.0f} kr", delta="-Unødvendig", delta_color="inverse")
                
                st.divider()
                st.subheader("Hvilken konto trekkes gjelden fra?")
                debt_by_acc = df_debt.groupby('Account')['Out'].sum()
                st.bar_chart(debt_by_acc)
                
                st.subheader("Detaljert liste over gjeldsposter")
                st.dataframe(
                    df_debt[['Date', 'Description', 'Category', 'Out', 'Account']].sort_values('Date', ascending=False), 
                    use_container_width=True
                )
            else:
                st.success("Ingen gjeldsutgifter (lån/inkasso) funnet i denne perioden! 🎉")

        # --- FANE 3: DETALJER ---
        with tab_details:
            st.subheader("Søk i transaksjoner")
            
            # Filtrering
            c1, c2 = st.columns(2)
            acc_filter = c1.multiselect("Filtrer på konto", df_view['Account'].unique())
            cat_filter = c2.multiselect("Filtrer på kategori", sorted(df_view['Category'].unique()))
            
            filtered = df_view.copy()
            if acc_filter:
                filtered = filtered[filtered['Account'].isin(acc_filter)]
            if cat_filter:
                filtered = filtered[filtered['Category'].isin(cat_filter)]
            
            # Søkefelt
            search_term = st.text_input("Søk i beskrivelse (f.eks. 'Rema')")
            if search_term:
                filtered = filtered[filtered['Description'].astype(str).str.contains(search_term, case=False, na=False)]

            st.dataframe(
                filtered[['Date', 'Description', 'Category', 'Account', 'In', 'Out']].sort_values('Date', ascending=False), 
                use_container_width=True
            )
            
            # Last ned CSV
            csv = filtered.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Last ned utvalg som CSV", csv, "transaksjoner_filtert.csv", "text/csv")

    else:
        st.info("👈 Start med å laste opp filer i menyen til venstre.")

if __name__ == "__main__":
    main()
