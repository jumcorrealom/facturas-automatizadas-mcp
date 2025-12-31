import os
import imaplib
import email
import zipfile
import io
from datetime import datetime
from email.header import decode_header
from google.cloud import storage
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

CORREO = os.getenv('CORREO')
PASSWORD = os.getenv('PASSWORD')
BUCKET_NAME = 'facturacion-mcp'

def main(request):
    print("Iniciando revisión diaria...")

    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(CORREO, PASSWORD)
    except Exception as e:
        return f"Error de conexión: {e}", 500

    mail.select('INBOX')

    # --- SOLUCIÓN DE FECHA ---
    # Creamos la fecha manualmente para asegurar que el mes esté en inglés
    # sin importar el idioma de tu Windows.
    ahora = datetime.now()
    meses_ingles = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    
    # Restamos 1 al mes porque las listas en Python empiezan en 0
    nombre_mes = meses_ingles[ahora.month - 1] 
    
    # Formato requerido: "30-Dec-2025"
    fecha_hoy = f"{ahora.day}-{nombre_mes}-{ahora.year}"
    
    # Búsqueda combinada: (SINCE fecha Y UNSEEN)
    criterio_busqueda = f'(SINCE "{fecha_hoy}" UNSEEN)'
    print(f"Buscando correos con criterio: {criterio_busqueda}")
    
    status, messages = mail.search(None, criterio_busqueda)
    
    email_ids = messages[0].split()
    if not email_ids:
        print("No hay correos nuevos de hoy.")
        return "Sin correos nuevos", 200

    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    archivos_procesados = 0

    for e_id in email_ids:
        res, msg_data = mail.fetch(e_id, '(RFC822)')
        
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                
                subject, encoding = decode_header(msg['Subject'])[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding if encoding else 'utf-8')
                
                if 'factura' not in subject.lower():
                    print(f"Saltando: {subject}")
                    continue
                
                print(f"Procesando: {subject}")

                for part in msg.walk():
                    if part.get_content_maintype() == 'multipart' or part.get('Content-Disposition') is None:
                        continue

                    filename = part.get_filename()
                    if not filename: continue

                    file_data = part.get_payload(decode=True)

                    # Procesar PDF directo
                    if filename.lower().endswith('.pdf'):
                        bucket.blob(filename).upload_from_string(file_data, content_type='application/pdf')
                        archivos_procesados += 1
                        print(f"  -> PDF subido: {filename}")

                    # Procesar ZIP
                    elif filename.lower().endswith('.zip'):
                        try:
                            zip_buffer = io.BytesIO(file_data)
                            with zipfile.ZipFile(zip_buffer, 'r') as z:
                                for name in z.namelist():
                                    if name.lower().endswith('.pdf'):
                                        pdf_content = z.read(name)
                                        bucket.blob(name).upload_from_string(pdf_content, content_type='application/pdf')
                                        archivos_procesados += 1
                                        print(f"  -> PDF extraído y subido: {name}")
                        except zipfile.BadZipFile:
                            print(f"ZIP corrupto: {filename}")

    mail.close()
    mail.logout()
    
    return f"Proceso terminado. Facturas de hoy subidas: {archivos_procesados}", 200

if __name__ == "__main__":
    main(None)