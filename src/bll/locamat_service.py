from datetime import date

from src.dal.articles_dal import ArticlesDAL
from src.dal.clients_dal import ClientsDAL
from src.dal.contrats_dal import ContratsDAL
from src.dal.dashboard_dal import DashboardDAL
from src.dal.retours_dal import RetoursDAL


class LocamatService:
    def __init__(self):
        self.articles_dal = ArticlesDAL()
        self.clients_dal = ClientsDAL()
        self.contrats_dal = ContratsDAL()
        self.dashboard_dal = DashboardDAL()
        self.retours_dal = RetoursDAL()

    # -------------------
    # Clients
    # -------------------
    def lister_clients(self):
        return self.clients_dal.get_all()

    def creer_client(self, nom: str, prenom: str, est_vip: bool = False):
        nom = (nom or "").strip()
        prenom = (prenom or "").strip()
        if not nom or not prenom:
            raise ValueError("Nom et prénom obligatoires.")

        ok, result = self.clients_dal.create_client(nom, prenom, est_vip)
        if not ok:
            raise RuntimeError(result)

        return {
            "id_client": result,
            "nom": nom,
            "prenom": prenom,
            "est_vip": est_vip,
        }

    # -------------------
    # Articles
    # -------------------
    def lister_articles(self):
        return self.articles_dal.get_all()

    def lister_articles_disponibles(self):
        return self.articles_dal.get_disponibles()

    def lister_articles_avec_location(self):
        return self.articles_dal.get_all_with_location()

    def supprimer_article(self, id_article: int):
        if id_article <= 0:
            raise ValueError("id_article invalide.")
        ok, result = self.articles_dal.delete_if_possible(id_article)
        if not ok:
            raise RuntimeError(result)
        return result

    def stock_resume(self):
        return self.articles_dal.stock_resume()

    def changer_statut_article(self, id_article: int, new_statut: str):
        if id_article <= 0:
            raise ValueError("id_article invalide.")
        ok, result = self.articles_dal.update_statut(id_article, new_statut)
        if not ok:
            raise RuntimeError(result)
        return result
    
    def changer_statut_article(self, id_article: int, new_statut: str):
        if id_article <= 0:
            raise ValueError("id_article invalide.")
    
        new_statut = (new_statut or "").strip()
    
        # normalisation minimale
        allowed = {"Disponible", "Loue", "Maintenance", "Rebut"}
        if new_statut not in allowed:
            raise ValueError("Statut invalide.")
    
        ok, msg = self.articles_dal.update_statut_if_allowed(id_article, new_statut)
        if not ok:
            raise RuntimeError(msg)
        return msg



    # -------------------
    # Dashboard
    # -------------------
    def dashboard(self):
        top5 = self.dashboard_dal.top5_rentables_mois()
        ca30 = self.dashboard_dal.ca_30_derniers_jours()
        alertes = self.dashboard_dal.alertes_retards()
        return {"top5": top5, "ca_30j": ca30, "alertes_retards": alertes}

    # -------------------
    # Retours
    # -------------------
    def lister_retours_possibles(self):
        # nécessite RetoursDAL.get_non_retournes()
        return self.retours_dal.get_non_retournes()

    def enregistrer_retour(self, id_ligne: int, date_retour: date):
        if id_ligne <= 0:
            raise ValueError("id_ligne invalide.")

        ok, result = self.retours_dal.enregistrer_retour(id_ligne, date_retour, "Retourne")
        if not ok:
            raise RuntimeError(result)
        return result

    # -------------------
    # Contrats / Location
    # -------------------
    
    
    def valider_contrat(
        self,
        id_client: int,
        date_debut: date,
        date_fin_prevue: date,
        article_ids: list[int],
    ):
        # 1) validations
        if id_client <= 0:
            raise ValueError("id_client invalide.")
        if not article_ids:
            raise ValueError("Aucun article sélectionné.")

        nb_jours = (date_fin_prevue - date_debut).days
        if nb_jours <= 0:
            raise ValueError("La date de fin doit être après la date de début.")

        # 2) client
        client = self.clients_dal.get_by_id(id_client)
        if not client:
            raise ValueError("Client introuvable.")

        # D) blocage si le client a UNE LOCATION EN COURS EN RETARD
        # (ça ne contredit pas l'algorithme 'retard dernière location', c'est différent)
        if self.contrats_dal.client_a_location_en_retard(id_client):
            raise RuntimeError("Location refusée : ce client a déjà une location en retard (contrat en cours).")

        # 3) articles + prix journaliers
        articles = self.articles_dal.get_by_ids(article_ids)
        if not articles or len(articles) != len(article_ids):
            raise ValueError("Certains articles sont introuvables.")

        # 4) règles de pricing (celles du prof)
        remise_duree_pct = 10 if nb_jours > 7 else 0
        remise_vip_pct = 15 if client["est_vip"] else 0
        surcharge_retard_pct = 5 if client["a_eu_retard_derniere_location"] else 0

        # 5) détail par article (C)
        lignes = []
        prix_base = 0.0
        prix_final = 0.0

        for a in articles:
            base_ligne = float(a["prix_journalier_actuel"]) * nb_jours
            montant = base_ligne
            montant *= (1 - remise_duree_pct / 100)
            montant *= (1 - remise_vip_pct / 100)
            montant *= (1 + surcharge_retard_pct / 100)

            base_ligne = round(base_ligne, 2)
            montant = round(montant, 2)

            prix_base += base_ligne
            prix_final += montant

            lignes.append({
                "id_article": a["id_article"],
                "prix_journalier_applique": float(a["prix_journalier_actuel"]),
                "nombre_jours": nb_jours,
                "prix_base_ligne": base_ligne,
                "remise_duree_pct": remise_duree_pct,
                "remise_vip_pct": remise_vip_pct,
                "surcharge_retard_pct": surcharge_retard_pct,
                "prix_total_ligne": montant,
            })

        prix_base = round(prix_base, 2)
        prix_final = round(prix_final, 2)

        # 6) transaction DB
        ok, result = self.contrats_dal.valider_contrat_transaction(
            id_client=id_client,
            date_debut=date_debut,
            date_fin_prevue=date_fin_prevue,
            article_ids=article_ids,
            prix_final=prix_final,
            lignes=lignes,
        )
        if not ok:
            raise RuntimeError(result)

        # payload complet pour ton message.html (C)
        return {
            "id_contrat": result,
            "id_client": id_client,
            "nb_jours": nb_jours,
            "prix_base": prix_base,
            "remise_duree_pct": remise_duree_pct,
            "remise_vip_pct": remise_vip_pct,
            "surcharge_retard_pct": surcharge_retard_pct,
            "prix_final": prix_final,
            "lignes": lignes,
        }
