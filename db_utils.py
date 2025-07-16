# db_utils.py
# Utilidades para manejo de base de datos

import psycopg2
import urllib.parse
import os
from functools import wraps
from datetime import datetime

def get_db_connection():
    """
    Obtiene una conexión a la base de datos
    """
    DATABASE_URL = os.getenv('DATABASE_URL')
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL no está definido")
    
    url = urllib.parse.urlparse(DATABASE_URL)
    return psycopg2.connect(
        dbname=url.path[1:],
        user=url.username,
        password=url.password,
        host=url.hostname,
        port=url.port
    )

def execute_query(query, params=None, fetch_one=False, fetch_all=False, return_id=False):
    """
    Ejecuta una consulta SQL y maneja la conexión automáticamente
    
    Args:
        query: Consulta SQL a ejecutar
        params: Parámetros para la consulta
        fetch_one: Si debe retornar un solo resultado
        fetch_all: Si debe retornar todos los resultados
        return_id: Si debe retornar el ID del registro insertado
    
    Returns:
        Resultado de la consulta según los parámetros especificados
    """
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute(query, params or ())
        
        if return_id:
            result = cur.fetchone()[0]
        elif fetch_one:
            result = cur.fetchone()
        elif fetch_all:
            result = cur.fetchall()
        else:
            result = None
        
        conn.commit()
        return result
        
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

def execute_query_with_columns(query, params=None, fetch_one=False):
    """
    Ejecuta una consulta y retorna el resultado con nombres de columnas
    """
    import logging
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(query, params or ())
        columns = [desc[0] for desc in cur.description]
        if fetch_one:
            row = cur.fetchone()
            if row:
                if len(columns) != len(row):
                    print(f"[DEBUG] Desajuste columnas/valores: columnas={columns}, valores={row}, n_col={len(columns)}, n_val={len(row)}")
                return dict(zip(columns, row))
            return None
        else:
            rows = cur.fetchall()
            for r in rows:
                if len(columns) != len(r):
                    print(f"[DEBUG] Desajuste columnas/valores: columnas={columns}, valores={r}, n_col={len(columns)}, n_val={len(r)}")
            return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        raise e
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

def batch_execute(queries_and_params):
    """
    Ejecuta múltiples consultas en una sola transacción
    
    Args:
        queries_and_params: Lista de tuplas (query, params)
    
    Returns:
        Lista de resultados
    """
    conn = None
    cur = None
    results = []
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        for query, params in queries_and_params:
            cur.execute(query, params or ())
            try:
                result = cur.fetchone()
                results.append(result[0] if result else None)
            except:
                results.append(None)
        
        conn.commit()
        return results
        
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

def check_record_exists(table, field, value):
    """
    Verifica si existe un registro en una tabla
    """
    query = f"SELECT 1 FROM {table} WHERE {field} = %s LIMIT 1;"
    result = execute_query(query, (value,), fetch_one=True)
    return result is not None

def get_record_by_field(table, field, value, columns="*"):
    """
    Obtiene un registro por un campo específico
    """
    query = f"SELECT {columns} FROM {table} WHERE {field} = %s;"
    return execute_query_with_columns(query, (value,), fetch_one=True)

def get_records_by_field(table, field, value, columns="*", order_by=None):
    """
    Obtiene múltiples registros por un campo específico
    """
    query = f"SELECT {columns} FROM {table} WHERE {field} = %s"
    if order_by:
        query += f" ORDER BY {order_by}"
    query += ";"
    return execute_query_with_columns(query, (value,))

def soft_delete_record(table, record_id):
    """
    Realiza un soft delete (marcado con timestamp) de un registro
    """
    query = f"UPDATE {table} SET removed_at = %s WHERE id = %s;"
    execute_query(query, (datetime.now(), record_id))

def restore_record(table, record_id):
    """
    Restaura un registro soft-deleted
    """
    query = f"UPDATE {table} SET removed_at = NULL WHERE id = %s;"
    execute_query(query, (record_id,))

def permanent_delete_record(table, record_id):
    """
    Elimina permanentemente un registro
    """
    query = f"DELETE FROM {table} WHERE id = %s;"
    execute_query(query, (record_id,))

def update_record_fields(table, record_id, field_updates):
    """
    Actualiza campos específicos de un registro
    
    Args:
        table: Nombre de la tabla
        record_id: ID del registro a actualizar
        field_updates: Diccionario con campo: valor a actualizar
    """
    if not field_updates:
        return False
    
    set_clauses = []
    values = []
    
    for field, value in field_updates.items():
        if value is None:
            set_clauses.append(f"{field} = NULL")
        else:
            set_clauses.append(f"{field} = %s")
            values.append(value)
    
    values.append(record_id)
    query = f"UPDATE {table} SET {', '.join(set_clauses)} WHERE id = %s;"
    
    execute_query(query, values)
    return True
