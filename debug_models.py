# debug_models.py
import os
import google.generativeai as genai
from dotenv import load_dotenv

def audit_api_key():
    print("Iniciando auditoría de modelos disponibles para tu API Key...\n")
    load_dotenv()
    
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: GOOGLE_API_KEY no encontrada en el archivo .env")
        return

    genai.configure(api_key=api_key)
    
    try:
        models = genai.list_models()
        print("Modelos habilitados que soportan generación de texto:")
        print("-" * 50)
        found = False
        for m in models:
            if 'generateContent' in m.supported_generation_methods:
                print(f"- {m.name}")
                found = True
        
        if not found:
            print("Tu API Key no tiene permisos para generar texto.")
    except Exception as e:
        print(f"Error al conectar con la API de Google: {e}")

if __name__ == "__main__":
    audit_api_key()