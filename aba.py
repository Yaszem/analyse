import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
from supabase import create_client

# Configuration de la page
st.set_page_config(
    page_title="Suivi de conduite - Poids Lourd",
    page_icon="🚛",
    layout="wide"
)

st.title("🚛 Suivi des heures de conduite - Objectif 210h/mois")
st.markdown("Application de gestion de trajets pour chauffeur poids lourd")

# ---------- Connexion à Supabase ----------
@st.cache_resource
def init_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

# ---------- Fonctions utilitaires ----------
def calculer_duree(date_trajet, debut, fin, pause_min):
    debut_dt = datetime.combine(date_trajet, debut)
    fin_dt = datetime.combine(date_trajet, fin)
    if fin_dt < debut_dt:
        fin_dt += timedelta(days=1)
    duree_totale = (fin_dt - debut_dt).total_seconds() / 3600
    duree_conduite = duree_totale - (pause_min / 60)
    return max(0, duree_conduite)

def charger_donnees():
    """Charge tous les trajets depuis Supabase."""
    response = supabase.table("trajets").select("*").order("date", desc=True).execute()
    if response.data:
        df = pd.DataFrame(response.data)
        df['date'] = pd.to_datetime(df['date']).dt.date
        # Conversion des colonnes km en int (au cas où)
        for col in ['km_aller', 'km_retour', 'total_km']:
            df[col] = df[col].astype(int, errors='ignore')
        return df
    else:
        return pd.DataFrame(columns=[
            'id', 'date', 'heure_debut', 'heure_fin', 'pause_min',
            'km_aller', 'km_retour', 'heures_cond', 'total_km'
        ])

def ajouter_trajet(date, debut, fin, pause, km_a, km_r):
    """Insère un trajet dans Supabase."""
    duree = calculer_duree(date, debut, fin, pause)
    total_km = int(km_a) + int(km_r)
    data = {
        'date': str(date),
        'heure_debut': debut.strftime('%H:%M:%S'),
        'heure_fin': fin.strftime('%H:%M:%S'),
        'pause_min': pause,
        'km_aller': int(km_a),
        'km_retour': int(km_r),
        'heures_cond': round(duree, 2),
        'total_km': total_km
    }
    supabase.table("trajets").insert(data).execute()

# ---------- Charger les données existantes ----------
df = charger_donnees()

# Renommer pour compatibilité avec le reste du code
df.columns = ['Id', 'Date', 'Heure_Debut', 'Heure_Fin', 'Pause_min',
              'Km_Aller', 'Km_Retour', 'Heures_Cond', 'Total_Km']

# ---------- Barre latérale : Saisie ----------
with st.sidebar:
    st.header("📝 Nouveau trajet")
    with st.form("form_trajet", clear_on_submit=True):
        date_trajet = st.date_input("Date", value=date.today())
        col1, col2 = st.columns(2)
        with col1:
            heure_debut = st.time_input("Début", value=datetime.strptime("08:00", "%H:%M").time())
        with col2:
            heure_fin = st.time_input("Fin", value=datetime.strptime("17:00", "%H:%M").time())
        pause_min = st.number_input("Pause (min)", min_value=0, value=45, step=5)
        col3, col4 = st.columns(2)
        with col3:
            km_aller = st.number_input("Km Aller", min_value=0, value=0, step=10)
        with col4:
            km_retour = st.number_input("Km Retour", min_value=0, value=0, step=10)

        if st.form_submit_button("➕ Ajouter"):
            ajouter_trajet(date_trajet, heure_debut, heure_fin, pause_min, km_aller, km_retour)
            st.success("Trajet sauvegardé !")
            st.rerun()

# ---------- Zone principale ----------
if df.empty:
    st.info("Aucun trajet. Ajoutes-en via le formulaire.")
    st.stop()

# Nettoyage et préparation
df['Date'] = pd.to_datetime(df['Date'])
df['Semaine'] = df['Date'].dt.isocalendar().week.astype(int)
df['Mois'] = df['Date'].dt.to_period('M').astype(str)
OBJECTIF_HEURES = 210

# ---------- Dialogues (modales) ----------
@st.dialog("Courbes par jour", width="large")
def show_daily_charts(daily):
    col1, col2 = st.columns(2)
    with col1:
        fig_h = px.line(daily, x='Date', y='Heures', markers=True,
                        labels={'Heures':'Heures', 'Date':'Jour'},
                        title="Heures par jour")
        fig_h.update_traces(line=dict(width=2, color='#1f77b4'))
        st.plotly_chart(fig_h, use_container_width=True)
    with col2:
        fig_k = px.line(daily, x='Date', y='Km', markers=True,
                        labels={'Km':'Kilomètres', 'Date':'Jour'},
                        title="Kilomètres par jour")
        fig_k.update_traces(line=dict(width=2, color='#EF553B'))
        st.plotly_chart(fig_k, use_container_width=True)

@st.dialog("Courbes par semaine", width="large")
def show_weekly_charts(weekly):
    col1, col2 = st.columns(2)
    with col1:
        fig_h = px.line(weekly, x='Libellé', y='Heures', markers=True,
                        labels={'Heures':'Heures', 'Libellé':'Semaine'},
                        title="Heures par semaine")
        fig_h.update_traces(line=dict(width=2, color='#1f77b4'))
        st.plotly_chart(fig_h, use_container_width=True)
    with col2:
        fig_k = px.line(weekly, x='Libellé', y='Km', markers=True,
                        labels={'Km':'Kilomètres', 'Libellé':'Semaine'},
                        title="Kilomètres par semaine")
        fig_k.update_traces(line=dict(width=2, color='#EF553B'))
        st.plotly_chart(fig_k, use_container_width=True)

@st.dialog("Courbes par mois", width="large")
def show_monthly_charts(monthly):
    col1, col2 = st.columns(2)
    with col1:
        fig_h = px.line(monthly, x='Mois', y='Heures', markers=True,
                        labels={'Heures':'Heures', 'Mois':'Mois'},
                        title="Heures par mois")
        fig_h.update_traces(line=dict(width=2, color='#1f77b4'))
        st.plotly_chart(fig_h, use_container_width=True)
    with col2:
        fig_k = px.line(monthly, x='Mois', y='Km', markers=True,
                        labels={'Km':'Kilomètres', 'Mois':'Mois'},
                        title="Kilomètres par mois")
        fig_k.update_traces(line=dict(width=2, color='#EF553B'))
        st.plotly_chart(fig_k, use_container_width=True)

@st.dialog("Progression cumulée", width="large")
def show_cumul_chart(mois_courant):
    fig_cumul = px.line(mois_courant, x='Date', y='Cumul',
                        title="Évolution cumulée dans le mois",
                        labels={'Cumul':'Heures cumulées', 'Date':'Jour'})
    fig_cumul.add_hline(y=OBJECTIF_HEURES, line_dash="dash", line_color="red",
                        annotation_text=f"Objectif {OBJECTIF_HEURES}h")
    st.plotly_chart(fig_cumul, use_container_width=True)

# ---------- Agrégations ----------
daily = df.groupby('Date').agg(
    Heures=('Heures_Cond','sum'),
    Km=('Total_Km','sum')
).reset_index().sort_values('Date')

weekly = df.groupby('Semaine').agg(
    Heures=('Heures_Cond','sum'),
    Km=('Total_Km','sum'),
    Date_Min=('Date','min')
).reset_index().sort_values('Date_Min')
weekly['Libellé'] = weekly.apply(
    lambda r: f"S{r.Semaine} (du {r.Date_Min.strftime('%d/%m')})", axis=1)

monthly = df.groupby('Mois').agg(
    Heures=('Heures_Cond','sum'),
    Km=('Total_Km','sum')
).reset_index().sort_values('Mois')

dernier_mois = df['Mois'].max()
masque = df['Mois'] == dernier_mois
total_heures_mois = df.loc[masque, 'Heures_Cond'].sum()
reste = max(0, OBJECTIF_HEURES - total_heures_mois)

mois_courant = df[masque].sort_values('Date')
mois_courant['Cumul'] = mois_courant['Heures_Cond'].cumsum()

# ---------- Onglets principaux ----------
tab1, tab2, tab3, tab4 = st.tabs(["📅 Par Jour", "📆 Par Semaine", "📈 Par Mois", "🎯 Progression Objectif"])

with tab1:
    st.metric("Dernier jour de conduite", 
              f"{daily['Heures'].iloc[-1]:.1f} h / {int(daily['Km'].iloc[-1])} km" if not daily.empty else "N/A")
    if st.button("📊 Voir les courbes par jour", key="btn_daily"):
        show_daily_charts(daily)

with tab2:
    if not weekly.empty:
        st.metric("Dernière semaine", f"{weekly['Heures'].iloc[-1]:.1f} h / {int(weekly['Km'].iloc[-1])} km")
    if st.button("📊 Voir les courbes par semaine", key="btn_weekly"):
        show_weekly_charts(weekly)

with tab3:
    if not monthly.empty:
        st.metric("Dernier mois", f"{monthly['Heures'].iloc[-1]:.1f} h / {int(monthly['Km'].iloc[-1])} km")
    if st.button("📊 Voir les courbes par mois", key="btn_monthly"):
        show_monthly_charts(monthly)

with tab4:
    st.subheader(f"🎯 Objectif {OBJECTIF_HEURES} h/mois")
    col1, col2, col3 = st.columns(3)
    col1.metric("Heures effectuées", f"{total_heures_mois:.1f} h")
    col2.metric("Objectif", f"{OBJECTIF_HEURES} h")
    col3.metric("Heures restantes", f"{reste:.1f} h")

    # Jauge
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=total_heures_mois,
        domain={'x': [0,1], 'y': [0,1]},
        title={'text': f"Progression - {dernier_mois}"},
        delta={'reference': OBJECTIF_HEURES, 'increasing': {'color': "red"}},
        gauge={
            'axis': {'range': [None, OBJECTIF_HEURES]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [0, OBJECTIF_HEURES*0.5], 'color': "lightgray"},
                {'range': [OBJECTIF_HEURES*0.5, OBJECTIF_HEURES*0.8], 'color': "gray"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': OBJECTIF_HEURES
            }
        }
    ))
    st.plotly_chart(fig_gauge, use_container_width=True)

    if not mois_courant.empty:
        if st.button("📈 Voir la progression cumulée", key="btn_cumul"):
            show_cumul_chart(mois_courant)
    else:
        st.info("Pas encore de données pour ce mois.")

# ---------- Tableau récapitulatif ----------
st.divider()
st.subheader("📋 Historique des trajets")
# Affichage sans décimales pour les km
display_df = df[['Date', 'Heure_Debut', 'Heure_Fin', 'Pause_min', 'Km_Aller', 'Km_Retour', 'Heures_Cond', 'Total_Km']].copy()
display_df['Km_Aller'] = display_df['Km_Aller'].astype(int)
display_df['Km_Retour'] = display_df['Km_Retour'].astype(int)
display_df['Total_Km'] = display_df['Total_Km'].astype(int)
st.dataframe(display_df.sort_values('Date', ascending=False).reset_index(drop=True),
             use_container_width=True)
