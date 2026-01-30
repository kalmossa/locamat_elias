import psycopg2
from psycopg2 import OperationalError
import logging
import os
from dotenv import load_dotenv

load_dotenv()

# créer dossier logs
if not os.path.exists("logs"):
    os.makedirs("logs")

logging.basicConfig(
    filename="logs/db_errors.log",
    level=logging.ERROR,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

def log_critical_error(context, exception):
    logging.error(f"{context} | {exception}")

def get_connection():
    """
    Connexion PostgreSQL
    Support: DATABASE_URL (cloud) ou variables séparées (local)
    """
    try:
        # mode cloud 
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            # ajouter ssl si manquant
            if "sslmode=" not in database_url:
                sep = "&" if "?" in database_url else "?"
                database_url = f"{database_url}{sep}sslmode=require"
            return psycopg2.connect(database_url)

        # mode local
        sslmode = os.getenv("DB_SSLMODE")
        kwargs = {
            "host": os.getenv("DB_HOST"),
            "dbname": os.getenv("DB_NAME"),
            "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASSWORD"),
            "port": os.getenv("DB_PORT"),
            "options": "-c client_encoding=UTF8",
        }
        if sslmode:
            kwargs["sslmode"] = sslmode

        return psycopg2.connect(**kwargs)

    except OperationalError as e:
        log_critical_error("Connexion SGBD", e)
        return None