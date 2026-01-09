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
    'Gjeld & Finans',
    'Sparing & Overføring',
    'Shopping & Tech',
    'Transport',
    'Fritid & Abonnement',
    'Annet'
]

# --- HÅNDTERING AV BRUKERREGLER ---
def load_custom_rules():
    # På Streamlit Cloud må filen eksistere i GitHub-repoet for å bli funnet første gang
    if os.path.exists(RULE_FILE):
        try:
            with open(RULE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_custom_rules(rules):
    # Denne lagringen virker kun midlertidig på Streamlit Cloud
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
    if any(x in desc for x in ['lønn', 'lÃ¸nn', 'innskudd', 'renter', 'nav']):
        return 'Inntekt'
    
    if any(x in desc for x in ['overføring mellom egne', 'morsom sparing', 'fondshandel', 'firi', 'aksjesparekont', 'dnb verdipapirservice', 'mobil overføring']):
        return 'Sparing & Overføring'

    if any(x in desc for x in ['leie', 'utleiemegleren', 'fjordkraft', 'strøm', 'efaktura', 'husleie', 'aneo', 'ropo', 'sameiet', 'world energy', 'movel']):
        return 'Bolig & Regninger'

    if any(x in desc for x in ['thorn', 'lowell', 'sambla', 'lån', 'avtalegiro', 'morrow bank', 'ikano', 'svea', 'intrum', 'purring']):
        return 'Gjeld & Finans'

    if any(x in desc for x in ['meny', 'coop', 'rema', 'kiwi', 'joker', 'bunnepris', 'dagligvare']):
        return 'Mat & Drikke'

    if any(x in desc for x in ['microsoft', 'apple', 'elkjøp', 'power', 'klær', 'steam', 'aljibe']):
        return 'Shopping & Tech'

    if any(x in desc for x in ['easypark', 'bensin', 'parkering', 'vy', 'ruter']):
        return 'Transport'
    
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

    # --- SIDEBAR: REGLER OG FILOPPLASTING ---
    with st.sidebar:
        st.header("Filopplasting")
        uploaded_files = st.file_uploader("Velg filer", type=['txt', 'csv'], accept_multiple_files=True)
        
        st.divider()
        st.header("⚙️ Kategori-innstillinger")
        
        with st.expander("Legg til / Endre regler", expanded=False):
            st.info("På Streamlit Cloud slettes endringer når appen restartes. Last ned reglene dine nedenfor og legg filen i GitHub-repoet ditt for å lagre permanent.")
            
            # Skjema for ny regel
            with st.form("add_rule_form"):
                new_keyword = st.text_input("Tekst inneholder (f.eks. 'vipps')")
                new_category = st.selectbox("Sett til kategori", DEFAULT_CATEGORIES)
                submit_rule = st.form_submit_button("Legre regel (Midlertidig)")
                
                if submit_rule and new_keyword:
                    custom_rules[new_keyword.lower()] = new_category
                    save_custom_rules(custom_rules)
                    st.success(f"Regel lagt til. Husk å laste ned JSON-filen!")
                    st.rerun()

            # Slette regler
            if custom_rules:
                st.write("**Aktive regler:**")
                rules_to_delete = []
                for kw, cat in custom_rules.items():
                    col_txt, col_del = st.columns([3, 1])
                    col_txt.text(f"'{kw}' ➔ {cat}")
                    if col_del.button("Slett", key=f"del_{kw}"):
                        rules_to_delete.append(kw)
                
                if rules_to_delete:
                    for kw in rules_to_delete:
                        del custom_rules[kw]
                    save_custom_rules(custom_rules)
                    st.rerun()
            
            # LAST NED JSON KNAPP (VIKTIG FOR CLOUD)
            st.write("---")
            st.write("📥 **Sikkerhetskopi av regler**")
            json_str = json.dumps(custom_rules, indent=4, ensure_ascii=False)
            st.download_button(
                label="Last ned oppdaterte regler (JSON)",
                data=json_str,
                file_name="kategori_regler.json",
                mime="application/json",
                help="Last ned denne og last den opp til GitHub hvis du vil beholde reglene permanent."
            )

    if uploaded_files:
        df = process_uploaded_files(uploaded_files, custom_rules)
        
        if df.empty:
            st.warning("Ingen gyldige data funnet.")
            return

        st.sidebar.divider()
        st.sidebar.header("Filter")
        if df['Date'].dt.year.dropna().empty:
             st.error("Fant ingen gyldige datoer.")
             return

        all_years = sorted(df['Date'].dt.year.dropna().unique().astype(int))
        selected_year = st.sidebar.selectbox("Velg årstall", all_years, index=len(all_years)-1)
        
        df_view = df[df['Date'].dt.year == selected_year].copy()
        
        if df_view.empty:
            st.info(f"Ingen data for {selected_year}.")
            return

        # --- KPI ---
        st.divider()
        col1, col2, col3 = st.columns(3)
        total_in = df_view['In'].sum()
        total_out = df_view['Out'].sum()
        df_no_savings = df_view[df_view['Category'] != 'Sparing & Overføring']
        real_spending = df_no_savings['Out'].sum()
        
        col1.metric("Total Inntekt", f"{total_in:,.0f} kr")
        col2.metric("Total Ut", f"{total_out:,.0f} kr", delta=f"{total_in - total_out:,.0f} Netto")
        col3.metric("Faktisk Forbruk", f"{real_spending:,.0f} kr", help="Ekskl. sparing")
        
        st.divider()

        # --- GRAFER ---
        monthly = df_view.groupby('Month')[['In', 'Out']].sum()
        monthly.index = monthly.index.astype(str)
        monthly_expenses_real = df_no_savings.groupby('Month')['Out'].sum()
        monthly_expenses_real.index = monthly_expenses_real.index.astype(str)

        st.subheader(f"Månedlig Utvikling - {selected_year}")
        plt.style.use('ggplot')
        fig, ax = plt.subplots(figsize=(10, 4))
        x_indexes = range(len(monthly))
        width = 0.4
        ax.bar([x - width/2 for x in x_indexes], monthly['In'], width=width, label='Inntekt', color='green', alpha=0.7)
        ax.bar([x + width/2 for x in x_indexes], monthly_expenses_real, width=width, label='Faktisk Forbruk', color='red', alpha=0.7)
        ax.set_xticks(list(x_indexes))
        ax.set_xticklabels(monthly.index, rotation=45)
        ax.set_ylabel("Beløp (NOK)")
        ax.legend()
        ax.grid(axis='y', linestyle='--', alpha=0.5)
        st.pyplot(fig)

        st.subheader("Hva går pengene til?")
        col_chart, col_data = st.columns([2, 1])
        with col_chart:
            expense_categories = df_no_savings.groupby('Category')['Out'].sum().sort_values(ascending=False)
            expense_categories = expense_categories[expense_categories > 0]
            if not expense_categories.empty:
                fig2, ax2 = plt.subplots(figsize=(6, 6))
                expense_categories.plot(kind='pie', ax=ax2, autopct='%1.1f%%', startangle=90, cmap='tab10')
                ax2.set_ylabel('')
                st.pyplot(fig2)
            else:
                st.info("Ingen utgifter å vise.")
        with col_data:
            st.dataframe(expense_categories, height=300)

        # --- PIVOT ---
        st.divider()
        st.subheader("Kategorioversikt (Pivot)")
        df_expenses_only = df_view[~df_view['Category'].isin(['Inntekt', 'Sparing & Overføring'])]
        if not df_expenses_only.empty:
            pivot_table = df_expenses_only.pivot_table(index='Category', columns='Month', values='Out', aggfunc='sum', fill_value=0)
            st.dataframe(pivot_table.style.format("{:,.0f}"), use_container_width=True)

        # --- TRANSAKSJONER ---
        st.subheader("Transaksjonsoversikt")
        available_categories = sorted(df_view['Category'].unique())
        selected_categories = st.multiselect("Filtrer på kategori", available_categories, default=available_categories)
        filtered_df = df_view[df_view['Category'].isin(selected_categories)]
        with st.expander("Vis transaksjonsliste", expanded=True):
            st.dataframe(filtered_df[['Date', 'Description', 'Category', 'In', 'Out']].sort_values('Date', ascending=False), use_container_width=True)
            csv = filtered_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Last ned CSV", csv, f"transaksjoner_{selected_year}.csv", "text/csv")
    else:
        st.info("👈 Last opp filer for å starte.")

if __name__ == "__main__":
    main()
