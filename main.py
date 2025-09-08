from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
from datetime import datetime

app = Flask(__name__)
CORS(app)

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
    """Busca llamadas por cliente o operador"""
    try:
        client = request.args.get('client', '')
        operator = request.args.get('operator', '')
        
        response = requests.get(f"{FIREBASE_URL}/calls.json")
        if response.status_code == 200:
            all_calls = response.json()
            if not all_calls:
                return jsonify({
                    "success": True,
                    "data": [],
                    "total": 0
                })
            
            filtered_calls = {}
            for call_id, call_data in all_calls.items():
                match = True
                if client and client.lower() not in call_data.get('Client', '').lower():
                    match = False
                if operator and operator.lower() not in call_data.get('Operator', '').lower():
                    match = False
                
                if match:
                    filtered_calls[call_id] = call_data
            
            return jsonify({
                "success": True,
                "data": filtered_calls,
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
    """Actualiza una llamada existente"""
    try:
        data = request.get_json()
        data['UpdatedAt'] = datetime.now().isoformat()
        
        response = requests.patch(f"{FIREBASE_URL}/calls/{call_id}.json", 
                                json=data)
        
        if response.status_code == 200:
            return jsonify({
                "success": True,
                "message": "Call updated successfully",
                "call_id": call_id
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)