# 🔗 Sincronización Base de Datos - Contratos Inteligentes

Este documento explica cómo la base de datos se sincroniza con los contratos inteligentes `WrapPool.sol` y `WrapSell.sol`.

## 📋 Estructura de Tablas Principales

### 1. **`wrap_pools`** - Contratos WrapPool
Refleja cada instancia del contrato `WrapPool.sol`:

```sql
CREATE TABLE wrap_pools (
    contract_address VARCHAR(42) UNIQUE NOT NULL,  -- Dirección del contrato desplegado
    name VARCHAR(100) NOT NULL,                    -- nombre del ERC20
    symbol VARCHAR(10) NOT NULL,                   -- símbolo del ERC20  
    owner_wallet VARCHAR(42),                      -- owner() del contrato
    collateralization_ratio INTEGER DEFAULT 150,   -- collateralizationRatio del contrato
    total_supply DECIMAL(28,18) DEFAULT 0,         -- totalSupply() del ERC20
    total_collateral_value DECIMAL(28,18) DEFAULT 0, -- getTotalCollateralValue()
    is_healthy BOOLEAN DEFAULT true                -- isHealthy()
);
```

**Sincronización:**
- `contract_address` ← Dirección cuando se despliega
- `total_supply` ← `totalSupply()` del contrato
- `total_collateral_value` ← `getTotalCollateralValue()`
- `is_healthy` ← `isHealthy()`

### 2. **`wrap_sells`** - Contratos WrapSell
Refleja cada instancia del contrato `WrapSell.sol`:

```sql
CREATE TABLE wrap_sells (
    contract_address VARCHAR(42) UNIQUE NOT NULL,     -- Dirección del contrato
    name VARCHAR(100) NOT NULL,                       -- name del ERC20
    symbol VARCHAR(10) NOT NULL,                      -- symbol del ERC20
    card_id INTEGER NOT NULL,                         -- cardId del contrato
    card_name VARCHAR(255) NOT NULL,                  -- cardName del contrato
    rarity VARCHAR(50) NOT NULL,                      -- rarity del contrato
    estimated_value_per_card DECIMAL(28,18) NOT NULL, -- estimatedValuePerCard
    owner_wallet VARCHAR(42),                         -- owner() del contrato
    wrap_pool_address VARCHAR(42),                    -- wrapPool del contrato
    total_supply DECIMAL(28,18) DEFAULT 0,            -- totalSupply()
    total_cards_deposited INTEGER DEFAULT 0,          -- totalCardsDeposited
    total_tokens_issued DECIMAL(28,18) DEFAULT 0      -- totalTokensIssued
);
```

**Sincronización:**
- `contract_address` ← Dirección cuando se despliega
- `card_id`, `card_name`, `rarity` ← Variables del contrato
- `estimated_value_per_card` ← `estimatedValuePerCard`
- `total_cards_deposited` ← `totalCardsDeposited`
- `total_tokens_issued` ← `totalTokensIssued`

### 3. **`wrap_pool_collateral`** - Relaciones WrapPool ↔ WrapSell
Refleja el mapping `acceptedWrapSells` y `wrapSellWeights`:

```sql
CREATE TABLE wrap_pool_collateral (
    wrap_pool_address VARCHAR(42),      -- Dirección del WrapPool
    wrap_sell_address VARCHAR(42),      -- Dirección del WrapSell
    weight DECIMAL(28,18) NOT NULL,     -- wrapSellWeights[address]
    is_active BOOLEAN DEFAULT true      -- acceptedWrapSells[address]
);
```

**Sincronización:**
- `weight` ← `wrapSellWeights[wrapSellAddress]`
- `is_active` ← `acceptedWrapSells[wrapSellAddress]`

### 4. **`card_deposits`** - Depósitos de Usuario
Refleja el mapping `cardDeposits` de WrapSell:

```sql
CREATE TABLE card_deposits (
    wrap_sell_address VARCHAR(42),      -- Dirección del contrato WrapSell
    user_wallet VARCHAR(42),            -- Dirección del usuario
    cards_deposited INTEGER DEFAULT 0,  -- cardDeposits[user]
    tokens_received DECIMAL(28,18),     -- Tokens ERC20 que recibió
    deposit_value DECIMAL(28,18)        -- Valor en ETH del depósito
);
```

**Sincronización:**
- `cards_deposited` ← `cardDeposits[userAddress]`
- `tokens_received` ← `balanceOf(userAddress)`

## 🔄 Eventos de Sincronización

### Eventos WrapPool.sol
```solidity
event StablecoinMinted(address indexed user, uint256 amount, uint256 collateralValue);
event StablecoinBurned(address indexed user, uint256 amount);
event WrapSellAdded(address indexed wrapSell, uint256 weight);
event WrapSellRemoved(address indexed wrapSell);
```

**→ Tabla `stablecoin_transactions`**

### Eventos WrapSell.sol
```solidity
event CardsDeposited(address indexed user, uint256 cardCount, uint256 tokensIssued);
event CardsWithdrawn(address indexed user, uint256 cardCount, uint256 tokensBurned);
event CardInfoUpdated(string cardName, string rarity, uint256 estimatedValue);
```

**→ Tabla `card_transactions`**

## 🛠️ Implementación de Sincronización

### 1. **Listener de Eventos** (Recomendado)
```javascript
// Escuchar eventos del contrato y actualizar BD
contract.on('CardsDeposited', (user, cardCount, tokensIssued, event) => {
    // Actualizar card_deposits y card_transactions
    updateCardDeposits(user, cardCount, tokensIssued);
});
```

### 2. **Polling Periódico**
```javascript
// Cada X minutos, sincronizar estado
setInterval(async () => {
    const totalSupply = await wrapPoolContract.totalSupply();
    const collateralValue = await wrapPoolContract.getTotalCollateralValue();
    // Actualizar wrap_pools table
}, 60000); // Cada minuto
```

### 3. **API Endpoints de Sincronización**
```javascript
// POST /api/sync/wrap-pool/{address}
// POST /api/sync/wrap-sell/{address}
// POST /api/sync/all
```

## 📊 Consultas Importantes

### Estado de un WrapPool
```sql
SELECT 
    wp.*,
    (wp.total_collateral_value * 100 / wp.total_supply) as current_ratio
FROM wrap_pools wp 
WHERE wp.contract_address = '0x...';
```

### Depósitos de un Usuario
```sql
SELECT 
    ws.card_name,
    cd.cards_deposited,
    cd.tokens_received,
    (cd.cards_deposited * ws.estimated_value_per_card) as total_value
FROM card_deposits cd
JOIN wrap_sells ws ON cd.wrap_sell_address = ws.contract_address
WHERE cd.user_wallet = '0x...';
```

### Health Check de Pools
```sql
SELECT 
    contract_address,
    name,
    (total_collateral_value * 100 / NULLIF(total_supply, 0)) as ratio,
    collateralization_ratio as min_ratio,
    is_healthy
FROM wrap_pools
WHERE is_healthy = false;
```

## 🔧 Mantenimiento

### Comandos de Sincronización
```bash
# Sincronizar todos los contratos
npm run sync:all

# Sincronizar un contrato específico
npm run sync:wrap-pool 0x123...
npm run sync:wrap-sell 0x456...

# Verificar health de todos los pools
npm run health-check
```

### Monitoreo
- **Alertas** cuando `is_healthy = false`
- **Logs** de todas las sincronizaciones
- **Métricas** de latencia de sincronización
- **Validación** de consistencia BD ↔ Blockchain

Esta estructura permite mantener la base de datos siempre sincronizada con el estado real de los contratos inteligentes.
