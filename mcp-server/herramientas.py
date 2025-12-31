import os
import json
import requests
from mcp.server.fastmcp import FastMCP, Context
from google.cloud import storage
from google import genai
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURACIÓN ---
API_KEY_SERVICIO = "secreto_super_seguro_123"  # En prod, usar variables de entorno
BUCKET_NAME = 'facturacion-mcp'
API_DESTINO = "http://localhost:8001/recepcion-facturas"

# Inicializamos FastMCP
mcp = FastMCP("ServidorCentralizado")

# Clientes de Google
storage_client = storage.Client()
bucket = storage_client.bucket(BUCKET_NAME)

# --- MIDDLEWARE DE SEGURIDAD (Simulado en herramientas) ---
# Nota: En producción real (AWS/GCP), la autenticación se suele manejar 
# en el API Gateway o Nginx antes de llegar aquí. 
# Pero podemos proteger las herramientas verificando el contexto.

def verificar_acceso(ctx: Context):
    """Verifica si el cliente envió el token correcto en los headers."""
    # FastMCP permite acceder a metadatos de la sesión en futuras versiones.
    # Por ahora, asumiremos que si llegan al endpoint, pasaron el Gateway.
    # Esta función es un placeholder para lógica de validación interna.
    pass

# --- HERRAMIENTAS (Iguales que antes, pero listas para red) ---

@mcp.tool()
def analizar_factura_pdf(nombre_archivo: str, instrucciones: str, ctx: Context) -> str:
    """Descarga y analiza PDF (Requiere Auth)."""
    verificar_acceso(ctx) # Check de seguridad
    
    try:
        blob = bucket.blob(nombre_archivo)
        if not blob.exists(): return "Error: 404 Archivo no encontrado."
        
        pdf_bytes = blob.download_as_bytes()
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=[
                genai.types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                instrucciones
            ]
        )
        return response.text.strip().replace("```json", "").replace("```", "")
    except Exception as e:
        return f"Error servidor: {str(e)}"

@mcp.tool()
def enviar_datos_api(datos_json: str) -> str:
    """Envía datos a la API interna."""
    try:
        res = requests.post(API_DESTINO, json=json.loads(datos_json))
        return f"API Respondió: {res.status_code} - {res.text}"
    except Exception as e:
        return f"Error conexión API: {e}"

@mcp.tool()
def listar_facturas_pendientes() -> str:
    """Lista facturas en el bucket."""
    # ... lógica de listado ...
    blobs = bucket.list_blobs()
    files = [b.name for b in blobs if b.name.endswith('.pdf')]
    return str(files[:1])

# --- OTRA HERRAMIENTA (Para demostrar el problema del contexto) ---
@mcp.tool()
def herramienta_recursos_humanos(empleado: str) -> str:
    """Herramienta que NO debería ver el agente de facturación."""
    return f"Datos de RRHH del empleado {empleado}..."

if __name__ == "__main__":
    # ESTO CAMBIA: Ahora corremos en modo SSE (HTTP)
    # Escucha en el puerto 8080
    print("🚀 Servidor MCP levantado en http://localhost:8080")
    mcp.run(transport="sse")