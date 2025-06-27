from flask import Flask, request, jsonify
import os
import psycopg2
import extraer
from parsetodb import json_to_insert

# filepath: /home/ignatus/Documentos/Github/WrapSell/backend_local/app.py

app = Flask(__name__)

# Configuración de la base de datos desde compose.yaml
DB_NAME = "mydatabase"
DB_USER = "user"
DB_PASSWORD = "password"
DB_HOST = "db"
DB_PORT = "5432"
TABLE_NAME = "cards"  # Cambia esto por el nombre real de tu tabla

DB_URL = f"dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD} host={DB_HOST} port={DB_PORT}"

@app.route('/cards', methods=['GET'])
def get_cards():
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("SELECT * FROM cards;")
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        cards = [dict(zip(columns, row)) for row in rows]
        cur.close()
        conn.close()
        return jsonify(cards), 200
    except Exception as e:
        return jsonify({"error": f"Error al obtener las cartas: {e}"}), 500

@app.route('/cards/<int:card_id>', methods=['GET'])
def get_card(card_id):
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("SELECT * FROM cards WHERE id = %s;", (card_id,))
        row = cur.fetchone()
        columns = [desc[0] for desc in cur.description]
        cur.close()
        conn.close()
        if row:
            return jsonify(dict(zip(columns, row))), 200
        else:
            return jsonify({"error": "Carta no encontrada"}), 404
    except Exception as e:
        return jsonify({"error": f"Error al obtener la carta: {e}"}), 500

@app.route('/cards', methods=['POST'])
def create_card():
    data = request.get_json()
    required_fields = ['name', 'card_id', 'edition', 'market_value']
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Faltan campos requeridos"}), 400
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO cards (name, card_id, edition, user_wallet, url, market_value, in_pool)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """, (
            data['name'],
            data['card_id'],
            data.get('edition'),
            data.get('user_wallet'),
            data.get('url'),
            data['market_value'],
            data.get('in_pool', True)
        ))
        new_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Carta creada correctamente", "id": new_id}), 201
    except Exception as e:
        return jsonify({"error": f"Error al crear la carta: {e}"}), 500

@app.route('/cards/<int:card_id>', methods=['PUT'])
def update_card(card_id):
    data = request.get_json()
    fields = []
    values = []
    for key in ['name', 'card_id', 'edition', 'user_wallet', 'url', 'market_value', 'in_pool']:
        if key in data:
            fields.append(f"{key} = %s")
            values.append(data[key])
    if not fields:
        return jsonify({"error": "No se proporcionaron campos para actualizar"}), 400
    values.append(card_id)
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute(f"""
            UPDATE cards SET {', '.join(fields)} WHERE id = %s;
        """, tuple(values))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Carta actualizada correctamente"}), 200
    except Exception as e:
        return jsonify({"error": f"Error al actualizar la carta: {e}"}), 500

@app.route('/cards/<int:card_id>', methods=['DELETE'])
def delete_card(card_id):
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("DELETE FROM cards WHERE id = %s;", (card_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Carta eliminada correctamente"}), 200
    except Exception as e:
        return jsonify({"error": f"Error al eliminar la carta: {e}"}), 500
    
@app.route('/users', methods=['POST'])
def create_user():
    data = request.get_json()
    required_fields = ['wallet_address', 'wallet_type']
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Faltan campos requeridos"}), 400
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (wallet_address, wallet_type, username, email)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (wallet_address) DO NOTHING;
        """, (
            data['wallet_address'],
            data['wallet_type'],
            data.get('username'),
            data.get('email')
        ))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Usuario creado correctamente"}), 201
    except Exception as e:
        return jsonify({"error": f"Error al crear el usuario: {e}"}), 500
    
@app.route('/total_value', methods=['GET'])
def get_total_value():
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(SUM(market_value), 0) FROM cards WHERE in_pool = TRUE;")
        total = cur.fetchone()[0]
        cur.close()
        conn.close()
        return jsonify({"total_collection_value": float(total)}), 200
    except Exception as e:
        return jsonify({"error": f"Error al calcular el valor total: {e}"}), 500
    
@app.route('/update_prices', methods=['POST'])
def update_prices_endpoint():
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("SELECT id, edition, name, card_id FROM cards WHERE in_pool = TRUE;")
        cards = cur.fetchall()
        updated = 0
        not_updated = []

        for card in cards:
            card_db_id, edition, name, card_number = card
            card_data = extraer.extract_ungraded_card_data(edition, name, card_number)
            if card_data and card_data["market_value"] != "N/A":
                new_value = str(card_data["market_value"]).replace("$", "").replace(",", "")
                try:
                    cur.execute(
                        "UPDATE cards SET market_value = %s WHERE id = %s;",
                        (new_value, card_db_id)
                    )
                    conn.commit()
                    updated += 1
                except Exception as e:
                    not_updated.append({"id": card_db_id, "error": str(e)})
            else:
                not_updated.append({"id": card_db_id, "error": "No se pudo obtener el precio actualizado"})
        cur.close()
        conn.close()
        return jsonify({
            "message": f"Precios actualizados para {updated} cartas.",
            "not_updated": not_updated
        }), 200
    except Exception as e:
        return jsonify({"error": f"Error general al actualizar precios: {e}"}), 500
    
    
@app.route('/users/<string:wallet_address>/cards', methods=['GET'])
def get_user_cards(wallet_address):
    """
    Retorna todas las cartas asociadas a una dirección de billetera específica.
    """
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # Ejecuta una consulta para seleccionar las cartas filtrando por user_wallet
        cur.execute("SELECT * FROM cards WHERE user_wallet = %s;", (wallet_address,))
        
        rows = cur.fetchall()
        
        # Si no se encuentran cartas, fetchall() devuelve una lista vacía, lo cual es correcto.
        
        columns = [desc[0] for desc in cur.description]
        cards = [dict(zip(columns, row)) for row in rows]
        
        cur.close()
        conn.close()
        
        return jsonify(cards), 200
    except Exception as e:
        return jsonify({"error": f"Error al obtener las cartas del usuario: {e}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)