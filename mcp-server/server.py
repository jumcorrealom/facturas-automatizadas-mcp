import asyncio
import os
from dotenv import load_dotenv
import google.generativeai as genai
from google.ai.generativelanguage import Content, Part, FunctionResponse
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Cargar claves
load_dotenv()

# Configurar Gemini
# NOTA: Asegúrate de usar el modelo correcto. Si -001 falla, prueba "gemini-1.5-flash"
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

async def main():
    # 1. Parámetros del Servidor
    server_params = StdioServerParameters(
        command="python",
        args=["mcp-server/server.py"],
        env=os.environ.copy()
    )

    print("🔌 Conectando con el servidor MCP...")

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            
            await session.initialize()
            tools_list = await session.list_tools()
            print(f"🛠️  Herramientas detectadas: {[t.name for t in tools_list.tools]}")

            # 2. Declaración de Herramientas para Gemini
            # Solo definimos las firmas (nombres y qué hacen), no la lógica.
            tools_declarations = [
                {
                    "name": "analizar_factura_pdf",
                    "description": "Analiza un PDF del bucket y extrae datos JSON.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "nombre_archivo": {"type": "STRING", "description": "Nombre exacto del archivo PDF"}
                        },
                        "required": ["nombre_archivo"]
                    }
                },
                {
                    "name": "enviar_datos_api",
                    "description": "Envía el JSON extraído a la API de procesamiento.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "datos_json": {"type": "STRING", "description": "JSON en formato texto"}
                        },
                        "required": ["datos_json"]
                    }
                },
                {
                    "name": "listar_facturas_pendientes",
                    "description": "Lista los archivos PDF en el bucket.",
                    "parameters": {"type": "OBJECT", "properties": {}}
                }
            ]

            model = genai.GenerativeModel(
                model_name="gemini-3-flash-preview", # Intenta regresar al nombre estándar
                tools=tools_declarations
            )
            
            # Iniciamos el chat SIN la llamada automática
            chat = model.start_chat(enable_automatic_function_calling=False)

            print("\n" + "="*40)
            print("🤖 CLIENTE FACTURACIÓN (MODO MANUAL) LISTO")
            print("="*40 + "\n")

            # 3. Bucle Principal de Chat
            while True:
                user_input = input("Tú: ")
                if user_input.lower() in ["salir", "exit"]:
                    break
                
                # Enviamos el mensaje inicial
                response = await chat.send_message_async(user_input)
                
                # --- BUCLE DE RESOLUCIÓN DE HERRAMIENTAS ---
                # Mientras Gemini nos responda pidiendo una función (function_call),
                # la ejecutamos y le devolvemos el resultado.
                while response.parts and response.parts[0].function_call:
                    
                    fc = response.parts[0].function_call
                    fn_name = fc.name
                    fn_args = fc.args
                    
                    print(f"⚡ Ejecutando herramienta: {fn_name}...")
                    
                    # Ejecutamos la herramienta en el servidor MCP (AQUÍ usamos el await correctamente)
                    try:
                        if fn_name == "analizar_factura_pdf":
                            result_mcp = await session.call_tool(fn_name, arguments={"nombre_archivo": fn_args["nombre_archivo"]})
                        elif fn_name == "enviar_datos_api":
                            result_mcp = await session.call_tool(fn_name, arguments={"datos_json": fn_args["datos_json"]})
                        elif fn_name == "listar_facturas_pendientes":
                            result_mcp = await session.call_tool(fn_name, arguments={})
                        else:
                            result_mcp = f"Error: Herramienta {fn_name} no reconocida."
                            
                        # El resultado suele venir en una lista de contenidos
                        texto_resultado = result_mcp.content[0].text if hasattr(result_mcp, 'content') else str(result_mcp)

                    except Exception as e:
                        texto_resultado = f"Error ejecutando herramienta: {str(e)}"

                    # Enviamos el resultado de vuelta a Gemini
                    # Construimos la respuesta de función requerida por la API
                    response = await chat.send_message_async(
                        Content(parts=[Part(
                            function_response=FunctionResponse(
                                name=fn_name,
                                response={"result": texto_resultado}
                            )
                        )])
                    )
                
                # Si llegamos aquí, Gemini ya no pide funciones, sino que nos habla a nosotros
                print(f"\nGemini: {response.text}\n")

if __name__ == "__main__":
    asyncio.run(main())