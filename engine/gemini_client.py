# engine/gemini_client.py
import os
import requests
import json
from .prompt_builder import build_analysis_prompt

class GeminiAnalyzer:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("Error Arquitectónico: GOOGLE_API_KEY no encontrada.")
        
        # Utilizamos el modelo confirmado por la prueba unitaria
        self.model_name = "gemini-2.5-pro"
        self.endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"

    def analyze_matchup(self, matchup_data: dict, market: str) -> str:
        prompt = build_analysis_prompt(matchup_data, market)
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2, # Determinismo cuantitativo
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
                return f"Error HTTP {response.status_code}: {response.text}"
                
        except Exception as e:
            return f"Error en la red REST: {str(e)}"