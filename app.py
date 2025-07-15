from flask import Flask, request, jsonify
from flask_cors import CORS
import urllib.parse
import os
import psycopg2
import extraer
from functools import wraps
import sys
import json

# Importar nuestros módulos personalizados
from db_utils import get_db_connection
from services import UserService, CardService, PoolService, DashboardService, AdminService
from blockchain_service import get_blockchain_service

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
        
        # Leer el archivo de migración de blockchain
        blockchain_migration_path = os.path.join(os.path.dirname(__file__), '03_blockchain_migration.sql')
        blockchain_migration_script = ""
        try:
            with open(blockchain_migration_path, 'r', encoding='utf-8') as f:
                blockchain_migration_script = f.read()
        except FileNotFoundError:
            print("Advertencia: Archivo de migración 03_blockchain_migration.sql no encontrado")
        
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

# Configurar CORS para permitir cualquier origen, pero solo si la solicitud incluye la clave API
from flask_cors import cross_origin

# Permitir cualquier origen, pero solo para rutas que requieren API key
CORS(app, origins="*", supports_credentials=True)

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
    Ahora también despliega automáticamente un contrato WrapSell y asocia la dirección a la carta.
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

        # 1. Agregar la carta normalmente
        result = CardService.add_card_by_url(url, user_wallet, pool_id)
        if not result or not result.get('card_id'):
            return jsonify({"error": "No se pudo crear la carta"}), 500

        card_id = result['card_id']
        card = CardService.get_card_by_id(card_id)
        if not card:
            return jsonify({"error": "No se pudo obtener la carta recién creada"}), 500

        # Cargar el ABI de WrapSell desde artifacts
        try:
            artifacts_dir = os.path.join(os.path.dirname(__file__), 'contracts', 'artifacts', 'contracts', 'WrapSellTest.sol')
            abi_path = os.path.join(artifacts_dir, 'WrapSellTest.json')
            if not os.path.exists(abi_path):
                # fallback to WrapSell.json if WrapSellTest.json does not exist
                abi_path = os.path.join(os.path.dirname(__file__), 'contracts', 'artifacts', 'contracts', 'WrapSell.sol', 'WrapSell.json')
            with open(abi_path, 'r', encoding='utf-8') as f:
                artifact = json.load(f)
                abi = artifact['abi']
        except Exception as e:
            return jsonify({"error": f"No se pudo cargar el ABI del contrato: {e}"}), 500

        # Si la carta ya tiene contrato asociado, mintear tokens en el contrato SOLO si la wallet es admin
        if card.get('wrapsell_contract_address'):
            contract_address = card['wrapsell_contract_address']
            blockchain_service = get_blockchain_service()
            tokens_to_mint = int(1 * 10**18)  # 1 token por carta

            admin_wallet = user_wallet
            if admin_wallet not in ADMIN_WALLETS:
                return jsonify({"error": "Solo un administrador puede mintear tokens en el contrato."}), 403

            try:
                mint_result = blockchain_service.mint_wrapsell_tokens(
                    contract_address=contract_address,
                    to_address=user_wallet,
                    amount=tokens_to_mint,
                    abi=abi
                )
            except Exception as e:
                return jsonify({"error": f"Error al mintear tokens en el contrato: {e}"}), 500

            result['wrapsell_contract_address'] = contract_address
            result['wrapsell_mint'] = {
                "transaction_hash": mint_result.get('transaction_hash'),
                "block_number": mint_result.get('block_number'),
                "gas_used": mint_result.get('gas_used'),
                "minted_to": user_wallet,
                "amount": tokens_to_mint
            }
            result['message'] = "La carta ya tiene un contrato asociado. Se mintearon tokens en el contrato existente (solo admin)."
            return jsonify(result), 200

        # 2. Desplegar el contrato WrapSell automáticamente SOLO si no existe
        blockchain_service = get_blockchain_service()
        name = card.get('name')
        symbol = (name[:3] if name else "WRP").upper()
        rarity = card.get('rarity', 'Common')
        estimated_value = card.get('market_value', '0.01')
        card_name = card.get('name')

        try:
            estimated_value_wei = int(float(estimated_value) * 10**18)
        except Exception:
            estimated_value_wei = 0

        deploy_result = blockchain_service.deploy_wrapsell_contract(
            name=name,
            symbol=symbol,
            card_id=int(card_id),
            rarity=rarity,
            estimated_value_per_card=estimated_value_wei,
            wrap_pool=pool_id  # Use 'wrap_pool' instead of 'wrap_pool_address'
        )

        if not deploy_result.get('success'):
            return jsonify({"error": f"Error al desplegar contrato: {deploy_result.get('error', 'desconocido')}"}), 500

        contract_address = deploy_result['contract_address']
        CardService.update_card_contract_address(card_id, contract_address)

        result['wrapsell_contract_address'] = contract_address
        result['wrapsell_deploy'] = {
            "transaction_hash": deploy_result['transaction_hash'],
            "block_number": deploy_result['block_number'],
            "gas_used": deploy_result['gas_used']
        }
        return jsonify(result), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Error al añadir carta o desplegar contrato: {e}"}), 500

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
        "0xEf4dE33f51a75C0d3Dfa5e8B0B23370f0B3B6a87",  # Wallet de usuario conectado
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
                "--- ENDPOINTS DE CONTRATOS ---": "Operaciones sobre contratos blockchain",
                "/contracts/wrap-pools": "Obtener todos los contratos WrapPool (GET)",
                "/contracts/wrap-sells": "Obtener todos los contratos WrapSell (GET)",
                "/contracts/wrapsell": "Obtener todos los contratos WrapSell (GET, legacy)",
                "/contracts/wrapsell/deploy": "[ADMIN] Crear (deploy) un contrato WrapSell (POST)",
                "/contracts/wrappool/deploy": "[ADMIN] Crear (deploy) un contrato WrapPool (POST)",
                "/contracts/associate": "[ADMIN] Asociar un WrapSell a un WrapPool (POST)",
                "/contracts/status/<contract_address>": "Consultar el estado de un contrato (GET)",
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

# === ENDPOINTS DE CONTRATOS ===

@app.route('/contracts/wrap-pools', methods=['GET'])
@require_api_key
def get_wrap_pools():
    """
    Obtener todos los contratos WrapPool
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
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

@app.route('/contracts/wrap-sells', methods=['GET'])
@require_api_key
def get_wrap_sells():
    """
    Obtener todos los contratos WrapSell
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
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

# ========================================
# BLOCKCHAIN CONTRACT DEPLOYMENT ENDPOINTS
# ========================================

@app.route('/contracts/wrapsell/deploy', methods=['POST'])
@require_admin_wallet
def deploy_wrapsell_contract():
    """
    [ADMIN] Deploy a new WrapSell contract to the blockchain
    """
    try:
        data = request.get_json()
        
        # Required fields
        name = data.get('name')
        symbol = data.get('symbol') 
        card_id = data.get('card_id')
        card_name = data.get('card_name')
        rarity = data.get('rarity')
        estimated_value_per_card = data.get('estimated_value_per_card')
        admin_wallet = data.get('admin_wallet')
        
        # Campo opcional: wrap_pool (acepta ambos nombres, pero solo se usará como wrap_pool)
        wrap_pool = data.get('wrap_pool') or data.get('wrap_pool_address')

        if not all([name, symbol, card_id, card_name, rarity, estimated_value_per_card, admin_wallet]):
            return jsonify({"error": "Missing required fields"}), 400

        # Convert estimated value to wei (assuming it's provided in ETH)
        try:
            estimated_value_wei = int(float(estimated_value_per_card) * 10**18)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid estimated_value_per_card format"}), 400

        # Get blockchain service
        blockchain_service = get_blockchain_service()

        # Deploy contract (solo pasa wrap_pool si está presente, nunca wrap_pool_address)
        deploy_kwargs = {
            "name": name,
            "symbol": symbol,
            "card_id": card_id,
            "card_name": card_name,
            "rarity": rarity,
            "estimated_value_per_card": estimated_value_per_card,
            "admin_wallet": admin_wallet,
            # "wrap_pool_address": wrap_pool_address,  # <-- NO INCLUIR
            "wrap_pool": wrap_pool  # <-- SOLO ESTE SI ES NECESARIO
        }
        # Elimina wrap_pool_address si existe por error
        deploy_kwargs.pop("wrap_pool_address", None)

        deploy_result = blockchain_service.deploy_wrapsell_contract(**data)
        
        if deploy_result['success']:
            # Store contract info in database
            conn = get_db_connection()
            cur = conn.cursor()
            
            cur.execute("""
                INSERT INTO wrap_sells (
                    contract_address, name, symbol, card_id, card_name, 
                    rarity, estimated_value_per_card, owner_wallet, 
                    wrap_pool_address, total_supply, total_cards_deposited, 
                    total_tokens_issued, transaction_hash, block_number
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                deploy_result['contract_address'], name, symbol, card_id, card_name,
                rarity, str(estimated_value_wei), admin_wallet,
                wrap_pool, '0', 0, '0', 
                deploy_result['transaction_hash'], deploy_result['block_number']
            ))
            
            conn.commit()
            cur.close()
            conn.close()
            
            return jsonify({
                "message": "WrapSell contract deployed successfully",
                "contract_address": deploy_result['contract_address'],
                "transaction_hash": deploy_result['transaction_hash'],
                "gas_used": deploy_result['gas_used'],
                "block_number": deploy_result['block_number']
            }), 201
        else:
            return jsonify({
                "error": f"Contract deployment failed: {deploy_result['error']}"
            }), 500
            
    except Exception as e:
        return jsonify({"error": f"Error deploying WrapSell contract: {e}"}), 500

@app.route('/contracts/wrappool/deploy', methods=['POST'])
@require_admin_wallet  
def deploy_wrappool_contract():
    """
    [ADMIN] Deploy a new WrapPool contract to the blockchain
    """
    try:
        data = request.get_json()
        
        # Required fields
        name = data.get('name')
        symbol = data.get('symbol')
        owner = data.get('owner')
        admin_wallet = data.get('admin_wallet')
        
        # Optional fields
        collateralization_ratio = data.get('collateralization_ratio', 150)
        
        if not all([name, symbol, owner, admin_wallet]):
            return jsonify({"error": "Missing required fields"}), 400
        
        # Get blockchain service
        blockchain_service = get_blockchain_service()
        
        # Deploy contract
        result = blockchain_service.deploy_wrappool_contract(
            name=name,
            symbol=symbol, 
            owner=owner,
            collateralization_ratio=int(collateralization_ratio)
        )
        
        if result['success']:
            # Store contract info in database
            conn = get_db_connection()
            cur = conn.cursor()
            
            cur.execute("""
                INSERT INTO wrap_pools (
                    contract_address, name, symbol, owner_wallet, 
                    collateralization_ratio, total_supply, total_collateral_value,
                    is_healthy, transaction_hash, block_number
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                result['contract_address'], name, symbol, owner,
                collateralization_ratio, '0', '0', True,
                result['transaction_hash'], result['block_number']
            ))
            
            conn.commit()
            cur.close()
            conn.close()
            
            return jsonify({
                "message": "WrapPool contract deployed successfully",
                "contract_address": result['contract_address'],
                "transaction_hash": result['transaction_hash'],
                "gas_used": result['gas_used'],
                "block_number": result['block_number']
            }), 201
        else:
            return jsonify({
                "error": f"Contract deployment failed: {result['error']}"
            }), 500
            
    except Exception as e:
        return jsonify({"error": f"Error deploying WrapPool contract: {e}"}), 500

@app.route('/contracts/associate', methods=['POST'])
@require_admin_wallet
def associate_wrapsell_to_pool():
    """
    [ADMIN] Associate a WrapSell contract to a WrapPool
    """
    try:
        data = request.get_json()
        
        wrapsell_address = data.get('wrapsell_address')
        pool_address = data.get('pool_address')
        admin_wallet = data.get('admin_wallet')
        
        if not all([wrapsell_address, pool_address, admin_wallet]):
            return jsonify({"error": "Missing required fields"}), 400
        
        # Get blockchain service
        blockchain_service = get_blockchain_service()
        
        # Associate contracts
        result = blockchain_service.associate_wrapsell_to_pool(
            wrapsell_address=wrapsell_address,
            pool_address=pool_address
        )
        
        if result['success']:
            # Update database
            conn = get_db_connection()
            cur = conn.cursor()
            
            cur.execute("""
                UPDATE wrap_sells 
                SET wrap_pool_address = %s 
                WHERE contract_address = %s
            """, (pool_address, wrapsell_address))
            
            conn.commit()
            cur.close()
            conn.close()
            
            return jsonify({
                "message": "WrapSell successfully associated to WrapPool",
                "transaction_hash": result['transaction_hash']
            }), 200
        else:
            return jsonify({
                "error": f"Association failed: {result['error']}"
            }), 500
            
    except Exception as e:
        return jsonify({"error": f"Error associating contracts: {e}"}), 500

@app.route('/contracts/status/<contract_address>', methods=['GET'])
def get_contract_status(contract_address):
    """
    Get the status of a deployed contract from the blockchain
    """
    try:
        # Get blockchain service
        blockchain_service = get_blockchain_service()
        
        # Check if address is a contract
        code = blockchain_service.w3.eth.get_code(contract_address)
        
        if len(code) > 0:
            return jsonify({
                "is_contract": True,
                "contract_address": contract_address,
                "message": "Contract exists on blockchain"
            }), 200
        else:
            return jsonify({
                "is_contract": False,
                "contract_address": contract_address,
                "message": "No contract found at this address"
            }), 404
            
    except Exception as e:
        return jsonify({"error": f"Error checking contract status: {e}"}), 500

@app.route('/contracts/wrapsell', methods=['GET'])
def get_wrapsell_contracts():
    """
    Get all deployed WrapSell contracts
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, contract_address, name, symbol, card_id, card_name, 
                   rarity, estimated_value_per_card, owner_wallet, wrap_pool_address,
                   total_supply, total_cards_deposited, total_tokens_issued,
                   transaction_hash, block_number, created_at
            FROM wrap_sells 
            ORDER BY created_at DESC
        """)
        
        contracts = []
        for row in cur.fetchall():
            contracts.append({
                "id": row[0],
                "contract_address": row[1],
                "name": row[2],
                "symbol": row[3],
                "card_id": row[4],
                "card_name": row[5],
                "rarity": row[6],
                "estimated_value_per_card": row[7],
                "owner_wallet": row[8],
                "wrap_pool_address": row[9],
                "total_supply": row[10],
                "total_cards_deposited": row[11],
                "total_tokens_issued": row[12],
                "transaction_hash": row[13],
                "block_number": row[14],
                "created_at": row[15].isoformat() if row[15] else None
            })
        
        cur.close()
        conn.close()
        
        return jsonify(contracts), 200
        
    except Exception as e:
        return jsonify({"error": f"Error fetching WrapSell contracts: {e}"}), 500

# Cargar ABI de WrapSell desde archivo (solo el campo 'abi')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
