from google import genai
from dotenv import load_dotenv
import os

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

print("🔍 Buscando modelos disponibles para tu API Key...")
try:
    # Listamos modelos que soporten generación de contenido
    for m in client.models.list():
        if "generateContent" in m.supported_actions:
            name = m.name.replace("models/", "")
            print(f" - {name}")
except Exception as e:
    print(f"❌ Error al listar: {e}")