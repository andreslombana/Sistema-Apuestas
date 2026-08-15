# backend/data_client.py
import os
import requests
import logging
import pandas as pd
from nba_api.stats.endpoints import leaguedashteamstats
from nba_api.stats.static import teams

class NBADataClient:
    def __init__(self):
        logging.info("Inicializando Cliente de Datos Cuantitativos NBA...")
        self.odds_api_key = os.getenv("ODDS_API_KEY")

    def get_all_teams(self) -> list:
        nba_teams = teams.get_teams()
        return sorted([team['full_name'] for team in nba_teams])

    def get_matchup_stats(self, team_a: str, team_b: str) -> dict:
        try:
            # Extracción de Estadísticas Base (Net Rating, W-L)
            base_season = leaguedashteamstats.LeagueDashTeamStats(per_mode_detailed='PerGame').get_data_frames()[0]
            base_l10 = leaguedashteamstats.LeagueDashTeamStats(per_mode_detailed='PerGame', last_n_games='10').get_data_frames()[0]
            
            # Extracción de Estadísticas Avanzadas (Los 4 Factores)
            adv_season = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense='Advanced', per_mode_detailed='PerGame').get_data_frames()[0]
            adv_l10 = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense='Advanced', per_mode_detailed='PerGame', last_n_games='10').get_data_frames()[0]

            def extract_quant_data(df_base, df_adv, team_name):
                base = df_base[df_base['TEAM_NAME'].str.contains(team_name, case=False, na=False)]
                adv = df_adv[df_adv['TEAM_NAME'].str.contains(team_name, case=False, na=False)]
                if base.empty or adv.empty: return None
                
                return {
                    "win_loss": f"{base.iloc[0]['W']}-{base.iloc[0]['L']}",
                    "net_rating": round(base.iloc[0]['PLUS_MINUS'], 1),
                    "advanced_metrics": {
                        "eFG_pct": round(adv.iloc[0]['EFG_PCT'] * 100, 1), # Effective Field Goal %
                        "tov_pct": round(adv.iloc[0]['TM_TOV_PCT'] * 100, 1), # Turnover %
                        "oreb_pct": round(adv.iloc[0]['OREB_PCT'] * 100, 1) # Offensive Rebound %
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
        # (Mantén la función de The-Odds-API exactamente igual a la versión anterior)
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