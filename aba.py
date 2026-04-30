import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
from supabase import create_client, Client

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
        return df
    else:
        return pd.DataFrame(columns=[
            'id', 'date', 'heure_debut', 'heure_fin', 'pause_min',
            'km_aller', 'km_retour', 'heures_cond', 'total_km'
        ])

def ajouter_trajet(date, debut, fin, pause, km_a, km_r):
    """Insère un trajet dans Supabase."""
    duree = calculer_duree(date, debut, fin, pause)
    total_km = km_a + km_r
    data = {
        'date': str(date),
        'heure_debut': debut.strftime('%H:%M:%S'),
        'heure_fin': fin.strftime('%H:%M:%S'),
        'pause_min': pause,
        'km_aller': km_a,
        'km_retour': km_r,
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
            km_aller = st.number_input("Km Aller", min_value=0.0, value=0.0, step=10.0)
        with col4:
            km_retour = st.number_input("Km Retour", min_value=0.0, value=0.0, step=10.0)

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

# Onglets
tab1, tab2, tab3, tab4 = st.tabs(["📅 Par Jour", "📆 Par Semaine", "📈 Par Mois", "🎯 Progression Objectif"])

with tab1:
    st.subheader("Courbes par jour")
    daily = df.groupby('Date').agg(
        Heures=('Heures_Cond','sum'),
        Km=('Total_Km','sum')
    ).reset_index().sort_values('Date')

    col1, col2 = st.columns(2)
    with col1:
        fig_heures = px.line(daily, x='Date', y='Heures', markers=True,
                             labels={'Heures':'Heures', 'Date':'Jour'},
                             title="Heures conduites par jour")
        fig_heures.update_traces(line=dict(width=2, color='#1f77b4'))
        st.plotly_chart(fig_heures, use_container_width=True)
    with col2:
        fig_km = px.line(daily, x='Date', y='Km', markers=True,
                         labels={'Km':'Kilomètres', 'Date':'Jour'},
                         title="Kilomètres par jour")
        fig_km.update_traces(line=dict(width=2, color='#EF553B'))
        st.plotly_chart(fig_km, use_container_width=True)

with tab2:
    st.subheader("Courbes par semaine")
    weekly = df.groupby('Semaine').agg(
        Heures=('Heures_Cond','sum'),
        Km=('Total_Km','sum'),
        Date_Min=('Date','min')
    ).reset_index().sort_values('Date_Min')
    weekly['Libellé'] = weekly.apply(
        lambda r: f"S{r.Semaine} (du {r.Date_Min.strftime('%d/%m')})", axis=1)

    col1, col2 = st.columns(2)
    with col1:
        fig_heures_w = px.line(weekly, x='Libellé', y='Heures', markers=True,
                               labels={'Heures':'Heures', 'Libellé':'Semaine'},
                               title="Heures par semaine")
        fig_heures_w.update_traces(line=dict(width=2, color='#1f77b4'))
        st.plotly_chart(fig_heures_w, use_container_width=True)
    with col2:
        fig_km_w = px.line(weekly, x='Libellé', y='Km', markers=True,
                           labels={'Km':'Kilomètres', 'Libellé':'Semaine'},
                           title="Kilomètres par semaine")
        fig_km_w.update_traces(line=dict(width=2, color='#EF553B'))
        st.plotly_chart(fig_km_w, use_container_width=True)

with tab3:
    st.subheader("Courbes par mois")
    monthly = df.groupby('Mois').agg(
        Heures=('Heures_Cond','sum'),
        Km=('Total_Km','sum')
    ).reset_index().sort_values('Mois')

    col1, col2 = st.columns(2)
    with col1:
        fig_heures_m = px.line(monthly, x='Mois', y='Heures', markers=True,
                               labels={'Heures':'Heures', 'Mois':'Mois'},
                               title="Heures par mois")
        fig_heures_m.update_traces(line=dict(width=2, color='#1f77b4'))
        st.plotly_chart(fig_heures_m, use_container_width=True)
    with col2:
        fig_km_m = px.line(monthly, x='Mois', y='Km', markers=True,
                           labels={'Km':'Kilomètres', 'Mois':'Mois'},
                           title="Kilomètres par mois")
        fig_km_m.update_traces(line=dict(width=2, color='#EF553B'))
        st.plotly_chart(fig_km_m, use_container_width=True)

with tab4:
    st.subheader(f"🎯 Objectif {OBJECTIF_HEURES}h/mois")
    dernier_mois = df['Mois'].max()
    masque = df['Mois'] == dernier_mois
    total_heures = df.loc[masque, 'Heures_Cond'].sum()
    reste = max(0, OBJECTIF_HEURES - total_heures)

    col1, col2, col3 = st.columns(3)
    col1.metric("Heures effectuées", f"{total_heures:.1f} h")
    col2.metric("Objectif", f"{OBJECTIF_HEURES} h")
    col3.metric("Heures restantes", f"{reste:.1f} h")

    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=total_heures,
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

    mois_courant = df[masque].sort_values('Date')
    mois_courant['Cumul'] = mois_courant['Heures_Cond'].cumsum()
    if not mois_courant.empty:
        fig_cumul = px.line(mois_courant, x='Date', y='Cumul',
                            title="Évolution cumulée dans le mois",
                            labels={'Cumul':'Heures cumulées', 'Date':'Jour'})
        fig_cumul.add_hline(y=OBJECTIF_HEURES, line_dash="dash", line_color="red",
                            annotation_text=f"Objectif {OBJECTIF_HEURES}h")
        st.plotly_chart(fig_cumul, use_container_width=True)
    else:
        st.info("Pas encore de données pour ce mois.")

# Tableau récapitulatif
st.divider()
st.subheader("📋 Historique des trajets")
st.dataframe(
    df[['Date', 'Heure_Debut', 'Heure_Fin', 'Pause_min', 'Km_Aller', 'Km_Retour', 'Heures_Cond', 'Total_Km']]
    .sort_values('Date', ascending=False).reset_index(drop=True),
    use_container_width=True
)
