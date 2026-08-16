# engine/gemini_client.py
import os
import requests
import json
import logging
from engine.prompt_builder import build_nba_analysis_prompt, build_football_analysis_prompt

class GeminiAnalyzer:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("Error Arquitectónico: GOOGLE_API_KEY no encontrada en el entorno.")
        
        # Mantenemos el modelo 2.5 Pro que demostró máxima eficacia matemática
        self.model_name = "gemini-2.5-pro"
        self.endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"

    def analyze_matchup(self, raw_data: dict, market: str, sport: str = "NBA (Baloncesto)") -> str:
        """
        Enruta los datos crudos hacia el constructor de prompts adecuado según el deporte.
        """
        # Patrón Estrategia de Enrutamiento de Prompts
        if "Fútbol" in sport:
            prompt = build_football_analysis_prompt(raw_data, market)
        else:
            prompt = build_nba_analysis_prompt(raw_data, market)
            
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2, # Mantenemos baja temperatura para determinismo matemático
                "topP": 0.8
            }
        }
        
        headers = {"Content-Type": "application/json"}
        
        try:
            response = requests.post(
                f"{self.endpoint}?key={self.api_key}",
                headers=headers,
                data=json.dumps(payload)
            )
            
            if response.status_code == 200:
                data = response.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            else:
                logging.error(f"Error Gemini HTTP {response.status_code}: {response.text}")
                return f"Error HTTP {response.status_code} al conectar con Gemini."
                
        except Exception as e:
            return f"Excepción Crítica en la red REST: {str(e)}"