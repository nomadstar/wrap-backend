-- Script de migración para reestructurar la base de datos
-- Este script migra de la estructura legacy a la nueva estructura que refleja los contratos

-- 1. CREAR NUEVAS TABLAS (solo si no existen)

-- Tabla de administradores del sistema
CREATE TABLE IF NOT EXISTS admins (
    id SERIAL PRIMARY KEY,
    wallet_address VARCHAR(42) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE,
    role VARCHAR(50) NOT NULL DEFAULT 'admin', -- 'super_admin', 'admin', 'moderator'
    permissions JSONB DEFAULT '{}', -- Permisos específicos en formato JSON
    is_active BOOLEAN DEFAULT true,
    created_by VARCHAR(42) REFERENCES admins(wallet_address),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de WrapPool contracts (WrapPool.sol)
CREATE TABLE IF NOT EXISTS wrap_pools (
    id SERIAL PRIMARY KEY,
    contract_address VARCHAR(42) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    owner_wallet VARCHAR(42) REFERENCES users(wallet_address),
    collateralization_ratio INTEGER DEFAULT 150, -- 150% = 150
    total_supply DECIMAL(28,18) DEFAULT 0, -- ERC20 total supply with 18 decimals
    total_collateral_value DECIMAL(28,18) DEFAULT 0,
    is_healthy BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de WrapSell contracts (WrapSell.sol)
CREATE TABLE IF NOT EXISTS wrap_sells (
    id SERIAL PRIMARY KEY,
    contract_address VARCHAR(42) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    card_id INTEGER NOT NULL, -- ID único de la carta en el contrato
    card_name VARCHAR(255) NOT NULL,
    rarity VARCHAR(50) NOT NULL,
    estimated_value_per_card DECIMAL(28,18) NOT NULL, -- Valor estimado por carta en wei
    owner_wallet VARCHAR(42) REFERENCES users(wallet_address),
    wrap_pool_address VARCHAR(42) REFERENCES wrap_pools(contract_address),
    total_supply DECIMAL(28,18) DEFAULT 0, -- ERC20 total supply
    total_cards_deposited INTEGER DEFAULT 0,
    total_tokens_issued DECIMAL(28,18) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de relaciones WrapPool -> WrapSell
CREATE TABLE IF NOT EXISTS wrap_pool_collateral (
    id SERIAL PRIMARY KEY,
    wrap_pool_address VARCHAR(42) REFERENCES wrap_pools(contract_address),
    wrap_sell_address VARCHAR(42) REFERENCES wrap_sells(contract_address),
    weight DECIMAL(28,18) NOT NULL, -- Weight/multiplier para el collateral
    is_active BOOLEAN DEFAULT true,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(wrap_pool_address, wrap_sell_address)
);

-- Tabla de depósitos de cartas por usuario (WrapSell.cardDeposits mapping)
CREATE TABLE IF NOT EXISTS card_deposits (
    id SERIAL PRIMARY KEY,
    wrap_sell_address VARCHAR(42) REFERENCES wrap_sells(contract_address),
    user_wallet VARCHAR(42) REFERENCES users(wallet_address),
    cards_deposited INTEGER NOT NULL DEFAULT 0,
    tokens_received DECIMAL(28,18) NOT NULL DEFAULT 0,
    deposit_value DECIMAL(28,18) NOT NULL DEFAULT 0, -- Valor en ETH/wei del depósito
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(wrap_sell_address, user_wallet)
);

-- Tabla de transacciones de cartas (eventos de los contratos)
CREATE TABLE IF NOT EXISTS card_transactions (
    id SERIAL PRIMARY KEY,
    transaction_hash VARCHAR(66) UNIQUE NOT NULL, -- Hash de la transacción blockchain
    wrap_sell_address VARCHAR(42) REFERENCES wrap_sells(contract_address),
    user_wallet VARCHAR(42) REFERENCES users(wallet_address),
    transaction_type VARCHAR(20) NOT NULL, -- 'deposit' o 'withdraw'
    card_count INTEGER NOT NULL,
    tokens_amount DECIMAL(28,18) NOT NULL,
    value_in_wei DECIMAL(28,18) NOT NULL,
    block_number BIGINT,
    transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de transacciones de stablecoins (WrapPool mint/burn)
CREATE TABLE IF NOT EXISTS stablecoin_transactions (
    id SERIAL PRIMARY KEY,
    transaction_hash VARCHAR(66) UNIQUE NOT NULL,
    wrap_pool_address VARCHAR(42) REFERENCES wrap_pools(contract_address),
    user_wallet VARCHAR(42) REFERENCES users(wallet_address),
    transaction_type VARCHAR(10) NOT NULL, -- 'mint' o 'burn'
    amount DECIMAL(28,18) NOT NULL,
    collateral_value DECIMAL(28,18),
    collateralization_ratio INTEGER,
    block_number BIGINT,
    transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. AGREGAR COLUMNAS A TABLAS EXISTENTES (solo si no existen)

-- Agregar columnas a card_pools para linkear con contratos
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                  WHERE table_name = 'card_pools' AND column_name = 'wrap_pool_address') THEN
        ALTER TABLE card_pools ADD COLUMN wrap_pool_address VARCHAR(42) REFERENCES wrap_pools(contract_address);
    END IF;
END $$;

-- Agregar columnas a cards para linkear con contratos
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                  WHERE table_name = 'cards' AND column_name = 'wrap_sell_address') THEN
        ALTER TABLE cards ADD COLUMN wrap_sell_address VARCHAR(42) REFERENCES wrap_sells(contract_address);
    END IF;
END $$;

-- 3. MIGRAR DATOS EXISTENTES A NUEVAS ESTRUCTURAS

-- Esta parte se ejecutaría después de desplegar contratos reales
-- Por ahora creamos datos de ejemplo para desarrollo

-- Insertar pools de ejemplo (solo si la tabla está vacía)
INSERT INTO wrap_pools (contract_address, name, symbol, owner_wallet, collateralization_ratio)
SELECT '0x1111111111111111111111111111111111111111', 'Pokemon Stable Pool', 'PSP', 
       u.wallet_address, 150
FROM users u
WHERE NOT EXISTS (SELECT 1 FROM wrap_pools)
LIMIT 1;

INSERT INTO wrap_pools (contract_address, name, symbol, owner_wallet, collateralization_ratio)
SELECT '0x2222222222222222222222222222222222222222', 'Yu-Gi-Oh Stable Pool', 'YSP', 
       u.wallet_address, 120
FROM users u
WHERE NOT EXISTS (SELECT 1 FROM wrap_pools WHERE contract_address = '0x2222222222222222222222222222222222222222')
LIMIT 1;

-- Linkear card_pools existentes con wrap_pools
UPDATE card_pools 
SET wrap_pool_address = '0x1111111111111111111111111111111111111111'
WHERE TCG = 'Pokemon' AND wrap_pool_address IS NULL;

UPDATE card_pools 
SET wrap_pool_address = '0x2222222222222222222222222222222222222222'
WHERE TCG = 'Yu-Gi-Oh' AND wrap_pool_address IS NULL;

-- Insertar administradores del sistema
INSERT INTO admins (wallet_address, email, role, permissions, is_active)
VALUES 
    ('0xEf4dE33f51a75C0d3Dfa5e8B0B23370f0B3B6a87', NULL, 'super_admin', '{"all": true}', true)
ON CONFLICT (wallet_address) DO NOTHING;

-- 4. CREAR ÍNDICES PARA OPTIMIZAR CONSULTAS

CREATE INDEX IF NOT EXISTS idx_wrap_pools_owner ON wrap_pools(owner_wallet);
CREATE INDEX IF NOT EXISTS idx_wrap_sells_owner ON wrap_sells(owner_wallet);
CREATE INDEX IF NOT EXISTS idx_wrap_sells_pool ON wrap_sells(wrap_pool_address);
CREATE INDEX IF NOT EXISTS idx_card_deposits_user ON card_deposits(user_wallet);
CREATE INDEX IF NOT EXISTS idx_card_deposits_contract ON card_deposits(wrap_sell_address);
CREATE INDEX IF NOT EXISTS idx_card_transactions_user ON card_transactions(user_wallet);
CREATE INDEX IF NOT EXISTS idx_card_transactions_contract ON card_transactions(wrap_sell_address);
CREATE INDEX IF NOT EXISTS idx_stablecoin_transactions_user ON stablecoin_transactions(user_wallet);
CREATE INDEX IF NOT EXISTS idx_stablecoin_transactions_pool ON stablecoin_transactions(wrap_pool_address);
CREATE INDEX IF NOT EXISTS idx_admins_role ON admins(role);
CREATE INDEX IF NOT EXISTS idx_admins_active ON admins(is_active);
CREATE INDEX IF NOT EXISTS idx_admins_created_by ON admins(created_by);

-- 5. CREAR VISTAS PARA COMPATIBILIDAD CON CÓDIGO EXISTENTE

-- Vista que combina datos legacy con nuevos contratos
CREATE OR REPLACE VIEW cards_with_contracts AS
SELECT 
    c.*,
    ws.contract_address as wrap_sell_contract,
    ws.estimated_value_per_card,
    wp.contract_address as wrap_pool_contract,
    wp.name as pool_contract_name
FROM cards c
LEFT JOIN wrap_sells ws ON c.wrap_sell_address = ws.contract_address
LEFT JOIN card_pools cp ON c.pool_id = cp.id
LEFT JOIN wrap_pools wp ON cp.wrap_pool_address = wp.contract_address;

-- Vista de resumen de pools
CREATE OR REPLACE VIEW pool_summary AS
SELECT 
    wp.contract_address,
    wp.name,
    wp.symbol,
    wp.total_supply,
    wp.total_collateral_value,
    wp.collateralization_ratio,
    wp.is_healthy,
    COUNT(DISTINCT ws.contract_address) as total_wrapsells,
    COUNT(DISTINCT c.id) as total_cards,
    COALESCE(SUM(c.market_value), 0) as legacy_total_value
FROM wrap_pools wp
LEFT JOIN wrap_sells ws ON wp.contract_address = ws.wrap_pool_address
LEFT JOIN cards c ON ws.contract_address = c.wrap_sell_address
GROUP BY wp.contract_address, wp.name, wp.symbol, wp.total_supply, 
         wp.total_collateral_value, wp.collateralization_ratio, wp.is_healthy;

COMMIT;
