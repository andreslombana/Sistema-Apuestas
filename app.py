# app.py
import streamlit as st
import plotly.graph_objects as go
from backend.nba_client import NBADataClient          # <--- CORREGIDO
from backend.football_client import FootballDataClient 
from engine.gemini_client import GeminiAnalyzer
from utils.db_manager import init_db, log_prediction, get_history_df
from dotenv import load_dotenv

# ==========================================
# 1. CONFIGURACIÓN E INICIALIZACIÓN
# ==========================================
load_dotenv()
st.set_page_config(page_title="Quant Sports System PRO", layout="wide", page_icon="🏟️")

# Inicializar Base de Datos SQLite en el arranque
init_db()

# ==========================================
# 2. FUNCIONES AUXILIARES Y CACHÉ
# ==========================================
@st.cache_data(ttl=3600)
def cached_get_matchup_stats(_client, team_a, team_b):
    """Envoltorio asilado para la ingesta de datos cuantitativos (Multi-Deporte)."""
    return _client.get_matchup_stats(team_a, team_b)

def calculate_implied_probability(odds: float) -> float:
    """Calcula la probabilidad implícita matemática del mercado."""
    return (1 / odds) * 100 if odds and odds > 1.0 else 0.0

# --- Gráficos Específicos por Deporte ---
def plot_nba_comparison(data, team_a, team_b):
    fig = go.Figure()
    try:
        season_ratings = [data[team_a]['season']['net_rating'], data[team_b]['season']['net_rating']]
        l10_ratings = [data[team_a]['last_10']['net_rating'], data[team_b]['last_10']['net_rating']]
        fig.add_trace(go.Bar(x=[team_a, team_b], y=season_ratings, name='Temporada', marker_color='#1f77b4'))
        fig.add_trace(go.Bar(x=[team_a, team_b], y=l10_ratings, name='L10', marker_color='#ff7f0e'))
        fig.update_layout(title="NBA: Net Rating (Season vs L10)", barmode='group', template='plotly_dark')
    except Exception as e:
        fig.update_layout(title=f"Error Visual NBA: {str(e)}")
    return fig

def plot_football_comparison(data, team_a, team_b):
    fig = go.Figure()
    try:
        gf = [data[team_a]['goals_for_avg'], data[team_b]['goals_for_avg']]
        ga = [data[team_a]['goals_against_avg'], data[team_b]['goals_against_avg']]
        fig.add_trace(go.Bar(x=[team_a, team_b], y=gf, name='Goles a Favor (GF)', marker_color='#2ca02c'))
        fig.add_trace(go.Bar(x=[team_a, team_b], y=ga, name='Goles en Contra (GA)', marker_color='#d62728'))
        fig.update_layout(title="Fútbol: Eficiencia Goleadora (GF vs GA)", barmode='group', template='plotly_dark')
    except Exception as e:
        fig.update_layout(title=f"Error Visual Fútbol: {str(e)}")
    return fig

# ==========================================
# 3. NÚCLEO DE LA APLICACIÓN (UI & LÓGICA)
# ==========================================
def main():
    # --- BARRA LATERAL: ORQUESTADOR DE DEPORTE (STRATEGY PATTERN) ---
    st.sidebar.title("⚙️ Configuración Quant")
    deporte_seleccionado = st.sidebar.radio("Seleccione Deporte / Liga", ["NBA (Baloncesto)", "Liga BetPlay (Fútbol)"])
    
    st.title(f"Terminal Cuantitativa: {deporte_seleccionado}")
    st.markdown("Plataforma de arbitraje financiero basada en datos en tiempo real y Gemini AI.")
    
    tab_analysis, tab_history = st.tabs(["Análisis Quant En Vivo", "Auditoría y Backtesting (ROI)"])
    llm_engine = GeminiAnalyzer()

    # --- INICIALIZACIÓN DINÁMICA DE CLIENTES ---
    if deporte_seleccionado == "NBA (Baloncesto)":
        data_client = NBADataClient()
        mercados_disponibles = ["Moneyline (Ganador)", "Handicap (Spread)", "Totales (Over/Under)"]
        plot_function = plot_nba_comparison
        contexto_label = "Lesiones / Bajas"
    else:
        data_client = FootballDataClient()
        mercados_disponibles = ["1X2 (Local/Empate/Visita)", "Over/Under 2.5", "Ambos Marcan (BTTS)"]
        plot_function = plot_football_comparison
        contexto_label = "Contexto (Ej. Altura Bogotá, Lluvia, Bajas)"

    # --- PESTAÑA 1: ANÁLISIS EN VIVO ---
    with tab_analysis:
        with st.spinner("Sincronizando catálogo de franquicias/clubes..."):
            all_teams = data_client.get_all_teams() if hasattr(data_client, 'get_all_teams') else data_client.get_teams()

        # Controles de Selección
        col1, col2, col3 = st.columns(3)
        with col1:
            team_a = st.selectbox("Equipo Local", all_teams, index=0)
            contexto_a = st.text_input(f"{contexto_label} {team_a}")
        with col2:
            team_b = st.selectbox("Equipo Visitante", all_teams, index=1 if len(all_teams)>1 else 0)
            contexto_b = st.text_input(f"{contexto_label} {team_b}")
        with col3:
            market = st.selectbox("Mercado Estratégico", mercados_disponibles)
            
            # Mapeo de mercado a la API
            api_market = "h2h" # Default
            if "Spread" in market: api_market = "spreads"
            if "Over/Under" in market: api_market = "totals"
            if "1X2" in market: api_market = "1X2"

        st.markdown("---")
        st.subheader("Cuotas y Líneas del Mercado")
        
        # Extracción de cuotas
        live_odds = data_client.get_live_odds(team_a, team_b, market_type=api_market)
        
        # Resolución dinámica de llaves
        if "Over" in api_market or "totals" in api_market:
            key_1, key_2 = "Over", "Under"
            if deporte_seleccionado != "NBA (Baloncesto)":
                key_1, key_2 = "Over 2.5", "Under 2.5"
        else:
            key_1, key_2 = team_a, team_b
        
        # Fallback de Interfaz
        if not live_odds or "error" in live_odds:
            st.warning(f"Modo Offline activo. Ingresa cuotas manualmente para: {market}")
            c1, c2 = st.columns(2)
            with c1: 
                price_1 = st.number_input(f"Cuota {key_1}", value=1.90, step=0.05)
                point_1 = st.number_input(f"Línea {key_1} (Opcional)", value=0.0)
            with c2: 
                price_2 = st.number_input(f"Cuota {key_2}", value=1.90, step=0.05)
                point_2 = st.number_input(f"Línea {key_2} (Opcional)", value=0.0)
            
            point_1 = point_1 if point_1 != 0.0 else None
            point_2 = point_2 if point_2 != 0.0 else None
            
            # Soporte especial para el Empate (Fútbol)
            if "1X2" in market:
                price_x = st.number_input("Cuota Empate (X)", value=3.00, step=0.05)
        else:
            st.success("✅ Datos inyectados desde el pool de liquidez.")
            
            data_1 = live_odds.get(key_1, {"price": 1.90, "point": None})
            data_2 = live_odds.get(key_2, {"price": 1.90, "point": None})
            
            price_1 = float(data_1.get("price", 1.90) if isinstance(data_1, dict) else data_1)
            point_1 = data_1.get("point") if isinstance(data_1, dict) else None
            price_2 = float(data_2.get("price", 1.90) if isinstance(data_2, dict) else data_2)
            point_2 = data_2.get("point") if isinstance(data_2, dict) else None

            label_1 = f"{key_1} (Línea: {point_1})" if point_1 else f"{key_1}"
            label_2 = f"{key_2} (Línea: {point_2})" if point_2 else f"{key_2}"
            
            cols = st.columns(3 if "1X2" in market else 2)
            cols[0].metric(label=label_1, value=price_1)
            if "1X2" in market:
                price_x = float(live_odds.get("Empate (X)", {"price": 3.00}).get("price", 3.00) if isinstance(live_odds.get("Empate (X)"), dict) else live_odds.get("Empate (X)", 3.00))
                cols[1].metric(label="Empate (X)", value=price_x)
                cols[2].metric(label=label_2, value=price_2)
            else:
                cols[1].metric(label=label_2, value=price_2)

        # ==========================================
        # EJECUCIÓN DEL ALGORITMO CUANTITATIVO
        # ==========================================
        if st.button("Ejecutar Motor de Inferencia", type="primary"):
            if team_a == team_b:
                st.error("Error de lógica: Selecciona equipos distintos.")
                return

            with st.spinner("1. Ingestando Telemetría Avanzada..."):
                raw_data = cached_get_matchup_stats(data_client, team_a, team_b)
                if "error" in raw_data:
                    st.error(raw_data["error"])
                    return

                # Empaquetado estricto
                raw_data["betting_market"] = {
                    key_1: {"odds": price_1, "implied_probability": round(calculate_implied_probability(price_1), 2)},
                    key_2: {"odds": price_2, "implied_probability": round(calculate_implied_probability(price_2), 2)}
                }
                if "1X2" in market:
                    raw_data["betting_market"]["Empate (X)"] = {"odds": price_x, "implied_probability": round(calculate_implied_probability(price_x), 2)}
                
                raw_data["context_report"] = {team_a: contexto_a, team_b: contexto_b}
                raw_data["sport"] = deporte_seleccionado
                raw_data["market_analyzed"] = market

            st.subheader("📈 Telemetría de Eficiencia")
            st.plotly_chart(plot_function(raw_data.get("matchup_data", {}), team_a, team_b), use_container_width=True)

            with st.spinner("2. LLM procesando Valor Esperado (+EV)..."):
                # Se pasa el parámetro sport para que GeminiAnalyzer decida qué prompt usar
                analysis = llm_engine.analyze_matchup(raw_data, market, sport=deporte_seleccionado)
                st.write(analysis)
                
            with st.expander("🔍 Inspeccionar Data Payload (JSON)"):
                st.json(raw_data)
                
            with st.expander("💾 Registrar Operación en Base de Datos (Backtesting)"):
                st.markdown("Almacena esta proyección para auditar la rentabilidad del modelo.")
                pick_name = st.text_input("Selección (Ej. Millonarios / Over 2.5)", value=key_1)
                ev_val = st.number_input("Valor EV Calculado (%)", value=0.0)
                odds_val = st.number_input("Cuota Tomada", value=float(price_1))
                if st.button("Guardar Pick en Historial"):
                    log_prediction(team_a, team_b, f"{deporte_seleccionado} - {market}", pick_name, ev_val, odds_val)
                    st.success("✅ Registro encriptado y almacenado en SQLite.")

    # --- PESTAÑA 2: AUDITORÍA Y BACKTESTING ---
    with tab_history:
        st.subheader("Historial de Operaciones y Auditoría Financiera")
        df_history = get_history_df()
        
        if not df_history.empty:
            st.dataframe(df_history, use_container_width=True)
        else:
            st.info("La base de datos local está vacía. Ejecuta una inferencia y guarda el registro para comenzar.")

if __name__ == "__main__":
    main()