import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
from datetime import date

# ============================================================
# 1. CARGAR VARIABLES DE ENTORNO
# ============================================================
load_dotenv()

DB_HOST     = os.getenv("DB_HOST")
DB_PORT     = os.getenv("DB_PORT")
DB_NAME     = os.getenv("DB_NAME")
DB_USER     = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# ============================================================
# 2. QUERY (la misma del ejercicio 1c)
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
# 3. CONECTAR, EJECUTAR Y EXPORTAR
# ============================================================
def main():
    print("Conectando a la base de datos...")

    try:
        # SQLAlchemy arma la URL de conexion con todas las credenciales
        # Formato: postgresql://usuario:password@host:puerto/base_de_datos
        engine = create_engine(
            f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        )
        print("Conexion exitosa")

        # Ejecuta la query y carga el resultado en un DataFrame
        df = pd.read_sql_query(QUERY, engine)
        print(f"Query ejecutada -- {len(df)} usuarios encontrados")

        # Genera el nombre del archivo con la fecha de hoy
        today    = date.today().strftime("%Y-%m-%d")
        filename = f"exclusion_audience_{today}.csv"

        # Exporta el DataFrame a CSV
        df.to_csv(filename, index=False)
        print(f"Archivo exportado: {filename}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()