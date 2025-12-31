# 🧾 Facturas Automatizadas MCP

Este proyecto implementa un sistema automatizado para la recepción, procesamiento y extracción de datos de facturas utilizando **Model Context Protocol (MCP)** y **Google Gemini AI**.

El sistema monitorea una cuenta de correo electrónico en busca de facturas, las sube a la nube, extrae la información relevante (proveedor, fecha, total, ítems) usando Inteligencia Artificial y envía los datos estructurados a una API de backend.

## 🚀 Arquitectura del Proyecto

El sistema se divide en cuatro módulos principales:

1.  **Watcher (`watcher/`)**: Script que revisa el correo electrónico diariamente, busca correos con el asunto "factura", descarga los adjuntos (PDF o ZIPs con PDFs) y los sube a un Bucket de Google Cloud Storage.
2.  **API de Procesamiento (`api-procesamiento/`)**: Una API local construida con FastAPI que simula el sistema contable o ERP donde se recibirán los datos finales.
3.  **Servidor MCP (`mcp-server/`)**: Servidor que expone herramientas (*tools*) para que la IA interactúe con el mundo real: leer archivos del bucket, analizar contenido con Gemini y enviar datos a la API.
4.  **Cliente (`cliente/`)**: Interfaz de chat donde el usuario interactúa con Gemini. Gemini decide cuándo invocar las herramientas del servidor MCP para completar la tarea.

## 📋 Requisitos Previos

* Python 3.10+
* Cuenta de Google Cloud Platform (con un Bucket creado llamado `facturacion-mcp`).
* API Key de Google Gemini.
* Contraseña de aplicación de Gmail (para acceso IMAP).

## ⚙️ Configuración e Instalación

### 1. Clonar el repositorio y configurar variables de entorno

Crea un archivo `.env` en la raíz del proyecto con las siguientes credenciales (asegúrate de no subirlo al repositorio):

```env
CORREO=tu_correo@gmail.com
PASSWORD=tu_contraseña_de_aplicacion
GEMINI_API_KEY=tu_api_key_de_gemini
```

### 2. Instalación de dependencias

Cada módulo tiene sus propias dependencias. Instálalas en tu entorno virtual:

```bash
# Dependencias del Watcher (Correo -> Cloud Storage)
pip install -r watcher/requirements.txt

# Dependencias del Servidor MCP (Lógica AI)
pip install -r mcp-server/requirements.txt

# Dependencias de la API (Backend simulado)
pip install -r api-procesamiento/requirements.txt
```

*(Nota: Las librerías principales incluyen `fastapi`, `uvicorn`, `google-generativeai`, `google-cloud-storage`, `mcp` y `python-dotenv`).*

## ▶️ Ejecución

Para ver el sistema completo en funcionamiento, necesitarás correr los componentes en terminales separadas:

### Paso 1: Iniciar la API de Recepción
Esta API recibirá los datos JSON extraídos.

```bash
python api-procesamiento/main.py
# La API correrá en [http://0.0.0.0:8000](http://0.0.0.0:8000)
```

### Paso 2: Ejecutar el Watcher (Opcional si ya tienes archivos en la nube)
Este script buscará correos de **hoy** que contengan "factura" en el asunto y subirá los PDFs a Google Cloud Storage.

```bash
python watcher/main.py
```

### Paso 3: Iniciar el Cliente MCP (El Chatbot)
Este script inicia la sesión de chat con Gemini, conectando automáticamente con el servidor de herramientas (`mcp-server/herramientas.py`).

```bash
python cliente/cliente.py
```

Una vez iniciado, verás un prompt donde podrás escribir comandos en lenguaje natural, por ejemplo:
> *"Revisa si hay facturas pendientes, analízalas y envía los datos a la API"*

## 🛠️ Estructura del Código

```text
📂 .
├── 📄 .env                    # Credenciales (NO subir al repo)
├── 📂 api-procesamiento       # Backend destino
│   ├── main.py                # Servidor FastAPI
│   └── requirements.txt
├── 📂 cliente                 # Cliente MCP (Usuario -> Gemini)
│   └── cliente.py
├── 📂 mcp-server              # Servidor MCP (Herramientas)
│   ├── herramientas.py        # Implementación de FastMCP
│   ├── server.py              # Definición alternativa del servidor
│   └── requirements.txt
└── 📂 watcher                 # Ingesta de datos
    ├── main.py                # Lógica IMAP y Upload a GCS
    └── requirements.txt
```

## 🤖 Capacidades de la IA

Gracias a la integración con MCP y Gemini, el agente puede:
* **Listar archivos**: Consulta el bucket de almacenamiento en tiempo real.
* **OCR Semántico**: Lee PDFs (incluso imágenes) y extrae: `proveedor`, `fecha`, `numero_factura`, `total`, `items`.
* **Interacción API**: Formatea la respuesta como JSON y realiza peticiones POST al backend local.

---
**Autor:** jumcorrealom
