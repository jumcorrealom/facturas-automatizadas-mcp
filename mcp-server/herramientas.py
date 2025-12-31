# Archivo: mcp-server/herramientas.py
import os
import json
import requests
from mcp.server.fastmcp import FastMCP
from google.cloud import storage
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Configuración
BUCKET_NAME = 'facturacion-mcp' 
storage_client = storage.Client()
bucket = storage_client.bucket(BUCKET_NAME)
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

mcp = FastMCP("ServidorFacturas")
API_DESTINO = "http://localhost:8000/recepcion-facturas"

@mcp.tool()
def analizar_factura_pdf(nombre_archivo: str) -> str:
    """Descarga un PDF del bucket y extrae datos con Gemini."""
    try:
        blob = bucket.blob(nombre_archivo)
        if not blob.exists(): return "Error: Archivo no encontrado."
        
        pdf_bytes = blob.download_as_bytes()
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        prompt = """Extrae en JSON: proveedor, fecha, numero_factura, total, items. 
        Si no es visible usa null. Respuesta SOLO JSON."""
        
        response = model.generate_content([
            {"mime_type": "application/pdf", "data": pdf_bytes}, prompt
        ])
        return response.text.strip().replace("```json", "").replace("```", "")
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def enviar_datos_api(datos_json: str) -> str:
    """Envía el JSON a la API local."""
    try:
        payload = json.loads(datos_json)
        res = requests.post(API_DESTINO, json=payload)
        return f"Status {res.status_code}: {res.text}"
    except Exception as e:
        return f"Error de envío: {str(e)}"

@mcp.tool()
def listar_facturas_pendientes() -> str:
    """Lista archivos PDF en el bucket."""
    blobs = bucket.list_blobs()
    files = [b.name for b in blobs if b.name.endswith('.pdf')]
    return str(files) if files else "No hay facturas."

if __name__ == "__main__":
    mcp.run()