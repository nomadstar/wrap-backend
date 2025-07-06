from flask import Flask, request, jsonify
from flask_cors import CORS
import urllib.parse
import os
import psycopg2
import extraer
from functools import wraps
import sys

# filepath: /home/ignatus/Documentos/Github/WrapSell/backend_local/app.py

def initialize_database():
    """
    Inicializa la base de datos ejecutando el script 01_init.sql
    que crea las tablas solo si no existen.
    """
    try:
        # Leer el archivo SQL de inicialización
        script_path = os.path.join(os.path.dirname(__file__), '01_init.sql')
        with open(script_path, 'r', encoding='utf-8') as f:
            sql_script = f.read()
        
        # Conectar a la base de datos
        DATABASE_URL = os.getenv('DATABASE_URL')
        if not DATABASE_URL:
            raise ValueError("DATABASE_URL no está definido")
        
        url = urllib.parse.urlparse(DATABASE_URL)
        conn = psycopg2.connect(
            dbname=url.path[1:], user=url.username,
            password=url.password, host=url.hostname,
            port=url.port
        )
        
        # Ejecutar el script SQL
        cur = conn.cursor()
        cur.execute(sql_script)
        conn.commit()
        cur.close()
        conn.close()
        
        print("Base de datos inicializada correctamente - Tablas creadas si no existían")
        return True
        
    except FileNotFoundError:
        print("Advertencia: Archivo 01_init.sql no encontrado")
        return False
    except Exception as e:
        print(f"Error al inicializar la base de datos: {e}")
        return False


app = Flask(__name__)

# Configurar CORS para permitir solicitudes desde el frontend
CORS(app, origins=[
    "http://localhost:3000",  # Desarrollo local
    "https://wrap-sell.vercel.app",  # Producción en Vercel (si aplica)
    "https://*.vercel.app",  # Cualquier subdominio de Vercel
    "*"  # Permitir todos los orígenes (solo para desarrollo)
])

try:
    DATABASE_URL = os.getenv('DATABASE_URL')
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL no está definido")
    url = urllib.parse.urlparse(DATABASE_URL)
    # Prueba de conexión a la base de datos
    conn_test = psycopg2.connect(
        dbname=url.path[1:], user=url.username,
        password=url.password, host=url.hostname,
        port=url.port
    )
    conn_test.close()
    print("Conexión a la base de datos exitosa")
    
    # Inicializar la base de datos (crear tablas si no existen)
    initialize_database()
    
except Exception as e:
    print(f"Error al conectar a la base de datos: {e}")
    sys.exit(1)

# Clave secreta para la API
API_SECRET_KEY = os.getenv('API_SECRET_KEY')
if not API_SECRET_KEY:
    print("API_SECRET_KEY no está definida")
else:
    print(f"API_SECRET_KEY: {API_SECRET_KEY}")

TABLE_NAME = "cards"  # Cambia esto por el nombre real de tu tabla

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
@require_api_key
def home():
    """
    Página principal - Muestra información sobre las rutas disponibles.
    Requiere credenciales (X-API-Key o api_key).
    """
    valid_key = request.headers.get('X-API-Key') or request.args.get('api_key')
    if request.method == 'GET' and valid_key:
        response = {
            "message": "Bienvenido a la API de WrapSell",
            "endpoints": {
                "/users": "Crear un nuevo usuario (POST)",
                "/users/<wallet_address>": "Obtener datos de un usuario (GET)",
                "/users/<wallet_address>/cards": "Obtener cartas de un usuario específico (GET)",
                "/cards": "Obtener todas las cartas (GET)",
                "/cards/<card_id>": "Obtener una carta específica (GET)",
                "/cards/add-by-url": "Añadir carta usando URL de pricecharting (POST)",
                "/cards/batch-add-by-urls": "Añadir múltiples cartas usando URLs (POST)",
                "/pools": "Crear nuevo pool (POST) / Obtener todos los pools (GET)",
                "/dashboard/pools": "Obtener pools para dashboard (GET)",
                "/dashboard/user/<wallet_address>/summary": "Resumen del usuario para dashboard (GET)",
                "/total_value": "Obtener el valor total de la colección (GET)",
                "/update_prices": "Actualizar precios de cartas (POST)",
                "--- ENDPOINTS ADMINISTRATIVOS ---": "Requieren wallet autorizada",
                "/cards_admin/add-by-url": "[ADMIN] Añadir carta por URL (POST)",
                "/cards_admin/add-manual": "[ADMIN] Añadir carta manualmente (POST)",
                "/cards_admin/edit/<card_id>": "[ADMIN] Editar carta existente (PUT)",
                "/cards_admin/remove/<card_id>": "[ADMIN] Marcar carta como removida (DELETE)",
                "/cards_admin/restore/<card_id>": "[ADMIN] Restaurar carta removida (PUT)",
                "/cards_admin/delete-permanent/<card_id>": "[ADMIN] Eliminar permanentemente (DELETE)",
                "/cards_admin/move-to-pool": "[ADMIN] Mover cartas entre pools (PUT)",
                "/cards_admin/batch-update-prices": "[ADMIN] Actualizar precios masivamente (PUT)"
            }
        }
    else:
        response = {
            "message": "Bienvenido a la API de WrapSell, por favor proporciona una clave API válida en los headers (X-API-Key) o como parámetro de consulta (api_key).",
            "endpoints": {
                "please": "provide a valid API key in the headers (X-API-Key) or as a query parameter (api_key)."
            }
        }
    return jsonify(response), 200

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
        # Calcular el valor total de todas las cartas activas (no removidas)
        cur.execute("SELECT COALESCE(SUM(market_value), 0) FROM cards WHERE removed_at IS NULL;")
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
        # Actualizar precios de todas las cartas activas (no removidas)
        cur.execute("SELECT id, edition, name, card_id FROM cards WHERE removed_at IS NULL;")
        cards = cur.fetchall()
        updated = 0
        not_updated = []

        for card in cards:
            card_db_id, edition, name, card_number = card
            card_data = extraer.extract_ungraded_card_data(edition, name, card_number)
            if card_data and card_data["market_value"] is not None:
                try:
                    cur.execute(
                        "UPDATE cards SET market_value = %s WHERE id = %s;",
                        (card_data["market_value"], card_db_id)
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

@app.route('/cards/add-by-url', methods=['POST'])
@require_api_key
def add_card_by_url():
    """
    Añadir una nueva carta a la base de datos usando una URL de pricecharting.com
    Espera JSON con: url, user_wallet, pool_id (opcional)
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "JSON requerido"}), 400
        
        url = data.get('url')
        user_wallet = data.get('user_wallet')
        pool_id = data.get('pool_id')  # Opcional
        
        if not url or not user_wallet:
            return jsonify({"error": "url y user_wallet son requeridos"}), 400
        
        # Usar la función de extraer.py para obtener los datos de la carta
        card_data = extraer.extract_ungraded_card_data_by_link(url)
        
        if not card_data:
            return jsonify({"error": "No se pudieron extraer los datos de la carta desde la URL"}), 400
        
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # Verificar si el usuario existe
        cur.execute("SELECT wallet_address FROM users WHERE wallet_address = %s;", (user_wallet,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"error": "Usuario no encontrado. Debe crear el usuario primero."}), 404
        
        # Verificar si el pool existe (si se proporcionó)
        if pool_id:
            cur.execute("SELECT id FROM card_pools WHERE id = %s;", (pool_id,))
            if not cur.fetchone():
                cur.close()
                conn.close()
                return jsonify({"error": "Pool no encontrado"}), 404
        
        # Insertar la carta en la base de datos
        cur.execute(
            """
            INSERT INTO cards (name, card_id, edition, user_wallet, url, market_value, pool_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (
                card_data['name'],
                card_data['card_id'],
                card_data['edition'],
                user_wallet,
                card_data['url'],
                card_data['market_value'],
                pool_id
            )
        )
        
        new_card_id = cur.fetchone()[0]
        conn.commit()
        
        # Si se especificó un pool, también agregar a la tabla pool
        if pool_id:
            cur.execute(
                "INSERT INTO pool (card_id, added_by) VALUES (%s, %s);",
                (new_card_id, user_wallet)
            )
            conn.commit()
        
        cur.close()
        conn.close()
        
        return jsonify({
            "message": "Carta añadida exitosamente",
            "card_id": new_card_id,
            "card_data": card_data
        }), 201
        
    except Exception as e:
        return jsonify({"error": f"Error al añadir carta: {e}"}), 500

@app.route('/cards/batch-add-by-urls', methods=['POST'])
@require_api_key
def batch_add_cards_by_urls():
    """
    Añadir múltiples cartas a la base de datos usando URLs
    Espera JSON con: urls (array), user_wallet, pool_id (opcional)
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "JSON requerido"}), 400
        
        urls = data.get('urls', [])
        user_wallet = data.get('user_wallet')
        pool_id = data.get('pool_id')
        
        if not urls or not user_wallet:
            return jsonify({"error": "urls (array) y user_wallet son requeridos"}), 400
        
        if not isinstance(urls, list):
            return jsonify({"error": "urls debe ser un array"}), 400
        
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # Verificar si el usuario existe
        cur.execute("SELECT wallet_address FROM users WHERE wallet_address = %s;", (user_wallet,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"error": "Usuario no encontrado"}), 404
        
        # Verificar si el pool existe (si se proporcionó)
        if pool_id:
            cur.execute("SELECT id FROM card_pools WHERE id = %s;", (pool_id,))
            if not cur.fetchone():
                cur.close()
                conn.close()
                return jsonify({"error": "Pool no encontrado"}), 404
        
        added_cards = []
        failed_cards = []
        
        for url in urls:
            try:
                # Extraer datos de la carta
                card_data = extraer.extract_ungraded_card_data_by_link(url)
                
                if not card_data:
                    failed_cards.append({"url": url, "error": "No se pudieron extraer los datos"})
                    continue
                
                # Insertar en la base de datos
                cur.execute(
                    """
                    INSERT INTO cards (name, card_id, edition, user_wallet, url, market_value, pool_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (
                        card_data['name'],
                        card_data['card_id'],
                        card_data['edition'],
                        user_wallet,
                        card_data['url'],
                        card_data['market_value'],
                        pool_id
                    )
                )
                
                new_card_id = cur.fetchone()[0]
                
                # Si se especificó un pool, agregar a la tabla pool
                if pool_id:
                    cur.execute(
                        "INSERT INTO pool (card_id, added_by) VALUES (%s, %s);",
                        (new_card_id, user_wallet)
                    )
                
                added_cards.append({
                    "card_id": new_card_id,
                    "card_data": card_data
                })
                
            except Exception as e:
                failed_cards.append({"url": url, "error": str(e)})
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            "message": f"Procesadas {len(urls)} URLs. {len(added_cards)} cartas añadidas, {len(failed_cards)} fallaron.",
            "added_cards": added_cards,
            "failed_cards": failed_cards
        }), 201
        
    except Exception as e:
        return jsonify({"error": f"Error al añadir cartas: {e}"}), 500

# === ENDPOINTS PARA EL DASHBOARD ===

@app.route('/dashboard/pools', methods=['GET'])
@require_api_key
def get_dashboard_pools():
    """
    Obtener información de pools para el dashboard
    """
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # Obtener pools con estadísticas agregadas
        cur.execute("""
            SELECT 
                cp.id,
                cp.name,
                cp.description,
                cp.TCG,
                cp.created_at,
                COUNT(DISTINCT c.id) as total_cards,
                COUNT(DISTINCT c.user_wallet) as total_investors,
                COALESCE(SUM(c.market_value), 0) as total_value,
                COALESCE(AVG(c.market_value), 0) as avg_card_value
            FROM card_pools cp
            LEFT JOIN cards c ON cp.id = c.pool_id AND c.removed_at IS NULL
            GROUP BY cp.id, cp.name, cp.description, cp.TCG, cp.created_at
            ORDER BY cp.created_at DESC;
        """)
        
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        pools = []
        
        for row in rows:
            pool_data = dict(zip(columns, row))
            
            # Calcular días activos
            from datetime import datetime
            created_date = pool_data['created_at']
            if isinstance(created_date, str):
                created_date = datetime.fromisoformat(created_date.replace('Z', '+00:00'))
            days_active = (datetime.now() - created_date.replace(tzinfo=None)).days
            
            # Simular performance (esto puede ser calculado basado en datos históricos)
            import random
            performance_change = random.uniform(-5.0, 15.0)
            
            pools.append({
                "id": pool_data['id'],
                "name": pool_data['name'],
                "description": pool_data['description'],
                "tcg": pool_data['tcg'],
                "value": float(pool_data['total_value']),
                "total_cards": pool_data['total_cards'],
                "investors": pool_data['total_investors'],
                "daysActive": days_active,
                "performance": f"{performance_change:+.1f}%",
                "isPositive": performance_change > 0,
                "avgCardValue": float(pool_data['avg_card_value']),
                "gradient": f"from-blue-500 to-purple-600"  # Puedes personalizar esto
            })
        
        cur.close()
        conn.close()
        
        return jsonify(pools), 200
        
    except Exception as e:
        return jsonify({"error": f"Error al obtener pools para dashboard: {e}"}), 500

@app.route('/dashboard/user/<string:wallet_address>/summary', methods=['GET'])
@require_api_key
def get_user_dashboard_summary(wallet_address):
    """
    Obtener resumen del usuario para el dashboard
    """
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # Obtener inversiones del usuario por pool
        cur.execute("""
            SELECT 
                cp.id as pool_id,
                cp.name as pool_name,
                COUNT(c.id) as user_cards,
                COALESCE(SUM(c.market_value), 0) as user_investment,
                (
                    SELECT COALESCE(SUM(market_value), 0) 
                    FROM cards 
                    WHERE pool_id = cp.id AND removed_at IS NULL
                ) as total_pool_value
            FROM card_pools cp
            LEFT JOIN cards c ON cp.id = c.pool_id 
                AND c.user_wallet = %s 
                AND c.removed_at IS NULL
            GROUP BY cp.id, cp.name
            HAVING COUNT(c.id) > 0
            ORDER BY user_investment DESC;
        """, (wallet_address,))
        
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        user_pools = [dict(zip(columns, row)) for row in rows]
        
        # Calcular totales
        total_investment = sum(float(pool['user_investment']) for pool in user_pools)
        total_pool_value = sum(float(pool['total_pool_value']) for pool in user_pools)
        
        # Obtener total de cartas del usuario
        cur.execute("""
            SELECT COUNT(*) as total_cards
            FROM cards 
            WHERE user_wallet = %s AND removed_at IS NULL;
        """, (wallet_address,))
        
        total_cards = cur.fetchone()[0]
        
        cur.close()
        conn.close()
        
        return jsonify({
            "totalInvestment": total_investment,
            "totalPoolValue": total_pool_value,
            "totalCards": total_cards,
            "userPools": user_pools
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Error al obtener resumen del usuario: {e}"}), 500

@app.route('/pools', methods=['POST'])
@require_api_key
def create_pool():
    """
    Crear un nuevo pool de cartas
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "JSON requerido"}), 400
        
        name = data.get('name')
        description = data.get('description', '')
        tcg = data.get('tcg')
        created_by = data.get('created_by')
        
        if not name or not tcg or not created_by:
            return jsonify({"error": "name, tcg y created_by son requeridos"}), 400
        
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # Verificar si el usuario existe
        cur.execute("SELECT wallet_address FROM users WHERE wallet_address = %s;", (created_by,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"error": "Usuario no encontrado"}), 404
        
        # Insertar nuevo pool
        cur.execute(
            """
            INSERT INTO card_pools (name, description, TCG, created_by)
            VALUES (%s, %s, %s, %s)
            RETURNING id;
            """,
            (name, description, tcg, created_by)
        )
        
        new_pool_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            "message": "Pool creado exitosamente",
            "pool_id": new_pool_id
        }), 201
        
    except Exception as e:
        return jsonify({"error": f"Error al crear pool: {e}"}), 500

@app.route('/pools', methods=['GET'])
@require_api_key
def get_pools():
    """
    Obtener todos los pools
    """
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                cp.*,
                COUNT(c.id) as total_cards,
                COALESCE(SUM(c.market_value), 0) as total_value
            FROM card_pools cp
            LEFT JOIN cards c ON cp.id = c.pool_id AND c.removed_at IS NULL
            GROUP BY cp.id
            ORDER BY cp.created_at DESC;
        """)
        
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        pools = [dict(zip(columns, row)) for row in rows]
        
        cur.close()
        conn.close()
        
        return jsonify(pools), 200
        
    except Exception as e:
        return jsonify({"error": f"Error al obtener pools: {e}"}), 500

# Lista de wallets administrativas autorizadas desde variable de entorno
ADMIN_WALLETS_ENV = os.getenv('ADMIN_WALLETS', "")
if ADMIN_WALLETS_ENV:
    ADMIN_WALLETS = [wallet.strip() for wallet in ADMIN_WALLETS_ENV.split(',')]
else:
    # Wallets por defecto si no se especifica en .env
    ADMIN_WALLETS = [
        "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",  # Wallet admin principal
        "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",  # Wallet admin secundaria
    ]

print(f"Wallets administrativas autorizadas: {ADMIN_WALLETS}")

def require_admin_wallet(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Verificar API key primero
        api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
        if not api_key or api_key != API_SECRET_KEY:
            return jsonify({"error": "API key requerida o inválida"}), 401
        
        # Verificar wallet administrativa
        data = request.get_json()
        if not data:
            return jsonify({"error": "JSON requerido con wallet_address"}), 400
        
        admin_wallet = data.get('admin_wallet')
        if not admin_wallet or admin_wallet not in ADMIN_WALLETS:
            return jsonify({"error": "Wallet administrativa no autorizada"}), 403
        
        return f(*args, **kwargs)
    return decorated_function

# === ENDPOINTS ADMINISTRATIVOS PARA GESTIÓN DE CARTAS ===

@app.route('/cards_admin/add-by-url', methods=['POST'])
@require_admin_wallet
def admin_add_card_by_url():
    """
    [ADMIN] Añadir una nueva carta usando URL de pricecharting.com
    Espera JSON con: admin_wallet, url, user_wallet, pool_id (opcional)
    """
    try:
        data = request.get_json()
        
        url = data.get('url')
        user_wallet = data.get('user_wallet')
        pool_id = data.get('pool_id')
        admin_wallet = data.get('admin_wallet')
        
        if not url or not user_wallet:
            return jsonify({"error": "url y user_wallet son requeridos"}), 400
        
        # Extraer datos de la carta
        card_data = extraer.extract_ungraded_card_data_by_link(url)
        
        if not card_data:
            return jsonify({"error": "No se pudieron extraer los datos de la carta desde la URL"}), 400
        
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # Verificar si el usuario existe
        cur.execute("SELECT wallet_address FROM users WHERE wallet_address = %s;", (user_wallet,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"error": "Usuario no encontrado. Debe crear el usuario primero."}), 404
        
        # Verificar si el pool existe (si se proporcionó)
        if pool_id:
            cur.execute("SELECT id FROM card_pools WHERE id = %s;", (pool_id,))
            if not cur.fetchone():
                cur.close()
                conn.close()
                return jsonify({"error": "Pool no encontrado"}), 404
        
        # Insertar la carta
        cur.execute(
            """
            INSERT INTO cards (name, card_id, edition, user_wallet, url, market_value, pool_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (
                card_data['name'],
                card_data['card_id'],
                card_data['edition'],
                user_wallet,
                card_data['url'],
                card_data['market_value'],
                pool_id
            )
        )
        
        new_card_id = cur.fetchone()[0]
        conn.commit()
        
        # Si se especificó un pool, agregar a la tabla pool
        if pool_id:
            cur.execute(
                "INSERT INTO pool (card_id, added_by) VALUES (%s, %s);",
                (new_card_id, admin_wallet)
            )
            conn.commit()
        
        cur.close()
        conn.close()
        
        return jsonify({
            "message": "Carta añadida exitosamente por administrador",
            "card_id": new_card_id,
            "card_data": card_data,
            "admin_action": f"Añadida por {admin_wallet}"
        }), 201
        
    except Exception as e:
        return jsonify({"error": f"Error al añadir carta: {e}"}), 500

@app.route('/cards_admin/add-manual', methods=['POST'])
@require_admin_wallet
def admin_add_card_manual():
    """
    [ADMIN] Añadir carta manualmente especificando todos los datos
    Espera JSON con: admin_wallet, name, card_id, edition, user_wallet, market_value, url (opcional), pool_id (opcional)
    """
    try:
        data = request.get_json()
        
        name = data.get('name')
        card_id = data.get('card_id')
        edition = data.get('edition')
        user_wallet = data.get('user_wallet')
        market_value = data.get('market_value')
        url = data.get('url')
        pool_id = data.get('pool_id')
        admin_wallet = data.get('admin_wallet')
        
        if not all([name, card_id, edition, user_wallet]):
            return jsonify({"error": "name, card_id, edition y user_wallet son requeridos"}), 400
        
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # Verificar si el usuario existe
        cur.execute("SELECT wallet_address FROM users WHERE wallet_address = %s;", (user_wallet,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"error": "Usuario no encontrado"}), 404
        
        # Verificar si el pool existe (si se proporcionó)
        if pool_id:
            cur.execute("SELECT id FROM card_pools WHERE id = %s;", (pool_id,))
            if not cur.fetchone():
                cur.close()
                conn.close()
                return jsonify({"error": "Pool no encontrado"}), 404
        
        # Insertar la carta
        cur.execute(
            """
            INSERT INTO cards (name, card_id, edition, user_wallet, url, market_value, pool_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (name, card_id, edition, user_wallet, url, market_value, pool_id)
        )
        
        new_card_id = cur.fetchone()[0]
        conn.commit()
        
        # Si se especificó un pool, agregar a la tabla pool
        if pool_id:
            cur.execute(
                "INSERT INTO pool (card_id, added_by) VALUES (%s, %s);",
                (new_card_id, admin_wallet)
            )
            conn.commit()
        
        cur.close()
        conn.close()
        
        return jsonify({
            "message": "Carta añadida manualmente por administrador",
            "card_id": new_card_id,
            "admin_action": f"Añadida manualmente por {admin_wallet}"
        }), 201
        
    except Exception as e:
        return jsonify({"error": f"Error al añadir carta manualmente: {e}"}), 500

@app.route('/cards_admin/edit/<int:card_id>', methods=['PUT'])
@require_admin_wallet
def admin_edit_card(card_id):
    """
    [ADMIN] Editar una carta existente
    Espera JSON con: admin_wallet y los campos a modificar
    """
    try:
        data = request.get_json()
        admin_wallet = data.get('admin_wallet')
        
        # Campos editables
        name = data.get('name')
        card_id_value = data.get('card_id')
        edition = data.get('edition')
        market_value = data.get('market_value')
        url = data.get('url')
        user_wallet = data.get('user_wallet')
        pool_id = data.get('pool_id')
        
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # Verificar que la carta existe
        cur.execute("SELECT id FROM cards WHERE id = %s;", (card_id,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"error": "Carta no encontrada"}), 404
        
        # Construir consulta de actualización dinámicamente
        update_fields = []
        update_values = []
        
        if name is not None:
            update_fields.append("name = %s")
            update_values.append(name)
        
        if card_id_value is not None:
            update_fields.append("card_id = %s")
            update_values.append(card_id_value)
        
        if edition is not None:
            update_fields.append("edition = %s")
            update_values.append(edition)
        
        if market_value is not None:
            update_fields.append("market_value = %s")
            update_values.append(market_value)
        
        if url is not None:
            update_fields.append("url = %s")
            update_values.append(url)
        
        if user_wallet is not None:
            # Verificar que el nuevo usuario existe
            cur.execute("SELECT wallet_address FROM users WHERE wallet_address = %s;", (user_wallet,))
            if not cur.fetchone():
                cur.close()
                conn.close()
                return jsonify({"error": "Nuevo usuario no encontrado"}), 404
            update_fields.append("user_wallet = %s")
            update_values.append(user_wallet)
        
        if pool_id is not None:
            if pool_id == "":  # Remover de pool
                update_fields.append("pool_id = NULL")
            else:
                # Verificar que el pool existe
                cur.execute("SELECT id FROM card_pools WHERE id = %s;", (pool_id,))
                if not cur.fetchone():
                    cur.close()
                    conn.close()
                    return jsonify({"error": "Pool no encontrado"}), 404
                update_fields.append("pool_id = %s")
                update_values.append(pool_id)
        
        if not update_fields:
            return jsonify({"error": "No hay campos para actualizar"}), 400
        
        # Ejecutar actualización
        update_values.append(card_id)
        query = f"UPDATE cards SET {', '.join(update_fields)} WHERE id = %s;"
        cur.execute(query, update_values)
        conn.commit();
        
        cur.close()
        conn.close()
        
        return jsonify({
            "message": "Carta actualizada exitosamente",
            "card_id": card_id,
            "admin_action": f"Editada por {admin_wallet}"
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Error al editar carta: {e}"}), 500

@app.route('/cards_admin/remove/<int:card_id>', methods=['DELETE'])
@require_admin_wallet
def admin_remove_card(card_id):
    """
    [ADMIN] Marcar carta como removida (soft delete)
    Espera JSON con: admin_wallet
    """
    try:
        data = request.get_json()
        admin_wallet = data.get('admin_wallet')
        
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # Verificar que la carta existe y no está ya removida
        cur.execute("SELECT id, removed_at FROM cards WHERE id = %s;", (card_id,))
        card_info = cur.fetchone()
        
        if not card_info:
            cur.close()
            conn.close()
            return jsonify({"error": "Carta no encontrada"}), 404
        
        if card_info[1] is not None:  # Ya está removida
            cur.close()
            conn.close()
            return jsonify({"error": "La carta ya está marcada como removida"}), 400
        
        # Marcar como removida
        from datetime import datetime
        cur.execute(
            "UPDATE cards SET removed_at = %s WHERE id = %s;",
            (datetime.now(), card_id)
        )
        
        # También marcar en la tabla pool si existe
        cur.execute(
            "UPDATE pool SET removed_at = %s WHERE card_id = %s AND removed_at IS NULL;",
            (datetime.now(), card_id)
        )
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            "message": "Carta marcada como removida exitosamente",
            "card_id": card_id,
            "admin_action": f"Removida por {admin_wallet}"
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Error al remover carta: {e}"}), 500

@app.route('/cards_admin/restore/<int:card_id>', methods=['PUT'])
@require_admin_wallet
def admin_restore_card(card_id):
    """
    [ADMIN] Restaurar carta removida
    Espera JSON con: admin_wallet
    """
    try:
        data = request.get_json()
        admin_wallet = data.get('admin_wallet')
        
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # Verificar que la carta existe y está removida
        cur.execute("SELECT id, removed_at FROM cards WHERE id = %s;", (card_id,))
        card_info = cur.fetchone()
        
        if not card_info:
            cur.close()
            conn.close()
            return jsonify({"error": "Carta no encontrada"}), 404
        
        if card_info[1] is None:  # No está removida
            cur.close()
            conn.close()
            return jsonify({"error": "La carta no está marcada como removida"}), 400
        
        # Restaurar carta
        cur.execute(
            "UPDATE cards SET removed_at = NULL WHERE id = %s;",
            (card_id,)
        )
        
        # También restaurar en la tabla pool si existe
        cur.execute(
            "UPDATE pool SET removed_at = NULL WHERE card_id = %s;",
            (card_id,)
        )
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            "message": "Carta restaurada exitosamente",
            "card_id": card_id,
            "admin_action": f"Restaurada por {admin_wallet}"
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Error al restaurar carta: {e}"}), 500

@app.route('/cards_admin/delete-permanent/<int:card_id>', methods=['DELETE'])
@require_admin_wallet
def admin_delete_card_permanent(card_id):
    """
    [ADMIN] Eliminar carta permanentemente de la base de datos
    ADVERTENCIA: Esta acción es irreversible
    Espera JSON con: admin_wallet, confirm: true
    """
    try:
        data = request.get_json()
        admin_wallet = data.get('admin_wallet')
        confirm = data.get('confirm')
        
        if not confirm:
            return jsonify({"error": "Debe confirmar la eliminación permanente con 'confirm: true'"}), 400
        
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # Verificar que la carta existe
        cur.execute("SELECT id FROM cards WHERE id = %s;", (card_id,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"error": "Carta no encontrada"}), 404
        
        # Eliminar de la tabla pool primero (clave foránea)
        cur.execute("DELETE FROM pool WHERE card_id = %s;", (card_id,))
        
        # Eliminar transacciones relacionadas
        cur.execute("DELETE FROM transactions WHERE card_id = %s;", (card_id,))
        
        # Eliminar la carta
        cur.execute("DELETE FROM cards WHERE id = %s;", (card_id,))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            "message": "Carta eliminada permanentemente",
            "card_id": card_id,
            "admin_action": f"ELIMINACIÓN PERMANENTE por {admin_wallet}",
            "warning": "Esta acción es irreversible"
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Error al eliminar carta permanentemente: {e}"}), 500

@app.route('/cards_admin/move-to-pool', methods=['PUT'])
@require_admin_wallet
def admin_move_card_to_pool():
    """
    [ADMIN] Mover carta(s) a un pool diferente
    Espera JSON con: admin_wallet, card_ids (array), new_pool_id
    """
    try:
        data = request.get_json()
        admin_wallet = data.get('admin_wallet')
        card_ids = data.get('card_ids', [])
        new_pool_id = data.get('new_pool_id')
        
        if not card_ids or not isinstance(card_ids, list):
            return jsonify({"error": "card_ids debe ser un array con al menos un ID"}), 400
        
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # Verificar que el nuevo pool existe (si no es None)
        if new_pool_id is not None:
            cur.execute("SELECT id FROM card_pools WHERE id = %s;", (new_pool_id,))
            if not cur.fetchone():
                cur.close()
                conn.close()
                return jsonify({"error": "Nuevo pool no encontrado"}), 404
        
        moved_cards = []
        failed_cards = []
        
        for card_id in card_ids:
            try:
                # Verificar que la carta existe
                cur.execute("SELECT id, pool_id FROM cards WHERE id = %s;", (card_id,))
                card_info = cur.fetchone()
                
                if not card_info:
                    failed_cards.append({"card_id": card_id, "error": "Carta no encontrada"})
                    continue
                
                old_pool_id = card_info[1]
                
                # Actualizar pool_id en la tabla cards
                cur.execute(
                    "UPDATE cards SET pool_id = %s WHERE id = %s;",
                    (new_pool_id, card_id)
                )
                
                # Manejar tabla pool
                if old_pool_id is not None:
                    # Marcar como removida de pool anterior
                    cur.execute(
                        "UPDATE pool SET removed_at = NOW() WHERE card_id = %s AND removed_at IS NULL;",
                        (card_id,)
                    )
                
                if new_pool_id is not None:
                    # Agregar al nuevo pool
                    cur.execute(
                        "INSERT INTO pool (card_id, added_by) VALUES (%s, %s);",
                        (card_id, admin_wallet)
                    )
                
                moved_cards.append({
                    "card_id": card_id,
                    "old_pool_id": old_pool_id,
                    "new_pool_id": new_pool_id
                })
                
            except Exception as e:
                failed_cards.append({"card_id": card_id, "error": str(e)})
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            "message": f"{len(moved_cards)} cartas movidas exitosamente",
            "moved_cards": moved_cards,
            "failed_cards": failed_cards,
            "admin_action": f"Movidas por {admin_wallet}"
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Error al mover cartas: {e}"}), 500

@app.route('/cards_admin/batch-update-prices', methods=['PUT'])
@require_admin_wallet
def admin_batch_update_prices():
    """
    [ADMIN] Actualizar precios de cartas específicas o todas
    Espera JSON con: admin_wallet, card_ids (opcional, si no se proporciona actualiza todas)
    """
    try:
        data = request.get_json()
        admin_wallet = data.get('admin_wallet')
        card_ids = data.get('card_ids')  # Opcional
        
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # Construir consulta según si se especificaron IDs
        if card_ids and isinstance(card_ids, list):
            placeholders = ','.join(['%s'] * len(card_ids))
            query = f"SELECT id, edition, name, card_id FROM cards WHERE id IN ({placeholders}) AND removed_at IS NULL;"
            cur.execute(query, card_ids)
        else:
            cur.execute("SELECT id, edition, name, card_id FROM cards WHERE removed_at IS NULL;")
        
        cards = cur.fetchall()
        updated = 0
        not_updated = []
        
        for card in cards:
            card_db_id, edition, name, card_number = card
            
            try:
                # Usar la función que construye la URL a partir de propiedades
                card_data = extraer.extract_ungraded_card_data(edition, name, card_number)
                
                if card_data and card_data["market_value"] is not None:
                    cur.execute(
                        "UPDATE cards SET market_value = %s WHERE id = %s;",
                        (card_data["market_value"], card_db_id)
                    )
                    updated += 1
                else:
                    not_updated.append({
                        "card_id": card_db_id,
                        "error": "No se pudo obtener precio actualizado"
                    })
            except Exception as e:
                not_updated.append({
                    "card_id": card_db_id,
                    "error": str(e)
                })
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            "message": f"Actualización completada por administrador",
            "updated": updated,
            "not_updated": len(not_updated),
            "details": not_updated,
            "admin_action": f"Precios actualizados por {admin_wallet}"
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Error al actualizar precios: {e}"}), 500
