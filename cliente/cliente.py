import asyncio
import os
from dotenv import load_dotenv
import google.generativeai as genai
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Cargar claves (Gemini API Key)
load_dotenv()

# Configurar Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

async def main():
    # 1. Definir cómo arrancar el servidor
    # Aquí usamos el comando que me confirmaste
    server_params = StdioServerParameters(
        command="python",
        args=["mcp-server/herramientas.py"], # <--- ¡AQUÍ ESTÁ LA CLAVE! Apuntamos al archivo de herramientas
        env=os.environ.copy()
    )

    print("🔌 Conectando con el servidor MCP...")

    # 2. Iniciar la conexión (El "Handshake")
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            
            # Inicializar herramientas disponibles
            await session.initialize()
            
            # Obtener lista de herramientas del servidor
            tools_list = await session.list_tools()
            print(f"🛠️  Herramientas detectadas en el servidor: {[t.name for t in tools_list.tools]}")

            # --- PUENTE ENTRE GEMINI Y MCP ---
            # Para que Gemini pueda usar las herramientas del servidor,
            # creamos funciones "envoltura" en el cliente que llaman al servidor.

            async def bridge_analizar_factura(nombre_archivo: str):
                """Llama a la herramienta del servidor para analizar un PDF."""
                print(f"🤖 Gemini solicita analizar: {nombre_archivo}")
                result = await session.call_tool("analizar_factura_pdf", arguments={"nombre_archivo": nombre_archivo})
                return result.content[0].text

            async def bridge_enviar_api(datos_json: str):
                """Llama a la herramienta del servidor para enviar datos a la API."""
                print(f"🤖 Gemini solicita enviar datos a la API...")
                result = await session.call_tool("enviar_datos_api", arguments={"datos_json": datos_json})
                return result.content[0].text
            
            async def bridge_listar_facturas():
                """Llama a la herramienta del servidor para listar archivos."""
                result = await session.call_tool("listar_facturas_pendientes", arguments={})
                return result.content[0].text

            # 3. Configurar el Chat con Herramientas
            # Le damos estas funciones puente a Gemini
            tools_for_gemini = [bridge_analizar_factura, bridge_enviar_api, bridge_listar_facturas]
            model = genai.GenerativeModel(
                model_name="gemini-3-flash-preview",
                tools=tools_for_gemini
            )
            
            chat = model.start_chat(enable_automatic_function_calling=True)

            print("\n" + "="*40)
            print("🤖 CLIENTE FACTURACIÓN IA LISTO")
            print("Escribe 'salir' para terminar.")
            print("="*40 + "\n")

            # 4. Bucle de Chat (Loop principal)
            while True:
                user_input = input("Tú: ")
                if user_input.lower() in ["salir", "exit"]:
                    break
                
                try:
                    # Enviamos mensaje a Gemini.
                    # Al tener 'enable_automatic_function_calling=True', 
                    # él solo ejecutará los puentes si lo necesita.
                    response = await chat.send_message_async(user_input)
                    print(f"\nGemini: {response.text}\n")
                    
                except Exception as e:
                    print(f"❌ Error en el chat: {e}")

if __name__ == "__main__":
    asyncio.run(main())