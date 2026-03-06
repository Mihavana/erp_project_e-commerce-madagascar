import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import os
import groq

# --- LIAISON AVEC LE DOCKER-COMPOSE ---
ANALYTICS_API_URL = os.getenv("ANALYTICS_API_URL", "http://analytics:8001")
GROQ_TOKEN = os.getenv("GROQ_TOKEN", "")
client = groq.Groq(api_key=GROQ_TOKEN)

st.set_page_config(page_title="Dashboard Décisionnel", layout="wide")

st.title("ERP & BI : Pilotage Décisionnel Intelligent")
st.markdown("*Distribution Commerciale - Master 1*")

tab1, tab2, tab3 = st.tabs(["👥 Segmentation Client (RFM)", "📈 Prédictions des Ventes (ARIMA)", "🤖 Reporting IA (NLG)"])

# --- ONGLET 1 : DATA MINING (RFM) ---
with tab1:
    st.header("Analyse RFM & Clustering K-Means")
    if st.button("Lancer la segmentation"):
        with st.spinner("Calcul des clusters en cours..."):
            res = requests.get(f"{ANALYTICS_API_URL}/mining/rfm")
            if res.status_code == 200:
                data = res.json()
                if isinstance(data, dict) and "status" in data:
                    st.warning(data["status"])
                else:
                    df = pd.DataFrame(data)
                    st.dataframe(df)
                    fig = px.scatter(df, x="recence", y="frequence", size="montant_total", color="segment",
                                     title="Répartition des Segments Clients (VIP vs Risque)",
                                     color_discrete_map={"VIP": "green", "Occasionnels": "blue", "À risque": "red"})
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.error("Erreur de connexion au service Analytics.")

# --- ONGLET 2 : PRÉDICTIONS (ARIMA) ---
with tab2:
    st.header("Prédiction des Ventes sur 3 Mois")
    if st.button("Lancer les prédictions (ARIMA)"):
        with st.spinner("Modélisation des séries temporelles..."):
            res = requests.get(f"{ANALYTICS_API_URL}/mining/predictions")
            if res.status_code == 200:
                data = res.json()
                if data.get("status") == "mock":
                    st.info(data["message"])
                
                df_pred = pd.DataFrame(data["data"])
                df_pred.columns = ["Période", "Chiffre d'Affaires Prévu (€)"]
                
                st.dataframe(df_pred)
                fig2 = px.line(df_pred, x="Période", y="Chiffre d'Affaires Prévu (€)", markers=True,
                               title="Tendance des Ventes Futures", line_shape="spline")
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.error("Erreur lors des prédictions.")

# --- ONGLET 3 : IA & NLG ---
with tab3:
    st.header("Génération de Rapport Assisté par IA")
    
    if st.button("🤖 Générer le Rapport (via Groq)"):
        with st.spinner("Analyse ultra-rapide..."):
            try:
                # Récupération des chiffres
                kpi_res = requests.get(f"{ANALYTICS_API_URL}/kpis")
                kpis = kpi_res.json()
                ca, marge = kpis.get("ca_total", 0), kpis.get("marge_totale", 0)
                ca_precedent = kpis.get("ca_annee_derniere", 40000000)

                croissance = ((ca - ca_precedent) / ca_precedent) * 100

                # Appel à Groq (Modèle Llama 3)
                chat_completion = client.chat.completions.create(
                    messages=[{
                        "role": "user",
                        "content": f"""
                        Rédige un rapport financier court avec ces données :
                        - CA Actuel : {ca}€
                        - Marge : {marge}€
                        - Croissance par rapport à l'an dernier : {croissance:.1f}%
                        Ne laisse pas de variables comme 'X%' dans le texte.
                        """
                    }],
                    model="llama-3.1-8b-instant",
                )
                
                texte_ia = chat_completion.choices[0].message.content
                st.success("Rapport généré instantanément !")
                st.info(f'"{texte_ia}"')

            except Exception as e:
                st.error(f"Erreur Groq : {e}")
                st.info(f"Fallback : CA {ca}€, Marge {marge}€.")
