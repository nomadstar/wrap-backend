from flask import Flask, request, jsonify
from flask_cors import CORS
import urllib.parse
import os
import psycopg2
import extraer
from functools import wraps
import sys

# Importar nuestros módulos personalizados
from db_utils import get_db_connection
from services import UserService, CardService, PoolService, DashboardService, AdminService

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
        
        # Leer el archivo de migración
        migration_path = os.path.join(os.path.dirname(__file__), '02_migration.sql')
        migration_script = ""
        try:
            with open(migration_path, 'r', encoding='utf-8') as f:
                migration_script = f.read()
        except FileNotFoundError:
            print("Advertencia: Archivo de migración 02_migration.sql no encontrado")
        
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
        
        # Ejecutar el script SQL principal
        cur = conn.cursor()
        cur.execute(sql_script)
        conn.commit()
        print("✅ Script principal 01_init.sql ejecutado")
        
        # Ejecutar migración si existe
        if migration_script:
            cur.execute(migration_script)
            conn.commit()
            print("✅ Script de migración 02_migration.sql ejecutado")
        
        cur.close()
        conn.close()
        
        print("Base de datos inicializada correctamente - Tablas creadas/migradas si no existían")
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
    
    # Prueba de conexión a la base de datos usando nuestra utilidad
    conn_test = get_db_connection()
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
        
        result = UserService.create_user(wallet_address, wallet_type, username, email)
        return jsonify(result), 201
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return jsonify({"error": f"Error al crear usuario: {e}"}), 500
@app.route('/users/<string:wallet_address>', methods=['GET'])
@require_api_key
def get_user(wallet_address):
    """
    Obtener los datos de un usuario según su wallet_address
    """
    try:
        user = UserService.get_user(wallet_address)
        return jsonify(user), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
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
                "/admin/check/<wallet_address>": "[ADMIN] Verificar status de administrador (GET)",
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
        cards = CardService.get_all_cards()
        return jsonify(cards), 200
    except Exception as e:
        return jsonify({"error": f"Error al obtener las cartas: {e}"}), 500

@app.route('/cards/<int:card_id>', methods=['GET'])
@require_api_key
def get_card(card_id):
    try:
        card = CardService.get_card_by_id(card_id)
        return jsonify(card), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Error al obtener la carta: {e}"}), 500

@app.route('/total_value', methods=['GET'])
@require_api_key
def get_total_value():
    try:
        total = CardService.get_total_collection_value()
        return jsonify({"total_collection_value": total}), 200
    except Exception as e:
        return jsonify({"error": f"Error al calcular el valor total: {e}"}), 500
    
@app.route('/update_prices', methods=['POST'])
@require_api_key
def update_prices_endpoint():
    try:
        result = CardService.update_card_prices()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": f"Error general al actualizar precios: {e}"}), 500
    
@app.route('/users/<string:wallet_address>/cards', methods=['GET'])
@require_api_key
def get_user_cards(wallet_address):
    """
    Retorna todas las cartas asociadas a una dirección de billetera específica.
    """
    try:
        cards = CardService.get_user_cards(wallet_address)
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
        pool_id = data.get('pool_id')
        
        if not url or not user_wallet:
            return jsonify({"error": "url y user_wallet son requeridos"}), 400
        
        result = CardService.add_card_by_url(url, user_wallet, pool_id)
        return jsonify(result), 201
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
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
        
        result = CardService.batch_add_cards_by_urls(urls, user_wallet, pool_id)
        return jsonify(result), 201
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
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
        pools = PoolService.get_dashboard_pools()
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
        summary = DashboardService.get_user_summary(wallet_address)
        return jsonify(summary), 200
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
        
        result = PoolService.create_pool(name, description, tcg, created_by)
        return jsonify(result), 201
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Error al crear pool: {e}"}), 500

@app.route('/pools', methods=['GET'])
@require_api_key
def get_pools():
    """
    Obtener todos los pools
    """
    try:
        pools = PoolService.get_all_pools()
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

# === ENDPOINT PARA VERIFICACIÓN DE ADMINISTRADOR ===

@app.route('/admin/check/<string:wallet_address>', methods=['GET'])
def check_admin_status(wallet_address):
    """
    Verificar si una wallet tiene permisos de administrador
    """
    try:
        # Verificar API key
        api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
        if not api_key or api_key != API_SECRET_KEY:
            return jsonify({"error": "API key requerida o inválida"}), 401
        
        result = AdminService.check_admin_status(wallet_address, ADMIN_WALLETS)
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({"error": f"Error al verificar status de admin: {e}"}), 500

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
        
        result = AdminService.add_card_by_url_admin(url, user_wallet, pool_id, admin_wallet)
        return jsonify(result), 201
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
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
        
        result = AdminService.add_card_manual_admin(
            name, card_id, edition, user_wallet, market_value, admin_wallet, url, pool_id
        )
        return jsonify(result), 201
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Error al añadir carta manualmente: {e}"}), 500

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
        
        result = AdminService.remove_card_admin(card_id, admin_wallet)
        return jsonify(result), 200
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
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
        
        result = AdminService.restore_card_admin(card_id, admin_wallet)
        return jsonify(result), 200
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
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
        
        result = AdminService.delete_card_permanent_admin(card_id, admin_wallet, confirm)
        return jsonify(result), 200
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
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
        
        result = AdminService.move_cards_to_pool_admin(card_ids, new_pool_id, admin_wallet)
        return jsonify(result), 200
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
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

# === ENDPOINTS PARA CONTRATOS INTELIGENTES ===

@app.route('/contracts/wrap-pools', methods=['GET'])
@require_api_key
def get_wrap_pools():
    """
    Obtener todos los contratos WrapPool
    """
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT wp.*, 
                   COUNT(DISTINCT ws.contract_address) as total_wrapsells,
                   COALESCE(SUM(ws.total_cards_deposited), 0) as total_cards
            FROM wrap_pools wp
            LEFT JOIN wrap_sells ws ON wp.contract_address = ws.wrap_pool_address
            GROUP BY wp.id, wp.contract_address, wp.name, wp.symbol, wp.owner_wallet,
                     wp.collateralization_ratio, wp.total_supply, wp.total_collateral_value,
                     wp.is_healthy, wp.created_at, wp.updated_at
            ORDER BY wp.created_at DESC;
        """)
        
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        pools = [dict(zip(columns, row)) for row in rows]
        
        cur.close()
        conn.close()
        
        return jsonify(pools), 200
        
    except Exception as e:
        return jsonify({"error": f"Error al obtener WrapPools: {e}"}), 500

@app.route('/contracts/wrap-pools', methods=['POST'])
@require_api_key
def create_wrap_pool():
    """
    Registrar un nuevo contrato WrapPool en la base de datos
    Espera: contract_address, name, symbol, owner_wallet, collateralization_ratio
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "JSON requerido"}), 400
        
        contract_address = data.get('contract_address')
        name = data.get('name')
        symbol = data.get('symbol')
        owner_wallet = data.get('owner_wallet')
        collateralization_ratio = data.get('collateralization_ratio', 150)
        
        if not all([contract_address, name, symbol, owner_wallet]):
            return jsonify({"error": "contract_address, name, symbol y owner_wallet son requeridos"}), 400
        
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # Verificar que el owner existe
        cur.execute("SELECT wallet_address FROM users WHERE wallet_address = %s;", (owner_wallet,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"error": "Owner wallet no encontrada"}), 404
        
        # Insertar WrapPool
        cur.execute("""
            INSERT INTO wrap_pools (contract_address, name, symbol, owner_wallet, collateralization_ratio)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id;
        """, (contract_address, name, symbol, owner_wallet, collateralization_ratio))
        
        pool_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            "message": "WrapPool registrado exitosamente",
            "pool_id": pool_id,
            "contract_address": contract_address
        }), 201
        
    except Exception as e:
        return jsonify({"error": f"Error al crear WrapPool: {e}"}), 500

@app.route('/contracts/wrap-sells', methods=['GET'])
@require_api_key
def get_wrap_sells():
    """
    Obtener todos los contratos WrapSell
    """
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT ws.*, wp.name as pool_name, wp.symbol as pool_symbol
            FROM wrap_sells ws
            LEFT JOIN wrap_pools wp ON ws.wrap_pool_address = wp.contract_address
            ORDER BY ws.created_at DESC;
        """)
        
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        sells = [dict(zip(columns, row)) for row in rows]
        
        cur.close()
        conn.close()
        
        return jsonify(sells), 200
        
    except Exception as e:
        return jsonify({"error": f"Error al obtener WrapSells: {e}"}), 500

@app.route('/contracts/wrap-sells', methods=['POST'])
@require_api_key
def create_wrap_sell():
    """
    Registrar un nuevo contrato WrapSell en la base de datos
    Espera: contract_address, name, symbol, card_id, card_name, rarity, 
            estimated_value_per_card, owner_wallet, wrap_pool_address
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "JSON requerido"}), 400
        
        required_fields = ['contract_address', 'name', 'symbol', 'card_id', 'card_name', 
                          'rarity', 'estimated_value_per_card', 'owner_wallet']
        
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"{field} es requerido"}), 400
        
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # Verificar que el owner existe
        cur.execute("SELECT wallet_address FROM users WHERE wallet_address = %s;", (data['owner_wallet'],))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"error": "Owner wallet no encontrada"}), 404
        
        # Verificar que el wrap_pool existe (si se proporciona)
        wrap_pool_address = data.get('wrap_pool_address')
        if wrap_pool_address:
            cur.execute("SELECT contract_address FROM wrap_pools WHERE contract_address = %s;", (wrap_pool_address,))
            if not cur.fetchone():
                cur.close()
                conn.close()
                return jsonify({"error": "WrapPool no encontrado"}), 404
        
        # Insertar WrapSell
        cur.execute("""
            INSERT INTO wrap_sells (contract_address, name, symbol, card_id, card_name, rarity,
                                   estimated_value_per_card, owner_wallet, wrap_pool_address)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """, (
            data['contract_address'], data['name'], data['symbol'], data['card_id'],
            data['card_name'], data['rarity'], data['estimated_value_per_card'],
            data['owner_wallet'], wrap_pool_address
        ))
        
        sell_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            "message": "WrapSell registrado exitosamente",
            "sell_id": sell_id,
            "contract_address": data['contract_address']
        }), 201
        
    except Exception as e:
        return jsonify({"error": f"Error al crear WrapSell: {e}"}), 500

@app.route('/contracts/wrap-pools/<string:contract_address>/summary', methods=['GET'])
@require_api_key
def get_wrap_pool_summary(contract_address):
    """
    Obtener resumen detallado de un WrapPool específico
    """
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # Información básica del pool
        cur.execute("SELECT * FROM wrap_pools WHERE contract_address = %s;", (contract_address,))
        pool_data = cur.fetchone()
        
        if not pool_data:
            cur.close()
            conn.close()
            return jsonify({"error": "WrapPool no encontrado"}), 404
        
        pool_columns = [desc[0] for desc in cur.description]
        pool_info = dict(zip(pool_columns, pool_data))
        
        # WrapSells asociados
        cur.execute("""
            SELECT ws.*, COUNT(cd.user_wallet) as total_depositors,
                   COALESCE(SUM(cd.cards_deposited), 0) as total_cards_deposited,
                   COALESCE(SUM(cd.tokens_received), 0) as total_tokens_issued
            FROM wrap_sells ws
            LEFT JOIN card_deposits cd ON ws.contract_address = cd.wrap_sell_address
            WHERE ws.wrap_pool_address = %s
            GROUP BY ws.id, ws.contract_address, ws.name, ws.symbol, ws.card_id,
                     ws.card_name, ws.rarity, ws.estimated_value_per_card,
                     ws.owner_wallet, ws.wrap_pool_address, ws.total_supply,
                     ws.total_cards_deposited, ws.total_tokens_issued,
                     ws.created_at, ws.updated_at;
        """, (contract_address,))
        
        wrapsells_data = cur.fetchall()
        wrapsells_columns = [desc[0] for desc in cur.description]
        wrapsells = [dict(zip(wrapsells_columns, row)) for row in wrapsells_data]
        
        # Transacciones recientes
        cur.execute("""
            SELECT st.* FROM stablecoin_transactions st
            WHERE st.wrap_pool_address = %s
            ORDER BY st.transaction_date DESC
            LIMIT 10;
        """, (contract_address,))
        
        transactions_data = cur.fetchall()
        transactions_columns = [desc[0] for desc in cur.description]
        recent_transactions = [dict(zip(transactions_columns, row)) for row in transactions_data]
        
        cur.close()
        conn.close()
        
        return jsonify({
            "pool_info": pool_info,
            "wrapsells": wrapsells,
            "recent_transactions": recent_transactions,
            "summary": {
                "total_wrapsells": len(wrapsells),
                "total_unique_cards": len(set(ws['card_name'] for ws in wrapsells)),
                "total_depositors": sum(ws['total_depositors'] for ws in wrapsells),
                "total_cards_in_system": sum(ws['total_cards_deposited'] for ws in wrapsells)
            }
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Error al obtener resumen del WrapPool: {e}"}), 500

@app.route('/contracts/user/<string:wallet_address>/positions', methods=['GET'])
@require_api_key
def get_user_contract_positions(wallet_address):
    """
    Obtener todas las posiciones de un usuario en contratos (depósitos, tokens, etc)
    """
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # Depósitos en WrapSells
        cur.execute("""
            SELECT cd.*, ws.name, ws.symbol, ws.card_name, wp.name as pool_name
            FROM card_deposits cd
            JOIN wrap_sells ws ON cd.wrap_sell_address = ws.contract_address
            LEFT JOIN wrap_pools wp ON ws.wrap_pool_address = wp.contract_address
            WHERE cd.user_wallet = %s
            ORDER BY cd.created_at DESC;
        """, (wallet_address,))
        
        deposits_data = cur.fetchall()
        deposits_columns = [desc[0] for desc in cur.description]
        card_deposits = [dict(zip(deposits_columns, row)) for row in deposits_data]
        
        # Transacciones de stablecoins
        cur.execute("""
            SELECT st.*, wp.name, wp.symbol
            FROM stablecoin_transactions st
            JOIN wrap_pools wp ON st.wrap_pool_address = wp.contract_address
            WHERE st.user_wallet = %s
            ORDER BY st.transaction_date DESC
            LIMIT 20;
        """, (wallet_address,))
        
        stablecoin_data = cur.fetchall()
        stablecoin_columns = [desc[0] for desc in cur.description]
        stablecoin_transactions = [dict(zip(stablecoin_columns, row)) for row in stablecoin_data]
        
        cur.close()
        conn.close()
        
        return jsonify({
            "card_deposits": card_deposits,
            "stablecoin_transactions": stablecoin_transactions,
            "summary": {
                "total_deposits": len(card_deposits),
                "total_cards_deposited": sum(cd['cards_deposited'] for cd in card_deposits),
                "total_tokens_received": sum(cd['tokens_received'] for cd in card_deposits),
                "unique_contracts": len(set(cd['wrap_sell_address'] for cd in card_deposits))
            }
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Error al obtener posiciones del usuario: {e}"}), 500

# === ENDPOINTS PARA DESPLIEGUE DE CONTRATOS ===

try:
    from contract_deployer import ContractDeployer
    contract_deployer = ContractDeployer()
    CONTRACTS_ENABLED = True
    print("✅ Módulo de despliegue de contratos cargado")
except Exception as e:
    CONTRACTS_ENABLED = False
    print(f"⚠️  Módulo de contratos no disponible: {e}")

@app.route('/contracts/deploy/pending', methods=['POST'])
@require_admin_wallet
def deploy_pending_contracts():
    """
    [ADMIN] Desplegar contratos pendientes basándose en la base de datos
    Espera JSON con: admin_wallet
    """
    if not CONTRACTS_ENABLED:
        return jsonify({"error": "Módulo de contratos no disponible. Instale web3, eth-account y py-solc-x"}), 503
    
    try:
        data = request.get_json()
        admin_wallet = data.get('admin_wallet')
        
        # Ejecutar despliegue de contratos pendientes
        results = contract_deployer.deploy_pending_contracts()
        
        return jsonify({
            "message": "Proceso de despliegue completado",
            "results": results,
            "admin_action": f"Despliegue ejecutado por {admin_wallet}"
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Error en el despliegue de contratos: {e}"}), 500

@app.route('/contracts/deploy/wrapsell', methods=['POST'])
@require_admin_wallet
def deploy_single_wrapsell():
    """
    [ADMIN] Desplegar un contrato WrapSell específico
    Espera JSON con: admin_wallet, card_id (ID de la carta en la base de datos)
    """
    if not CONTRACTS_ENABLED:
        return jsonify({"error": "Módulo de contratos no disponible"}), 503
    
    try:
        data = request.get_json()
        admin_wallet = data.get('admin_wallet')
        card_id = data.get('card_id')
        
        if not card_id:
            return jsonify({"error": "card_id es requerido"}), 400
        
        # Obtener datos de la carta
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, name, card_id, edition, market_value, user_wallet, pool_id
            FROM cards 
            WHERE id = %s AND removed_at IS NULL AND wrap_sell_address IS NULL
        """, (card_id,))
        
        card_data = cur.fetchone()
        cur.close()
        conn.close()
        
        if not card_data:
            return jsonify({"error": "Carta no encontrada o ya tiene contrato desplegado"}), 404
        
        # Convertir a diccionario
        card_dict = {
            'id': card_data[0],
            'name': card_data[1],
            'card_id': card_data[2],
            'edition': card_data[3],
            'market_value': float(card_data[4]) if card_data[4] else 0.01,
            'user_wallet': card_data[5],
            'pool_id': card_data[6]
        }
        
        # Desplegar contrato
        contract_address = contract_deployer.deploy_wrapsell_contract(card_dict)
        contract_deployer.update_card_contract_address(card_id, contract_address)
        
        return jsonify({
            "message": "WrapSell desplegado exitosamente",
            "card_id": card_id,
            "card_name": card_dict['name'],
            "contract_address": contract_address,
            "admin_action": f"Desplegado por {admin_wallet}"
        }), 201
        
    except Exception as e:
        return jsonify({"error": f"Error al desplegar WrapSell: {e}"}), 500

@app.route('/contracts/deploy/wrappool', methods=['POST'])
@require_admin_wallet
def deploy_single_wrappool():
    """
    [ADMIN] Desplegar un contrato WrapPool específico
    Espera JSON con: admin_wallet, pool_id (ID del pool en la base de datos)
    """
    if not CONTRACTS_ENABLED:
        return jsonify({"error": "Módulo de contratos no disponible"}), 503
    
    try:
        data = request.get_json()
        admin_wallet = data.get('admin_wallet')
        pool_id = data.get('pool_id')
        
        if not pool_id:
            return jsonify({"error": "pool_id es requerido"}), 400
        
        # Obtener datos del pool
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, name, description, TCG, created_by
            FROM card_pools 
            WHERE id = %s AND wrap_pool_address IS NULL
        """, (pool_id,))
        
        pool_data = cur.fetchone()
        cur.close()
        conn.close()
        
        if not pool_data:
            return jsonify({"error": "Pool no encontrado o ya tiene contrato desplegado"}), 404
        
        # Convertir a diccionario
        pool_dict = {
            'id': pool_data[0],
            'name': pool_data[1],
            'description': pool_data[2],
            'tcg': pool_data[3],
            'created_by': pool_data[4],
            'symbol': f"{pool_data[1][:3].upper()}USD"
        }
        
        # Desplegar contrato
        contract_address = contract_deployer.deploy_wrappool_contract(pool_dict)
        contract_deployer.update_pool_contract_address(pool_id, contract_address)
        
        return jsonify({
            "message": "WrapPool desplegado exitosamente",
            "pool_id": pool_id,
            "pool_name": pool_dict['name'],
            "contract_address": contract_address,
            "admin_action": f"Desplegado por {admin_wallet}"
        }), 201
        
    except Exception as e:
        return jsonify({"error": f"Error al desplegar WrapPool: {e}"}), 500

@app.route('/contracts/pending-deployments', methods=['GET'])
@require_api_key
def get_pending_deployments():
    """
    Obtener lista de cartas y pools que necesitan contratos desplegados
    """
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # Cartas sin contratos
        cur.execute("""
            SELECT c.id, c.name, c.card_id, c.edition, c.market_value, c.user_wallet, c.pool_id,
                   cp.name as pool_name
            FROM cards c
            LEFT JOIN card_pools cp ON c.pool_id = cp.id
            WHERE c.wrap_sell_address IS NULL 
            AND c.removed_at IS NULL
            AND c.market_value > 0
            ORDER BY c.market_value DESC
            LIMIT 50;
        """)
        
        pending_cards_data = cur.fetchall()
        pending_cards_columns = [desc[0] for desc in cur.description]
        pending_cards = [dict(zip(pending_cards_columns, row)) for row in pending_cards_data]
        
        # Pools sin contratos
        cur.execute("""
            SELECT cp.id, cp.name, cp.description, cp.TCG, cp.created_by,
                   COUNT(c.id) as total_cards,
                   COALESCE(SUM(c.market_value), 0) as total_value
            FROM card_pools cp
            LEFT JOIN cards c ON cp.id = c.pool_id AND c.removed_at IS NULL
            WHERE cp.wrap_pool_address IS NULL
            GROUP BY cp.id, cp.name, cp.description, cp.TCG, cp.created_by
            ORDER BY total_value DESC;
        """)
        
        pending_pools_data = cur.fetchall()
        pending_pools_columns = [desc[0] for desc in cur.description]
        pending_pools = [dict(zip(pending_pools_columns, row)) for row in pending_pools_data]
        
        cur.close()
        conn.close()
        
        return jsonify({
            "pending_cards": pending_cards,
            "pending_pools": pending_pools,
            "summary": {
                "total_pending_cards": len(pending_cards),
                "total_pending_pools": len(pending_pools),
                "estimated_total_value": sum(float(card['market_value'] or 0) for card in pending_cards),
                "contracts_module_available": CONTRACTS_ENABLED
            }
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Error al obtener despliegues pendientes: {e}"}), 500

@app.route('/contracts/deployment-config', methods=['GET'])
@require_api_key
def get_deployment_config():
    """
    Obtener configuración actual para el despliegue de contratos
    """
    if not CONTRACTS_ENABLED:
        return jsonify({
            "contracts_enabled": False,
            "error": "Módulo de contratos no disponible"
        }), 200
    
    try:
        # Verificar configuración
        config = {
            "contracts_enabled": True,
            "web3_connected": contract_deployer.w3.is_connected() if contract_deployer.w3 else False,
            "account_configured": contract_deployer.account is not None,
            "account_address": contract_deployer.account.address if contract_deployer.account else None,
            "chain_id": contract_deployer.chain_id,
            "rpc_url": os.getenv('RPC_URL', 'http://localhost:8545'),
            "balance": None
        }
        
        # Obtener balance si la cuenta está configurada
        if config["web3_connected"] and config["account_configured"]:
            try:
                balance_wei = contract_deployer.w3.eth.get_balance(contract_deployer.account.address)
                config["balance"] = contract_deployer.w3.from_wei(balance_wei, 'ether')
            except:
                config["balance"] = "Error al obtener balance"
        
        return jsonify(config), 200
        
    except Exception as e:
        return jsonify({"error": f"Error al obtener configuración: {e}"}), 500

if __name__ == '__main__':
    app.run(debug=True)
