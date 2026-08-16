# app.py
import streamlit as st
import plotly.graph_objects as go
from backend.data_client import NBADataClient
from engine.gemini_client import GeminiAnalyzer
from utils.db_manager import init_db, log_prediction, get_history_df
from dotenv import load_dotenv

# ==========================================
# 1. CONFIGURACIÓN E INICIALIZACIÓN
# ==========================================
load_dotenv()
st.set_page_config(page_title="Quant NBA System PRO", layout="wide", page_icon="🏀")

# Inicializar Base de Datos SQLite en el arranque
init_db()

# ==========================================
# 2. FUNCIONES AUXILIARES Y CACHÉ
# ==========================================
@st.cache_data(ttl=3600) # Caché de 1 hora para evitar baneos del WAF de Akamai (NBA API)
def cached_get_matchup_stats(_client, team_a, team_b):
    """Envoltorio asilado para la ingesta de datos cuantitativos."""
    return _client.get_matchup_stats(team_a, team_b)

def calculate_implied_probability(odds: float) -> float:
    """Calcula la probabilidad implícita matemática del mercado."""
    return (1 / odds) * 100 if odds and odds > 1.0 else 0.0

def plot_net_rating_comparison(data, team_a, team_b):
    """Genera telemetría visual interactiva del Momentum de las franquicias."""
    fig = go.Figure()
    teams = [team_a, team_b]
    
    try:
        season_ratings = [data[team_a]['season']['net_rating'], data[team_b]['season']['net_rating']]
        l10_ratings = [data[team_a]['last_10']['net_rating'], data[team_b]['last_10']['net_rating']]

        fig.add_trace(go.Bar(x=teams, y=season_ratings, name='Temporada Completa', marker_color='#1f77b4'))
        fig.add_trace(go.Bar(x=teams, y=l10_ratings, name='Últimos 10 Juegos', marker_color='#ff7f0e'))
        fig.update_layout(title="Momentum Cuantitativo: Net Rating (Season vs L10)", barmode='group', template='plotly_dark')
    except Exception as e:
        fig.update_layout(title=f"Error en visualización: {str(e)}")
        
    return fig

# ==========================================
# 3. NÚCLEO DE LA APLICACIÓN (UI & LÓGICA)
# ==========================================
def main():
    st.title("🏀 Terminal Cuantitativa NBA")
    st.markdown("Plataforma de arbitraje financiero basada en Los 4 Factores, Análisis de Tendencias y Gemini AI.")
    
    # Orquestación de Pestañas (Dashboards)
    tab_analysis, tab_history = st.tabs(["Análisis Quant En Vivo", "Auditoría y Backtesting (ROI)"])
    
    # Instanciación de Clientes
    data_client = NBADataClient()
    llm_engine = GeminiAnalyzer()

    # --- PESTAÑA 1: ANÁLISIS EN VIVO ---
    with tab_analysis:
        with st.spinner("Sincronizando catálogo de franquicias..."):
            all_teams = data_client.get_all_teams()

        # Controles de Selección
        col1, col2, col3 = st.columns(3)
        with col1:
            team_a = st.selectbox("Equipo Local", all_teams, index=all_teams.index("Boston Celtics") if "Boston Celtics" in all_teams else 0)
            injuries_a = st.text_input(f"Lesiones/Bajas {team_a}", placeholder="Ej: Jayson Tatum (Out)")
        with col2:
            team_b = st.selectbox("Equipo Visitante", all_teams, index=all_teams.index("Dallas Mavericks") if "Dallas Mavericks" in all_teams else 1)
            injuries_b = st.text_input(f"Lesiones/Bajas {team_b}", placeholder="Ej: Ninguna")
        with col3:
            market = st.selectbox("Mercado Estratégico", ["Moneyline (Ganador)", "Handicap (Spread)", "Totales (Over/Under)"])
            
            # Mapeo de mercado a la nomenclatura de The-Odds-API
            api_market = "h2h"
            if "Spread" in market: api_market = "spreads"
            if "Over/Under" in market: api_market = "totals"

        st.markdown("---")
        st.subheader("Cuotas y Líneas del Mercado (API Pipeline)")
        
        # Extracción de cuotas en vivo
        live_odds = data_client.get_live_odds(team_a, team_b, market_type=api_market)
        
        # Resolución dinámica de llaves (Over/Under vs Team Names)
        if api_market == "totals":
            key_1, key_2 = "Over", "Under"
        else:
            key_1, key_2 = team_a, team_b
        
        # Fallback de Interfaz (Offseason o Bloqueo)
        if not live_odds or "error" in live_odds:
            st.warning(f"Modo Offline activo (Offseason). Ingresa cuotas y líneas manualmente para: {market}")
            c1, c2 = st.columns(2)
            with c1: 
                price_1 = st.number_input(f"Cuota {key_1}", value=1.90, step=0.05)
                point_1 = st.number_input(f"Línea {key_1} (Opcional)", value=0.0)
            with c2: 
                price_2 = st.number_input(f"Cuota {key_2}", value=1.90, step=0.05)
                point_2 = st.number_input(f"Línea {key_2} (Opcional)", value=0.0)
            
            point_1 = point_1 if point_1 != 0.0 else None
            point_2 = point_2 if point_2 != 0.0 else None
        else:
            st.success("✅ Datos inyectados desde el pool de liquidez (The-Odds-API).")
            
            # Extracción segura garantizando el tipado correcto para Streamlit
            data_1 = live_odds.get(key_1, {"price": 1.90, "point": None})
            data_2 = live_odds.get(key_2, {"price": 1.90, "point": None})
            
            price_1 = float(data_1.get("price", 1.90))
            point_1 = data_1.get("point")
            price_2 = float(data_2.get("price", 1.90))
            point_2 = data_2.get("point")
            
            # Renderizado Dinámico
            label_1 = f"{key_1} (Línea: {point_1})" if point_1 else f"{key_1}"
            label_2 = f"{key_2} (Línea: {point_2})" if point_2 else f"{key_2}"
            
            c1, c2 = st.columns(2)
            c1.metric(label=label_1, value=price_1)
            c2.metric(label=label_2, value=price_2)

        # ==========================================
        # EJECUCIÓN DEL ALGORITMO CUANTITATIVO
        # ==========================================
        if st.button("Ejecutar Motor de Inferencia", type="primary"):
            if team_a == team_b:
                st.error("Error de lógica: Selecciona equipos distintos.")
                return

            with st.spinner("1. Ingestando Telemetría Avanzada (NBA API)..."):
                raw_data = cached_get_matchup_stats(data_client, team_a, team_b)
                if "error" in raw_data:
                    st.error(raw_data["error"])
                    return

                # Empaquetado estricto del contrato de datos para el LLM
                raw_data["betting_market"] = {
                    key_1: {"odds": price_1, "point": point_1, "implied_probability": round(calculate_implied_probability(price_1), 2)},
                    key_2: {"odds": price_2, "point": point_2, "implied_probability": round(calculate_implied_probability(price_2), 2)}
                }
                raw_data["injury_report"] = {team_a: injuries_a, team_b: injuries_b}
                raw_data["market_analyzed"] = market

            # Gráfica de Momentum
            st.subheader("📈 Telemetría de Eficiencia (Los 4 Factores)")
            st.plotly_chart(plot_net_rating_comparison(raw_data["matchup_data"], team_a, team_b), use_container_width=True)

            with st.spinner("2. LLM procesando Valor Esperado (+EV)..."):
                analysis = llm_engine.analyze_matchup(raw_data, market)
                st.write(analysis)
                
            # Auditoría y Logging Estructurado
            with st.expander("🔍 Inspeccionar Data Payload (JSON)"):
                st.json(raw_data)
                
            with st.expander("💾 Registrar Operación en Base de Datos (Backtesting)"):
                st.markdown("Almacena esta proyección para auditar la rentabilidad del modelo.")
                pick_name = st.text_input("Selección (Ej. Boston -5.5 / Over 225)", value=key_1)
                ev_val = st.number_input("Valor EV Calculado (%)", value=0.0)
                odds_val = st.number_input("Cuota Tomada", value=float(price_1))
                if st.button("Guardar Pick en Historial"):
                    log_prediction(team_a, team_b, market, pick_name, ev_val, odds_val)
                    st.success("✅ Registro encriptado y almacenado en SQLite.")

    # --- PESTAÑA 2: AUDITORÍA Y BACKTESTING ---
    with tab_history:
        st.subheader("Historial de Operaciones y Auditoría Financiera")
        st.markdown("Visualiza el histórico de decisiones de la IA para calcular el ROI real.")
        df_history = get_history_df()
        
        if not df_history.empty:
            st.dataframe(df_history, use_container_width=True)
        else:
            st.info("La base de datos local está vacía. Ejecuta una inferencia y guarda el registro para comenzar.")

if __name__ == "__main__":
    main()