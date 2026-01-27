import psycopg2
from psycopg2 import OperationalError
import logging
import os

from dotenv import load_dotenv
load_dotenv()

# Création du dossier de logs (utile en local)
if not os.path.exists("logs"):
    os.makedirs("logs")

logging.basicConfig(
    filename="logs/db_errors.log",
    level=logging.ERROR,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

def log_critical_error(context, exception):
    logging.error(f"Contexte: {context} | Exception: {exception}")

def get_connection():
    """
    Connexion PostgreSQL.
    Supporte:
    - DATABASE_URL (recommandé cloud)
    - ou variables séparées DB_HOST/DB_NAME/DB_USER/DB_PASSWORD/DB_PORT
    Ajoute sslmode=require si nécessaire.
    """
    try:
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            # Neon/Supabase donnent souvent une URL avec sslmode=require déjà.
            # Si pas présent, on l'ajoute.
            if "sslmode=" not in database_url:
                sep = "&" if "?" in database_url else "?"
                database_url = f"{database_url}{sep}sslmode=require"
            return psycopg2.connect(database_url)

        # Fallback local (variables séparées)
        sslmode = os.getenv("DB_SSLMODE")  # ex: "require" (optionnel)
        kwargs = dict(
            host=os.getenv("DB_HOST"),
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            port=os.getenv("DB_PORT"),
            options="-c client_encoding=UTF8",
        )
        if sslmode:
            kwargs["sslmode"] = sslmode

        return psycopg2.connect(**kwargs)

    except OperationalError as e:
        log_critical_error("Connexion SGBD", e)
        return None
