import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
import io

# Configuration de la page
st.set_page_config(
    page_title="Suivi de conduite - Poids Lourd",
    page_icon="🚛",
    layout="wide"
)

st.title("🚛 Suivi des heures de conduite - Objectif 210h/mois")
st.markdown("Application de gestion de trajets pour chauffeur poids lourd")

# Initialisation du dataframe en session_state
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame(columns=[
        'Date', 'Heure_Debut', 'Heure_Fin', 'Pause_min',
        'Km_Aller', 'Km_Retour', 'Heures_Cond', 'Total_Km'
    ])

# Fonctions utilitaires
def calculer_duree(date_trajet, debut, fin, pause_min):
    """Calcule la durée de conduite (fin - début - pause) en heures décimales."""
    debut_dt = datetime.combine(date_trajet, debut)
    fin_dt = datetime.combine(date_trajet, fin)
    # Si l'heure de fin est avant celle de début, on considère que le trajet a eu lieu le lendemain
    if fin_dt < debut_dt:
        fin_dt += timedelta(days=1)
    duree_totale = (fin_dt - debut_dt).total_seconds() / 3600
    duree_conduite = duree_totale - (pause_min / 60)
    return max(0, duree_conduite)  # On évite les valeurs négatives

# Barre latérale : Saisie des trajets
with st.sidebar:
    st.header("📝 Saisir un nouveau trajet")
    with st.form("form_trajet", clear_on_submit=True):
        date_trajet = st.date_input("Date du trajet", value=date.today())
        col1, col2 = st.columns(2)
        with col1:
            heure_debut = st.time_input("Heure de début", value=datetime.strptime("08:00", "%H:%M").time())
        with col2:
            heure_fin = st.time_input("Heure de fin", value=datetime.strptime("17:00", "%H:%M").time())
        pause_min = st.number_input("Pause (minutes)", min_value=0, value=45, step=5)
        col3, col4 = st.columns(2)
        with col3:
            km_aller = st.number_input("Kilomètres Aller", min_value=0.0, value=0.0, step=10.0)
        with col4:
            km_retour = st.number_input("Kilomètres Retour", min_value=0.0, value=0.0, step=10.0)
        
        submitted = st.form_submit_button("➕ Ajouter le trajet")
        
        if submitted:
            duree = calculer_duree(date_trajet, heure_debut, heure_fin, pause_min)
            total_km = km_aller + km_retour
            nouveau = {
                'Date': pd.to_datetime(date_trajet).date(),
                'Heure_Debut': heure_debut,
                'Heure_Fin': heure_fin,
                'Pause_min': pause_min,
                'Km_Aller': km_aller,
                'Km_Retour': km_retour,
                'Heures_Cond': round(duree, 2),
                'Total_Km': total_km
            }
            st.session_state.df = pd.concat(
                [st.session_state.df, pd.DataFrame([nouveau])],
                ignore_index=True
            )
            st.success(f"Trajet ajouté ! {duree:.2f}h de conduite, {total_km:.0f} km")

    st.divider()
    # Sauvegarde et chargement des données (pour persistance sur Streamlit Cloud)
    st.header("💾 Sauvegarde / Chargement")
    
    if not st.session_state.df.empty:
        csv_buffer = io.StringIO()
        st.session_state.df.to_csv(csv_buffer, index=False)
        st.download_button(
            label="📥 Télécharger les données (CSV)",
            data=csv_buffer.getvalue(),
            file_name="trajets_conduite.csv",
            mime="text/csv"
        )
    
    uploaded_file = st.file_uploader("📂 Charger un fichier CSV", type="csv")
    if uploaded_file is not None:
        df_charge = pd.read_csv(uploaded_file)
        # Vérifier la présence des colonnes obligatoires
        if set(['Date','Heure_Debut','Heure_Fin','Pause_min','Km_Aller','Km_Retour']).issubset(df_charge.columns):
            # Convertir les dates
            df_charge['Date'] = pd.to_datetime(df_charge['Date']).dt.date
            # Recalculer Heures_Cond et Total_Km pour sécurité
            for idx, row in df_charge.iterrows():
                duree = calculer_duree(row['Date'], 
                                       datetime.strptime(row['Heure_Debut'], '%H:%M:%S').time() if isinstance(row['Heure_Debut'], str) else row['Heure_Debut'],
                                       datetime.strptime(row['Heure_Fin'], '%H:%M:%S').time() if isinstance(row['Heure_Fin'], str) else row['Heure_Fin'],
                                       row['Pause_min'])
                df_charge.at[idx, 'Heures_Cond'] = round(duree, 2)
                df_charge.at[idx, 'Total_Km'] = row['Km_Aller'] + row['Km_Retour']
            st.session_state.df = df_charge
            st.success("Données chargées avec succès !")
        else:
            st.error("Le fichier CSV ne contient pas les colonnes requises.")

# Zone principale : Analyses
df = st.session_state.df

if df.empty:
    st.info("Aucun trajet enregistré. Utilise le formulaire dans la barre latérale pour commencer.")
    st.stop()

# Préparer les colonnes temporelles pour l'agrégation
df['Date'] = pd.to_datetime(df['Date'])
df['Semaine'] = df['Date'].dt.isocalendar().week.astype(int)
df['Mois'] = df['Date'].dt.to_period('M').astype(str)  # ex: "2025-04"

# Objectif mensuel
OBJECTIF_HEURES = 210

# ---- Onglets ----
tab1, tab2, tab3, tab4 = st.tabs(["📅 Par Jour", "📆 Par Semaine", "📈 Par Mois", "🎯 Progression Objectif"])

with tab1:
    st.subheader("Heures de conduite par jour")
    daily = df.groupby('Date').agg(
        Heures=('Heures_Cond', 'sum'),
        Km=('Total_Km', 'sum')
    ).reset_index().sort_values('Date')
    
    fig_daily = px.bar(daily, x='Date', y='Heures', text=daily['Heures'].round(1),
                       labels={'Heures': 'Heures de conduite', 'Date': 'Jour'},
                       title="Heures conduites par jour")
    fig_daily.update_traces(textposition='outside')
    st.plotly_chart(fig_daily, use_container_width=True)
    
    st.subheader("Kilomètres par jour")
    fig_km = px.bar(daily, x='Date', y='Km', text=daily['Km'].round(1),
                    labels={'Km': 'Kilomètres', 'Date': 'Jour'},
                    color_discrete_sequence=['#EF553B'])
    fig_km.update_traces(textposition='outside')
    st.plotly_chart(fig_km, use_container_width=True)

with tab2:
    st.subheader("Heures de conduite par semaine")
    weekly = df.groupby('Semaine').agg(
        Heures=('Heures_Cond', 'sum'),
        Km=('Total_Km', 'sum'),
        Date_Min=('Date', 'min')
    ).reset_index().sort_values('Date_Min')
    # Créer un libellé de semaine
    weekly['Libellé'] = weekly.apply(lambda r: f"S{r.Semaine} (du {r.Date_Min.strftime('%d/%m')})", axis=1)
    
    fig_weekly = px.bar(weekly, x='Libellé', y='Heures', text=weekly['Heures'].round(1),
                        labels={'Heures': 'Heures', 'Libellé': 'Semaine'},
                        title="Heures par semaine")
    fig_weekly.update_traces(textposition='outside')
    st.plotly_chart(fig_weekly, use_container_width=True)
    
    st.subheader("Kilomètres par semaine")
    fig_week_km = px.bar(weekly, x='Libellé', y='Km', text=weekly['Km'].round(1),
                         labels={'Km': 'Km', 'Libellé': 'Semaine'},
                         color_discrete_sequence=['#EF553B'])
    fig_week_km.update_traces(textposition='outside')
    st.plotly_chart(fig_week_km, use_container_width=True)

with tab3:
    st.subheader("Heures de conduite par mois")
    monthly = df.groupby('Mois').agg(
        Heures=('Heures_Cond', 'sum'),
        Km=('Total_Km', 'sum')
    ).reset_index().sort_values('Mois')
    
    fig_monthly = px.bar(monthly, x='Mois', y='Heures', text=monthly['Heures'].round(1),
                         labels={'Heures': 'Heures', 'Mois': 'Mois'},
                         title="Heures par mois")
    fig_monthly.update_traces(textposition='outside')
    st.plotly_chart(fig_monthly, use_container_width=True)
    
    st.subheader("Kilomètres par mois")
    fig_monthly_km = px.bar(monthly, x='Mois', y='Km', text=monthly['Km'].round(1),
                            labels={'Km': 'Km', 'Mois': 'Mois'},
                            color_discrete_sequence=['#EF553B'])
    fig_monthly_km.update_traces(textposition='outside')
    st.plotly_chart(fig_monthly_km, use_container_width=True)

with tab4:
    st.subheader(f"🎯 Progression vers l'objectif de {OBJECTIF_HEURES}h/mois")
    
    # Filtrer le mois courant (le plus récent dans les données)
    dernier_mois = df['Mois'].max()
    masque_mois = df['Mois'] == dernier_mois
    total_heures_mois = df.loc[masque_mois, 'Heures_Cond'].sum()
    reste = max(0, OBJECTIF_HEURES - total_heures_mois)
    pourcentage = min(100, (total_heures_mois / OBJECTIF_HEURES) * 100)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Heures effectuées", f"{total_heures_mois:.1f} h")
    col2.metric("Objectif", f"{OBJECTIF_HEURES} h")
    col3.metric("Heures restantes", f"{reste:.1f} h")
    
    # Jauge
    fig_gauge = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = total_heures_mois,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': f"Progression - {dernier_mois}"},
        delta = {'reference': OBJECTIF_HEURES, 'increasing': {'color': "red"}},
        gauge = {
            'axis': {'range': [None, OBJECTIF_HEURES]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [0, OBJECTIF_HEURES*0.5], 'color': "lightgray"},
                {'range': [OBJECTIF_HEURES*0.5, OBJECTIF_HEURES*0.8], 'color': "gray"}],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': OBJECTIF_HEURES
                }
        }
    ))
    st.plotly_chart(fig_gauge, use_container_width=True)
    
    # Courbe d'évolution cumulée dans le mois
    mois_actuel_df = df[masque_mois].sort_values('Date')
    mois_actuel_df['Cumul_Heures'] = mois_actuel_df['Heures_Cond'].cumsum()
    
    if not mois_actuel_df.empty:
        fig_cumul = px.line(mois_actuel_df, x='Date', y='Cumul_Heures',
                            title="Évolution cumulée des heures dans le mois",
                            labels={'Cumul_Heures': 'Heures cumulées', 'Date': 'Jour'})
        fig_cumul.add_hline(y=OBJECTIF_HEURES, line_dash="dash", line_color="red",
                            annotation_text=f"Objectif {OBJECTIF_HEURES}h")
        st.plotly_chart(fig_cumul, use_container_width=True)
    else:
        st.info("Pas encore de données pour ce mois.")

# Tableau récapitulatif des trajets
st.divider()
st.subheader("📋 Journal des trajets")
st.dataframe(
    df[['Date', 'Heure_Debut', 'Heure_Fin', 'Pause_min', 'Km_Aller', 'Km_Retour', 'Heures_Cond', 'Total_Km']]
    .sort_values('Date', ascending=False)
    .reset_index(drop=True),
    use_container_width=True
)
