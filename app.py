# app.py
import streamlit as st
import plotly.graph_objects as go
from backend.data_client import NBADataClient
from engine.gemini_client import GeminiAnalyzer
from dotenv import load_dotenv

load_dotenv()
st.set_page_config(page_title="Quant NBA System PRO", layout="wide")

def calculate_implied_probability(odds: float) -> float:
    return (1 / odds) * 100 if odds > 1.0 else 0.0

def plot_net_rating_comparison(data, team_a, team_b):
    """Genera un gráfico comparativo de Net Rating (Season vs L10)"""
    fig = go.Figure()
    
    teams = [team_a, team_b]
    season_ratings = [data[team_a]['season']['net_rating'], data[team_b]['season']['net_rating']]
    l10_ratings = [data[team_a]['last_10']['net_rating'], data[team_b]['last_10']['net_rating']]

    fig.add_trace(go.Bar(x=teams, y=season_ratings, name='Temporada Completa', marker_color='#1f77b4'))
    fig.add_trace(go.Bar(x=teams, y=l10_ratings, name='Últimos 10 Juegos', marker_color='#ff7f0e'))
    
    fig.update_layout(title="Momentum: Net Rating (Season vs L10)", barmode='group', template='plotly_dark')
    return fig

def main():
    st.title("🏀 Dashboard Cuantitativo NBA (Advanced Stats & Vis)")
    
    data_client = NBADataClient()
    llm_engine = GeminiAnalyzer()

    with st.spinner("Cargando catálogo de franquicias..."):
        all_teams = data_client.get_all_teams()

    col1, col2, col3 = st.columns(3)
    with col1:
        team_a = st.selectbox("Equipo Local", all_teams, index=all_teams.index("Boston Celtics") if "Boston Celtics" in all_teams else 0)
        # NUEVO: Input de lesiones
        injuries_a = st.text_input(f"Bajas / Lesiones clave en {team_a}", placeholder="Ej: Jayson Tatum (Out)")
    with col2:
        team_b = st.selectbox("Equipo Visitante", all_teams, index=all_teams.index("Dallas Mavericks") if "Dallas Mavericks" in all_teams else 1)
        # NUEVO: Input de lesiones
        injuries_b = st.text_input(f"Bajas / Lesiones clave en {team_b}", placeholder="Ej: Ninguna")
    with col3:
        market = st.selectbox("Mercado", ["Moneyline (Ganador)"])

    st.markdown("---")
    
    live_odds = data_client.get_live_odds(team_a, team_b)
    
    if not live_odds or "error" in live_odds:
        st.warning("Offseason / Partido inactivo. Ingreso manual de cuotas habilitado.")
        c1, c2 = st.columns(2)
        with c1: odds_team_a = st.number_input(f"Cuota para {team_a}", min_value=1.01, value=1.90, step=0.05)
        with c2: odds_team_b = st.number_input(f"Cuota para {team_b}", min_value=1.01, value=1.90, step=0.05)
    else:
        st.success("✅ Cuotas inyectadas desde The-Odds-API")
        odds_team_a = live_odds.get(team_a, 1.90)
        odds_team_b = live_odds.get(team_b, 1.90)
        st.metric(label=f"Cuota {team_a}", value=odds_team_a)
        st.metric(label=f"Cuota {team_b}", value=odds_team_b)

    if st.button("Ejecutar Análisis Quant Institucional", type="primary"):
        if team_a == team_b:
            st.error("Selecciona equipos distintos.")
            return

        with st.spinner("1. Ingestando Advanced Stats (eFG%, TOV%, OREB%)..."):
            raw_data = data_client.get_matchup_stats(team_a, team_b)
            
            if "error" in raw_data:
                st.error(raw_data["error"])
                return

            # Enriqueciendo el JSON con Cuotas Y LESIONES
            raw_data["betting_market"] = {
                team_a: {"odds": odds_team_a, "implied_probability": round(calculate_implied_probability(odds_team_a), 2)},
                team_b: {"odds": odds_team_b, "implied_probability": round(calculate_implied_probability(odds_team_b), 2)}
            }
            raw_data["injury_report"] = {
                team_a: injuries_a if injuries_a else "Plantilla completa / Sin reportes",
                team_b: injuries_b if injuries_b else "Plantilla completa / Sin reportes"
            }

        # Renderizado Visual Interactivo
        st.subheader("📈 Telemetría Cuantitativa de Franquicias")
        st.plotly_chart(plot_net_rating_comparison(raw_data["matchup_data"], team_a, team_b), use_container_width=True)

        with st.spinner("2. Procesando Motor de Lenguaje (Gemini 2.5 Pro)..."):
            analysis = llm_engine.analyze_matchup(raw_data, market)
            
            st.subheader("🧠 Reporte Analítico y Detección de +EV")
            st.write(analysis)
            
            with st.expander("Inspeccionar JSON Data Payload (Auditoría)"):
                st.json(raw_data)

if __name__ == "__main__":
    main()