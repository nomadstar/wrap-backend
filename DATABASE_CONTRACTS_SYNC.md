# Documentación: Base de Datos Sincronizada con Contratos Inteligentes

## 🏗️ Arquitectura de la Base de Datos

La base de datos ha sido reestructurada para reflejar fielmente los contratos inteligentes `WrapPool.sol` y `WrapSell.sol`, manteniendo compatibilidad con el sistema legacy.

## 📊 Nuevas Tablas Principales

### 1. `wrap_pools` - Contratos WrapPool
Refleja los contratos ERC20 que actúan como stablecoins respaldados por cartas:

```sql
-- Campos principales:
- contract_address: Dirección del contrato en blockchain
- name: Nombre del stablecoin (ej: "Pokemon Stable Pool")
- symbol: Símbolo del token (ej: "PSP")
- owner_wallet: Creador del pool
- collateralization_ratio: Ratio de colateralización (150% = 150)
- total_supply: Total de tokens emitidos (18 decimales)
- total_collateral_value: Valor total del colateral
- is_healthy: Estado de salud del pool
```

### 2. `wrap_sells` - Contratos WrapSell
Refleja los contratos ERC20 que representan cartas específicas:

```sql
-- Campos principales:
- contract_address: Dirección del contrato en blockchain
- card_id: ID único de la carta en el contrato
- card_name: Nombre de la carta (ej: "Charizard")
- rarity: Rareza de la carta
- estimated_value_per_card: Valor estimado por carta en wei
- wrap_pool_address: Pool al que pertenece este WrapSell
- total_cards_deposited: Total de cartas físicas depositadas
- total_tokens_issued: Total de tokens emitidos
```

### 3. `wrap_pool_collateral` - Relaciones Pool->WrapSell
Mapea qué WrapSells sirven como colateral para cada WrapPool:

```sql
-- Campos principales:
- wrap_pool_address: Pool que usa el colateral
- wrap_sell_address: WrapSell que actúa como colateral
- weight: Multiplicador/peso del colateral
- is_active: Si está activo como colateral
```

### 4. `card_deposits` - Depósitos de Usuarios
Refleja el mapping `cardDeposits` de los contratos WrapSell:

```sql
-- Campos principales:
- wrap_sell_address: Contrato donde se depositó
- user_wallet: Usuario que depositó
- cards_deposited: Cantidad de cartas depositadas
- tokens_received: Tokens WrapSell recibidos
- deposit_value: Valor del depósito en wei
```

### 5. `card_transactions` - Transacciones de Cartas
Registra eventos de depósito/retiro de cartas:

```sql
-- Campos principales:
- transaction_hash: Hash de la transacción blockchain
- transaction_type: 'deposit' o 'withdraw'
- card_count: Cantidad de cartas
- tokens_amount: Cantidad de tokens
- block_number: Número de bloque
```

### 6. `stablecoin_transactions` - Transacciones de Stablecoins
Registra eventos de mint/burn de los WrapPools:

```sql
-- Campos principales:
- transaction_hash: Hash de la transacción blockchain
- transaction_type: 'mint' o 'burn'
- amount: Cantidad de stablecoins
- collateral_value: Valor del colateral
- collateralization_ratio: Ratio en el momento
```

## 🔄 Compatibilidad Legacy

Se mantienen las tablas originales para compatibilidad:
- `cards` - Ahora incluye `wrap_sell_address`
- `card_pools` - Ahora incluye `wrap_pool_address`
- `transactions` - Transacciones legacy
- `pool` - Relaciones legacy

## 🎯 Endpoints de API Añadidos

### WrapPools
- `GET /contracts/wrap-pools` - Listar todos los WrapPools
- `POST /contracts/wrap-pools` - Registrar nuevo WrapPool
- `GET /contracts/wrap-pools/{address}/summary` - Resumen detallado

### WrapSells
- `GET /contracts/wrap-sells` - Listar todos los WrapSells
- `POST /contracts/wrap-sells` - Registrar nuevo WrapSell

### Usuarios
- `GET /contracts/user/{wallet}/positions` - Posiciones del usuario

## 📈 Vistas Útiles

### `cards_with_contracts`
Combina datos legacy con nuevos contratos:
```sql
SELECT * FROM cards_with_contracts WHERE user_wallet = '0x123...';
```

### `pool_summary`
Resumen de pools con estadísticas:
```sql
SELECT * FROM pool_summary WHERE is_healthy = true;
```

## 🚀 Migración Automática

El script `02_migration.sql` se ejecuta automáticamente al iniciar la aplicación:

1. ✅ Crea nuevas tablas si no existen
2. ✅ Agrega columnas a tablas existentes
3. ✅ Crea datos de ejemplo para desarrollo
4. ✅ Establece índices para optimización
5. ✅ Crea vistas para compatibilidad

## 💡 Uso en el Frontend

```javascript
// Obtener WrapPools disponibles
const pools = await fetch('/contracts/wrap-pools');

// Obtener posiciones del usuario
const positions = await fetch(`/contracts/user/${wallet}/positions`);

// Registrar nuevo contrato
await fetch('/contracts/wrap-sells', {
  method: 'POST',
  body: JSON.stringify({
    contract_address: '0x...',
    name: 'Charizard Token',
    symbol: 'CHAR',
    card_id: 6,
    card_name: 'Charizard',
    rarity: 'Rare Holo',
    estimated_value_per_card: '1000000000000000000', // 1 ETH en wei
    owner_wallet: wallet
  })
});
```

## 🔐 Sincronización con Blockchain

Para mantener la base de datos sincronizada con los contratos:

1. **Eventos de Contratos**: Escuchar eventos de los contratos
2. **Actualización Automática**: Webhook o polling para nuevos bloques
3. **Validación**: Comparar estado de BD vs blockchain
4. **Recuperación**: Sistema para reconstruir estado desde eventos

Esta estructura permite que la aplicación refleje exactamente el estado de los contratos inteligentes mientras mantiene compatibilidad con el código existente.
