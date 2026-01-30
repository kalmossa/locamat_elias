import os
from datetime import date
from flask import Flask, render_template, request, redirect, url_for, session
from psycopg2 import OperationalError
from src.bll.locamat_service import LocamatService
from src.database_config import get_connection


def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret")
    service = LocamatService()

    @app.route("/")
    def home():
        return render_template("home.html", title="LOCA-MAT ENTREPRISE")

    @app.route("/dashboard/ui")
    def dashboard_ui():
        dash = service.dashboard()
        return render_template("dashboard.html", title="Dashboard", dash=dash)

    @app.route("/dashboard")
    def dashboard():
        return service.dashboard()

    # check si db ok
    @app.route("/health")
    def health():
        conn = None
        try:
            conn = get_connection()
            if not conn:
                return {"status": "ok", "db": "error", "detail": "No connection"}, 503
            
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()
            return {"status": "ok", "db": "ok"}
        except OperationalError as e:
            return {"status": "ok", "db": "error", "detail": str(e)}, 503
        except Exception as e:
            return {"status": "ok", "db": "error", "detail": str(e)}, 500
        finally:
            if conn:
                conn.close()

    # liste articles avec leur loc en cours
    @app.route("/articles/ui")
    def articles_ui():
        data = service.lister_articles_avec_location()
        stock = service.stock_resume()
        return render_template("articles_list.html", title="Articles", articles=data, stock=stock)

    @app.route("/articles")
    def articles():
        items = service.lister_articles()
        return {"count": len(items), "items": items}

    @app.route("/articles/disponibles")
    def articles_disponibles():
        items = service.lister_articles_disponibles()
        return {"count": len(items), "items": items}

    # changer statut article (dispo/maintenance/rebut)
    @app.route("/articles/<int:id_article>/statut", methods=["POST"])
    def update_article_statut(id_article):
        try:
            new_statut = request.form.get("statut", "")
            service.changer_statut_article(id_article, new_statut)
            return redirect(url_for("articles_ui"))
        except RuntimeError as e:
            return render_template("error.html", title="Changement impossible", message=str(e)), 409
        except Exception as e:
            return render_template("error.html", title="Erreur", message=str(e)), 500

    # supprimer article
    @app.route("/articles/<int:id_article>/delete", methods=["POST"])
    def delete_article(id_article):
        try:
            service.supprimer_article(id_article)
            return redirect(url_for("articles_ui"))
        except RuntimeError as e:
            return render_template("error.html", title="Suppression impossible", message=str(e)), 409
        except Exception as e:
            return render_template("error.html", title="Erreur", message=str(e)), 500

    # page confirmation (pattern PRG)
    @app.route("/message/ui")
    def message_ui():
        payload = session.pop("last_payload", None)
        title = session.pop("last_title", "Message")
        if not payload:
            return redirect(url_for("home"))
        return render_template("message.html", title=title, payload=payload)

    # créer contrat location
    @app.route("/contrats/ui", methods=["GET", "POST"])
    def contrats_ui():
        if request.method == "GET":
            clients = service.lister_clients()
            articles_dispo = service.lister_articles_disponibles()
            return render_template("contrat_form.html", title="Créer un contrat",
                                 clients=clients, articles_dispo=articles_dispo)

        try:
            # récup client
            raw_client = (request.form.get("id_client") or "").strip()
            if not raw_client:
                raise ValueError("Choisis un client.")

            # récup dates
            date_debut_str = request.form.get("date_debut")
            date_fin_str = request.form.get("date_fin_prevue")
            if not date_debut_str or not date_fin_str:
                raise ValueError("Dates obligatoires.")

            date_debut = date.fromisoformat(date_debut_str)
            date_fin = date.fromisoformat(date_fin_str)

            # récup articles
            article_ids = [int(x) for x in request.form.getlist("article_ids")]
            if not article_ids:
                raise ValueError("Sélectionne au moins un article disponible.")

            # si nouveau client, créer d'abord
            if raw_client == "__NEW__":
                nom = (request.form.get("new_nom") or "").strip()
                prenom = (request.form.get("new_prenom") or "").strip()
                est_vip = (request.form.get("new_est_vip") == "on")
                if not nom or not prenom:
                    raise ValueError("Nom et prénom obligatoires pour un nouveau client.")

                payload_client = service.creer_client(nom, prenom, est_vip)
                id_client = int(payload_client["id_client"])
            else:
                id_client = int(raw_client)

            # valider le contrat
            result = service.valider_contrat(id_client, date_debut, date_fin, article_ids)

            # PRG : éviter double soumission
            session["last_payload"] = result
            session["last_title"] = "Contrat validé"
            return redirect(url_for("message_ui"))

        except Exception as e:
            clients = service.lister_clients()
            articles_dispo = service.lister_articles_disponibles()
            return render_template("contrat_form.html", title="Créer un contrat",
                                 clients=clients, articles_dispo=articles_dispo, error=str(e)), 400

    # enregistrer retour
    @app.route("/retours/ui", methods=["GET", "POST"])
    def retours_ui():
        if request.method == "GET":
            retours = service.lister_retours_possibles()
            return render_template("retour_form.html", title="Enregistrer un retour", retours=retours)

        try:
            id_ligne = int(request.form["id_ligne"])
            date_retour = date.fromisoformat(request.form["date_retour_effective"])
            result = service.enregistrer_retour(id_ligne, date_retour)

            # PRG
            session["last_payload"] = result
            session["last_title"] = "Retour enregistré"
            return redirect(url_for("message_ui"))

        except Exception as e:
            retours = service.lister_retours_possibles()
            return render_template("retour_form.html", title="Enregistrer un retour",
                                 retours=retours, error=str(e)), 400

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)