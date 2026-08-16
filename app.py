# app.py
import streamlit as st
import plotly.graph_objects as go
from backend.data_client import NBADataClient
from engine.gemini_client import GeminiAnalyzer
from dotenv import load_dotenv

# Carga de variables de entorno (.env)
load_dotenv()

# Configuración base de la interfaz
st.set_page_config(page_title="Quant NBA System PRO", layout="wide")

# ==========================================
# FUNCIONES AUXILIARES Y DE CACHÉ
# ==========================================

@st.cache_data(ttl=3600) # El caché dura 1 hora para evitar ser bloqueados por la API de la NBA
def cached_get_matchup_stats(_client, team_a, team_b):
    """
    Envoltorio cacheado para la ingesta de datos. 
    Evita hacer requests repetidos si el usuario solo cambia parámetros locales (ej. cuotas o lesiones).
    """
    return _client.get_matchup_stats(team_a, team_b)

def calculate_implied_probability(odds: float) -> float:
    """Calcula la probabilidad implícita a partir de una cuota decimal (European Odds)."""
    return (1 / odds) * 100 if odds > 1.0 else 0.0

def plot_net_rating_comparison(data, team_a, team_b):
    """Genera un gráfico comparativo de Net Rating (Season vs L10) usando Plotly."""
    fig = go.Figure()
    
    teams = [team_a, team_b]
    season_ratings = [data[team_a]['season']['net_rating'], data[team_b]['season']['net_rating']]
    l10_ratings = [data[team_a]['last_10']['net_rating'], data[team_b]['last_10']['net_rating']]

    # Barras de Temporada Completa
    fig.add_trace(go.Bar(x=teams, y=season_ratings, name='Temporada Completa', marker_color='#1f77b4'))
    # Barras de Tendencia Reciente (Últimos 10)
    fig.add_trace(go.Bar(x=teams, y=l10_ratings, name='Últimos 10 Juegos', marker_color='#ff7f0e'))
    
    fig.update_layout(title="Momentum: Net Rating (Season vs L10)", barmode='group', template='plotly_dark')
    return fig

# ==========================================
# BUCLE PRINCIPAL DE LA APLICACIÓN
# ==========================================

def main():
    st.title("🏀 Dashboard Cuantitativo NBA (Advanced Stats, Vis & Injuries)")
    st.markdown("Plataforma de arbitraje financiero deportivo basada en *Los 4 Factores* y Modelos de Lenguaje.")
    
    # Inicialización de clientes
    data_client = NBADataClient()
    llm_engine = GeminiAnalyzer()

    # Carga de catálogo de franquicias desde la API estática
    with st.spinner("Cargando catálogo de franquicias..."):
        all_teams = data_client.get_all_teams()

    # Controles de Interfaz: Equipos, Lesiones y Mercado
    col1, col2, col3 = st.columns(3)
    with col1:
        team_a = st.selectbox("Equipo Local", all_teams, index=all_teams.index("Boston Celtics") if "Boston Celtics" in all_teams else 0)
        injuries_a = st.text_input(f"Bajas / Lesiones en {team_a}", placeholder="Ej: Jayson Tatum (Out)")
    with col2:
        team_b = st.selectbox("Equipo Visitante", all_teams, index=all_teams.index("Dallas Mavericks") if "Dallas Mavericks" in all_teams else 1)
        injuries_b = st.text_input(f"Bajas / Lesiones en {team_b}", placeholder="Ej: Ninguna")
    with col3:
        market = st.selectbox("Mercado", ["Moneyline (Ganador)"])

    st.markdown("---")
    st.subheader("Cuotas del Mercado (Pipeline Híbrido)")
    
    # Lógica de Extracción de Cuotas (Fallback en caso de Offseason)
    live_odds = data_client.get_live_odds(team_a, team_b)
    
    if not live_odds or "error" in live_odds:
        st.warning("Offseason / Partido inactivo hoy. Ingreso manual de cuotas habilitado para Backtesting.")
        c1, c2 = st.columns(2)
        with c1: odds_team_a = st.number_input(f"Cuota para {team_a}", min_value=1.01, value=1.90, step=0.05)
        with c2: odds_team_b = st.number_input(f"Cuota para {team_b}", min_value=1.01, value=1.90, step=0.05)
    else:
        st.success("✅ Cuotas inyectadas exitosamente desde The-Odds-API")
        odds_team_a = live_odds.get(team_a, 1.90)
        odds_team_b = live_odds.get(team_b, 1.90)
        st.metric(label=f"Cuota {team_a}", value=odds_team_a)
        st.metric(label=f"Cuota {team_b}", value=odds_team_b)

    # ==========================================
    # EJECUCIÓN DEL MOTOR CUANTITATIVO
    # ==========================================
    if st.button("Ejecutar Análisis Quant Institucional", type="primary"):
        if team_a == team_b:
            st.error("Error Arquitectónico: Selecciona equipos distintos para el cruce de datos.")
            return

        with st.spinner("1. Ingestando Advanced Stats (eFG%, TOV%, OREB%)..."):
            # Llama a la función con @st.cache_data para mitigar timeouts de la NBA
            raw_data = cached_get_matchup_stats(data_client, team_a, team_b)
            
            if "error" in raw_data:
                st.error(raw_data["error"])
                return

            # Enriqueciendo el payload JSON con Cuotas Matemáticas y Reporte Cualitativo de Lesiones
            raw_data["betting_market"] = {
                team_a: {"odds": odds_team_a, "implied_probability": round(calculate_implied_probability(odds_team_a), 2)},
                team_b: {"odds": odds_team_b, "implied_probability": round(calculate_implied_probability(odds_team_b), 2)}
            }
            raw_data["injury_report"] = {
                team_a: injuries_a if injuries_a else "Plantilla completa / Sin reportes",
                team_b: injuries_b if injuries_b else "Plantilla completa / Sin reportes"
            }

        # Renderizado Visual Interactivo (Telemetría)
        st.subheader("📈 Telemetría Cuantitativa de Franquicias")
        st.plotly_chart(plot_net_rating_comparison(raw_data["matchup_data"], team_a, team_b), use_container_width=True)

        with st.spinner("2. Procesando Motor de Inferencia (Gemini 2.5 Pro)..."):
            # Envío del payload final estructurado al LLM
            analysis = llm_engine.analyze_matchup(raw_data, market)
            
            st.subheader("🧠 Reporte Analítico y Detección de Valor Esperado (+EV)")
            st.write(analysis)
            
            # Modal de auditoría para verificar la integridad del contrato de datos
            with st.expander("Inspeccionar JSON Data Payload (Auditoría Técnica)"):
                st.json(raw_data)

if __name__ == "__main__":
    main()