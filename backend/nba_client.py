# backend/data_client.py
import os
import time
import requests
import logging
import pandas as pd
from nba_api.stats.endpoints import leaguedashteamstats
from nba_api.stats.static import teams

class NBADataClient:
    def __init__(self):
        logging.info("Inicializando Cliente de Datos NBA (Cloud Resilient Mode)...")
        self.odds_api_key = os.getenv("ODDS_API_KEY")
        
        # Cabeceras de evasión nivel 2 (Simulación estricta de Chrome moderno)
        self.custom_headers = {
            'Host': 'stats.nba.com',
            'Connection': 'keep-alive',
            'Accept': 'application/json, text/plain, */*',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Referer': 'https://www.nba.com/',
            'Origin': 'https://www.nba.com',
            'Accept-Language': 'en-US,en;q=0.9',
            'Sec-Ch-Ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
        }

    def get_all_teams(self) -> list:
        nba_teams = teams.get_teams()
        return sorted([team['full_name'] for team in nba_teams])

    def _fetch_with_backoff(self, measure_type='Base', last_n='0', max_retries=3):
        """
        Ejecuta la llamada a la API con reintentos. 
        Si el WAF de Akamai bloquea la IP (Cloud Deployment), lanza una excepción para activar el Fallback.
        """
        for attempt in range(max_retries):
            try:
                stats = leaguedashteamstats.LeagueDashTeamStats(
                    measure_type_detailed_defense=measure_type,
                    per_mode_detailed='PerGame',
                    last_n_games=last_n,
                    headers=self.custom_headers,
                    timeout=15 # Reducimos el timeout a 15s. Si Akamai nos bloquea, no vale la pena esperar 60s.
                )
                return stats.get_data_frames()[0]
            except Exception as e:
                if attempt == max_retries - 1:
                    logging.error(f"Bloqueo WAF detectado (Timeout). Activando Circuit Breaker.")
                    raise Exception("WAF_BLOCK")
                
                sleep_time = 2 ** attempt
                logging.warning(f"Intento {attempt + 1} fallido. Reintentando en {sleep_time}s...")
                time.sleep(sleep_time)

    def _get_fallback_snapshot(self, team_a: str, team_b: str) -> dict:
        """
        Patrón Fallback: Snapshot estático de la liga para garantizar la continuidad
        operativa del dashboard cuando la IP de la nube está baneada.
        """
        logging.warning("Inyectando Snapshot de Contingencia (Temporada 25-26).")
        # Snapshot genérico con métricas élite vs promedio para probar el LLM
        return {
            "matchup_data": {
                team_a: {
                    "season": {"win_loss": "55-27", "net_rating": 6.5, "advanced_metrics": {"eFG_pct": 56.2, "tov_pct": 13.1, "oreb_pct": 32.5}},
                    "last_10": {"win_loss": "7-3", "net_rating": 8.1, "advanced_metrics": {"eFG_pct": 58.0, "tov_pct": 12.8, "oreb_pct": 33.1}}
                },
                team_b: {
                    "season": {"win_loss": "42-40", "net_rating": 1.2, "advanced_metrics": {"eFG_pct": 54.1, "tov_pct": 14.5, "oreb_pct": 30.2}},
                    "last_10": {"win_loss": "4-6", "net_rating": -2.1, "advanced_metrics": {"eFG_pct": 52.5, "tov_pct": 15.6, "oreb_pct": 29.8}}
                }
            },
            "source": "Fallback Snapshot (WAF Block Mitigation)"
        }

    def get_matchup_stats(self, team_a: str, team_b: str) -> dict:
        try:
            # Intentamos la ingesta en vivo
            base_season = self._fetch_with_backoff(measure_type='Base', last_n='0')
            base_l10 = self._fetch_with_backoff(measure_type='Base', last_n='10')
            adv_season = self._fetch_with_backoff(measure_type='Advanced', last_n='0')
            adv_l10 = self._fetch_with_backoff(measure_type='Advanced', last_n='10')

            def extract_quant_data(df_base, df_adv, team_name):
                base = df_base[df_base['TEAM_NAME'].str.contains(team_name, case=False, na=False)]
                adv = df_adv[df_adv['TEAM_NAME'].str.contains(team_name, case=False, na=False)]
                if base.empty or adv.empty: return None
                
                return {
                    "win_loss": f"{base.iloc[0]['W']}-{base.iloc[0]['L']}",
                    "net_rating": round(base.iloc[0]['PLUS_MINUS'], 1),
                    "advanced_metrics": {
                        "eFG_pct": round(adv.iloc[0]['EFG_PCT'] * 100, 1),
                        "tov_pct": round(adv.iloc[0]['TM_TOV_PCT'] * 100, 1),
                        "oreb_pct": round(adv.iloc[0]['OREB_PCT'] * 100, 1)
                    }
                }

            team_a_season = extract_quant_data(base_season, adv_season, team_a)
            team_b_season = extract_quant_data(base_season, adv_season, team_b)
            team_a_l10 = extract_quant_data(base_l10, adv_l10, team_a)
            team_b_l10 = extract_quant_data(base_l10, adv_l10, team_b)

            if not team_a_season or not team_b_season:
                return {"error": "Equipos no encontrados en la extracción."}

            return {
                "matchup_data": {
                    team_a: {"season": team_a_season, "last_10": team_a_l10},
                    team_b: {"season": team_b_season, "last_10": team_b_l10}
                },
                "source": "stats.nba.com (Live)"
            }

        except Exception as e:
            if "WAF_BLOCK" in str(e):
                # Si estamos en la nube y Akamai nos bloquea, inyectamos el Fallback estático
                return self._get_fallback_snapshot(team_a, team_b)
            return {"error": f"Fallo Crítico de Ingesta: {str(e)}"}

    def get_live_odds(self, team_a: str, team_b: str, market_type: str = "h2h") -> dict:
        """
        Extrae cuotas dinámicas basándose en el mercado seleccionado.
        market_type: 'h2h' (Moneyline), 'spreads' (Handicap), 'totals' (Over/Under)
        """
        if not self.odds_api_key:
            return {"error": "ODDS_API_KEY no configurada"}
            
        # Modificamos la URL para aceptar el mercado dinámico
        url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/odds/?apiKey={self.odds_api_key}&regions=us&markets={market_type}&oddsFormat=decimal"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                games = response.json()
                for game in games:
                    if (team_a in game['home_team'] or team_a in game['away_team']) and \
                       (team_b in game['home_team'] or team_b in game['away_team']):
                        bookmaker = game['bookmakers'][0] 
                        outcomes = bookmaker['markets'][0]['outcomes']
                        odds_data = {}
                        
                        # Parseo dinámico según el mercado
                        for outcome in outcomes:
                            # Para Moneyline y Spreads
                            if team_a in outcome.get('name', ''): 
                                odds_data[team_a] = {"price": outcome['price'], "point": outcome.get('point', None)}
                            if team_b in outcome.get('name', ''): 
                                odds_data[team_b] = {"price": outcome['price'], "point": outcome.get('point', None)}
                            # Para Totales (Over/Under)
                            if outcome.get('name') == 'Over':
                                odds_data['Over'] = {"price": outcome['price'], "point": outcome['point']}
                            if outcome.get('name') == 'Under':
                                odds_data['Under'] = {"price": outcome['price'], "point": outcome['point']}
                        return odds_data
                return {}
            return {"error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}