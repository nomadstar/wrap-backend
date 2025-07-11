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
        
        # Conectar a la base de datos usando nuestra utilidad
        conn = get_db_connection()
        
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

# === ENDPOINTS DE USUARIOS ===

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

# === ENDPOINTS DE CARTAS ===

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

# === ENDPOINTS DE POOLS ===

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

# === CONFIGURACIÓN DE ADMINISTRADORES ===

# Lista de wallets administrativas autorizadas desde variable de entorno
ADMIN_WALLETS_ENV = os.getenv('ADMIN_WALLETS', "")
if ADMIN_WALLETS_ENV:
    ADMIN_WALLETS = [wallet.strip() for wallet in ADMIN_WALLETS_ENV.split(',')]
else:
    # Wallets por defecto si no se especifica en .env
    ADMIN_WALLETS = [
        "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",  # Wallet admin principal
        "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",  # Wallet admin secundaria
        "0xEf4dE33f51a75C0d3Dfa5e8B0B23370f0B3B6a87",  # Wallet del usuario ignatus
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

# === PÁGINA PRINCIPAL CON DOCUMENTACIÓN ===

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
                "/cards_admin/remove/<card_id>": "[ADMIN] Marcar carta como removida (DELETE)",
                "/cards_admin/restore/<card_id>": "[ADMIN] Restaurar carta removida (PUT)",
                "/cards_admin/delete-permanent/<card_id>": "[ADMIN] Eliminar permanentemente (DELETE)",
                "/cards_admin/move-to-pool": "[ADMIN] Mover cartas entre pools (PUT)"
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
