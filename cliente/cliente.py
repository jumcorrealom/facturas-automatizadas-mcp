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

# Usamos el mismo modelo Lite en el cliente
MODEL_ID = "gemini-flash-latest"

tool_analizar = types.FunctionDeclaration(
    name="analizar_factura_pdf",
    description="Analiza un PDF del bucket y extrae datos JSON.",
    parameters={
        "type": "OBJECT",
        "properties": {"nombre_archivo": {"type": "STRING"}},
        "required": ["nombre_archivo"]
    }
)
tool_enviar = types.FunctionDeclaration(
    name="enviar_datos_api",
    description="Envía el JSON extraído a la API.",
    parameters={
        "type": "OBJECT",
        "properties": {"datos_json": {"type": "STRING"}},
        "required": ["datos_json"]
    }
)
tool_listar = types.FunctionDeclaration(
    name="listar_facturas_pendientes",
    description="Lista los archivos PDF pendientes.",
    parameters={"type": "OBJECT", "properties": {}}
)

mcp_tools = [tool_analizar, tool_enviar, tool_listar]

async def main():
    server_params = StdioServerParameters(
        command="python",
        args=["mcp-server/herramientas.py"], 
        env=os.environ.copy()
    )

    print("🔌 Conectando servidor MCP...")

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print(f"🛠️  Servidor conectado. Usando modelo: {MODEL_ID}")

            client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            
            chat = client.chats.create(
                model=MODEL_ID,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(function_declarations=mcp_tools)]
                )
            )

            print("\n" + "="*40)
            print("🤖 CLIENTE ANTI-CUOTA LISTO")
            print("Escribe 'salir' para terminar.")
            print("="*40 + "\n")

            while True:
                try:
                    user_input = input("Tú: ")
                    if user_input.lower() in ["salir", "exit"]:
                        break

                    # Intento de envío con manejo de error 429
                    while True:
                        try:
                            response = chat.send_message(user_input)
                            break
                        except ClientError as e:
                            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                                print("⏳ Cuota llena. Esperando 10 segundos...")
                                time.sleep(10)
                            else:
                                raise e

                    # Procesamiento de herramientas
                    while True:
                        function_calls = []
                        if response.candidates and response.candidates[0].content.parts:
                            for part in response.candidates[0].content.parts:
                                if part.function_call:
                                    function_calls.append(part.function_call)
                        
                        if not function_calls:
                            break 

                        parts_response = []
                        for call in function_calls:
                            print(f"⚡ Ejecutando: {call.name}...")
                            
                            # LLAMADA AL SERVIDOR MCP
                            result_mcp = await session.call_tool(call.name, arguments=dict(call.args))
                            tool_output = result_mcp.content[0].text
                            
                            # --- AGREGAR ESTO PARA VER EL ERROR REAL ---
                            print(f"🔍 DEBUG SERVIDOR: {tool_output}") 
                            # -------------------------------------------
                            
                            # Si detectamos error de cuota en el output del servidor
                            if "Error" in tool_output and "429" in tool_output:
                                print("⚠️ El servidor reportó cuota llena.")

                            parts_response.append(
                                types.Part.from_function_response(
                                    name=call.name,
                                    response={"result": tool_output}
                                )
                            )

                        # Pausa táctica antes de enviar resultados a Gemini
                        # Esto reduce la frecuencia de peticiones por minuto
                        time.sleep(2) 
                        
                        try:
                            response = chat.send_message(parts_response)
                        except ClientError as e:
                             if "429" in str(e):
                                print("⏳ Esperando cuota para respuesta final (15s)...")
                                time.sleep(15)
                                response = chat.send_message(parts_response)
                    
                    if response.text:
                        print(f"\nGemini: {response.text}\n")

                except Exception as e:
                    print(f"❌ Error fatal: {e}")

if __name__ == "__main__":
    asyncio.run(main())