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


# Configuración de email
SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY')
FROM_EMAIL = "corysabel2017@gmail.com"
SURVEY_FORM_URL = "https://forms.gle/df1Wjxw8RQcWXqxZ9"  

# URL de tu Firebase
FIREBASE_URL = "https://nexuslink-7d374-default-rtdb.firebaseio.com"



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
    


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)