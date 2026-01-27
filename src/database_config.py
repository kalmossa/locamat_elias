import psycopg2
from psycopg2 import OperationalError
import logging
import os

from dotenv import load_dotenv
load_dotenv()

# Création du dossier de logs
if not os.path.exists("logs"):
    os.makedirs("logs")

logging.basicConfig(
    filename="logs/db_errors.log",
    level=logging.ERROR,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

def log_critical_error(context, exception):
    """ Enregistre l'erreur technique pour le développeur. """
    logging.error(f"Contexte: {context} | Exception: {exception}")

def get_connection():
    """
    Retourne une connexion psycopg2.
    Les identifiants viennent du .env.
    """
    try:
        return psycopg2.connect(
            host=os.getenv("DB_HOST"),
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            port=os.getenv("DB_PORT"),
            options="-c client_encoding=UTF8",
        )
    except OperationalError as e:
        log_critical_error("Connexion SGBD", e)
        return None
