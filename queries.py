# Archivo centralizado para todas las consultas SQL de la aplicación

# === CONSULTAS DE USUARIOS ===

USER_EXISTS_QUERY = """
    SELECT wallet_address FROM users WHERE wallet_address = %s;
"""

INSERT_USER_QUERY = """
    INSERT INTO users (wallet_address, wallet_type, username, email) 
    VALUES (%s, %s, %s, %s);
"""

GET_USER_QUERY = """
    SELECT * FROM users WHERE wallet_address = %s;
"""

# === CONSULTAS DE CARTAS ===

GET_ALL_CARDS_QUERY = """
    SELECT * FROM cards;
"""

GET_CARD_BY_ID_QUERY = """
    SELECT * FROM cards WHERE id = %s;
"""

GET_USER_CARDS_QUERY = """
    SELECT * FROM cards WHERE user_wallet = %s;
"""

GET_ACTIVE_CARDS_TOTAL_VALUE_QUERY = """
    SELECT COALESCE(SUM(market_value), 0) FROM cards WHERE removed_at IS NULL;
"""

GET_ACTIVE_CARDS_FOR_PRICE_UPDATE_QUERY = """
    SELECT id, edition, name, card_id FROM cards WHERE removed_at IS NULL;
"""

UPDATE_CARD_PRICE_QUERY = """
    UPDATE cards SET market_value = %s WHERE id = %s;
"""

INSERT_CARD_QUERY = """
    INSERT INTO cards (name, card_id, edition, user_wallet, url, market_value, pool_id)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    RETURNING id;
"""

# === CONSULTAS DE POOLS ===

POOL_EXISTS_QUERY = """
    SELECT id FROM card_pools WHERE id = %s;
"""

INSERT_POOL_QUERY = """
    INSERT INTO card_pools (name, description, TCG, created_by)
    VALUES (%s, %s, %s, %s)
    RETURNING id;
"""

INSERT_POOL_CARD_QUERY = """
    INSERT INTO pool (card_id, added_by) VALUES (%s, %s);
"""

GET_POOLS_WITH_STATS_QUERY = """
    SELECT 
        cp.*,
        COUNT(c.id) as total_cards,
        COALESCE(SUM(c.market_value), 0) as total_value
    FROM card_pools cp
    LEFT JOIN cards c ON cp.id = c.pool_id AND c.removed_at IS NULL
    GROUP BY cp.id
    ORDER BY cp.created_at DESC;
"""

# === CONSULTAS PARA DASHBOARD ===

GET_DASHBOARD_POOLS_QUERY = """
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
"""

GET_USER_POOL_INVESTMENTS_QUERY = """
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
"""

GET_USER_TOTAL_CARDS_QUERY = """
    SELECT COUNT(*) as total_cards
    FROM cards 
    WHERE user_wallet = %s AND removed_at IS NULL;
"""

# === CONSULTAS ADMINISTRATIVAS ===

CHECK_CARD_EXISTS_QUERY = """
    SELECT id FROM cards WHERE id = %s;
"""

CHECK_CARD_REMOVED_STATUS_QUERY = """
    SELECT id, removed_at FROM cards WHERE id = %s;
"""

SOFT_DELETE_CARD_QUERY = """
    UPDATE cards SET removed_at = %s WHERE id = %s;
"""

SOFT_DELETE_POOL_CARD_QUERY = """
    UPDATE pool SET removed_at = %s WHERE card_id = %s AND removed_at IS NULL;
"""

RESTORE_CARD_QUERY = """
    UPDATE cards SET removed_at = NULL WHERE id = %s;
"""

RESTORE_POOL_CARD_QUERY = """
    UPDATE pool SET removed_at = NULL WHERE card_id = %s;
"""

PERMANENT_DELETE_POOL_CARD_QUERY = """
    DELETE FROM pool WHERE card_id = %s;
"""

PERMANENT_DELETE_CARD_TRANSACTIONS_QUERY = """
    DELETE FROM transactions WHERE card_id = %s;
"""

PERMANENT_DELETE_CARD_QUERY = """
    DELETE FROM cards WHERE id = %s;
"""

UPDATE_CARD_POOL_QUERY = """
    UPDATE cards SET pool_id = %s WHERE id = %s;
"""

MARK_POOL_CARD_REMOVED_QUERY = """
    UPDATE pool SET removed_at = NOW() WHERE card_id = %s AND removed_at IS NULL;
"""

GET_CARD_POOL_INFO_QUERY = """
    SELECT id, pool_id FROM cards WHERE id = %s;
"""

# === CONSULTAS DE CONTRATOS BLOCKCHAIN ===

GET_WRAP_POOLS_QUERY = """
    SELECT * FROM wrap_pools ORDER BY created_at DESC;
"""

INSERT_WRAP_POOL_QUERY = """
    INSERT INTO wrap_pools (
        contract_address, name, symbol, owner_wallet, 
        collateralization_ratio, total_supply, total_collateral_value,
        is_healthy, created_at, updated_at, transaction_hash, block_number, gas_used
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING id;
"""

GET_WRAP_SELLS_QUERY = """
    SELECT * FROM wrap_sells ORDER BY created_at DESC;
"""

INSERT_WRAP_SELL_QUERY = """
    -- La siguiente consulta espera 15 valores en la tupla, en este orden:
    -- Campos básicos:
    -- 1. contract_address: VARCHAR(42) - Dirección del contrato
    -- 2. name: VARCHAR(100) - Nombre del token
    -- 3. symbol: VARCHAR(10) - Símbolo del token
    -- 4. card_id: INTEGER - ID único de la carta
    -- 5. card_name: VARCHAR(255) - Nombre de la carta
    -- 6. rarity: VARCHAR(50) - Rareza de la carta
    -- 7. estimated_value_per_card: DECIMAL(28,18) - Valor estimado por carta en wei
    -- 8. owner_wallet: VARCHAR(42) - Dirección del propietario
    -- 9. wrap_pool_address: VARCHAR(42) - Dirección del WrapPool asociado
    -- 10. total_supply: DECIMAL(28,18) - Supply total del token (default 0)
    -- 11. total_cards_deposited: INTEGER - Total de cartas depositadas (default 0)
    -- 12. total_tokens_issued: DECIMAL(28,18) - Total de tokens emitidos (default 0)
    -- Campos de blockchain (de 03_blockchain_migration.sql):
    -- 13. transaction_hash: VARCHAR(66) - Hash de la transacción
    -- 14. block_number: BIGINT - Número de bloque
    -- 15. gas_used: BIGINT - Gas utilizado
    INSERT INTO wrap_sells (
        contract_address, name, symbol, card_id, card_name, rarity,
        estimated_value_per_card, owner_wallet, wrap_pool_address,
        total_supply, total_cards_deposited, total_tokens_issued,
        transaction_hash, block_number, gas_used
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING id;
"""

# Utilidad para debug: imprime la consulta y la tupla de valores antes de ejecutar un INSERT
def debug_print_insert(query, values):
    print("\n[DEBUG SQL INSERT]")
    print("Consulta SQL:")
    print(query)
    print("\nValores proporcionados ({} valores):".format(len(values) if values else 0))
    if values:
        for i, value in enumerate(values, 1):
            print(f"{i}. {value} ({type(value).__name__})")
    else:
        print("¡No se proporcionaron valores!")
    print("\n")

GET_WRAP_POOL_SUMMARY_QUERY = """
    SELECT 
        wp.*,
        COUNT(DISTINCT ws.contract_address) as total_wrapsells,
        COUNT(DISTINCT c.id) as total_cards,
        COALESCE(SUM(c.market_value), 0) as legacy_total_value
    FROM wrap_pools wp
    LEFT JOIN wrap_sells ws ON wp.contract_address = ws.wrap_pool_address
    LEFT JOIN cards c ON ws.contract_address = c.wrap_sell_address
    WHERE wp.contract_address = %s
    GROUP BY wp.contract_address, wp.name, wp.symbol, wp.total_supply, 
             wp.total_collateral_value, wp.collateralization_ratio, wp.is_healthy, wp.id, wp.created_at, wp.updated_at, wp.transaction_hash, wp.block_number, wp.gas_used;
"""

GET_USER_POSITIONS_QUERY = """
    SELECT 
        wp.contract_address,
        wp.name,
        wp.symbol,
        COUNT(ws.contract_address) as wrap_sells_owned,
        COALESCE(SUM(ws.total_supply), 0) as total_tokens_issued
    FROM wrap_pools wp
    LEFT JOIN wrap_sells ws ON wp.contract_address = ws.wrap_pool_address
    WHERE ws.owner_wallet = %s
    GROUP BY wp.contract_address, wp.name, wp.symbol;
"""

INSERT_PENDING_DEPLOYMENT_QUERY = """
    INSERT INTO pending_deployments (
        deployment_type, pool_name, tcg_type, creator_address, 
        minimum_investment, target_value, blockchain_network, status
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING id;
"""

GET_PENDING_DEPLOYMENTS_QUERY = """
    SELECT * FROM pending_deployments 
    WHERE status IN ('pending', 'deploying') 
    ORDER BY created_at DESC;
"""

UPDATE_DEPLOYMENT_STATUS_QUERY = """
    UPDATE pending_deployments 
    SET status = %s, contract_address = %s, deployed_at = %s 
    WHERE id = %s;
"""

# === CONSULTAS DINÁMICAS PARA ACTUALIZACIONES ===

def build_dynamic_update_query(table_name, fields, where_clause):
    """
    Construye consultas UPDATE dinámicas basadas en los campos proporcionados
    """
    set_clause = ", ".join([f"{field} = %s" for field in fields])
    return f"UPDATE {table_name} SET {set_clause} WHERE {where_clause};"

def build_card_update_query(fields):
    """
    Construye consulta UPDATE específica para cartas
    """
    return build_dynamic_update_query("cards", fields, "id = %s")
