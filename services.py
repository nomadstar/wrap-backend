# services.py
# Servicios y lógica de negocio de la aplicación

import extraer
from datetime import datetime
import random
import json
from queries import *
from db_utils import *

class UserService:
    """Servicio para manejo de usuarios"""
    
    @staticmethod
    def create_user(wallet_address, wallet_type, username=None, email=None):
        """Crear un nuevo usuario"""
        # Verificar si el usuario ya existe
        if execute_query(USER_EXISTS_QUERY, (wallet_address,), fetch_one=True):
            raise ValueError("Usuario ya existe")
        
        # Crear el usuario
        execute_query(INSERT_USER_QUERY, (wallet_address, wallet_type, username, email))
        return {"message": "Usuario creado exitosamente", "wallet_address": wallet_address}
    
    @staticmethod
    def get_user(wallet_address):
        """Obtener datos de un usuario"""
        user = execute_query_with_columns(GET_USER_QUERY, (wallet_address,), fetch_one=True)
        if not user:
            raise ValueError("Usuario no encontrado")
        return user
    
    @staticmethod
    def user_exists(wallet_address):
        """Verificar si un usuario existe"""
        return execute_query(USER_EXISTS_QUERY, (wallet_address,), fetch_one=True) is not None

class CardService:
    """Servicio para manejo de cartas"""
    
    @staticmethod
    def get_all_cards():
        """Obtener todas las cartas"""
        return execute_query_with_columns(GET_ALL_CARDS_QUERY)
    
    @staticmethod
    def get_card_by_id(card_id):
        """Obtener una carta por ID"""
        card = execute_query_with_columns(GET_CARD_BY_ID_QUERY, (card_id,), fetch_one=True)
        if not card:
            raise ValueError("Carta no encontrada")
        return card
    
    @staticmethod
    def get_user_cards(wallet_address):
        """Obtener cartas de un usuario"""
        return execute_query_with_columns(GET_USER_CARDS_QUERY, (wallet_address,))
    
    @staticmethod
    def get_total_collection_value():
        """Obtener valor total de la colección"""
        total = execute_query(GET_ACTIVE_CARDS_TOTAL_VALUE_QUERY, fetch_one=True)[0]
        return float(total) if total else 0.0
    
    @staticmethod
    def add_card_by_url(url, user_wallet, pool_id=None):
        """Añadir carta usando URL de pricecharting"""
        # Verificar que el usuario existe
        if not UserService.user_exists(user_wallet):
            raise ValueError("Usuario no encontrado. Debe crear el usuario primero.")
        
        # Verificar que el pool existe si se proporcionó
        if pool_id and not PoolService.pool_exists(pool_id):
            raise ValueError("Pool no encontrado")
        
        # Extraer datos de la carta
        card_data = extraer.extract_ungraded_card_data_by_link(url)
        if not card_data:
            raise ValueError("No se pudieron extraer los datos de la carta desde la URL")
        
        # Insertar la carta
        new_card_id = execute_query(
            INSERT_CARD_QUERY,
            (
                card_data['name'],
                card_data['card_id'],
                card_data['edition'],
                user_wallet,
                card_data['url'],
                card_data['market_value'],
                pool_id
            ),
            return_id=True
        )
        
        # Si se especificó un pool, agregar a la tabla pool
        if pool_id:
            execute_query(INSERT_POOL_CARD_QUERY, (new_card_id, user_wallet))
        
        return {
            "message": "Carta añadida exitosamente",
            "card_id": new_card_id,
            "card_data": card_data
        }
    
    @staticmethod
    def batch_add_cards_by_urls(urls, user_wallet, pool_id=None):
        """Añadir múltiples cartas usando URLs"""
        if not UserService.user_exists(user_wallet):
            raise ValueError("Usuario no encontrado")
        
        if pool_id and not PoolService.pool_exists(pool_id):
            raise ValueError("Pool no encontrado")
        
        added_cards = []
        failed_cards = []
        
        for url in urls:
            try:
                result = CardService.add_card_by_url(url, user_wallet, pool_id)
                added_cards.append(result)
            except Exception as e:
                failed_cards.append({"url": url, "error": str(e)})
        
        return {
            "message": f"Procesadas {len(urls)} URLs. {len(added_cards)} cartas añadidas, {len(failed_cards)} fallaron.",
            "added_cards": added_cards,
            "failed_cards": failed_cards
        }
    
    @staticmethod
    def update_card_prices():
        """Actualizar precios de todas las cartas activas"""
        cards = execute_query(GET_ACTIVE_CARDS_FOR_PRICE_UPDATE_QUERY, fetch_all=True)
        updated = 0
        not_updated = []
        
        for card in cards:
            card_db_id, edition, name, card_number = card
            try:
                card_data = extraer.extract_ungraded_card_data(edition, name, card_number)
                if card_data and card_data["market_value"] is not None:
                    execute_query(UPDATE_CARD_PRICE_QUERY, (card_data["market_value"], card_db_id))
                    updated += 1
                else:
                    not_updated.append({"id": card_db_id, "error": "No se pudo obtener el precio actualizado"})
            except Exception as e:
                not_updated.append({"id": card_db_id, "error": str(e)})
        
        return {
            "message": f"Precios actualizados para {updated} cartas.",
            "not_updated": not_updated
        }

class PoolService:
    """Servicio para manejo de pools"""
    
    @staticmethod
    def pool_exists(pool_id):
        """Verificar si un pool existe"""
        return execute_query(POOL_EXISTS_QUERY, (pool_id,), fetch_one=True) is not None
    
    @staticmethod
    def create_pool(name, description, tcg, created_by):
        """Crear un nuevo pool"""
        if not UserService.user_exists(created_by):
            raise ValueError("Usuario no encontrado")
        
        new_pool_id = execute_query(
            INSERT_POOL_QUERY,
            (name, description, tcg, created_by),
            return_id=True
        )
        
        return {
            "message": "Pool creado exitosamente",
            "pool_id": new_pool_id
        }
    
    @staticmethod
    def get_all_pools():
        """Obtener todos los pools con estadísticas"""
        return execute_query_with_columns(GET_POOLS_WITH_STATS_QUERY)
    
    @staticmethod
    def get_dashboard_pools():
        """Obtener pools para el dashboard con estadísticas adicionales"""
        pools_data = execute_query_with_columns(GET_DASHBOARD_POOLS_QUERY)
        pools = []
        
        for pool_data in pools_data:
            # Calcular días activos
            created_date = pool_data['created_at']
            if isinstance(created_date, str):
                created_date = datetime.fromisoformat(created_date.replace('Z', '+00:00'))
            days_active = (datetime.now() - created_date.replace(tzinfo=None)).days
            
            # Simular performance (esto puede ser calculado basado en datos históricos)
            performance_change = random.uniform(-5.0, 15.0)
            
            pools.append({
                "id": pool_data['id'],
                "name": pool_data['name'],
                "description": pool_data['description'],
                "tcg": pool_data['tcg'],
                "value": float(pool_data['total_value']),
                "total_cards": pool_data['total_cards'],
                "investors": pool_data['total_investors'],
                "daysActive": days_active,
                "performance": f"{performance_change:+.1f}%",
                "isPositive": performance_change > 0,
                "avgCardValue": float(pool_data['avg_card_value']),
                "gradient": f"from-blue-500 to-purple-600"
            })
        
        return pools

class DashboardService:
    """Servicio para datos del dashboard"""
    
    @staticmethod
    def get_user_summary(wallet_address):
        """Obtener resumen del usuario para el dashboard"""
        # Obtener inversiones del usuario por pool
        user_pools = execute_query_with_columns(
            GET_USER_POOL_INVESTMENTS_QUERY, 
            (wallet_address,)
        )
        
        # Calcular totales
        total_investment = sum(float(pool['user_investment']) for pool in user_pools)
        total_pool_value = sum(float(pool['total_pool_value']) for pool in user_pools)
        
        # Obtener total de cartas del usuario
        total_cards_result = execute_query(GET_USER_TOTAL_CARDS_QUERY, (wallet_address,), fetch_one=True)
        total_cards = total_cards_result[0] if total_cards_result else 0
        
        return {
            "totalInvestment": total_investment,
            "totalPoolValue": total_pool_value,
            "totalCards": total_cards,
            "userPools": user_pools
        }

class AdminService:
    """Servicio para verificación de permisos de administrador"""
    
    @staticmethod
    def is_admin(wallet_address):
        """Verificar si una wallet es admin consultando exclusivamente la base de datos"""
        if not wallet_address:
            return False
        
        try:
            admin = execute_query(ADMIN_QUERIES['get_admin_by_wallet'], (wallet_address,), fetch_one=True)
            if admin and admin[2]:  # Si existe y está activo (is_active)
                # Actualizar última conexión
                execute_query(ADMIN_QUERIES['update_admin_last_login'], (wallet_address,))
                return True
            return False
        except Exception as e:
            print(f"Error verificando admin en BD: {e}")
            return False
    
    @staticmethod
    def check_admin_status(wallet_address):
        """Verificar status de admin y devolver información detallada"""
        if not wallet_address:
            return {"is_admin": False, "message": "Wallet address no proporcionada"}
        
        try:
            admin = execute_query(ADMIN_QUERIES['get_admin_by_wallet'], (wallet_address,), fetch_one=True)
            if admin:
                is_active = admin[2] if len(admin) > 2 else True
                return {
                    "is_admin": is_active,
                    "wallet_address": wallet_address,
                    "status": "active" if is_active else "inactive",
                    "message": "Admin verificado" if is_active else "Admin inactivo"
                }
            else:
                return {
                    "is_admin": False,
                    "wallet_address": wallet_address,
                    "status": "not_admin",
                    "message": "No es administrador"
                }
        except Exception as e:
            print(f"Error verificando admin en BD: {e}")
            return {"is_admin": False, "message": f"Error de verificación: {str(e)}"}
    
    @staticmethod
    def get_admin_permissions(wallet_address):
        """Obtener permisos específicos de un admin"""
        try:
            result = execute_query(ADMIN_QUERIES['check_admin_permission'], (wallet_address,), fetch_one=True)
            if result:
                return json.loads(result[0]) if isinstance(result[0], str) else result[0]
        except Exception as e:
            print(f"Error obteniendo permisos: {e}")
        
        # Permisos por defecto para admins válidos
        if AdminService.is_admin(wallet_address):
            return {
                "read": True, 
                "write": True, 
                "delete": True, 
                "manage_users": True, 
                "manage_admins": True
            }
        return None

class AdminManagementService:
    """Servicio para gestión avanzada de administradores"""
    
    @staticmethod
    def list_admins():
        """Listar todos los administradores"""
        return execute_query_with_columns(ADMIN_QUERIES['list_all_admins'])
    
    @staticmethod
    def add_admin(wallet_address, admin_level=1, permissions=None, created_by=None):
        """Agregar un nuevo administrador"""
        if not permissions:
            permissions = {
                "read": True,
                "write": admin_level >= 2,
                "delete": admin_level >= 3,
                "manage_users": admin_level >= 2,
                "manage_admins": admin_level >= 3
            }
        
        # Verificar que el usuario existe
        if not UserService.user_exists(wallet_address):
            raise ValueError("El usuario debe existir antes de ser admin")
        
        # Agregar admin
        result = execute_query(
            ADMIN_QUERIES['add_admin'], 
            (wallet_address, admin_level, json.dumps(permissions), created_by, True),
            fetch_one=True
        )
        
        if result:
            return {
                "message": "Administrador agregado exitosamente",
                "admin": {
                    "wallet_address": result[1],
                    "admin_level": result[2],
                    "permissions": json.loads(result[3]) if isinstance(result[3], str) else result[3],
                    "created_at": result[4].isoformat() if result[4] else None
                }
            }
        raise ValueError("Error al agregar administrador")
    
    @staticmethod
    def remove_admin(wallet_address):
        """Remover un administrador (desactivar)"""
        result = execute_query(ADMIN_QUERIES['remove_admin'], (wallet_address,), fetch_one=True)
        if result:
            return {"message": f"Administrador {result[0]} desactivado exitosamente"}
        raise ValueError("Administrador no encontrado o ya desactivado")
    
    @staticmethod
    def update_admin_permissions(wallet_address, permissions=None, admin_level=None):
        """Actualizar permisos de un administrador"""
        if not permissions or not admin_level:
            raise ValueError("Se requieren permisos y nivel de admin")
        
        result = execute_query(
            ADMIN_QUERIES['update_admin_permissions'], 
            (json.dumps(permissions), admin_level, wallet_address),
            fetch_one=True
        )
        
        if result:
            return {
                "message": "Permisos actualizados exitosamente",
                "wallet_address": result[0],
                "permissions": json.loads(result[1]) if isinstance(result[1], str) else result[1],
                "admin_level": result[2]
            }
        raise ValueError("Administrador no encontrado o no activo")
