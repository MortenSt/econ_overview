import streamlit as st
import pandas as pd
import json
import os

# --- KONFIGURASJON ---
st.set_page_config(page_title="Kontantstrøm & Buffer", layout="wide", page_icon="🛡️")
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

    # 2. STANDARD LOGIKK (SKREDDERSYDD)
    if any(x in desc for x in ['ch prosjekt', 'lønn', 'løn', 'innskudd', 'renter', 'nav', 'trygd']):
        return 'Inntekt'
    
    if any(x in desc for x in ['leie', 'husleie', 'utleiemegleren', 'fjordkraft', 'strøm', 'efaktura', 'aneo', 'sameiet', 'forsikring']):
        return 'Bolig & Regninger'

    if any(x in desc for x in ['facit', 'thorn', 'sambla', 'lån', 'avtalegiro', 'morrow', 'ikano', 'svea', 'resurs', 'bank norwegian', 'santander']):
        return 'Forbrukslån'

    if any(x in desc for x in ['purring', 'inkasso', 'intrum', 'lowell', 'namsmann', 'sileo', 'kredinor', 'sergel']):
        return 'Inkasso & Purring'

    if any(x in desc for x in ['overføring mellom egne', 'morsom sparing', 'fondshandel', 'aksjesparekont', 'sparing']):
        return 'Sparing & Overføring'

    if any(x in desc for x in ['meny', 'coop', 'rema', 'kiwi', 'joker', 'bunnepris', 'dagligvare', 'oda.no']):
        return 'Mat & Drikke'

    if any(x in desc for x in ['microsoft', 'apple', 'elkjøp', 'power', 'klær', 'steam', 'komplett', 'vipps']):
        return 'Shopping & Tech'

    if any(x in desc for x in ['easypark', 'bensin', 'parkering', 'vy', 'ruter', 'bom', 'flytoget', 'taxi']):
        return 'Transport'
    
    if any(x in desc for x in ['sats', 'netflix', 'spotify', 'restaurant', 'bar', 'vinmonopolet', 'hbo', 'kino']):
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
                df.columns = [c.strip().replace('"', '') for c in df.columns]
                df = standardize_columns(df)
                assigned_account = file_mapping.get(uploaded_file.name, "Ukjent")
                df['Account'] = assigned_account
                all_data.append(df)
            
        except Exception as e:
            st.error(f"Feil med fil {uploaded_file.name}: {e}")

    if not all_data:
        return pd.DataFrame()

    combined_df = pd.concat(all_data, ignore_index=True)
    
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
    st.title("📊 Økonomisk Oversikt & Buffer")
    
    custom_rules = load_custom_rules()

    # --- SIDEBAR ---
    with st.sidebar:
        st.header("1. Last opp filer")
        uploaded_files = st.file_uploader("Last opp CSV/TXT fra banken", type=['txt', 'csv'], accept_multiple_files=True)
        
        file_mapping = {}
        
        if uploaded_files:
            st.write("---")
            st.header("2. Velg kontoer")
            for f in uploaded_files:
                default_idx = 0
                f_name = f.name.lower()
                if "sparekonto" in f_name: default_idx = 2
                elif "kreditt" in f_name: default_idx = 3
                elif "løn" in f_name or "regning" in f_name: default_idx = 1
                
                account = st.selectbox(f"Fil: {f.name}", ACCOUNT_TYPES, index=default_idx, key=f.name)
                file_mapping[f.name] = account
        
        # --- BUFFER PLANLEGGER ---
        st.write("---")
        with st.expander("🛡️ Buffer-planlegger", expanded=True):
            st.info("Sett et mål for bufferen din!")
            current_buffer = st.number_input("Dagens saldo på sparekonto:", value=0, step=100)
            buffer_goal = st.number_input("Mitt sparemål (f.eks. 1 månedslønn):", value=25000, step=5000)
        
        # --- FREMTIDSSIMULATOR ---
        with st.expander("🔮 Privat lån (Simulering)", expanded=False):
            simulate_loan = st.checkbox("Inkluder privat lån i beregning", value=True)
            loan_amount = st.number_input("Månedlig beløp", value=1500, step=100)
        
        # --- REGEL-KNAPP ---
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

    if uploaded_files:
        df = process_uploaded_files(uploaded_files, custom_rules, file_mapping)
        
        if df.empty or df['Date'].dt.year.dropna().empty:
            st.warning("Ingen gyldige data funnet.")
            return

        st.sidebar.divider()
        all_years = sorted(df['Date'].dt.year.dropna().unique().astype(int))
        selected_year = st.sidebar.selectbox("Velg årstall", all_years, index=len(all_years)-1)
        
        df_view = df[df['Date'].dt.year == selected_year].copy()

        # --- TABS ---
        tab_overview, tab_debt, tab_details = st.tabs(["Oversikt", "⚠️ Gjeld & Lån", "Detaljer"])

        # --- FANE 1: OVERSIKT ---
        with tab_overview:
            st.subheader(f"Status for {selected_year}")
            
            # 1. BUFFER-STATUS
            if buffer_goal > 0:
                progress = min(current_buffer / buffer_goal, 1.0)
                st.write(f"**Veien til trygghet (Buffer: {current_buffer:,.0f} / {buffer_goal:,.0f} kr)**")
                st.progress(progress)
                if progress < 1.0:
                    st.caption(f"Du mangler **{buffer_goal - current_buffer:,.0f} kr** for å nå målet.")
                else:
                    st.balloons()
                    st.success("Gratulerer! Du har nådd buffer-målet ditt! 🎉")
            
            st.divider()

            # 2. KPIer
            col1, col2, col3 = st.columns(3)
            total_in = df_view['In'].sum()
            total_out = df_view['Out'].sum()
            real_result = total_in - total_out
            
            simulated_cost = 0
            if simulate_loan:
                months_active = df_view['Month'].nunique()
                simulated_cost = loan_amount * months_active
            
            final_result = real_result - simulated_cost
            
            col1.metric("Inn", f"{total_in:,.0f} kr")
            col2.metric("Ut", f"{total_out:,.0f} kr")
            col3.metric("Resultat", f"{final_result:,.0f} kr", 
                        delta=f"-{simulated_cost} kr (lån)" if simulate_loan else None)

            # Råd basert på resultat
            if final_result > 0:
                st.success(f"💪 Bra jobba! Du har et overskudd på **{final_result:,.0f} kr** hittil i år. "
                           f"Dette kan settes rett på bufferkontoen!")
            else:
                st.error(f"⚠️ Underskudd på **{abs(final_result):,.0f} kr**. "
                         "Bufferkontoen tæres på. Pass på utgiftene!")

            st.divider()
            
            # Likviditetsgraf
            st.subheader("🌊 Kontantstrøm: Saldo-utvikling")
            
            df_liq = df_view.sort_values('Date').copy()
            df_liq['Netto'] = df_liq['In'] - df_liq['Out']
            
            if simulate_loan:
                dates = pd.date_range(start=df_liq['Date'].min(), end=df_liq['Date'].max(), freq='ME')
                sim_data = pd.DataFrame({'Date': dates, 'Netto': -loan_amount})
                df_liq = pd.concat([df_liq[['Date', 'Netto']], sim_data[['Date', 'Netto']]], ignore_index=True)
                df_liq = df_liq.sort_values('Date')

            cumulative_balance = df_liq.groupby('Date')['Netto'].sum().cumsum()
            st.line_chart(cumulative_balance)

            # Månedlig
            st.divider()
            st.subheader("Inntekter vs Utgifter")
            monthly = df_view.groupby('Month')[['In', 'Out']].sum()
            monthly.index = monthly.index.astype(str)
            st.bar_chart(monthly, color=["#4ade80", "#f87171"])

        # --- FANE 2: GJELD ---
        with tab_debt:
            st.header("Gjeldsoversikt")
            st.warning(f"ℹ️ **Privat lån:** Husk lånet på 67 000 kr (4% rente). Dette kommer i tillegg til bankgjelden under.")
            
            debt_cats = ['Forbrukslån', 'Inkasso & Purring']
            df_debt = df_view[df_view['Category'].isin(debt_cats)].copy()
            
            if not df_debt.empty:
                col_d1, col_d2 = st.columns(2)
                lån_sum = df_debt[df_debt['Category'] == 'Forbrukslån']['Out'].sum()
                inkasso_sum = df_debt[df_debt['Category'] == 'Inkasso & Purring']['Out'].sum()
                
                col_d1.metric("Banklån/Kreditt (Ut)", f"{lån_sum:,.0f} kr")
                col_d2.metric("Inkasso (Ut)", f"{inkasso_sum:,.0f} kr", delta_color="inverse")
                
                st.subheader("Detaljer")
                st.dataframe(df_debt[['Date', 'Description', 'Category', 'Out', 'Account']].sort_values('Date', ascending=False), use_container_width=True)
            else:
                st.success("Ingen bank-gjeldsutgifter funnet i denne perioden.")

        # --- FANE 3: DETALJER ---
        with tab_details:
            st.subheader("Transaksjoner")
            c1, c2 = st.columns(2)
            acc_filter = c1.multiselect("Filtrer på konto", df_view['Account'].unique())
            cat_filter = c2.multiselect("Filtrer på kategori", sorted(df_view['Category'].unique()))
            
            filtered = df_view.copy()
            if acc_filter: filtered = filtered[filtered['Account'].isin(acc_filter)]
            if cat_filter: filtered = filtered[filtered['Category'].isin(cat_filter)]
            
            search_term = st.text_input("Søk i beskrivelse")
            if search_term:
                filtered = filtered[filtered['Description'].astype(str).str.contains(search_term, case=False, na=False)]

            st.dataframe(filtered[['Date', 'Description', 'Category', 'Account', 'In', 'Out']].sort_values('Date', ascending=False), use_container_width=True)
            csv = filtered.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Last ned CSV", csv, "transaksjoner.csv", "text/csv")

    else:
        st.info("👈 Start med å laste opp filer i menyen til venstre.")

if __name__ == "__main__":
    main()
