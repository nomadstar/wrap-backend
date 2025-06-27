import psycopg2
from extraer import extract_ungraded_card_data
import time

# Configuración de la base de datos (ajusta si es necesario)
DB_NAME = "mydatabase"
DB_USER = "user"
DB_PASSWORD = "password"
DB_HOST = "localhost"
DB_PORT = "5432"
TABLE_NAME = "cards"

DB_URL = f"dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD} host={DB_HOST} port={DB_PORT}"

def update_all_card_prices():
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("SELECT id, edition, name, card_id FROM cards WHERE in_pool = TRUE;")
        cards = cur.fetchall()
        print(f"Se encontraron {len(cards)} cartas para actualizar.")
        updated = 0

        for card in cards:
            card_db_id, edition, name, card_number = card
            print(f"\nActualizando: {name} #{card_number} ({edition})")
            card_data = extract_ungraded_card_data(edition, name, card_number)
            if card_data and card_data["market_value"] != "N/A":
                # Limpiar el símbolo $ si existe
                new_value = str(card_data["market_value"]).replace("$", "").replace(",", "")
                try:
                    cur.execute(
                        "UPDATE cards SET market_value = %s WHERE id = %s;",
                        (new_value, card_db_id)
                    )
                    conn.commit()
                    print(f"Precio actualizado a {new_value} USD.")
                    updated += 1
                except Exception as e:
                    print(f"Error al actualizar en la base de datos: {e}")
            else:
                print("No se pudo obtener el precio actualizado para esta carta.")
            time.sleep(1)  # Para evitar ser bloqueado por el sitio web

        cur.close()
        conn.close()
        print(f"\nActualización completada. {updated} cartas actualizadas.")
    except Exception as e:
        print(f"Error general: {e}")

if __name__ == "__main__":
    update_all_card_prices() 