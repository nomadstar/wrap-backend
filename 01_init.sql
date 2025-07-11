-- Crear tabla de usuarios
CREATE TABLE IF NOT EXISTS users (
    wallet_address VARCHAR(42) PRIMARY KEY,
    wallet_type VARCHAR(25) NOT NULL,
    username-- Insertar administrador por defecto (tu wallet address)
INSERT INTO users (wallet_address, wallet_type, username) 
VALUES ('0xEf4dE33f51a75C0d3Dfa5e8B0B23370f0B3B6a87', 'phantom', 'ignatus') 
ON CONFLICT (wallet_address) DO NOTHING;CHAR(30),
    email VARCHAR(100)
);

-- Crear tabla de WrapPool contracts (WrapPool.sol)
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

-- Crear tabla de WrapSell contracts (WrapSell.sol)
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

-- Crear tabla de relaciones WrapPool -> WrapSell
CREATE TABLE IF NOT EXISTS wrap_pool_collateral (
    id SERIAL PRIMARY KEY,
    wrap_pool_address VARCHAR(42) REFERENCES wrap_pools(contract_address),
    wrap_sell_address VARCHAR(42) REFERENCES wrap_sells(contract_address),
    weight DECIMAL(28,18) NOT NULL, -- Weight/multiplier para el collateral
    is_active BOOLEAN DEFAULT true,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(wrap_pool_address, wrap_sell_address)
);

-- Crear tabla de depósitos de cartas por usuario (WrapSell.cardDeposits mapping)
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

-- Crear tabla de transacciones de cartas (eventos de los contratos)
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

-- Crear tabla de transacciones de stablecoins (WrapPool mint/burn)
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

-- Crear tabla de pool de cartas (legacy - mantener compatibilidad)
CREATE TABLE IF NOT EXISTS card_pools (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    TCG VARCHAR(50) NOT NULL,
    created_by VARCHAR(42) REFERENCES users(wallet_address),
    wrap_pool_address VARCHAR(42) REFERENCES wrap_pools(contract_address), -- Link to smart contract
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Crear tabla de cartas (legacy - mantener compatibilidad)
CREATE TABLE IF NOT EXISTS cards (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    card_id VARCHAR(50) NOT NULL,
    edition VARCHAR(100),
    user_wallet VARCHAR(42) REFERENCES users(wallet_address),
    url TEXT,
    market_value DECIMAL(10,2),
    pool_id INTEGER REFERENCES card_pools(id) DEFAULT NULL,
    wrap_sell_address VARCHAR(42) REFERENCES wrap_sells(contract_address), -- Link to smart contract
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    removed_at TIMESTAMP DEFAULT NULL,
    UNIQUE (card_id, pool_id)
);

-- Crear tabla de transacciones (legacy - mantener compatibilidad)
CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    user_wallet VARCHAR(42) REFERENCES users(wallet_address),
    transaction_type VARCHAR(10),
    card_id INTEGER REFERENCES cards(id) NOT NULL,
    amount DECIMAL(12,2),
    stablecoins_involved DECIMAL(12,2),
    commission DECIMAL(8,2) DEFAULT 0,
    transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Crear tabla pool que contenga cartas (legacy - mantener compatibilidad)
CREATE TABLE IF NOT EXISTS pool (
    id SERIAL PRIMARY KEY,
    card_id INTEGER NOT NULL REFERENCES cards(id),
    added_by VARCHAR(42) NOT NULL REFERENCES users(wallet_address),
    added_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    removed_at TIMESTAMP DEFAULT NULL
);

-- Crear tabla de administradores
CREATE TABLE IF NOT EXISTS admins (
    id SERIAL PRIMARY KEY,
    wallet_address VARCHAR(42) UNIQUE NOT NULL REFERENCES users(wallet_address),
    admin_level INTEGER NOT NULL DEFAULT 1, -- 1=básico, 2=avanzado, 3=super admin
    permissions JSONB DEFAULT '{"read": true, "write": false, "delete": false, "manage_users": false, "manage_admins": false}',
    created_by VARCHAR(42) REFERENCES admins(wallet_address),
    is_active BOOLEAN DEFAULT true,
    last_login TIMESTAMP DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insertar administrador por defecto (tu wallet address)
INSERT INTO users (wallet_address, wallet_type, username) 
VALUES ('0xEf4dE33f51a75C0d3Dfa5e8B0B23370f0B3B6a87', 'panthom', 'ignatus') 
ON CONFLICT (wallet_address) DO NOTHING;

INSERT INTO admins (wallet_address, admin_level, permissions, is_active) 
VALUES ('0xEf4dE33f51a75C0d3Dfa5e8B0B23370f0B3B6a87', 3, 
        '{"read": true, "write": true, "delete": true, "manage_users": true, "manage_admins": true}', 
        true) 
ON CONFLICT (wallet_address) DO NOTHING;

-- Crear índices para optimizar consultas
CREATE INDEX IF NOT EXISTS idx_admins_wallet_address ON admins(wallet_address);
CREATE INDEX IF NOT EXISTS idx_admins_is_active ON admins(is_active);
CREATE INDEX IF NOT EXISTS idx_admins_admin_level ON admins(admin_level);

