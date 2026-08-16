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
        logging.info("Inicializando Cliente de Datos Cuantitativos (Resilient Mode)...")
        self.odds_api_key = os.getenv("ODDS_API_KEY")
        
        # Cabeceras para evadir el WAF de stats.nba.com
        self.custom_headers = {
            'Host': 'stats.nba.com',
            'Connection': 'keep-alive',
            'Cache-Control': 'max-age=0',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.nba.com/',
        }

    def get_all_teams(self) -> list:
        nba_teams = teams.get_teams()
        return sorted([team['full_name'] for team in nba_teams])

    def _fetch_with_backoff(self, measure_type='Base', last_n='0', max_retries=3):
        """
        Ejecuta la llamada a la API de la NBA con reintentos exponenciales y cabeceras personalizadas.
        """
        for attempt in range(max_retries):
            try:
                stats = leaguedashteamstats.LeagueDashTeamStats(
                    measure_type_detailed_defense=measure_type,
                    per_mode_detailed='PerGame',
                    last_n_games=last_n,
                    headers=self.custom_headers,
                    timeout=60 # Ampliamos de 30 a 60 segundos
                )
                return stats.get_data_frames()[0]
            except Exception as e:
                if attempt == max_retries - 1:
                    raise Exception(f"Timeout definitivo tras {max_retries} intentos: {str(e)}")
                # Exponential backoff: espera 1s, luego 2s...
                sleep_time = 2 ** attempt
                logging.warning(f"Timeout detectado. Reintentando en {sleep_time} segundos...")
                time.sleep(sleep_time)

    def get_matchup_stats(self, team_a: str, team_b: str) -> dict:
        try:
            # Uso del nuevo método resiliente
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
                return {"error": "Fallo en la resolución de entidades (Equipos no encontrados)."}

            return {
                "matchup_data": {
                    team_a: {"season": team_a_season, "last_10": team_a_l10},
                    team_b: {"season": team_b_season, "last_10": team_b_l10}
                },
                "source": "stats.nba.com (Base + Advanced Endpoint)"
            }
        except Exception as e:
            return {"error": f"Fallo Crítico de Ingesta: {str(e)}"}

    def get_live_odds(self, team_a: str, team_b: str) -> dict:
        # (El código de The-Odds-API se mantiene intacto)
        if not self.odds_api_key:
            return {"error": "ODDS_API_KEY no configurada"}
            
        url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/odds/?apiKey={self.odds_api_key}&regions=us&markets=h2h&oddsFormat=decimal"
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
                        for outcome in outcomes:
                            if team_a in outcome['name']: odds_data[team_a] = outcome['price']
                            if team_b in outcome['name']: odds_data[team_b] = outcome['price']
                        return odds_data
                return {}
            return {"error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}