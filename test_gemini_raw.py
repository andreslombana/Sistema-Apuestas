import os
import requests
from dotenv import load_dotenv

def test_api_connection():
    # 1. Cargar el entorno
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    
    if not api_key or api_key == "tu_clave_aqui":
        print("❌ ERROR: La variable GOOGLE_API_KEY está vacía o es la de por defecto.")
        return

    print(f"✅ Clave detectada (inicia con): {api_key[:10]}...")

    # 2. Hacer un GET crudo para listar modelos permitidos para esta clave
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    
    print("Conectando con Google AI Studio...")
    response = requests.get(url)
    
    print(f"Código HTTP de respuesta: {response.status_code}")
    
    if response.status_code == 200:
        print("✅ CONEXIÓN EXITOSA. La API Key funciona.")
        data = response.json()
        models = [m['name'] for m in data.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
        print(f"Modelos de texto disponibles para tu cuenta: {models[:3]} (mostrando primeros 3)")
    else:
        print("❌ ERROR DE INFRAESTRUCTURA:")
        print(response.json())

if __name__ == "__main__":
    test_api_connection()