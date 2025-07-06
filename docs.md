# 📚 WrapSell Backend - Documentación Técnica

## 📋 Índice
1. [Descripción General](#descripción-general)
2. [Arquitectura](#arquitectura)
3. [Instalación y Configuración](#instalación-y-configuración)
4. [Base de Datos](#base-de-datos)
5. [Autenticación](#autenticación)
6. [API Endpoints](#api-endpoints)
7. [Módulos y Servicios](#módulos-y-servicios)
8. [Deployment](#deployment)
9. [Testing](#testing)
10. [Troubleshooting](#troubleshooting)

---

## 🌟 Descripción General

WrapSell Backend es una API REST construida con Flask que gestiona un marketplace de cartas de trading (principalmente Pokémon TCG). El sistema permite:

- **Gestión de usuarios** y wallets de criptomonedas
- **Catálogo de cartas** con precios actualizados automáticamente
- **Pools de inversión** colaborativos
- **Scraping de precios** desde PriceCharting.com
- **Dashboard** con estadísticas y métricas
- **Sistema administrativo** para gestión avanzada

---

## 🏗️ Arquitectura

### Stack Tecnológico
- **Framework**: Flask 2.x (Python)
- **Base de Datos**: PostgreSQL 15+
- **ORM**: psycopg2 (driver nativo)
- **Servidor Web**: Gunicorn (producción)
- **Scraping**: BeautifulSoup4 + Requests
- **Procesamiento**: OpenCV (para imágenes)

### Estructura del Proyecto
```
wrap-backend/
├── app.py                    # Aplicación principal Flask
├── extraer.py               # Módulo de scraping de precios
├── market_updater.py        # Sistema de actualización automática
├── picture.py               # Captura de imágenes
├── walleter.py              # (Reservado para funciones de wallet)
├── parsetodb.py            # Utilidades de parseo
├── update_prices.py        # Script de actualización masiva
├── requirements.txt        # Dependencias Python
├── Procfile               # Configuración Heroku
└── .env                   # Variables de entorno
```

---

## ⚙️ Instalación y Configuración

### Prerrequisitos
- Python 3.9+
- PostgreSQL 13+
- Docker & Docker Compose (opcional)

### Instalación Local

1. **Clonar y configurar entorno:**
   ```bash
   cd wrap-backend
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # venv\Scripts\activate   # Windows
   pip install -r requirements.txt
   ```

2. **Configurar variables de entorno:**
   ```bash
   cp .env.example .env
   # Editar .env con tus configuraciones
   ```

3. **Configurar base de datos:**
   ```bash
   # Ejecutar migraciones
   psql -d mydatabase -f migrations/01_init.sql
   psql -d mydatabase -f migrations/02_data.sql
   ```

4. **Ejecutar aplicación:**
   ```bash
   python app.py
   ```

### Instalación con Docker

```bash
# Desde la raíz del proyecto
docker-compose up -d
```

---

## 🗄️ Base de Datos

### Esquema de Tablas

#### `users` - Usuarios del Sistema
```sql
CREATE TABLE users (
    wallet_address VARCHAR(42) PRIMARY KEY,  -- Dirección de wallet
    wallet_type VARCHAR(25) NOT NULL,        -- Tipo: ethereum, polygon, etc.
    username VARCHAR(30),                    -- Nombre de usuario opcional
    email VARCHAR(100),                      -- Email opcional
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### `cards` - Catálogo de Cartas
```sql
CREATE TABLE cards (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,              -- Nombre de la carta
    card_id VARCHAR(50) NOT NULL,            -- Número de carta
    edition VARCHAR(100),                    -- Edición/set
    user_wallet VARCHAR(42) REFERENCES users(wallet_address),
    url TEXT,                                -- URL de PriceCharting
    market_value DECIMAL(10,2),              -- Precio actual
    pool_id INTEGER REFERENCES card_pools(id),
    created_at TIMESTAMP DEFAULT NOW(),
    removed_at TIMESTAMP DEFAULT NULL,       -- Soft delete
    UNIQUE (card_id, pool_id)
);
```

#### `card_pools` - Pools de Inversión
```sql
CREATE TABLE card_pools (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,              -- Nombre del pool
    description TEXT,                        -- Descripción
    TCG VARCHAR(50) NOT NULL,                -- Trading Card Game
    created_by VARCHAR(42) REFERENCES users(wallet_address),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### `transactions` - Historial de Transacciones
```sql
CREATE TABLE transactions (
    id SERIAL PRIMARY KEY,
    user_wallet VARCHAR(42) REFERENCES users(wallet_address),
    transaction_type VARCHAR(10),            -- buy, sell, trade
    card_id INTEGER REFERENCES cards(id),
    amount DECIMAL(12,2),                    -- Monto de la transacción
    stablecoins_involved DECIMAL(12,2),      -- Stablecoins involucradas
    commission DECIMAL(8,2) DEFAULT 0,       -- Comisión
    transaction_date TIMESTAMP DEFAULT NOW()
);
```

### Índices Recomendados
```sql
-- Optimización de consultas frecuentes
CREATE INDEX idx_cards_user_wallet ON cards(user_wallet);
CREATE INDEX idx_cards_pool_id ON cards(pool_id);
CREATE INDEX idx_cards_removed_at ON cards(removed_at);
CREATE INDEX idx_transactions_user_wallet ON transactions(user_wallet);
CREATE INDEX idx_transactions_date ON transactions(transaction_date);
```

---

## 🔐 Autenticación

### Sistema de API Keys

El backend utiliza un sistema de autenticación basado en API Keys:

```python
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
        if not api_key or api_key != API_SECRET_KEY:
            return jsonify({"error": "API key requerida o inválida"}), 401
        return f(*args, **kwargs)
    return decorated_function
```

### Métodos de Autenticación

1. **Header HTTP:**
   ```bash
   curl -H "X-API-Key: your_secret_key" http://localhost:5000/endpoint
   ```

2. **Query Parameter:**
   ```bash
   curl "http://localhost:5000/endpoint?api_key=your_secret_key"
   ```

### Endpoints Administrativos

Algunos endpoints requieren además que la wallet esté en la lista de administradores:

```python
ADMIN_WALLETS = os.getenv('ADMIN_WALLETS', '').split(',')
```

---

## 🛠️ API Endpoints

### 👤 Gestión de Usuarios

#### `POST /users`
Crear nuevo usuario
```json
{
  "wallet_address": "0x123...",
  "wallet_type": "ethereum",
  "username": "usuario123",
  "email": "user@example.com"
}
```

**Respuesta:**
```json
{
  "message": "Usuario creado exitosamente",
  "wallet_address": "0x123..."
}
```

#### `GET /users/{wallet_address}`
Obtener datos de usuario
```json
{
  "wallet_address": "0x123...",
  "wallet_type": "ethereum",
  "username": "usuario123",
  "email": "user@example.com",
  "created_at": "2025-01-01T12:00:00Z"
}
```

#### `GET /users/{wallet_address}/cards`
Obtener cartas del usuario
```json
[
  {
    "id": 1,
    "name": "Charizard",
    "card_id": "4",
    "edition": "Base Set",
    "market_value": 1250.00,
    "created_at": "2025-01-01T12:00:00Z"
  }
]
```

### 🃏 Gestión de Cartas

#### `GET /cards`
Obtener todas las cartas
```json
[
  {
    "id": 1,
    "name": "Pikachu",
    "card_id": "25",
    "edition": "Base Set",
    "market_value": 89.99,
    "user_wallet": "0x123...",
    "pool_id": null
  }
]
```

#### `GET /cards/{card_id}`
Obtener carta específica

#### `POST /cards/add-by-url`
Añadir carta mediante URL de PriceCharting
```json
{
  "url": "https://www.pricecharting.com/game/pokemon-base-set/pikachu-25",
  "user_wallet": "0x123...",
  "pool_id": 1
}
```

#### `POST /cards/batch-add-by-urls`
Añadir múltiples cartas
```json
{
  "urls": [
    "https://www.pricecharting.com/game/pokemon-base-set/pikachu-25",
    "https://www.pricecharting.com/game/pokemon-base-set/charizard-4"
  ],
  "user_wallet": "0x123...",
  "pool_id": 1
}
```

#### `GET /total_value`
Obtener valor total de la colección
```json
{
  "total_collection_value": 15420.50
}
```

#### `POST /update_prices`
Actualizar precios de todas las cartas
```json
{
  "message": "Precios actualizados para 150 cartas.",
  "not_updated": [
    {
      "id": 25,
      "error": "No se pudo obtener el precio actualizado"
    }
  ]
}
```

### 🏊 Gestión de Pools

#### `POST /pools`
Crear nuevo pool
```json
{
  "name": "Pokemon Vintage Pool",
  "description": "Pool de cartas vintage de Pokemon",
  "TCG": "Pokemon",
  "created_by": "0x123..."
}
```

#### `GET /pools`
Obtener todos los pools
```json
[
  {
    "id": 1,
    "name": "Pokemon Vintage Pool",
    "description": "Pool de cartas vintage",
    "TCG": "Pokemon",
    "created_by": "0x123...",
    "card_count": 25,
    "total_value": 5420.80
  }
]
```

#### `GET /dashboard/pools`
Obtener pools para dashboard (con estadísticas)
```json
[
  {
    "id": 1,
    "name": "Pokemon Vintage Pool",
    "description": "Pool de cartas vintage",
    "current_amount": 5420.80,
    "target_amount": 10000.00,
    "investor_count": 8,
    "days_active": 45,
    "performance": "+12.5%"
  }
]
```

### 📊 Dashboard

#### `GET /dashboard/user/{wallet_address}/summary`
Resumen del usuario para dashboard
```json
{
  "total_investment": 2500.00,
  "total_cards": 15,
  "total_pools": 3,
  "wallet_balance": 2.3458,
  "recent_activity": [
    {
      "id": 1,
      "type": "purchase",
      "description": "Charizard VMAX purchased - Fury Cards Pool",
      "amount": 2450.00,
      "timestamp": "2025-07-05T10:30:00Z"
    }
  ]
}
```

### 🔧 Endpoints Administrativos

Requieren wallet autorizada además de API key.

#### `POST /cards_admin/add-by-url`
Añadir carta (admin)

#### `POST /cards_admin/add-manual`
Añadir carta manualmente
```json
{
  "name": "Charizard",
  "card_id": "4",
  "edition": "Base Set",
  "market_value": 1250.00,
  "user_wallet": "0x123...",
  "pool_id": 1
}
```

#### `PUT /cards_admin/edit/{card_id}`
Editar carta existente

#### `DELETE /cards_admin/remove/{card_id}`
Remover carta (soft delete)

#### `PUT /cards_admin/restore/{card_id}`
Restaurar carta removida

#### `DELETE /cards_admin/delete-permanent/{card_id}`
Eliminar carta permanentemente

#### `PUT /cards_admin/move-to-pool`
Mover cartas a pool
```json
{
  "card_ids": [1, 2, 3],
  "pool_id": 2
}
```

---

## 🔧 Módulos y Servicios

### `extraer.py` - Módulo de Scraping

Extrae precios de cartas desde PriceCharting.com:

```python
def extract_ungraded_card_data(edition_name, card_name_input, card_number_input):
    """
    Extrae información y precio de una carta desde pricecharting.com
    
    Args:
        edition_name (str): Nombre de la edición
        card_name_input (str): Nombre de la carta
        card_number_input (str): Número de la carta
    
    Returns:
        dict: Datos de la carta incluido market_value
    """
```

**Características:**
- Formato automático de URLs
- Limpieza de datos de precios
- Manejo de errores y timeouts
- Headers anti-bot

### `market_updater.py` - Actualizador de Precios

Sistema automatizado para actualización masiva:

```python
class MarketUpdater:
    def update_all_prices(self):
        """Actualiza precios de todas las cartas con delays"""
        
    def update_card_price(self, card):
        """Actualiza precio de una carta específica"""
```

**Características:**
- Actualización por lotes
- Delays para evitar rate limiting
- Logs detallados
- Manejo robusto de errores

### `picture.py` - Captura de Imágenes

Funcionalidad para capturar imágenes desde cámara:

```python
def capture_image_from_camera(camera_index=0, output_file='captured_image.jpg'):
    """Captura imagen desde cámara web usando OpenCV"""
```

---

## 🚀 Deployment

### Variables de Entorno Requeridas

```bash
# Base de datos
DATABASE_URL=postgresql://user:password@host:port/database

# Seguridad
API_SECRET_KEY=your-super-secret-key-here

# Administración
ADMIN_WALLETS=0xWallet1,0xWallet2,0xWallet3

# Desarrollo (Docker)
DB_HOST=db
DB_PORT=5432
DB_NAME=mydatabase
DB_USER=user
DB_PASSWORD=password
```

### Desarrollo Local
```bash
export FLASK_ENV=development
export FLASK_DEBUG=1
python app.py
```

### Producción con Gunicorn
```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Docker Compose
```yaml
services:
  backend:
    build: .
    ports:
      - "5000:5000"
    environment:
      - DATABASE_URL=postgresql://user:password@db:5432/mydatabase
      - API_SECRET_KEY=your_secret_key
    depends_on:
      - db
  
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: mydatabase
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
```

### Heroku
```bash
# Procfile ya incluido
git push heroku main

# Configurar variables
heroku config:set DATABASE_URL=postgres://...
heroku config:set API_SECRET_KEY=your_key
```

---

## 🧪 Testing

### Script de Pruebas Rápidas
```bash
# Ejecutar desde la raíz del proyecto
./test-backend-connection.sh
```

### Pruebas Manuales con curl

```bash
# Health check
curl -H "X-API-Key: your_secret_key" "http://localhost:5000/?api_key=your_secret_key"

# Obtener pools
curl -H "X-API-Key: your_secret_key" "http://localhost:5000/dashboard/pools"

# Crear usuario
curl -X POST \
  -H "X-API-Key: your_secret_key" \
  -H "Content-Type: application/json" \
  -d '{"wallet_address":"0x123","wallet_type":"ethereum"}' \
  "http://localhost:5000/users"
```

### Tests Unitarios (Recomendado)
```python
# test_app.py
import unittest
from app import app

class TestAPI(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.headers = {'X-API-Key': 'your_secret_key'}
    
    def test_health_check(self):
        response = self.app.get('/', headers=self.headers)
        self.assertEqual(response.status_code, 200)
```

---

## 🚨 Troubleshooting

### Errores Comunes

#### "API key requerida o inválida"
```bash
# Verificar variable de entorno
echo $API_SECRET_KEY

# Verificar header en request
curl -v -H "X-API-Key: wrong_key" http://localhost:5000/
```

#### "Error al conectar a la base de datos"
```bash
# Verificar conexión
psql $DATABASE_URL -c "SELECT 1;"

# Verificar variables
echo $DATABASE_URL
```

#### "Usuario ya existe"
```sql
-- Verificar usuarios existentes
SELECT * FROM users WHERE wallet_address = '0x123...';
```

#### "No se pudo obtener el precio actualizado"
- Verificar conectividad a PriceCharting.com
- Revisar formato de URL de la carta
- Comprobar rate limiting

### Logs y Debugging

```python
# Activar logs detallados
import logging
logging.basicConfig(level=logging.DEBUG)

# En producción, usar logs estructurados
import json
print(json.dumps({
    "level": "info",
    "message": "Card updated",
    "card_id": card_id,
    "timestamp": datetime.now().isoformat()
}))
```

### Monitoreo de Performance

```sql
-- Consultas lentas
SELECT query, mean_time, calls 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;

-- Tamaño de tablas
SELECT schemaname, tablename, 
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables 
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

---

## 📈 Optimizaciones Recomendadas

### Performance
- Implementar conexion pool para PostgreSQL
- Cachear precios de cartas (Redis)
- Paginación en endpoints de listado
- Índices en columnas frecuentemente consultadas

### Seguridad
- Rate limiting por IP
- Validación exhaustiva de inputs
- Logs de auditoría para acciones admin
- Encriptación de datos sensibles

### Escalabilidad
- Workers asíncronos para scraping (Celery)
- CDN para imágenes de cartas
- Separar read/write databases
- Microservicios por dominio

### Monitoring
- Health checks automáticos
- Métricas de APM (Application Performance Monitoring)
- Alertas por errores críticos
- Dashboard de métricas de negocio

---

## 📞 Soporte

Para reportar bugs, solicitar features o hacer preguntas:

1. **Issues**: Crear issue en el repositorio
2. **Documentation**: Consultar esta documentación
3. **Logs**: Incluir logs relevantes en reportes
4. **Environment**: Especificar versión y configuración

---

*Documentación actualizada: 5 de julio de 2025*

