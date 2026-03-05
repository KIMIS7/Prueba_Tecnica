import os
import hashlib
import json
import pandas as pd
import requests
from sqlalchemy import create_engine
from dotenv import load_dotenv
from datetime import date

# ============================================================
# 1. CARGAR VARIABLES DE ENTORNO
# ============================================================
# Las credenciales nunca se escriben directo en el codigo.
# Se leen desde el archivo .env para mantenerlas seguras.
load_dotenv()

DB_HOST     = os.getenv("DB_HOST")
DB_PORT     = os.getenv("DB_PORT")
DB_NAME     = os.getenv("DB_NAME")
DB_USER     = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# Credenciales de Meta (se agregan al .env, nunca en el codigo)
META_ACCESS_TOKEN   = os.getenv("META_ACCESS_TOKEN")    # Token de acceso de larga duracion
META_AD_ACCOUNT_ID  = os.getenv("META_AD_ACCOUNT_ID")   # act_XXXXXXXXXX
META_AUDIENCE_NAME  = "Exclusion - Borrowers Activos"

# ============================================================
# 2. QUERY (ejercicio 1c)
# ============================================================
QUERY = """
    SELECT DISTINCT ON (a.user_id)
        a.email,
        a.phone,
        a.user_id,
        DATE(a.booking_created_at) AS disbursement_date
    FROM app_master a
    WHERE a.booking = TRUE
      AND a.email   IS NOT NULL
      AND a.phone   IS NOT NULL
    ORDER BY a.user_id, a.booking_created_at DESC;
"""

# ============================================================
# 3. EXPORTAR CSV
# ============================================================
def exportar_csv(df):
    today    = date.today().strftime("%Y-%m-%d")
    filename = f"exclusion_audience_{today}.csv"
    df.to_csv(filename, index=False)
    print(f"Archivo exportado: {filename}")
    return filename

# ============================================================
# 4. HASHEAR DATOS PARA META
# ============================================================
# Meta requiere que los datos personales (email, telefono)
# vengan hasheados en SHA-256 antes de enviarlos.
# Esto protege la privacidad del usuario.
#
# Ejemplo:
#   "ana.garcia@gmail.com" -> "a3f2c1d4e5b6..."
#
def hashear(valor):
    if valor is None:
        return None
    return hashlib.sha256(valor.strip().lower().encode()).hexdigest()

# ============================================================
# 5. CREAR AUDIENCIA EN META (si no existe)
# ============================================================
# Endpoint: POST /act_{ad_account_id}/customaudiences
# Documentacion: https://developers.facebook.com/docs/marketing-api/audiences
#
def crear_audiencia():
    url = f"https://graph.facebook.com/v19.0/{META_AD_ACCOUNT_ID}/customaudiences"

    payload = {
        "name":        META_AUDIENCE_NAME,
        "subtype":     "CUSTOM",              # Audiencia de lista de clientes
        "description": "Usuarios con prestamo desembolsado - excluir de campanas",
        "customer_file_source": "USER_PROVIDED_ONLY",
        "access_token": META_ACCESS_TOKEN
    }

    response = requests.post(url, data=payload)

    if response.status_code == 200:
        audience_id = response.json().get("id")
        print(f"Audiencia creada con ID: {audience_id}")
        return audience_id
    else:
        print(f"Error al crear audiencia: {response.text}")
        return None

# ============================================================
# 6. SUBIR USUARIOS A LA AUDIENCIA
# ============================================================
# Endpoint: POST /{audience_id}/users
#
# Meta acepta hasta 10,000 usuarios por llamada (batch).
# Si tienes mas, hay que dividirlos en chunks.
#
# El payload tiene este formato:
# {
#   "schema": ["EMAIL", "PHONE"],
#   "data": [
#     ["hash_email_1", "hash_phone_1"],
#     ["hash_email_2", "hash_phone_2"],
#     ...
#   ]
# }
#
def subir_usuarios(audience_id, df):
    url = f"https://graph.facebook.com/v19.0/{audience_id}/users"

    # Hashear todos los emails y telefonos
    data = [
        [hashear(row["email"]), hashear(row["phone"])]
        for _, row in df.iterrows()
    ]

    # Dividir en chunks de 10,000 (limite de Meta por llamada)
    chunk_size = 10000
    chunks     = [data[i:i+chunk_size] for i in range(0, len(data), chunk_size)]

    for i, chunk in enumerate(chunks):
        payload = {
            "payload": json.dumps({
                "schema": ["EMAIL", "PHONE"],
                "data":   chunk
            }),
            "access_token": META_ACCESS_TOKEN
        }

        response = requests.post(url, data=payload)

        # Manejo de errores
        if response.status_code == 200:
            print(f"Chunk {i+1}/{len(chunks)} subido correctamente ({len(chunk)} usuarios)")

        elif response.status_code == 429:
            # Rate limit: Meta permite ~200 llamadas por hora por token
            # En produccion aqui iria un tiempo de espera (time.sleep)
            print(f"Rate limit alcanzado en chunk {i+1}. Reintentar en 1 hora.")
            break

        else:
            error = response.json().get("error", {})
            print(f"Error en chunk {i+1}: {error.get('message', response.text)}")
            break

# ============================================================
# 7. FLUJO PRINCIPAL
# ============================================================
def main():
    print("Conectando a la base de datos...")

    try:
        engine = create_engine(
            f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        )
        print("Conexion exitosa")

        df = pd.read_sql_query(QUERY, engine)
        print(f"Query ejecutada -- {len(df)} usuarios encontrados")

        # Paso 1: exportar CSV local
        exportar_csv(df)

        # Paso 2: subir a Meta
        print("Subiendo audiencia a Meta...")
        audience_id = crear_audiencia()

        if audience_id:
            subir_usuarios(audience_id, df)
            print("Proceso completado.")
        else:
            print("No se pudo crear la audiencia en Meta.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()