# services.py
# Servicios y lógica de negocio de la aplicación

import extraer
from datetime import datetime
import random
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
    """Servicio para funciones administrativas"""
    
    @staticmethod
    def check_admin_status(wallet_address, admin_wallets):
        """Verificar si una wallet es administradora"""
        is_admin = wallet_address in admin_wallets
        return {
            "wallet_address": wallet_address,
            "is_admin": is_admin,
            "admin_wallets_count": len(admin_wallets)
        }
    
    @staticmethod
    def add_card_by_url_admin(url, user_wallet, pool_id, admin_wallet):
        """Añadir carta como administrador"""
        result = CardService.add_card_by_url(url, user_wallet, pool_id)
        result["admin_action"] = f"Añadida por {admin_wallet}"
        result["message"] = "Carta añadida exitosamente por administrador"
        return result
    
    @staticmethod
    def add_card_manual_admin(name, card_id, edition, user_wallet, market_value, admin_wallet, url=None, pool_id=None):
        """Añadir carta manualmente como administrador"""
        if not UserService.user_exists(user_wallet):
            raise ValueError("Usuario no encontrado")
        
        if pool_id and not PoolService.pool_exists(pool_id):
            raise ValueError("Pool no encontrado")
        
        new_card_id = execute_query(
            INSERT_CARD_QUERY,
            (name, card_id, edition, user_wallet, url, market_value, pool_id),
            return_id=True
        )
        
        if pool_id:
            execute_query(INSERT_POOL_CARD_QUERY, (new_card_id, admin_wallet))
        
        return {
            "message": "Carta añadida manualmente por administrador",
            "card_id": new_card_id,
            "admin_action": f"Añadida manualmente por {admin_wallet}"
        }
    
    @staticmethod
    def edit_card_admin(card_id, updates, admin_wallet):
        """Editar carta como administrador"""
        # Verificar que la carta existe
        if not execute_query(CHECK_CARD_EXISTS_QUERY, (card_id,), fetch_one=True):
            raise ValueError("Carta no encontrada")
        
        # Validar usuario si se está actualizando
        if 'user_wallet' in updates and updates['user_wallet']:
            if not UserService.user_exists(updates['user_wallet']):
                raise ValueError("Nuevo usuario no encontrado")
        
        # Validar pool si se está actualizando
        if 'pool_id' in updates and updates['pool_id'] and updates['pool_id'] != "":
            if not PoolService.pool_exists(updates['pool_id']):
                raise ValueError("Pool no encontrado")
        
        # Aplicar actualizaciones
        update_record_fields("cards", card_id, updates)
        
        return {
            "message": "Carta actualizada exitosamente",
            "card_id": card_id,
            "admin_action": f"Editada por {admin_wallet}"
        }
    
    @staticmethod
    def remove_card_admin(card_id, admin_wallet):
        """Marcar carta como removida (soft delete)"""
        card_info = execute_query(CHECK_CARD_REMOVED_STATUS_QUERY, (card_id,), fetch_one=True)
        
        if not card_info:
            raise ValueError("Carta no encontrada")
        
        if card_info[1] is not None:  # Ya está removida
            raise ValueError("La carta ya está marcada como removida")
        
        # Marcar como removida
        now = datetime.now()
        execute_query(SOFT_DELETE_CARD_QUERY, (now, card_id))
        execute_query(SOFT_DELETE_POOL_CARD_QUERY, (now, card_id))
        
        return {
            "message": "Carta marcada como removida exitosamente",
            "card_id": card_id,
            "admin_action": f"Removida por {admin_wallet}"
        }
    
    @staticmethod
    def restore_card_admin(card_id, admin_wallet):
        """Restaurar carta removida"""
        card_info = execute_query(CHECK_CARD_REMOVED_STATUS_QUERY, (card_id,), fetch_one=True)
        
        if not card_info:
            raise ValueError("Carta no encontrada")
        
        if card_info[1] is None:  # No está removida
            raise ValueError("La carta no está marcada como removida")
        
        # Restaurar carta
        execute_query(RESTORE_CARD_QUERY, (card_id,))
        execute_query(RESTORE_POOL_CARD_QUERY, (card_id,))
        
        return {
            "message": "Carta restaurada exitosamente",
            "card_id": card_id,
            "admin_action": f"Restaurada por {admin_wallet}"
        }
    
    @staticmethod
    def delete_card_permanent_admin(card_id, admin_wallet, confirm=False):
        """Eliminar carta permanentemente"""
        if not confirm:
            raise ValueError("Debe confirmar la eliminación permanente con 'confirm: true'")
        
        if not execute_query(CHECK_CARD_EXISTS_QUERY, (card_id,), fetch_one=True):
            raise ValueError("Carta no encontrada")
        
        # Eliminar en orden correcto (relaciones primero)
        execute_query(PERMANENT_DELETE_POOL_CARD_QUERY, (card_id,))
        execute_query(PERMANENT_DELETE_CARD_TRANSACTIONS_QUERY, (card_id,))
        execute_query(PERMANENT_DELETE_CARD_QUERY, (card_id,))
        
        return {
            "message": "Carta eliminada permanentemente",
            "card_id": card_id,
            "admin_action": f"ELIMINACIÓN PERMANENTE por {admin_wallet}",
            "warning": "Esta acción es irreversible"
        }
    
    @staticmethod
    def move_cards_to_pool_admin(card_ids, new_pool_id, admin_wallet):
        """Mover cartas a un pool diferente"""
        if new_pool_id is not None and not PoolService.pool_exists(new_pool_id):
            raise ValueError("Nuevo pool no encontrado")
        
        moved_cards = []
        failed_cards = []
        
        for card_id in card_ids:
            try:
                card_info = execute_query(GET_CARD_POOL_INFO_QUERY, (card_id,), fetch_one=True)
                
                if not card_info:
                    failed_cards.append({"card_id": card_id, "error": "Carta no encontrada"})
                    continue
                
                old_pool_id = card_info[1]
                
                # Actualizar pool_id en la tabla cards
                execute_query(UPDATE_CARD_POOL_QUERY, (new_pool_id, card_id))
                
                # Manejar tabla pool
                if old_pool_id is not None:
                    execute_query(MARK_POOL_CARD_REMOVED_QUERY, (card_id,))
                
                if new_pool_id is not None:
                    execute_query(INSERT_POOL_CARD_QUERY, (card_id, admin_wallet))
                
                moved_cards.append({
                    "card_id": card_id,
                    "old_pool_id": old_pool_id,
                    "new_pool_id": new_pool_id
                })
                
            except Exception as e:
                failed_cards.append({"card_id": card_id, "error": str(e)})
        
        return {
            "message": f"{len(moved_cards)} cartas movidas exitosamente",
            "moved_cards": moved_cards,
            "failed_cards": failed_cards,
            "admin_action": f"Movidas por {admin_wallet}"
        }
