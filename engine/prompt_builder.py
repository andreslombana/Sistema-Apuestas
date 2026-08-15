# engine/prompt_builder.py
import json

def build_analysis_prompt(matchup_data: dict, market: str) -> str:
    data_str = json.dumps(matchup_data, indent=2)
    
    prompt = f"""
    Eres un Analista Cuantitativo Deportivo Senior (Quant) experto en la NBA.
    
    Data Estructurada (Temporada, L10, Métricas Avanzadas, Cuotas y REPORTE DE LESIONES):
    {data_str}
    
    Instrucciones de Inferencia Crítica:
    1. Revisa el 'injury_report'. Si un equipo tiene bajas de jugadores clave, DEBES aplicar una penalización al 'Net Rating' y 'eFG_pct' de ese equipo antes de hacer cualquier cálculo. Justifica esta penalización cualitativamente.
    2. Analiza el 'Net Rating' (Tendencia Global vs L10).
    3. Ejecuta un análisis de eficiencia basado en: 'eFG_pct', 'tov_pct' y 'oreb_pct'.
    4. Calcula tu probabilidad matemática de victoria ponderada.
    5. Devuelve el cálculo final de EV (Expected Value).
    
    Estructura de Salida: 'Impacto de Lesiones (Ajuste de Ratings)', 'Diagnóstico de los 4 Factores', 'Cálculo de Probabilidad Cuantitativa', 'Arbitraje de Cuotas y Veredicto (EV)'.
    """
    return prompt