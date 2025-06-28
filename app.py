from flask import Flask, request, jsonify
import urllib.parse
import os
import psycopg2
import extraer
from functools import wraps

# filepath: /home/ignatus/Documentos/Github/WrapSell/backend_local/app.py

app = Flask(__name__)
DATABASE_URL = os.getenv('DATABASE_URL')
url = urllib.parse.urlparse(DATABASE_URL)
TABLE_NAME = "cards"  # Cambia esto por el nombre real de tu tabla

# Clave secreta para la API
API_SECRET_KEY = os.getenv('API_SECRET_KEY', 'your-default-secret-key-here')

DB_URL = f"dbname={url.path[1:]} user={url.username} password={url.password} host={url.hostname} port={url.port}"

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
        if not api_key or api_key != API_SECRET_KEY:
            return jsonify({"error": "API key requerida o inválida"}), 401
        return f(*args, **kwargs)
    return decorated_function


@app.route('/users', methods=['POST'])
@require_api_key
def create_user():
    """
    Crear un nuevo usuario en la base de datos
    Espera JSON con: wallet_address, wallet_type, username (opcional), email (opcional)
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "JSON requerido"}), 400
        
        wallet_address = data.get('wallet_address')
        wallet_type = data.get('wallet_type')
        username = data.get('username')
        email = data.get('email')
        
        if not wallet_address or not wallet_type:
            return jsonify({"error": "wallet_address y wallet_type son requeridos"}), 400
        
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # Verificar si el usuario ya existe
        cur.execute("SELECT wallet_address FROM users WHERE wallet_address = %s;", (wallet_address,))
        if cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"error": "Usuario ya existe"}), 409
        
        # Insertar nuevo usuario
        cur.execute(
            "INSERT INTO users (wallet_address, wallet_type, username, email) VALUES (%s, %s, %s, %s);",
            (wallet_address, wallet_type, username, email)
        )
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({"message": "Usuario creado exitosamente", "wallet_address": wallet_address}), 201
    except Exception as e:
        return jsonify({"error": f"Error al crear usuario: {e}"}), 500
# Configuración de la base de datos desde compose.yaml

@app.route('/users/<string:wallet_address>', methods=['GET'])
@require_api_key
def get_user(wallet_address):
    """
    Obtener los datos de un usuario según su wallet_address
    """
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        cur.execute("SELECT * FROM users WHERE wallet_address = %s;", (wallet_address,))
        row = cur.fetchone()
        
        if not row:
            cur.close()
            conn.close()
            return jsonify({"error": "Usuario no encontrado"}), 404
        
        columns = [desc[0] for desc in cur.description]
        user = dict(zip(columns, row))
        
        cur.close()
        conn.close()
        
        return jsonify(user), 200
    except Exception as e:
        return jsonify({"error": f"Error al obtener el usuario: {e}"}), 500


@app.route('/', methods=['GET'])
def home():
    """
    Página principal - Muestra información sobre las rutas disponibles
    """
    return jsonify({
        "message": "Bienvenido a WrapSell API",
        "authentication": "Requiere X-API-Key header o api_key parameter",
        "endpoints": {
            "GET /cards": "Obtener todas las cartas",
            "GET /cards/<id>": "Obtener una carta específica",
            "GET /total_value": "Obtener valor total de la colección",
            "POST /update_prices": "Actualizar precios de las cartas",
            "GET /users/<wallet_address>/cards": "Obtener cartas de un usuario específico"
        }
    }), 200

@app.route('/cards', methods=['GET'])
@require_api_key
def get_cards():
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("SELECT * FROM cards;")
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        cards = [dict(zip(columns, row)) for row in rows]
        cur.close()
        conn.close()
        return jsonify(cards), 200
    except Exception as e:
        return jsonify({"error": f"Error al obtener las cartas: {e}"}), 500

@app.route('/cards/<int:card_id>', methods=['GET'])
@require_api_key
def get_card(card_id):
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("SELECT * FROM cards WHERE id = %s;", (card_id,))
        row = cur.fetchone()
        columns = [desc[0] for desc in cur.description]
        cur.close()
        conn.close()
        if row:
            return jsonify(dict(zip(columns, row))), 200
        else:
            return jsonify({"error": "Carta no encontrada"}), 404
    except Exception as e:
        return jsonify({"error": f"Error al obtener la carta: {e}"}), 500

@app.route('/total_value', methods=['GET'])
@require_api_key
def get_total_value():
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(SUM(market_value), 0) FROM cards WHERE in_pool = TRUE;")
        total = cur.fetchone()[0]
        cur.close()
        conn.close()
        return jsonify({"total_collection_value": float(total)}), 200
    except Exception as e:
        return jsonify({"error": f"Error al calcular el valor total: {e}"}), 500
    
@app.route('/update_prices', methods=['POST'])
@require_api_key
def update_prices_endpoint():
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("SELECT id, edition, name, card_id FROM cards WHERE in_pool = TRUE;")
        cards = cur.fetchall()
        updated = 0
        not_updated = []

        for card in cards:
            card_db_id, edition, name, card_number = card
            card_data = extraer.extract_ungraded_card_data(edition, name, card_number)
            if card_data and card_data["market_value"] != "N/A":
                new_value = str(card_data["market_value"]).replace("$", "").replace(",", "")
                try:
                    cur.execute(
                        "UPDATE cards SET market_value = %s WHERE id = %s;",
                        (new_value, card_db_id)
                    )
                    conn.commit()
                    updated += 1
                except Exception as e:
                    not_updated.append({"id": card_db_id, "error": str(e)})
            else:
                not_updated.append({"id": card_db_id, "error": "No se pudo obtener el precio actualizado"})
        cur.close()
        conn.close()
        return jsonify({
            "message": f"Precios actualizados para {updated} cartas.",
            "not_updated": not_updated
        }), 200
    except Exception as e:
        return jsonify({"error": f"Error general al actualizar precios: {e}"}), 500
    
@app.route('/users/<string:wallet_address>/cards', methods=['GET'])
@require_api_key
def get_user_cards(wallet_address):
    """
    Retorna todas las cartas asociadas a una dirección de billetera específica.
    """
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # Ejecuta una consulta para seleccionar las cartas filtrando por user_wallet
        cur.execute("SELECT * FROM cards WHERE user_wallet = %s;", (wallet_address,))
        
        rows = cur.fetchall()
        
        # Si no se encuentran cartas, fetchall() devuelve una lista vacía, lo cual es correcto.
        
        columns = [desc[0] for desc in cur.description]
        cards = [dict(zip(columns, row)) for row in rows]
        
        cur.close()
        conn.close()
        
        return jsonify(cards), 200
    except Exception as e:
        return jsonify({"error": f"Error al obtener las cartas del usuario: {e}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
