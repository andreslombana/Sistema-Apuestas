# backend/football_client.py
import os
import time
import requests
import logging

class FootballDataClient:
    def __init__(self):
        logging.info("Inicializando Cliente de Fútbol (API-Football - Resilient Mode)...")
        self.api_key = os.getenv("FOOTBALL_API_KEY")
        self.headers = {
            "x-rapidapi-host": "api-football-v1.p.rapidapi.com",
            "x-rapidapi-key": self.api_key if self.api_key else ""
        }
        self.base_url = "https://api-football-v1.p.rapidapi.com/v3"
        self.league_id = 239  # ID de la Primera A Colombia
        self.season = 2026

    def get_teams(self) -> list:
        """
        Retorna el catálogo de equipos de la Liga Colombiana.
        Implementa un caché estático como Fallback primario para ahorrar llamadas a la API
        y garantizar que los 20 equipos estén siempre disponibles para backtesting.
        """
        catalogo_fpc = sorted([
            "Millonarios", "Atlético Nacional", "América de Cali", "Independiente Santa Fe",
            "Junior", "Deportes Tolima", "Independiente Medellín", "Once Caldas",
            "Deportivo Cali", "Atlético Bucaramanga", "Deportivo Pereira", "La Equidad",
            "Águilas Doradas", "Envigado FC", "Boyacá Chicó", "Patriotas",
            "Alianza FC", "Fortaleza CEIF", "Deportivo Pasto", "Jaguares de Córdoba"
        ])
        
        # Si no hay llave, retornamos el catálogo estático inmediatamente
        if not self.api_key:
            logging.warning("FOOTBALL_API_KEY no detectada. Usando catálogo estático del FPC.")
            return catalogo_fpc
            
        try:
            url = f"{self.base_url}/teams?league={self.league_id}&season={self.season}"
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('results', 0) > 0:
                    return sorted([team['team']['name'] for team in data.get('response', [])])
            
            # Si la API responde un 200 pero vacío (ej. cambio de temporada), usa el estático
            return catalogo_fpc
        except Exception as e:
            logging.error(f"Fallo de red en API-Football: {e}. Activando Fallback Estático.")
            return catalogo_fpc

    def _get_fallback_snapshot(self, team_a, team_b):
        """Snapshot estático (Circuit Breaker) para la Liga Colombiana."""
        logging.warning("Inyectando Snapshot de Contingencia (Liga BetPlay).")
        return {
            "matchup_data": {
                team_a: {
                    "form_last_5": "WDLWW",
                    "goals_for_avg": 1.4,
                    "goals_against_avg": 0.8,
                    "clean_sheets_pct": 45.0,
                    "home_advantage_metric": "Alto (Altitud/Clima extremo)"
                },
                team_b: {
                    "form_last_5": "LLDWD",
                    "goals_for_avg": 0.9,
                    "goals_against_avg": 1.2,
                    "clean_sheets_pct": 20.0,
                    "home_advantage_metric": "N/A (Visitante)"
                }
            },
            "tactical_context": "Liga de baja anotación. Fuerte peso de la localía por geografía.",
            "source": "Fallback Snapshot (API-Football Block Mitigation)"
        }

    def get_matchup_stats(self, team_a: str, team_b: str) -> dict:
        """
        En producción, mapea el ID de los equipos y consulta los endpoints /teams/statistics.
        Por seguridad del MVP, si no hay conexión, ruteamos al fallback.
        """
        if not self.api_key:
             return self._get_fallback_snapshot(team_a, team_b)
             
        try:
            # Aquí iría la lógica requests.get() a los endpoints reales de H2H
            # Simulamos el retorno exitoso para mantener la estructura
            return self._get_fallback_snapshot(team_a, team_b)
        except Exception as e:
            return {"error": f"Fallo Crítico de Ingesta FPC: {str(e)}"}

    def get_live_odds(self, team_a: str, team_b: str, market_type: str = "1X2") -> dict:
        """
        Genera una estructura de cuotas simuladas coherentes para probar el LLM
        antes de conectar un feed de pago de cuotas en vivo.
        """
        if "1X2" in market_type:
            return {
                team_a: {"price": 2.10, "point": None},
                "Empate (X)": {"price": 3.10, "point": None},
                team_b: {"price": 3.80, "point": None}
            }
        elif "Over/Under" in market_type:
            return {
                "Over 2.5": {"price": 2.35, "point": 2.5},
                "Under 2.5": {"price": 1.55, "point": 2.5}
            }
        elif "Ambos Marcan" in market_type:
             return {
                "Sí (BTTS)": {"price": 1.95, "point": None},
                "No (BTTS)": {"price": 1.80, "point": None}
            }
        return {}