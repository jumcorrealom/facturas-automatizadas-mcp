import asyncio
import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import ClientError
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client

load_dotenv()

SERVER_URL = "http://localhost:8000/sse"
AUTH_HEADERS = {"Authorization": "Bearer secreto_super_seguro_123"}

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
# --- 3. LISTA BLANCA (WHITELIST) DE HERRAMIENTAS ---
# Aquí es donde evitas que el agente "se vuelva loco".
# Definimos explícitamente qué herramientas tiene permitido usar este agente.
HERRAMIENTAS_PERMITIDAS = {
    "analizar_factura_pdf",
    "enviar_datos_api",
    "listar_facturas_pendientes"
}
# Nota: "herramienta_recursos_humanos" NO está en la lista.
async def main():
    print(f"🌐 Conectando al servidor remoto: {SERVER_URL}...")

    try:
        async with sse_client(SERVER_URL, headers=AUTH_HEADERS) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # --- A) OBTENER Y FILTRAR HERRAMIENTAS ---
                list_tools_result = await session.list_tools()
                mis_tools_gemini = []
                
                for tool in list_tools_result.tools:
                    if tool.name in HERRAMIENTAS_PERMITIDAS:
                        print(f"✅ Cargando herramienta: {tool.name}")
                        declaracion = types.FunctionDeclaration(
                            name=tool.name,
                            description=tool.description,
                            parameters=tool.inputSchema
                        )
                        mis_tools_gemini.append(declaracion)
                    else:
                        print(f"🚫 Ignorando herramienta irrelevante: {tool.name}")

                # --- B) INICIAR EL CEREBRO (GEMINI) ---
                client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
                
                sys_instr = f"""
                Eres un agente autónomo de facturación.
                Tu objetivo es procesar todas las facturas pendientes.
                
                REGLA DE ORO:
                Cuando uses la herramienta 'analizar_factura_pdf', DEBES poner en el parámetro 
                'instrucciones' exáctamente este texto: '{PROMPT_CONTABILIDAD}'
                """

                chat = client.chats.create(
                    model="gemini-flash-latest",
                    config=types.GenerateContentConfig(
                        tools=[types.Tool(function_declarations=mis_tools_gemini)],
                        system_instruction=sys_instr
                    )
                )

                print("🤖 Agente Remoto Iniciado. Ejecutando flujo de trabajo...")
                
                # Disparamos la primera acción
                response = chat.send_message("Empieza a procesar las facturas pendientes ahora.")

                # --- C) BUCLE DE EJECUCIÓN AUTÓNOMA ---
                while True:
                    # 1. Detectar si Gemini quiere llamar herramientas
                    function_calls = []
                    if response.candidates and response.candidates[0].content.parts:
                        for part in response.candidates[0].content.parts:
                            if part.function_call:
                                function_calls.append(part.function_call)
                    
                    # 2. Si no hay llamadas, terminamos
                    if not function_calls:
                        print("\n✅ TAREA COMPLETADA.")
                        print(f"Reporte final: {response.text}")
                        break

                    # 3. Ejecutar las herramientas solicitadas
                    parts_response = []
                    for call in function_calls:
                        print(f"⚡ Ejecutando remotamente: {call.name}...")
                        
                        try:
                            # AQUÍ OCURRE LA MAGIA: El cliente llama al servidor HTTP por ti
                            result_mcp = await session.call_tool(call.name, arguments=dict(call.args))
                            
                            # Extraemos el texto del resultado
                            tool_output = result_mcp.content[0].text
                            print(f"   ↳ Servidor respondió: {tool_output[:100]}...")
                            
                            parts_response.append(
                                types.Part.from_function_response(
                                    name=call.name,
                                    response={"result": tool_output}
                                )
                            )
                        except Exception as e:
                            print(f"❌ Error ejecutando herramienta {call.name}: {e}")
                            parts_response.append(
                                types.Part.from_function_response(
                                    name=call.name,
                                    response={"error": str(e)}
                                )
                            )

                    # 4. Pausa táctica (evitar saturar la API)
                    time.sleep(2)

                    # 5. Devolver resultados a Gemini para que decida el siguiente paso
                    try:
                        response = chat.send_message(parts_response)
                    except ClientError as e:
                        if "429" in str(e):
                            print("⏳ Cuota llena. Esperando 15s...")
                            time.sleep(15)
                            response = chat.send_message(parts_response)
                        else:
                            raise e

    except Exception as e:
        print(f"\n❌ Error de conexión o ejecución: {e}")
        print("Asegúrate de que 'python mcp-server/herramientas.py' esté corriendo en otra terminal.")

if __name__ == "__main__":
    asyncio.run(main())