import asyncio
import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import ClientError
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

MODEL_ID = "gemini-flash-latest"

# --- 1. CONFIGURACIÓN DEL PROMPT MAESTRO ---
PROMPT_CONTABILIDAD = """
Analiza la factura adjunta y extrae la siguiente información en JSON estricto:
{
  "emisor": "Nombre empresa",
  "fecha": "YYYY-MM-DD",
  "numero_factura": "string",
  "total": 0.00,
  "items": [{"descripcion": "...", "cantidad": 0, "precio": 0.00}]
}
Si falta algún dato, usa null. Solo devuelve el JSON.
"""

# --- 2. DEFINICIÓN DE HERRAMIENTAS ---
# Notar el nuevo campo 'instrucciones' obligatorio
tool_analizar = types.FunctionDeclaration(
    name="analizar_factura_pdf",
    description="Analiza PDF y extrae JSON.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "nombre_archivo": {"type": "STRING"},
            "instrucciones": {"type": "STRING"} 
        },
        "required": ["nombre_archivo", "instrucciones"]
    }
)

tool_enviar = types.FunctionDeclaration(
    name="enviar_datos_api",
    description="Envía JSON a la API.",
    parameters={
        "type": "OBJECT",
        "properties": {"datos_json": {"type": "STRING"}},
        "required": ["datos_json"]
    }
)

tool_listar = types.FunctionDeclaration(
    name="listar_facturas_pendientes",
    description="Lista archivos PDF pendientes.",
    parameters={"type": "OBJECT", "properties": {}}
)

mcp_tools = [tool_analizar, tool_enviar, tool_listar]

async def main():
    server_params = StdioServerParameters(
        command="python",
        args=["mcp-server/herramientas.py"], 
        env=os.environ.copy()
    )

    print("🔌 Iniciando Agente Autónomo de Facturación...")

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            
            # Instrucción del sistema para autonomía total
            system_instruction = f"""
            Eres un agente autónomo de facturación. Tu trabajo es:
            1. Listar facturas pendientes.
            2. Si hay archivos, analízalos uno por uno usando SIEMPRE estas instrucciones en el parámetro 'instrucciones': '{PROMPT_CONTABILIDAD}'.
            3. Envía el resultado a la API.
            4. Informa el resultado final.
            
            No preguntes al usuario. Actúa directamente.
            """

            chat = client.chats.create(
                model=MODEL_ID,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(function_declarations=mcp_tools)],
                    system_instruction=system_instruction
                )
            )

            print("🤖 Agente iniciado. Ejecutando flujo de trabajo...")
            
            # --- DISPARADOR AUTOMÁTICO ---
            mensaje_inicial = "Inicia el proceso de revisión y procesamiento de facturas ahora."
            
            # Lógica de reintento simple para la primera llamada
            try:
                response = chat.send_message(mensaje_inicial)
            except ClientError as e:
                print(f"⚠️ Error inicial (posible cuota): {e}")
                return

            # --- BUCLE DE RESOLUCIÓN DE HERRAMIENTAS ---
            # Este bucle sigue corriendo mientras el modelo pida usar herramientas
            while True:
                function_calls = []
                if response.candidates and response.candidates[0].content.parts:
                    for part in response.candidates[0].content.parts:
                        if part.function_call:
                            function_calls.append(part.function_call)
                
                # Si no hay llamadas a herramientas, el trabajo terminó
                if not function_calls:
                    print("\n✅ TAREA COMPLETADA.")
                    print(f"Reporte final: {response.text}")
                    break

                # Ejecutar herramientas solicitadas
                parts_response = []
                for call in function_calls:
                    print(f"⚡ Ejecutando autónomamente: {call.name}...")
                    
                    # Llamada al servidor MCP
                    result_mcp = await session.call_tool(call.name, arguments=dict(call.args))
                    tool_output = result_mcp.content[0].text
                    
                    print(f"   ↳ Resultado: {tool_output[:100]}...") # Log corto
                    
                    parts_response.append(
                        types.Part.from_function_response(
                            name=call.name,
                            response={"result": tool_output}
                        )
                    )

                # Pausa para respetar cuotas (Rate Limiting)
                time.sleep(2)

                # Devolver resultados al modelo para que decida el siguiente paso
                try:
                    response = chat.send_message(parts_response)
                except ClientError as e:
                    if "429" in str(e):
                        print("⏳ Cuota llena. Pausando 15s antes de continuar...")
                        time.sleep(15)
                        response = chat.send_message(parts_response)
                    else:
                        print(f"❌ Error fatal en el bucle: {e}")
                        break

if __name__ == "__main__":
    asyncio.run(main())