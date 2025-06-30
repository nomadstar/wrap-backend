import psycopg2
import os
import urllib.parse
from extraer import extract_ungraded_card_data
import time
from datetime import datetime

class MarketUpdater:
    def __init__(self):
        # Configuración de la base de datos
        self.db_config = self._get_db_config()
        
    def _get_db_config(self):
        """Obtiene la configuración de la base de datos desde variables de entorno"""
        database_url = os.getenv('DATABASE_URL')
        
        if database_url:
            # Para Heroku/producción
            url = urllib.parse.urlparse(database_url)
            return {
                'host': url.hostname,
                'port': url.port,
                'database': url.path[1:],
                'user': url.username,
                'password': url.password
            }
        else:
            # Para desarrollo local (Docker Compose)
            return {
                'host': os.getenv('DB_HOST', 'db'),
                'port': int(os.getenv('DB_PORT', 5432)),
                'database': os.getenv('DB_NAME', 'mydatabase'),
                'user': os.getenv('DB_USER', 'user'),
                'password': os.getenv('DB_PASSWORD', 'password')
            }

    def connect_to_db(self):
        """Establece conexión con la base de datos"""
        try:
            conn = psycopg2.connect(**self.db_config)
            return conn
        except psycopg2.Error as e:
            print(f"Error al conectar con la base de datos: {e}")
            return None

    def get_all_cards(self):
        """Obtiene todas las cartas de la base de datos"""
        conn = self.connect_to_db()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor()
            query = """
                SELECT id, name, card_id, edition, market_value, url
                FROM cards 
                WHERE name IS NOT NULL 
                AND card_id IS NOT NULL 
                AND edition IS NOT NULL
                ORDER BY id
            """
            cursor.execute(query)
            cards = cursor.fetchall()
            
            # Convertir a lista de diccionarios
            card_list = []
            for card in cards:
                card_list.append({
                    'id': card[0],
                    'name': card[1],
                    'card_id': card[2],
                    'edition': card[3],
                    'current_market_value': card[4],
                    'url': card[5]
                })
            
            cursor.close()
            conn.close()
            return card_list
            
        except psycopg2.Error as e:
            print(f"Error al obtener las cartas: {e}")
            if conn:
                conn.close()
            return []

    def update_card_price(self, card_id, new_price, new_url=None):
        """Actualiza el precio de una carta específica"""
        conn = self.connect_to_db()
        if not conn:
            return False
        
        try:
            cursor = conn.cursor()
            
            if new_url:
                query = """
                    UPDATE cards 
                    SET market_value = %s, url = %s
                    WHERE id = %s
                """
                cursor.execute(query, (new_price, new_url, card_id))
            else:
                query = """
                    UPDATE cards 
                    SET market_value = %s
                    WHERE id = %s
                """
                cursor.execute(query, (new_price, card_id))
            
            conn.commit()
            cursor.close()
            conn.close()
            return True
            
        except psycopg2.Error as e:
            print(f"Error al actualizar la carta {card_id}: {e}")
            if conn:
                conn.rollback()
                conn.close()
            return False

    def update_all_prices(self, delay_between_requests=2):
        """
        Actualiza los precios de todas las cartas en la base de datos
        
        Args:
            delay_between_requests (int): Tiempo de espera entre peticiones para evitar ser bloqueado
        """
        print("🚀 Iniciando actualización de precios de cartas...")
        print(f"⏰ Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 60)
        
        cards = self.get_all_cards()
        if not cards:
            print("❌ No se encontraron cartas para actualizar.")
            return
        
        print(f"📊 Se encontraron {len(cards)} cartas para actualizar.")
        print("-" * 60)
        
        updated_count = 0
        failed_count = 0
        skipped_count = 0
        
        for i, card in enumerate(cards, 1):
            print(f"\n[{i}/{len(cards)}] Procesando: {card['name']} #{card['card_id']}")
            print(f"   Edición: {card['edition']}")
            print(f"   Precio actual: ${card['current_market_value'] or 'N/A'}")
            
            try:
                # Extraer datos actualizados usando la función de extraer.py
                updated_data = extract_ungraded_card_data(
                    card['edition'],
                    card['name'], 
                    card['card_id']
                )
                
                if updated_data and updated_data.get('market_value') is not None:
                    new_price = updated_data['market_value']
                    new_url = updated_data.get('url')
                    
                    # Actualizar en la base de datos
                    success = self.update_card_price(card['id'], new_price, new_url)
                    
                    if success:
                        price_change = ""
                        if card['current_market_value']:
                            old_price = float(card['current_market_value'])
                            change = new_price - old_price
                            if change > 0:
                                price_change = f" (↗️ +${change:.2f})"
                            elif change < 0:
                                price_change = f" (↘️ ${change:.2f})"
                            else:
                                price_change = " (➡️ Sin cambio)"
                        
                        print(f"   ✅ Actualizado: ${new_price:.2f}{price_change}")
                        updated_count += 1
                    else:
                        print(f"   ❌ Error al actualizar en la base de datos")
                        failed_count += 1
                else:
                    print(f"   ⚠️  No se pudo obtener precio actualizado")
                    skipped_count += 1
                
                # Pausa entre peticiones para evitar ser bloqueado
                if i < len(cards):  # No hacer pausa en la última iteración
                    print(f"   ⏳ Esperando {delay_between_requests} segundos...")
                    time.sleep(delay_between_requests)
                    
            except Exception as e:
                print(f"   ❌ Error al procesar carta: {e}")
                failed_count += 1
        
        # Resumen final
        print("\n" + "=" * 60)
        print("📈 RESUMEN DE ACTUALIZACIÓN")
        print("=" * 60)
        print(f"✅ Cartas actualizadas exitosamente: {updated_count}")
        print(f"⚠️  Cartas omitidas (sin precio): {skipped_count}")
        print(f"❌ Cartas con errores: {failed_count}")
        print(f"📊 Total procesadas: {len(cards)}")
        print(f"⏰ Completado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

    def update_single_card(self, card_name, card_id, edition):
        """
        Actualiza el precio de una carta específica por nombre, ID y edición
        
        Args:
            card_name (str): Nombre de la carta
            card_id (str): ID de la carta
            edition (str): Edición de la carta
        """
        print(f"🔍 Buscando carta: {card_name} #{card_id} ({edition})")
        
        conn = self.connect_to_db()
        if not conn:
            return False
        
        try:
            cursor = conn.cursor()
            query = """
                SELECT id, market_value 
                FROM cards 
                WHERE name ILIKE %s AND card_id = %s AND edition ILIKE %s
            """
            cursor.execute(query, (f"%{card_name}%", card_id, f"%{edition}%"))
            result = cursor.fetchone()
            
            if not result:
                print("❌ Carta no encontrada en la base de datos")
                cursor.close()
                conn.close()
                return False
            
            db_card_id, current_price = result
            print(f"✅ Carta encontrada (ID: {db_card_id})")
            print(f"💰 Precio actual: ${current_price or 'N/A'}")
            
            cursor.close()
            conn.close()
            
            # Obtener precio actualizado
            print("🌐 Obteniendo precio actualizado...")
            updated_data = extract_ungraded_card_data(edition, card_name, card_id)
            
            if updated_data and updated_data.get('market_value') is not None:
                new_price = updated_data['market_value']
                new_url = updated_data.get('url')
                
                success = self.update_card_price(db_card_id, new_price, new_url)
                
                if success:
                    price_change = ""
                    if current_price:
                        old_price = float(current_price)
                        change = new_price - old_price
                        if change > 0:
                            price_change = f" (↗️ +${change:.2f})"
                        elif change < 0:
                            price_change = f" (↘️ ${change:.2f})"
                        else:
                            price_change = " (➡️ Sin cambio)"
                    
                    print(f"✅ Precio actualizado: ${new_price:.2f}{price_change}")
                    return True
                else:
                    print("❌ Error al actualizar en la base de datos")
                    return False
            else:
                print("❌ No se pudo obtener precio actualizado")
                return False
                
        except psycopg2.Error as e:
            print(f"❌ Error de base de datos: {e}")
            if conn:
                conn.close()
            return False

def main():
    """Función principal con menú interactivo"""
    updater = MarketUpdater()
    
    print("🎯 ACTUALIZADOR DE PRECIOS DE CARTAS")
    print("=" * 40)
    print("1. Actualizar todas las cartas")
    print("2. Actualizar una carta específica")
    print("3. Ver estadísticas de cartas en DB")
    print("4. Salir")
    print("=" * 40)
    
    while True:
        choice = input("\nSelecciona una opción (1-4): ").strip()
        
        if choice == "1":
            delay = input("Tiempo entre peticiones en segundos (default: 2): ").strip()
            delay = int(delay) if delay.isdigit() else 2
            updater.update_all_prices(delay_between_requests=delay)
            break
            
        elif choice == "2":
            card_name = input("Nombre de la carta: ").strip()
            card_id = input("ID de la carta: ").strip()
            edition = input("Edición: ").strip()
            
            if card_name and card_id and edition:
                updater.update_single_card(card_name, card_id, edition)
            else:
                print("❌ Todos los campos son requeridos")
            break
            
        elif choice == "3":
            cards = updater.get_all_cards()
            print(f"\n📊 Estadísticas:")
            print(f"   Total de cartas: {len(cards)}")
            if cards:
                with_prices = len([c for c in cards if c['current_market_value']])
                print(f"   Con precio: {with_prices}")
                print(f"   Sin precio: {len(cards) - with_prices}")
            break
            
        elif choice == "4":
            print("👋 ¡Hasta luego!")
            break
            
        else:
            print("❌ Opción inválida. Intenta de nuevo.")

if __name__ == "__main__":
    main()