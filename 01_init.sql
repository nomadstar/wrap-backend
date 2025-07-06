-- Crear tabla de usuarios
CREATE TABLE IF NOT EXISTS users (
    wallet_address VARCHAR(42) PRIMARY KEY,
    wallet_type VARCHAR(25) NOT NULL,
    username VARCHAR(30),
    email VARCHAR(100)
);

-- Crear tabla de pool de cartas
CREATE TABLE IF NOT EXISTS card_pools (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    TCG VARCHAR(50) NOT NULL,
    created_by VARCHAR(42) REFERENCES users(wallet_address),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Crear tabla de cartas
CREATE TABLE IF NOT EXISTS cards (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    card_id VARCHAR(50) NOT NULL,
    edition VARCHAR(100),
    user_wallet VARCHAR(42) REFERENCES users(wallet_address),
    url TEXT,
    market_value DECIMAL(10,2),
    pool_id INTEGER REFERENCES card_pools(id) DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    removed_at TIMESTAMP DEFAULT NULL,
    UNIQUE (card_id, pool_id) -- Asegura que no haya
);

-- Crear tabla de transacciones
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
-- Crear tabla pool que contenga cartas
CREATE TABLE IF NOT EXISTS pool (
    id SERIAL PRIMARY KEY,
    card_id INTEGER NOT NULL REFERENCES cards(id),
    added_by VARCHAR(42) NOT NULL REFERENCES users(wallet_address),
    added_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    removed_at TIMESTAMP DEFAULT NULL
);
