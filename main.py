from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Imports para API SENDGRID
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import uuid

# Importaciones adicionales para Google Sheets
import gspread
from google.oauth2.service_account import Credentials
import json
import os
from datetime import datetime, timedelta
# Configuración de Google Sheets
GOOGLE_CREDENTIALS_FILE = 'google-credentials.json'
GOOGLE_SHEET_NAME = 'Encuesta de satisfacción NEXUSLINK (Respuestas)'  # CAMBIAR POR EL REAL

# Configuración de email
SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY')
FROM_EMAIL = "corysabel2017@gmail.com"
SURVEY_FORM_URL = "https://forms.gle/df1Wjxw8RQcWXqxZ9"  

# URL de tu Firebase
FIREBASE_URL = "https://nexuslink-7d374-default-rtdb.firebaseio.com"

def init_google_sheets():
    """Inicializa la conexión con Google Sheets"""
    try:
        print("🔍 Iniciando conexión con Google Sheets...")
        
        # Verificar si existe el archivo de credenciales
        if not os.path.exists(GOOGLE_CREDENTIALS_FILE):
            print(f"❌ Archivo {GOOGLE_CREDENTIALS_FILE} no encontrado")
            return None
            
        print(f"✅ Archivo de credenciales encontrado: {GOOGLE_CREDENTIALS_FILE}")
        
        # Definir los scopes necesarios
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        print(f"✅ Scopes configurados: {scope}")
        
        # Crear credenciales desde archivo
        creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=scope)
        print("✅ Credenciales cargadas correctamente")
        
        # Autorizar cliente de gspread
        client = gspread.authorize(creds)
        print("✅ Cliente autorizado correctamente")
        
        return client
        
    except Exception as e:
        print(f"❌ Error inicializando Google Sheets: {str(e)}")
        print(f"❌ Tipo de error: {type(e).__name__}")
        return None

def get_survey_responses_from_sheets():
    """Obtiene las respuestas del formulario desde Google Sheets"""
    try:
        print("📊 Obteniendo respuestas del formulario...")
        
        # Inicializar cliente
        client = init_google_sheets()
        if not client:
            return {"error": "No se pudo conectar con Google Sheets"}
        
        print(f"📋 Intentando abrir sheet: '{GOOGLE_SHEET_NAME}'")
        
        # Abrir la hoja de cálculo
        try:
            sheet = client.open(GOOGLE_SHEET_NAME).sheet1
            print(f"✅ Sheet abierto correctamente")
        except gspread.SpreadsheetNotFound:
            print(f"❌ Sheet no encontrado: {GOOGLE_SHEET_NAME}")
            return {"error": f"Sheet '{GOOGLE_SHEET_NAME}' no encontrado o no compartido correctamente"}
        except Exception as sheet_error:
            print(f"❌ Error abriendo sheet: {str(sheet_error)}")
            return {"error": f"Error accediendo al sheet: {str(sheet_error)}"}
        
        # Obtener todos los valores
        print("📥 Obteniendo datos del sheet...")
        all_values = sheet.get_all_values()
        
        if not all_values:
            print("⚠️ El sheet está vacío")
            return {"error": "El sheet está vacío"}
        
        print(f"✅ Se obtuvieron {len(all_values)} filas")
        
        # La primera fila son los headers
        headers = all_values[0]
        print(f"📋 Headers encontrados: {headers}")
        
        # Convertir a lista de diccionarios
        records = []
        for row in all_values[1:]:  # Saltar header
            if any(cell.strip() for cell in row):  # Solo filas no vacías
                record = {}
                for i, header in enumerate(headers):
                    value = row[i] if i < len(row) else ''
                    record[header] = value
                records.append(record)
        
        print(f"✅ Se procesaron {len(records)} respuestas")
        
        return {
            "success": True,
            "data": records,
            "headers": headers,
            "total": len(records)
        }
        
    except Exception as e:
        error_msg = f"Error obteniendo respuestas: {str(e)}"
        print(f"❌ {error_msg}")
        return {"error": error_msg}

def analyze_survey_responses(responses_data):
    """Analiza las respuestas y genera estadísticas"""
    try:
        if "error" in responses_data:
            return {"error": responses_data["error"]}
        
        records = responses_data["data"]
        headers = responses_data["headers"]
        
        print(f"🔍 Analizando {len(records)} respuestas...")
        print(f"🔍 Headers disponibles: {headers}")
        
        analysis = {
            "total_responses": len(records),
            "headers": headers,
            "ratings": {},
            "text_responses": {},
            "statistics": {},
            "recent_responses": records[-5:] if len(records) > 5 else records
        }
        
        # Analizar cada columna
        for header in headers:
            column_values = [record.get(header, '') for record in records]
            non_empty_values = [val for val in column_values if str(val).strip()]
            
            print(f"🔍 Analizando columna: {header} ({len(non_empty_values)} valores)")
            
            # Detectar si es una columna de rating/calificación
            if any(word in header.lower() for word in ['califica', 'rating', 'puntuación', 'estrellas', 'score']):
                numeric_values = []
                for val in non_empty_values:
                    try:
                        if str(val).replace('.', '').replace(',', '').isdigit():
                            numeric_values.append(float(str(val).replace(',', '.')))
                    except:
                        continue
                
                if numeric_values:
                    analysis["ratings"][header] = {
                        "average": round(sum(numeric_values) / len(numeric_values), 2),
                        "count": len(numeric_values),
                        "min": min(numeric_values),
                        "max": max(numeric_values),
                        "distribution": {}
                    }
                    
                    # Calcular distribución
                    for val in numeric_values:
                        val_str = str(int(val))
                        analysis["ratings"][header]["distribution"][val_str] = analysis["ratings"][header]["distribution"].get(val_str, 0) + 1
                    
                    print(f"📊 Rating {header}: Promedio {analysis['ratings'][header]['average']}")
            
            # Detectar columnas de texto (comentarios, etc.)
            elif any(word in header.lower() for word in ['comentario', 'comment', 'observ', 'suggest', 'feedback']):
                meaningful_comments = [val for val in non_empty_values if len(str(val).strip()) > 5]
                analysis["text_responses"][header] = {
                    "total_responses": len(meaningful_comments),
                    "sample_responses": meaningful_comments[:5]  # Primeros 5 comentarios
                }
                print(f"💬 Comentarios en {header}: {len(meaningful_comments)} respuestas")
        
        return analysis
        
    except Exception as e:
        error_msg = f"Error analizando respuestas: {str(e)}"
        print(f"❌ {error_msg}")
        return {"error": error_msg}


@app.route('/', methods=['GET'])
def home():
    """Endpoint de prueba"""
    return jsonify({
        "message": "NexusLink API is running",
        "version": "1.0.0",
        "status": "active"
    })

@app.route('/calls', methods=['GET'])
def get_all_calls():
    """Obtiene todas las llamadas"""
    try:
        response = requests.get(f"{FIREBASE_URL}/calls.json")
        if response.status_code == 200:
            data = response.json()
            if data:
                return jsonify({
                    "success": True,
                    "data": data,
                    "total": len(data)
                })
            else:
                return jsonify({
                    "success": True,
                    "data": {},
                    "total": 0
                })
        else:
            return jsonify({
                "success": False,
                "error": f"Firebase error: {response.status_code}"
            }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/calls/<call_id>', methods=['GET'])
def get_call_by_id(call_id):
    """Obtiene una llamada específica por ID"""
    try:
        response = requests.get(f"{FIREBASE_URL}/calls/{call_id}.json")
        if response.status_code == 200:
            data = response.json()
            if data:
                return jsonify({
                    "success": True,
                    "data": data
                })
            else:
                return jsonify({
                    "success": False,
                    "error": "Call not found"
                }), 404
        else:
            return jsonify({
                "success": False,
                "error": f"Firebase error: {response.status_code}"
            }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/calls/search', methods=['GET'])
def search_calls():
    """Busca llamadas por cliente o operador con formato mejorado"""
    try:
        client = request.args.get('client', '')
        operator = request.args.get('operator', '')
        
        response = requests.get(f"{FIREBASE_URL}/calls.json")
        if response.status_code == 200:
            all_calls = response.json()
            if not all_calls:
                return jsonify({
                    "success": True,
                    "message": f"No se encontraron llamadas para el cliente: {client}",
                    "results": [],
                    "total": 0
                })
            
            filtered_calls = []
            for call_id, call_data in all_calls.items():
                match = True
                if client and client.lower() not in call_data.get('Client', '').lower():
                    match = False
                if operator and operator.lower() not in call_data.get('Operator', '').lower():
                    match = False
                
                if match:
                    # Formatear los datos para mejor presentación
                    formatted_call = {
                        "call_id": call_id,
                        "client": call_data.get('Client', 'N/A'),
                        "operator": call_data.get('Operator', 'N/A'),
                        "date": call_data.get('Date', 'N/A'),
                        "conversation_summary": call_data.get('Conversation', 'N/A')[:200] + "..." if len(call_data.get('Conversation', '')) > 200 else call_data.get('Conversation', 'N/A'),
                        "full_conversation": call_data.get('Conversation', 'N/A')
                    }
                    filtered_calls.append(formatted_call)
            
            return jsonify({
                "success": True,
                "message": f"Se encontraron {len(filtered_calls)} llamadas para el cliente: {client}",
                "results": filtered_calls,
                "total": len(filtered_calls)
            })
        else:
            return jsonify({
                "success": False,
                "error": f"Firebase error: {response.status_code}"
            }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/calls', methods=['POST'])
def create_call():
    """Crea una nueva llamada"""
    try:
        data = request.get_json()
        
        # Validar datos requeridos
        required_fields = ['Operator', 'Client', 'Conversation']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    "success": False,
                    "error": f"Missing required field: {field}"
                }), 400
        
        # Agregar timestamp
        data['Date'] = datetime.now().isoformat()
        data['CreatedAt'] = datetime.now().isoformat()
        
        # Generar ID único
        import time
        call_id = f"call_{int(time.time())}"
        
        # Guardar en Firebase
        response = requests.put(f"{FIREBASE_URL}/calls/{call_id}.json", 
                              json=data)
        
        if response.status_code == 200:
            return jsonify({
                "success": True,
                "message": "Call created successfully",
                "call_id": call_id,
                "data": data
            }), 201
        else:
            return jsonify({
                "success": False,
                "error": f"Firebase error: {response.status_code}"
            }), 500
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/calls/<call_id>', methods=['PUT'])
def update_call(call_id):
    """Actualiza una llamada existente - VERSIÓN MEJORADA"""
    try:
        data = request.get_json()
        
        # Debug: mostrar datos recibidos
        print(f"📝 Updating call {call_id} with data:", data)
        
        # Verificar que la llamada existe
        get_response = requests.get(f"{FIREBASE_URL}/calls/{call_id}.json")
        if get_response.status_code != 200 or not get_response.json():
            return jsonify({
                "success": False,
                "error": f"Call {call_id} not found"
            }), 404
        
        # Obtener datos actuales
        current_data = get_response.json()
        print(f"📋 Current data:", current_data)
        
        # Preparar datos para actualización
        update_data = {}
        
        # Actualizar solo los campos que se enviaron
        updatable_fields = ['Call', 'Client', 'Operator', 'Conversation', 'Correo']
        
        for field in updatable_fields:
            if field in data and data[field] is not None:
                # Limpiar el dato
                if field == 'Conversation':
                    # Limpiar conversación
                    clean_value = str(data[field]).replace('\n', ' ').replace('\r', ' ')
                    clean_value = ' '.join(clean_value.split())
                    update_data[field] = clean_value
                elif field == 'Correo':
                    # Validar email
                    import re
                    email = str(data[field]).strip().lower()
                    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                    if not re.match(email_pattern, email):
                        return jsonify({
                            "success": False,
                            "error": f"Invalid email format: {email}"
                        }), 400
                    update_data[field] = email
                else:
                    # Campos normales
                    update_data[field] = str(data[field]).strip()
        
        # Agregar timestamp de actualización
        update_data['UpdatedAt'] = datetime.now().isoformat()
        
        print(f"🔄 Data to update:", update_data)
        
        # Actualizar en Firebase usando PATCH (actualización parcial)
        update_response = requests.patch(
            f"{FIREBASE_URL}/calls/{call_id}.json",
            json=update_data,
            headers={'Content-Type': 'application/json; charset=utf-8'}
        )
        
        print(f"🌐 Firebase response status: {update_response.status_code}")
        print(f"🌐 Firebase response text: {update_response.text}")
        
        if update_response.status_code == 200:
            # Verificar que se actualizó correctamente
            verify_response = requests.get(f"{FIREBASE_URL}/calls/{call_id}.json")
            updated_data = verify_response.json() if verify_response.status_code == 200 else {}
            
            return jsonify({
                "success": True,
                "message": f"Call {call_id} updated successfully",
                "call_id": call_id,
                "updated_fields": list(update_data.keys()),
                "updated_data": update_data,
                "verification": {
                    "current_email": updated_data.get('Correo', 'N/A'),
                    "current_client": updated_data.get('Client', 'N/A'),
                    "current_operator": updated_data.get('Operator', 'N/A'),
                    "last_updated": updated_data.get('UpdatedAt', 'N/A')
                }
            }), 200
        else:
            return jsonify({
                "success": False,
                "error": f"Firebase update failed: {update_response.status_code}",
                "firebase_response": update_response.text
            }), 500
            
    except Exception as e:
        print(f"❌ Error in update_call: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500

# Endpoint de prueba para verificar actualizaciones
@app.route('/calls/<call_id>/test-update', methods=['POST'])
def test_update_call(call_id):
    """Endpoint de prueba para actualizaciones"""
    try:
        # Datos de prueba
        test_data = {
            "Correo": "test.update@email.com",
            "UpdatedAt": datetime.now().isoformat()
        }
        
        print(f"🧪 Testing update for call {call_id}")
        
        # Simular actualización
        update_response = requests.patch(
            f"{FIREBASE_URL}/calls/{call_id}.json",
            json=test_data
        )
        
        # Verificar resultado
        get_response = requests.get(f"{FIREBASE_URL}/calls/{call_id}.json")
        current_data = get_response.json() if get_response.status_code == 200 else {}
        
        return jsonify({
            "test_update": {
                "call_id": call_id,
                "attempted_data": test_data,
                "firebase_status": update_response.status_code,
                "firebase_response": update_response.text,
                "current_email_in_db": current_data.get('Correo', 'Not found'),
                "update_successful": current_data.get('Correo') == test_data['Correo'],
                "full_current_data": current_data
            }
        })
        
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/analytics/summary', methods=['GET'])
def get_summary():
    """Obtiene resumen de llamadas"""
    try:
        response = requests.get(f"{FIREBASE_URL}/calls.json")
        if response.status_code == 200:
            all_calls = response.json()
            if not all_calls:
                return jsonify({
                    "success": True,
                    "total_calls": 0,
                    "operators": [],
                    "clients": []
                })
            
            operators = set()
            clients = set()
            
            for call_data in all_calls.values():
                operators.add(call_data.get('Operator', 'Unknown'))
                clients.add(call_data.get('Client', 'Unknown'))
            
            return jsonify({
                "success": True,
                "total_calls": len(all_calls),
                "total_operators": len(operators),
                "total_clients": len(clients),
                "operators": list(operators),
                "clients": list(clients)
            })
        else:
            return jsonify({
                "success": False,
                "error": f"Firebase error: {response.status_code}"
            }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    
@app.route('/calls/<call_id>/send-survey', methods=['POST'])
def send_satisfaction_survey(call_id):
    """Envía encuesta de satisfacción por email"""
    try:
        # 1. Obtener detalles de la llamada
        call_response = requests.get(f"{FIREBASE_URL}/calls/{call_id}.json")
        if call_response.status_code != 200 or not call_response.json():
            return jsonify({
                "success": False,
                "error": f"Call {call_id} not found"
            }), 404
            
        call_data = call_response.json()
        
        # 2. Verificar que tiene correo
        client_email = call_data.get('Correo')
        if not client_email:
            return jsonify({
                "success": False,
                "error": f"No email found for call {call_id}"
            }), 400
        
        # 3. Obtener datos básicos
        client_id = call_data.get('Client', 'Cliente')
        operator_name = call_data.get('Operator', 'Operador')
        call_date = call_data.get('Date', 'Fecha no disponible')
        
        # 4. Verificar si ya se envió encuesta para esta llamada
        existing_survey = check_existing_survey(call_id)
        if existing_survey:
            return jsonify({
                "success": False,
                "error": f"Survey already sent for this call on {existing_survey['sent_at']}"
            }), 400
        
        # 5. Crear contenido del email
        email_content = create_simple_email_content(client_id, operator_name, call_date)
        
        # 6. Enviar email
        email_sent = send_email(client_email, "Evaluación de Servicio - NEXUSLINK", email_content)
        
        if email_sent:
            # 7. Registrar envío en Firebase
            survey_data = {
                "call_id": call_id,
                "client_id": client_id,
                "client_email": client_email,
                "operator_name": operator_name,
                "call_date": call_date,
                "sent_at": datetime.now().isoformat(),
                "status": "sent"
            }
            
            # Guardar con ID único
            survey_id = f"survey_{call_id}_{int(datetime.now().timestamp())}"
            requests.put(f"{FIREBASE_URL}/surveys/{survey_id}.json", json=survey_data)
            
            return jsonify({
                "success": True,
                "message": f"Survey sent successfully for call {call_id}",
                "survey_id": survey_id,
                "sent_to": client_email,
                "client_id": client_id
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to send email"
            }), 500
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

def check_existing_survey(call_id):
    """Verifica si ya se envió encuesta para esta llamada"""
    try:
        response = requests.get(f"{FIREBASE_URL}/surveys.json")
        if response.status_code == 200:
            surveys = response.json() or {}
            
            for survey_id, survey_data in surveys.items():
                if survey_data.get('call_id') == call_id:
                    return survey_data
        return None
    except:
        return None

def create_simple_email_content(client_id, operator_name, call_date):
    """Crea el contenido HTML del email (simple)"""
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ 
                font-family: Arial, sans-serif; 
                line-height: 1.6; 
                color: #333; 
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{ 
                background-color: #0066cc; 
                color: white; 
                padding: 30px; 
                text-align: center; 
                border-radius: 10px 10px 0 0;
            }}
            .content {{ 
                padding: 30px; 
                background-color: #f9f9f9; 
                border-radius: 0 0 10px 10px;
            }}
            .button {{ 
                background-color: #28a745; 
                color: white; 
                padding: 15px 40px; 
                text-decoration: none; 
                border-radius: 5px; 
                display: inline-block; 
                margin: 20px 0;
                font-weight: bold;
                font-size: 16px;
            }}
            .button:hover {{
                background-color: #218838;
            }}
            .call-info {{
                background-color: #e9ecef;
                padding: 15px;
                border-radius: 5px;
                margin: 20px 0;
            }}
            .footer {{ 
                text-align: center; 
                padding: 20px; 
                font-size: 12px; 
                color: #666; 
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🌐 NEXUSLINK</h1>
            <h2>Evaluación de Servicio</h2>
        </div>
        
        <div class="content">
            <p>Estimado cliente,</p>
            
            <p>Esperamos que haya tenido una excelente experiencia con nuestro servicio de soporte técnico.</p>
            
            <div class="call-info">
                <strong>📞 Detalles de su consulta:</strong><br>
                • Cliente: {client_id}<br>
                • Operador: {operator_name}<br>
                • Fecha: {call_date}
            </div>
            
            <p>Su opinión es muy importante para nosotros. Por favor, tómese unos minutos para evaluar el servicio recibido.</p>
            
            <div style="text-align: center;">
                <a href="{SURVEY_FORM_URL}" class="button">📝 Evaluar Servicio</a>
            </div>
            
            <p><strong>¡Gracias por confiar en NEXUSLINK!</strong></p>
            <p>Su feedback nos ayuda a mejorar continuamente nuestro servicio.</p>
        </div>
        
        <div class="footer">
            <p>NEXUSLINK - Conectando tu mundo<br>
            Este es un email automático, por favor no responder.</p>
        </div>
    </body>
    </html>
    """
    
    return html_content

def send_email(to_email, subject, html_content):
    """Envía email usando SendGrid"""
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail
        
        sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_API_KEY)
        
        message = Mail(
            from_email=FROM_EMAIL,
            to_emails=to_email,
            subject=subject,
            html_content=html_content
        )
        
        response = sg.send(message)
        return response.status_code == 202
        
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

# Endpoint para obtener estadísticas de encuestas
@app.route('/surveys/stats', methods=['GET'])
def get_survey_stats():
    """Obtiene estadísticas de las encuestas enviadas"""
    try:
        response = requests.get(f"{FIREBASE_URL}/surveys.json")
        if response.status_code == 200:
            surveys = response.json() or {}
            
            if not surveys:
                return jsonify({
                    "success": True,
                    "total_sent": 0,
                    "by_operator": {},
                    "recent_surveys": [],
                    "today_count": 0
                })
            
            # Estadísticas básicas
            stats = {
                "total_sent": len(surveys),
                "by_operator": {},
                "recent_surveys": [],
                "today_count": 0
            }
            
            today = datetime.now().strftime('%Y-%m-%d')
            
            for survey_id, survey_data in surveys.items():
                # Contar por operador
                operator = survey_data.get('operator_name', 'Unknown')
                if operator not in stats['by_operator']:
                    stats['by_operator'][operator] = 0
                stats['by_operator'][operator] += 1
                
                # Contar enviadas hoy
                sent_date = survey_data.get('sent_at', '')[:10]
                if sent_date == today:
                    stats['today_count'] += 1
                
                # Últimas 10 encuestas
                if len(stats['recent_surveys']) < 10:
                    stats['recent_surveys'].append({
                        "survey_id": survey_id,
                        "call_id": survey_data.get('call_id'),
                        "client_id": survey_data.get('client_id'),
                        "operator": operator,
                        "sent_at": survey_data.get('sent_at'),
                        "status": survey_data.get('status')
                    })
            
            # Ordenar encuestas recientes por fecha
            stats['recent_surveys'].sort(key=lambda x: x['sent_at'], reverse=True)
            
            return jsonify({
                "success": True,
                "stats": stats
            })
        else:
            return jsonify({
                "success": False,
                "error": "Could not fetch survey data"
            }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# Endpoint para listar todas las encuestas
@app.route('/surveys', methods=['GET'])
def get_all_surveys():
    """Lista todas las encuestas enviadas"""
    try:
        response = requests.get(f"{FIREBASE_URL}/surveys.json")
        if response.status_code == 200:
            surveys = response.json() or {}
            
            survey_list = []
            for survey_id, survey_data in surveys.items():
                survey_list.append({
                    "survey_id": survey_id,
                    **survey_data
                })
            
            # Ordenar por fecha de envío (más recientes primero)
            survey_list.sort(key=lambda x: x.get('sent_at', ''), reverse=True)
            
            return jsonify({
                "success": True,
                "surveys": survey_list,
                "total": len(survey_list)
            })
        else:
            return jsonify({
                "success": False,
                "error": "Could not fetch surveys"
            }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    
@app.route('/surveys/google-responses', methods=['GET'])
def get_google_survey_responses():
    """Obtiene respuestas desde Google Sheets y las analiza"""
    try:
        print("🚀 Endpoint /surveys/google-responses llamado")
        
        # Obtener respuestas
        responses_data = get_survey_responses_from_sheets()
        
        if "error" in responses_data:
            return jsonify({
                "success": False,
                "error": responses_data["error"]
            }), 500
        
        # Analizar respuestas
        analysis = analyze_survey_responses(responses_data)
        
        if "error" in analysis:
            return jsonify({
                "success": False,
                "error": analysis["error"]
            }), 500
        
        return jsonify({
            "success": True,
            "message": "Survey responses retrieved successfully",
            "data": analysis
        })
        
    except Exception as e:
        print(f"❌ Error en endpoint: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/surveys/satisfaction-summary', methods=['GET'])
def get_satisfaction_summary():
    """Obtiene resumen de satisfacción para el agente"""
    try:
        print("📊 Generando resumen de satisfacción...")
        
        # Obtener y analizar datos
        responses_data = get_survey_responses_from_sheets()
        if "error" in responses_data:
            return jsonify({
                "success": False,
                "error": responses_data["error"]
            }), 500
        
        analysis = analyze_survey_responses(responses_data)
        if "error" in analysis:
            return jsonify({
                "success": False,
                "error": analysis["error"]
            }), 500
        
        # Crear resumen amigable para el agente
        summary = {
            "overview": {
                "total_responses": analysis["total_responses"],
                "survey_columns": analysis["headers"]
            },
            "satisfaction_scores": {},
            "key_insights": [],
            "recent_feedback": []
        }
        
        # Procesar ratings
        for rating_column, rating_data in analysis.get("ratings", {}).items():
            summary["satisfaction_scores"][rating_column] = {
                "average_score": rating_data["average"],
                "total_responses": rating_data["count"],
                "score_range": f"{rating_data['min']}-{rating_data['max']}",
                "distribution": rating_data["distribution"]
            }
            
            # Generar insights
            avg = rating_data["average"]
            if avg >= 4.5:
                summary["key_insights"].append(f"Excellent satisfaction in '{rating_column}' (avg: {avg})")
            elif avg >= 3.5:
                summary["key_insights"].append(f"Good satisfaction in '{rating_column}' (avg: {avg})")
            elif avg < 3.0:
                summary["key_insights"].append(f"Needs improvement in '{rating_column}' (avg: {avg})")
        
        # Procesar comentarios
        for text_column, text_data in analysis.get("text_responses", {}).items():
            if text_data["sample_responses"]:
                summary["recent_feedback"].extend([
                    {"source": text_column, "comment": comment} 
                    for comment in text_data["sample_responses"][:3]
                ])
        
        return jsonify({
            "success": True,
            "satisfaction_summary": summary
        })
        
    except Exception as e:
        print(f"❌ Error en satisfaction summary: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/surveys/customer-comments', methods=['GET'])
def get_customer_comments():
    """Obtiene comentarios de clientes"""
    try:
        print("💬 Obteniendo comentarios de clientes...")
        
        responses_data = get_survey_responses_from_sheets()
        if "error" in responses_data:
            return jsonify({
                "success": False,
                "error": responses_data["error"]
            }), 500
        
        analysis = analyze_survey_responses(responses_data)
        if "error" in analysis:
            return jsonify({
                "success": False,
                "error": analysis["error"]
            }), 500
        
        # Recopilar todos los comentarios
        all_comments = []
        for text_column, text_data in analysis.get("text_responses", {}).items():
            for comment in text_data["sample_responses"]:
                all_comments.append({
                    "source_column": text_column,
                    "comment": comment,
                    "length": len(str(comment))
                })
        
        # Ordenar por longitud (comentarios más detallados primero)
        all_comments.sort(key=lambda x: x["length"], reverse=True)
        
        return jsonify({
            "success": True,
            "total_comments": len(all_comments),
            "comments": all_comments[:10],  # Top 10 comentarios
            "summary": {
                "total_text_columns": len(analysis.get("text_responses", {})),
                "average_comment_length": sum(c["length"] for c in all_comments) / len(all_comments) if all_comments else 0
            }
        })
        
    except Exception as e:
        print(f"❌ Error obteniendo comentarios: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/surveys/answer-question', methods=['POST'])
def answer_survey_question():
    """Responde preguntas específicas sobre las encuestas"""
    try:
        data = request.get_json()
        question = data.get('question', '').lower()
        
        print(f"❓ Pregunta recibida: {question}")
        
        # Obtener datos actualizados
        responses_data = get_survey_responses_from_sheets()
        if "error" in responses_data:
            return jsonify({
                "success": False,
                "error": responses_data["error"]
            }), 500
        
        analysis = analyze_survey_responses(responses_data)
        if "error" in analysis:
            return jsonify({
                "success": False,
                "error": analysis["error"]
            }), 500
        
        # Generar respuesta según la pregunta
        answer = generate_intelligent_answer(question, analysis)
        
        return jsonify({
            "success": True,
            "question": data.get('question'),
            "answer": answer,
            "data_timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ Error respondiendo pregunta: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

def generate_intelligent_answer(question, analysis):
    """Genera respuestas inteligentes basadas en los datos"""
    
    total = analysis["total_responses"]
    ratings = analysis.get("ratings", {})
    comments = analysis.get("text_responses", {})
    
    # Preguntas sobre satisfacción
    if any(word in question for word in ['satisfacción', 'satisfaction', 'rating', 'calificación']):
        if not ratings:
            return "No se encontraron datos de calificación en las respuestas."
        
        answer = f"📊 **Resumen de Satisfacción** (basado en {total} respuestas):\n\n"
        for column, data in ratings.items():
            avg = data["average"]
            count = data["count"]
            answer += f"• **{column}**: {avg}/5.0 promedio ({count} respuestas)\n"
            
            if avg >= 4.5:
                answer += f"  ✅ Excelente nivel de satisfacción\n"
            elif avg >= 3.5:
                answer += f"  👍 Buen nivel de satisfacción\n"
            else:
                answer += f"  ⚠️ Área de mejora identificada\n"
            answer += "\n"
        
        return answer
    
    # Preguntas sobre comentarios
    elif any(word in question for word in ['comentarios', 'comments', 'feedback', 'opiniones']):
        if not comments:
            return "No se encontraron comentarios en las respuestas."
        
        answer = f"💬 **Comentarios de Clientes**:\n\n"
        comment_count = 0
        for column, data in comments.items():
            answer += f"**{column}** ({data['total_responses']} comentarios):\n"
            for i, comment in enumerate(data['sample_responses'][:3], 1):
                answer += f"{i}. \"{comment}\"\n"
                comment_count += 1
            answer += "\n"
        
        answer += f"📝 Total de comentarios procesados: {comment_count}"
        return answer
    
    # Preguntas sobre totales/resumen
    elif any(word in question for word in ['cuántas', 'total', 'resumen', 'summary']):
        answer = f"📈 **Resumen General de Encuestas**:\n\n"
        answer += f"📊 **Total de respuestas**: {total}\n"
        answer += f"📋 **Columnas en el formulario**: {len(analysis['headers'])}\n\n"
        
        if ratings:
            answer += f"🌟 **Métricas de Satisfacción**:\n"
            for column, data in ratings.items():
                answer += f"• {column}: {data['average']}/5.0\n"
            answer += "\n"
        
        if comments:
            total_comments = sum(data['total_responses'] for data in comments.values())
            answer += f"💬 **Total de comentarios**: {total_comments}\n"
        
        return answer
    
    # Pregunta no reconocida
    else:
        return f"❓ No pude identificar el tipo de pregunta. Puedes preguntar sobre:\n• Satisfacción/calificaciones\n• Comentarios/feedback\n• Resumen/totales\n\nDatos disponibles: {total} respuestas con {len(analysis['headers'])} columnas."

# ENDPOINT DE DEBUG COMPLETO
@app.route('/debug/google-sheets-test', methods=['GET'])
def debug_google_sheets_complete():
    """Endpoint completo de debugging para Google Sheets"""
    try:
        debug_info = {
            "step_1_file_check": {},
            "step_2_credentials": {},
            "step_3_connection": {},
            "step_4_sheet_access": {},
            "step_5_data_sample": {}
        }
        
        # PASO 1: Verificar archivo
        print("🔍 PASO 1: Verificando archivo de credenciales...")
        if os.path.exists(GOOGLE_CREDENTIALS_FILE):
            file_size = os.path.getsize(GOOGLE_CREDENTIALS_FILE)
            debug_info["step_1_file_check"] = {
                "file_exists": True,
                "file_size": file_size,
                "file_path": GOOGLE_CREDENTIALS_FILE
            }
            print(f"✅ Archivo encontrado: {file_size} bytes")
        else:
            debug_info["step_1_file_check"] = {
                "file_exists": False,
                "error": f"Archivo {GOOGLE_CREDENTIALS_FILE} no encontrado"
            }
            print("❌ Archivo no encontrado")
            return jsonify({"debug": debug_info})
        
        # PASO 2: Verificar credenciales
        print("🔍 PASO 2: Verificando credenciales...")
        try:
            with open(GOOGLE_CREDENTIALS_FILE, 'r') as f:
                creds_content = json.load(f)
            
            debug_info["step_2_credentials"] = {
                "valid_json": True,
                "client_email": creds_content.get("client_email", "No encontrado"),
                "project_id": creds_content.get("project_id", "No encontrado"),
                "has_private_key": "private_key" in creds_content
            }
            print(f"✅ Credenciales válidas para: {creds_content.get('client_email')}")
        except Exception as cred_error:
            debug_info["step_2_credentials"] = {
                "valid_json": False,
                "error": str(cred_error)
            }
            print(f"❌ Error en credenciales: {cred_error}")
            return jsonify({"debug": debug_info})
        
        # PASO 3: Probar conexión
        print("🔍 PASO 3: Probando conexión...")
        client = init_google_sheets()
        if client:
            debug_info["step_3_connection"] = {
                "connection_successful": True,
                "client_type": str(type(client))
            }
            print("✅ Conexión exitosa")
        else:
            debug_info["step_3_connection"] = {
                "connection_successful": False,
                "error": "No se pudo crear cliente"
            }
            print("❌ Fallo en conexión")
            return jsonify({"debug": debug_info})
        
        # PASO 4: Acceder al sheet
        print(f"🔍 PASO 4: Intentando acceder a sheet '{GOOGLE_SHEET_NAME}'...")
        try:
            sheet = client.open(GOOGLE_SHEET_NAME).sheet1
            sheet_info = {
                "sheet_accessible": True,
                "sheet_title": sheet.title,
                "sheet_id": sheet.id,
                "row_count": sheet.row_count,
                "col_count": sheet.col_count
            }
            debug_info["step_4_sheet_access"] = sheet_info
            print(f"✅ Sheet accesible: {sheet.title}")
        except Exception as sheet_error:
            debug_info["step_4_sheet_access"] = {
                "sheet_accessible": False,
                "error": str(sheet_error),
                "sheet_name_tried": GOOGLE_SHEET_NAME
            }
            print(f"❌ Error accediendo sheet: {sheet_error}")
            return jsonify({"debug": debug_info})
        
        # PASO 5: Obtener datos de muestra
        print("🔍 PASO 5: Obteniendo datos de muestra...")
        try:
            all_values = sheet.get_all_values()
            headers = all_values[0] if all_values else []
            sample_rows = all_values[1:4] if len(all_values) > 1 else []  # Primeras 3 filas de datos
            
            debug_info["step_5_data_sample"] = {
                "data_retrieved": True,
                "total_rows": len(all_values),
                "headers": headers,
                "sample_data": sample_rows,
                "headers_count": len(headers)
            }
            print(f"✅ Datos obtenidos: {len(all_values)} filas")
        except Exception as data_error:
            debug_info["step_5_data_sample"] = {
                "data_retrieved": False,
                "error": str(data_error)
            }
            print(f"❌ Error obteniendo datos: {data_error}")
        
        return jsonify({
            "debug": debug_info,
            "overall_status": "SUCCESS" if debug_info["step_5_data_sample"].get("data_retrieved") else "FAILED",
            "next_steps": [
                "Verificar que el sheet esté compartido con la cuenta de servicio",
                "Confirmar que el nombre del sheet sea exacto",
                "Verificar que haya datos en el formulario"
            ]
        })
        
    except Exception as e:
        return jsonify({
            "debug": {"general_error": str(e)},
            "overall_status": "FAILED"
        })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)