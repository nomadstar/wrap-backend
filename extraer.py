import requests
from bs4 import BeautifulSoup
import json

def format_for_url(text):
    """Convierte un texto a formato para URL (minúsculas, espacios a guiones)."""
    return text.lower().replace(' ', '-')

def clean_price_value(price_text):
    """Limpia el valor del precio y lo convierte a float si es posible."""
    if not price_text or price_text == '-':
        return None
    
    cleaned = price_text.replace('$', '').replace(',', '').strip()
    try:
        return float(cleaned)
    except ValueError:
        return None

def extract_ungraded_card_data(edition_name, card_name_input, card_number_input):
    """
    Extrae la información y el precio Ungraded de una carta de Pokémon TCG
    desde pricecharting.com.

    Args:
        edition_name (str): El nombre de la edición (ej: "Pokemon Ultra Prism").
        card_name_input (str): El nombre de la carta (ej: "Frost Rotom").
        card_number_input (str): El número de la carta (ej: "41").

    Returns:
        dict: Un diccionario con la información y el precio Ungraded de la carta,
              o None si ocurre un error.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    # --- 1. Construir la URL ---
    try:
        formatted_edition = format_for_url(edition_name)
        formatted_card_name = format_for_url(card_name_input)
        card_number_str = str(card_number_input)
        url = f"https://www.pricecharting.com/game/{formatted_edition}/{formatted_card_name}-{card_number_str}"
        print(f"URL construida: {url}")
    except Exception as e:
        print(f"Error al construir la URL: {e}")
        return None

    # --- 2. Realizar la petición y parsear el HTML ---
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Lanza un error para respuestas HTTP malas (4xx o 5xx)
    except requests.exceptions.HTTPError as e:
        if response.status_code == 404:
            print(f"Error: La página no fue encontrada (404) para la URL: {url}. Verifica los nombres y números.")
        else:
            print(f"Error HTTP al realizar la petición: {e}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error de conexión al realizar la petición HTTP: {e}")
        return None

    soup = BeautifulSoup(response.content, 'html.parser')

    # --- 3. Extraer el precio Ungraded ---
    ungraded_price = None  # Valor por defecto
    try:
        price_table = soup.find('table', id='price_data')
        if not price_table:
            print("Error: No se encontró la tabla de precios (id='price_data').")
            # Continuamos para devolver otros datos aunque falte el precio
        else:
            price_cell = price_table.find('td', id='used_price')
            if price_cell:
                price_span = price_cell.find('span', class_='price')
                if price_span:
                    price_text = price_span.text.strip()
                    ungraded_price = clean_price_value(price_text)
    except Exception as e:
        print(f"Error al extraer el precio de la tabla: {e}")

    # --- 4. Construir el objeto JSON de salida ---
    card_data_output = {
        "name": card_name_input.title(),
        "card_id": str(card_number_input),
        "edition": edition_name,
        "market_value": ungraded_price,  # Ahora es float o None
        "url": url,
        "in_pool": "true",
        "user_wallet": "null"
    }

    return card_data_output

def save_to_json(data, filename="card_data.json"):
    """
    Guarda los datos (un diccionario) en un archivo JSON.
    """
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Datos guardados exitosamente en {filename}")
    except IOError as e:
        print(f"Error al guardar el archivo JSON: {e}")
    except TypeError as e:
        print(f"Error de tipo al convertir a JSON: {e}")


# --- Ejemplo de uso ---
if __name__ == "__main__":
    # Solicitar datos al usuario
    input_edition = input("Ingresa la edición de la carta (ej: Pokemon Ultra Prism): ")
    input_card_name = input("Ingresa el nombre de la carta (ej: Frost Rotom): ")
    input_card_number = input("Ingresa el número de la carta (ej: 41): ")

    if input_edition == "" or input_card_name == "" or input_card_number == "":
        input_edition = "Pokemon Ultra Prism"
        input_card_name = "Frost Rotom"
        input_card_number = "41"
        

    print(f"\nExtrayendo datos para: {input_card_name} #{input_card_number} de la edición {input_edition}")
    
    # La función ahora devuelve un único diccionario con el precio Ungraded
    card_data = extract_ungraded_card_data(input_edition, input_card_name, input_card_number)

    if card_data:
        print("\n--- Datos Extraídos ---")
        print(json.dumps(card_data, indent=2))
        print("-----------------------\n")
        
        # Generar un nombre de archivo dinámico
        safe_card_name = format_for_url(input_card_name)
        json_filename = f"{safe_card_name}_{input_card_number}_data.json"
        save_to_json(card_data, json_filename)
    else:
        print(f"No se pudieron extraer los datos para {input_card_name} #{input_card_number}.")