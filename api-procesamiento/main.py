from fastapi import FastAPI, Request
from typing import Dict, Any
import uvicorn

app = FastAPI()

@app.get("/")
def home():
    return {"status": "API de Facturación Online 🟢"}

# Este es el endpoint clave donde llegará la info del MCP
@app.post("/recepcion-facturas")
async def recibir_factura(datos: Dict[str, Any]):
    print("\n" + "="*30)
    print("📢 NUEVA FACTURA RECIBIDA")
    print("="*30)
    
    # Aquí simplemente imprimimos lo que llega para verificar
    for clave, valor in datos.items():
        print(f"🔹 {clave}: {valor}")
        
    print("="*30 + "\n")
    
    return {"mensaje": "Datos recibidos correctamente", "recibido": datos}

if __name__ == "__main__":
    # Correrá en el puerto 8000
    uvicorn.run(app, host="0.0.0.0", port=8001)