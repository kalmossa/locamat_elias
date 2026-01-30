LOCA-MAT ENTREPRISE est une application de gestion de location de matériel informatique et industriel développée dans le cadre du module SGBD – Bac Informatique 3e année.

Le projet répond à un cahier des charges professionnel imposant :

une base de données relationnelle normalisée,

des règles métier strictes,

une architecture logicielle en couches (DAL / BLL / UI),

une gestion transactionnelle et concurrente des locations,

un déploiement sur une base de données Cloud.

L’objectif est de remplacer une gestion Excel devenue inefficace par un système robuste, cohérent et traçable.

Prérequis pour relancer le projet
3.1 Logiciels nécessaires
Python 3.10+
PostgreSQL 14+
pgAdmin 4
Git

Vérifier :
python --version
psql --version

1. Créer le serveur PostgreSQL (si nécessaire)

Dans pgAdmin 4 :

clic droit sur Servers
Register > Server
Onglet General :
Name : LOCA-MAT
Onglet Connection :
Host name/address : localhost
Port : 5432
Username : postgres (ou ton user)
Password : ton mot de passe PostgreSQL

2. Créer la base de données
clic droit sur le serveur → Create > Database
Database name : locamat
Owner : ton user PostgreSQL

3. Exécuter les 2 script SQL

4. puisCréer un environnement virtuel
python -m venv venv

Activation :

Windows :
venv\Scripts\activate


Linux / macOS :
source venv/bin/activate

2. Installer les dépendances
pip install -r requirements.txt

3. Créer le fichier .env À la racine du projet :

FLASK_SECRET_KEY=dev-secret
DB_HOST=localhost
DB_NAME=locamat
DB_USER=postgres
DB_PASSWORD=TON_MOT_DE_PASSE
DB_PORT=5432

Lancement de l’application
python app.py
Par défaut :

cpp
Copier le code
http://127.0.0.1:5000 

et avec ce lien en cloud : https://locamat-elias.onrender.com

Les erreurs SQL critiques sont loggées dans :

logs/db_errors.log

+) Reset complet de la DB 

faire: 

DROP TABLE IF EXISTS retours CASCADE;
DROP TABLE IF EXISTS lignes_contrat CASCADE;
DROP TABLE IF EXISTS contrats_location CASCADE;
DROP TABLE IF EXISTS articles CASCADE;
DROP TABLE IF EXISTS marques CASCADE;
DROP TABLE IF EXISTS categories CASCADE;
DROP TABLE IF EXISTS clients CASCADE;