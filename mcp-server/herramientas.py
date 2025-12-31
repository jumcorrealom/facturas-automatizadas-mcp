import os
import json
import time
import requests
from mcp.server.fastmcp import FastMCP
from google.cloud import storage
from google import genai
from google.genai import types
from google.genai.errors import ClientError
from dotenv import load_dotenv

load_dotenv()

# Configuración
BUCKET_NAME = 'facturacion-mcp' 
storage_client = storage.Client()
bucket = storage_client.bucket(BUCKET_NAME)

# Usamos el alias genérico
MODELO_ID = "gemini-flash-latest" 
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

mcp = FastMCP("ServidorFacturas")
API_DESTINO = "http://localhost:8000/recepcion-facturas"

def generar_con_reintento(model, contents):
    """Reintenta si hay error de cuota."""
    intentos = 0
    max_intentos = 3
    while intentos < max_intentos:
        try:
            return client.models.generate_content(model=model, contents=contents)
        except ClientError as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                # EMOJI ELIMINADO AQUÍ
                print(f"[ALERTA] Cuota llena en servidor. Reintentando en 10s... ({intentos+1})")
                time.sleep(10)
                intentos += 1
            else:
                raise e
    raise Exception("Servidor saturado: No se pudo procesar tras varios reintentos.")

@mcp.tool()
def analizar_factura_pdf(nombre_archivo: str) -> str:
    """Descarga un PDF y extrae datos JSON."""
    try:
        blob = bucket.blob(nombre_archivo)
        if not blob.exists(): 
            return "Error: Archivo no encontrado."
        
        pdf_bytes = blob.download_as_bytes()
        
        prompt = """Extrae en JSON estricto: proveedor, fecha, numero_factura, total, items.
        Sin markdown, solo texto plano JSON."""
        
        response = generar_con_reintento(
            model=MODELO_ID,
            contents=[
                types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                prompt
            ]
        )
        
        return response.text.strip().replace("```json", "").replace("```", "")

    except Exception as e:
        return f"Error procesando: {str(e)}"

@mcp.tool()
def enviar_datos_api(datos_json: str) -> str:
    """Envía el JSON a la API local real."""
    try:
        # 1. Convertir texto a diccionario Python
        payload = json.loads(datos_json)
        
        # 2. HACER EL ENVÍO REAL (Antes estaba comentado)
        print(f"[INFO] Enviando datos a {API_DESTINO}...")
        res = requests.post(API_DESTINO, json=payload)
        
        # 3. Retornar lo que respondió la API
        if res.status_code == 200:
            return f"Éxito. La API respondió: {res.json()}"
        else:
            return f"Error en API. Status: {res.status_code}"

    except requests.exceptions.ConnectionError:
        return "Error: No se pudo conectar a la API. ¿Está corriendo en el puerto 8000?"
    except Exception as e:
        return f"Error de envío: {str(e)}"

@mcp.tool()
def listar_facturas_pendientes() -> str:
    """Lista SOLO UNA factura para pruebas de cuota."""
    try:
        blobs = bucket.list_blobs()
        files = [b.name for b in blobs if b.name.endswith('.pdf')]
        
        if not files:
            return "No hay facturas."
            
        # Mantenemos el límite de 1 factura para proteger tu cuota
        archivo_prueba = files[:1] 
        
        # EMOJI ELIMINADO AQUÍ
        print(f"[DEBUG] Modo Prueba: Mostrando solo {archivo_prueba} de {len(files)} archivos.")
        return str(archivo_prueba)

    except Exception as e:
        # Esto captura el error si vuelve a pasar algo raro
        return f"Error bucket: {str(e)}"

if __name__ == "__main__":
    mcp.run()