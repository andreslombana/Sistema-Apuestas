# engine/prompt_builder.py
import json

def build_analysis_prompt(matchup_data: dict, market: str) -> str:
    data_str = json.dumps(matchup_data, indent=2)
    
    prompt = f"""
    Eres un Analista Cuantitativo Deportivo Senior (Quant) experto en la NBA.
    
    Data Estructurada (Temporada, L10, Métricas Avanzadas, REPORTE DE LESIONES y Mercado de Cuotas):
    {data_str}
    
    Mercado a analizar: {market}
    
    Instrucciones de Inferencia Crítica:
    1. Si hay lesiones, ajusta el 'Net Rating' y 'eFG_pct' cualitativamente.
    2. Si el mercado es 'Moneyline (Ganador)': Centra el análisis en Net Rating y Cuatro Factores para predecir el ganador directo.
    3. Si el mercado es 'Handicap (Spread)': Evalúa si la diferencia de puntos implícita en el Net Rating ponderado es suficiente para cubrir la línea (Point) de la casa de apuestas.
    4. Si el mercado es 'Totales (Over/Under)': Analiza el Pace (Ritmo) y el poder ofensivo (PPG / eFG%) combinado de ambos equipos frente a sus defensas para proyectar un puntaje total, y compáralo con la línea del mercado.
    5. Calcula el EV (Expected Value) final.
    
    Estructura de Salida: 'Diagnóstico Táctico y Lesiones', 'Proyección Matemática (Adaptada al Mercado)', 'Arbitraje de Cuotas y Veredicto (+EV)'.
    """
    return prompt