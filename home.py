import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import io

# --- KONFIGURASJON ---
st.set_page_config(page_title="Økonomisk Oversikt", layout="wide", page_icon="💰")

# --- KATEGORISERINGS-LOGIKK ---
def get_category(description, amount_out):
    desc = str(description).lower()
    
    # Utvidet sjekk for lønn (inkluderer tegnfeil-varianten 'lÃ¸nn' som kan oppstå)
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
    """
    Finner riktige kolonner selv om de har rare tegn (som 'å' i 'på')
    eller heter litt forskjellige ting.
    """
    col_map = {}
    for col in df.columns:
        c_lower = col.lower()
        # Finn Dato (unngå Rentedato)
        if 'dato' in c_lower and 'rente' not in c_lower:
            col_map[col] = 'Date'
        # Finn Beskrivelse
        elif 'forklaring' in c_lower or 'beskrivelse' in c_lower or 'tekst' in c_lower:
            col_map[col] = 'Description'
        # Finn Ut-beløp (ser etter 'ut' og 'konto'/'beløp')
        elif 'ut' in c_lower and ('konto' in c_lower or 'beløp' in c_lower):
            col_map[col] = 'Out'
        # Finn Inn-beløp (ser etter 'inn' og 'konto'/'beløp')
        elif 'inn' in c_lower and ('konto' in c_lower or 'beløp' in c_lower):
            col_map[col] = 'In'
            
    df.rename(columns=col_map, inplace=True)
    return df

# --- LASTE INN DATA FRA UPLOAD ---
@st.cache_data
def process_uploaded_files(uploaded_files):
    all_data = []
    
    for uploaded_file in uploaded_files:
        try:
            df = None
            # Sjekk filtype basert på navn
            if uploaded_file.name.lower().endswith('.txt'):
                # txt filer fra banken (semikolon, latin1)
                df = pd.read_csv(uploaded_file, sep=';', encoding='latin1', on_bad_lines='skip')
            elif uploaded_file.name.lower().endswith('.csv'):
                # csv filer (komma, utf-8)
                df = pd.read_csv(uploaded_file, sep=',', encoding='utf-8')
            
            if df is not None:
                # Rydd opp i kolonnenavn (fjern anførselstegn)
                df.columns = [c.strip().replace('"', '') for c in df.columns]
                
                # Bruk den smarte kolonne-finneren
                df = standardize_columns(df)
                
                all_data.append(df)
            
        except Exception as e:
            st.error(f"Feil ved lesing av {uploaded_file.name}: {e}")

    if not all_data:
        return pd.DataFrame()

    combined_df = pd.concat(all_data, ignore_index=True)
    
    # --- DATAVASK ---
    
    # Sikkerhetssjekk: Opprett kolonner hvis de mangler
    for required_col in ['Out', 'In']:
        if required_col not in combined_df.columns:
            combined_df[required_col] = 0
    
    if 'Date' not in combined_df.columns:
         st.error("Kunne ikke finne datokolonnen i filene. Sjekk at filene inneholder 'Dato'.")
         return pd.DataFrame()

    # Datoer
    combined_df['Date'] = pd.to_datetime(combined_df['Date'], dayfirst=True, errors='coerce')
    
    # Tallvask (fjerne komma/punktum rot)
    for col in ['Out', 'In']:
        if combined_df[col].dtype == object:
            combined_df[col] = combined_df[col].astype(str).str.replace('"', '').str.replace(',', '.')
            combined_df[col] = pd.to_numeric(combined_df[col], errors='coerce').fillna(0)
        else:
            combined_df[col] = combined_df[col].fillna(0)
            
    # Kategorisering
    if 'Description' in combined_df.columns:
        combined_df['Category'] = combined_df.apply(lambda row: get_category(row['Description'], row['Out']), axis=1)
    else:
        combined_df['Category'] = 'Ukjent'
        
    combined_df['Month'] = combined_df['Date'].dt.to_period('M')
    
    return combined_df

# --- HOVEDAPPLIKASJON ---
def main():
    st.title("📊 Økonomisk Analyse")
    st.write("Last opp kontoutskrifter (.txt) eller transaksjonslister (.csv) for å generere rapport.")

    # Sidebar for opplasting og filtre
    with st.sidebar:
        st.header("Filopplasting")
        uploaded_files = st.file_uploader(
            "Velg filer (du kan velge flere)", 
            type=['txt', 'csv'], 
            accept_multiple_files=True
        )
        
    if uploaded_files:
        df = process_uploaded_files(uploaded_files)
        
        if df.empty:
            st.warning("Ingen gyldige data funnet i filene.")
            return

        # Dato-filter i sidebar
        st.sidebar.header("Filter")
        # Håndter tilfeller hvor det ikke finnes årstall
        if df['Date'].dt.year.dropna().empty:
             st.error("Fant ingen gyldige datoer i filene.")
             return

        all_years = sorted(df['Date'].dt.year.dropna().unique().astype(int))
        selected_year = st.sidebar.selectbox("Velg årstall", all_years, index=len(all_years)-1) # Velger siste år som default
        
        # Filtrer data basert på år
        df_view = df[df['Date'].dt.year == selected_year].copy()
        
        if df_view.empty:
            st.info(f"Ingen data for {selected_year}.")
            return

        # --- KPI ---
        st.divider()
        col1, col2, col3 = st.columns(3)
        
        total_in = df_view['In'].sum()
        total_out = df_view['Out'].sum()
        
        # Beregn faktisk forbruk (uten sparing)
        df_no_savings = df_view[df_view['Category'] != 'Sparing & Overføring']
        real_spending = df_no_savings['Out'].sum()
        
        col1.metric("Total Inntekt", f"{total_in:,.0f} kr")
        col2.metric("Total Ut (Alt)", f"{total_out:,.0f} kr", delta=f"{total_in - total_out:,.0f} Netto")
        col3.metric("Faktisk Forbruk", f"{real_spending:,.0f} kr", help="Utgifter ekskludert sparing og interne overføringer")
        
        st.divider()

        # --- GRAFER ---
        
        # Forbered data for grafer
        monthly = df_view.groupby('Month')[['In', 'Out']].sum()
        monthly.index = monthly.index.astype(str) # For at grafen skal vise datoer pent
        
        monthly_expenses_real = df_no_savings.groupby('Month')['Out'].sum()
        monthly_expenses_real.index = monthly_expenses_real.index.astype(str)

        # Graf 1: Månedlig oversikt
        st.subheader(f"Månedlig Utvikling - {selected_year}")
        
        # Matplotlib Plot
        plt.style.use('ggplot')
        fig, ax = plt.subplots(figsize=(10, 4))
        
        # Vi plotter bare Inntekt og Faktisk forbruk for ryddighet
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

        # Graf 2: Kakediagram
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
                st.info("Ingen utgifter å vise i diagrammet.")
            
        with col_data:
            st.write("Detaljer:")
            st.dataframe(expense_categories, height=300)

        # --- DETALJERT TABELL ---
        st.subheader("Siste Transaksjoner")
        with st.expander("Vis transaksjonsliste"):
            st.dataframe(df_view[['Date', 'Description', 'Category', 'In', 'Out']].sort_values('Date', ascending=False), use_container_width=True)

    else:
        st.info("👈 Last opp filer i menyen til venstre for å starte.")

if __name__ == "__main__":
    main()
