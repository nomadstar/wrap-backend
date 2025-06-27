import requests
from bs4 import BeautifulSoup
import json
import extraer
import os
import sys
import psycopg2
import time

def clean_dollar_signs(json_obj):
    """
    Remove any dollar sign ($) from string values in a JSON object.
    Returns a new cleaned JSON object.
    """
    if isinstance(json_obj, list):
        return [clean_dollar_signs(item) for item in json_obj]
    
    if not isinstance(json_obj, dict):
        return json_obj
        
    cleaned_obj = {}
    for key, value in json_obj.items():
        if isinstance(value, str):
            cleaned_obj[key] = value.replace('$', '')
        elif isinstance(value, (dict, list)):
            cleaned_obj[key] = clean_dollar_signs(value)
        else:
            cleaned_obj[key] = value
    return cleaned_obj

def watch_and_insert_json_clean_dollars(directory, table_name, db_url, poll_interval=5):
    processed_files = set()
    while True:
        if not os.path.exists(directory):
            print(f"Directorio {directory} no existe. Esperando...")
            time.sleep(poll_interval)
            continue
        found = False
        for filename in os.listdir(directory):
            if filename.endswith('.json') and filename not in processed_files:
                found = True
                json_file_path = os.path.join(directory, filename)
                with open(json_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        data = [data]
                    for json_obj in data:
                        cleaned_json_obj = clean_dollar_signs(json_obj)
                        insert_stmt = json_to_insert(table_name, cleaned_json_obj)
                        try:
                            conn = psycopg2.connect(db_url)
                            cur = conn.cursor()
                            cur.execute(insert_stmt)
                            conn.commit()
                            cur.close()
                            conn.close()
                            print(f"Registro insertado correctamente desde {filename}.")
                        except Exception as e:
                            print(f"Error al insertar el registro desde {filename}: {e}")
                processed_files.add(filename)
        if not found:
            print("Esperando archivos .json en", directory)
        time.sleep(poll_interval)

def json_to_insert(table_name, json_obj):
    columns = ', '.join(json_obj.keys())
    values = []
    for v in json_obj.values():
        if isinstance(v, str):
            # Escapar comillas simples duplicándolas
            escaped_value = str(v).replace("'", "''")
            values.append(f"'{escaped_value}'")
        else:
            values.append(str(v))
    
    values_str = ', '.join(values)
    insert_stmt = f"INSERT INTO {table_name} ({columns}) VALUES ({values_str});"
    return insert_stmt

def insert_card_data_to_db(edition_name, card_name, card_number, table_name, db_url):
    # Extraer datos de la carta
    card_data = extraer.extract_ungraded_card_data(edition_name, card_name, card_number)
    if not card_data:
        print("No se pudo extraer la información de la carta.")
        return False

    # Generar el statement de inserción
    insert_stmt = json_to_insert(table_name, card_data)
    # Realizar la inserción en la base de datos PostgreSQL
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute(insert_stmt)
        conn.commit()
        cur.close()
        conn.close()
        print("Datos insertados correctamente en la base de datos.")
        return True
    except Exception as e:
        print(f"Error al insertar en la base de datos: {e}")
        return False

def watch_and_insert_json(directory, table_name, db_url, poll_interval=5):
    processed_files = set()
    while True:
        if not os.path.exists(directory):
            print(f"Directorio {directory} no existe. Esperando...")
            time.sleep(poll_interval)
            continue

        found = False
        for filename in os.listdir(directory):
            if filename.endswith('.json') and filename not in processed_files:
                found = True
                json_file_path = os.path.join(directory, filename)
                with open(json_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        data = [data]
                    for json_obj in data:
                        insert_stmt = json_to_insert(table_name, json_obj)
                        try:
                            conn = psycopg2.connect(db_url)
                            cur = conn.cursor()
                            cur.execute(insert_stmt)
                            conn.commit()
                            cur.close()
                            conn.close()
                            print(f"Registro insertado correctamente desde {filename}.")
                        except Exception as e:
                            print(f"Error al insertar el registro desde {filename}: {e}")
                processed_files.add(filename)
        if not found:
            print("Esperando archivos .json en", directory)
        time.sleep(poll_interval)

if __name__ == "__main__":
    # Configuración de la base de datos desde compose.yaml
    DB_NAME = "mydatabase"
    DB_USER = "user"
    DB_PASSWORD = "password"
    DB_HOST = "db"
    DB_PORT = "5432"
    TABLE_NAME = "cards"  # Cambia esto por el nombre real de tu tabla

    DB_URL = f"dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD} host={DB_HOST} port={DB_PORT}"

    # Directorio a observar
    directory_to_watch = "."

    # Esperar hasta que el directorio exista y luego observar
    try:
        while not os.path.exists(directory_to_watch):
            print(f"Directorio {directory_to_watch} no existe. Esperando...")
            time.sleep(5)
        watch_and_insert_json_clean_dollars(directory_to_watch, TABLE_NAME, DB_URL)
    except psycopg2.OperationalError as e:
        print(f"Error de conexión a la base de datos: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("Finalizando la observación de archivos.")
    except Exception as e:
        print(f"Error al observar el directorio: {e}")
        sys.exit(1)
