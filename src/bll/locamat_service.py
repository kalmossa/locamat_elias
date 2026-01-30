from datetime import date
from src.dal.articles_dal import ArticlesDAL
from src.dal.clients_dal import ClientsDAL
from src.dal.contrats_dal import ContratsDAL
from src.dal.dashboard_dal import DashboardDAL
from src.dal.retours_dal import RetoursDAL


class LocamatService:
    """Logique métier centrale"""
    
    def __init__(self):
        self.articles_dal = ArticlesDAL()
        self.clients_dal = ClientsDAL()
        self.contrats_dal = ContratsDAL()
        self.dashboard_dal = DashboardDAL()
        self.retours_dal = RetoursDAL()

    # === CLIENTS ===
    
    def lister_clients(self):
        return self.clients_dal.get_all()

    def creer_client(self, nom, prenom, est_vip=False):
        nom = nom.strip() if nom else ""
        prenom = prenom.strip() if prenom else ""
        if not nom or not prenom:
            raise ValueError("Nom et prénom obligatoires.")

        ok, result = self.clients_dal.create_client(nom, prenom, est_vip)
        if not ok:
            raise RuntimeError(result)

        return {"id_client": result, "nom": nom, "prenom": prenom, "est_vip": est_vip}

    # === ARTICLES ===
    
    def lister_articles_disponibles(self):
        return self.articles_dal.get_disponibles()

    def lister_articles_avec_location(self):
        return self.articles_dal.get_all_with_location()

    def supprimer_article(self, id_article):
        if id_article <= 0:
            raise ValueError("id_article invalide.")
        ok, result = self.articles_dal.delete_if_possible(id_article)
        if not ok:
            raise RuntimeError(result)
        return result

    def stock_resume(self):
        return self.articles_dal.stock_resume()

    def changer_statut_article(self, id_article, new_statut):
        if id_article <= 0:
            raise ValueError("id_article invalide.")
        
        new_statut = new_statut.strip() if new_statut else ""
        allowed = {"Disponible", "Loue", "EnMaintenance", "Rebut"}
        if new_statut not in allowed:
            raise ValueError("Statut invalide.")

        ok, msg = self.articles_dal.update_statut(id_article, new_statut)
        if not ok:
            raise RuntimeError(msg)
        return msg

    # === DASHBOARD ===
    
    def dashboard(self):
        top5 = self.dashboard_dal.top5_rentables_mois()
        ca30 = self.dashboard_dal.ca_30_derniers_jours()
        alertes = self.dashboard_dal.alertes_retards()
        return {"top5": top5, "ca_30j": ca30, "alertes_retards": alertes}

    # === RETOURS ===
    
    def lister_retours_possibles(self):
        return self.retours_dal.get_non_retournes()

    def enregistrer_retour(self, id_ligne, date_retour):
        if id_ligne <= 0:
            raise ValueError("id_ligne invalide.")
        
        ok, result = self.retours_dal.enregistrer_retour(id_ligne, date_retour, "Retourne")
        if not ok:
            raise RuntimeError(result)
        return result

    # === CONTRATS / LOCATION ===
    
    def valider_contrat(self, id_client, date_debut, date_fin_prevue, article_ids):
        # check basique
        if id_client <= 0:
            raise ValueError("id_client invalide.")
        if not article_ids:
            raise ValueError("Aucun article sélectionné.")

        nb_jours = (date_fin_prevue - date_debut).days
        if nb_jours <= 0:
            raise ValueError("Date fin doit être après date début.")

        # récup client
        client = self.clients_dal.get_by_id(id_client)
        if not client:
            raise ValueError("Client introuvable.")

        # check retard
        if self.contrats_dal.client_a_location_en_retard(id_client):
            raise RuntimeError("Location refusée : client a déjà une location en retard.")

        # récup articles
        articles = self.articles_dal.get_by_ids(article_ids)
        if not articles or len(articles) != len(article_ids):
            raise ValueError("Certains articles introuvables.")

        # calcul remises/surcharges
        remise_duree_pct = 10 if nb_jours > 7 else 0
        remise_vip_pct = 15 if client["est_vip"] else 0
        surcharge_retard_pct = 5 if client["a_eu_retard_derniere_location"] else 0

        # calcul prix
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

        # transaction
        ok, result = self.contrats_dal.valider_contrat_transaction(
            id_client, date_debut, date_fin_prevue, article_ids, prix_final, lignes
        )
        if not ok:
            raise RuntimeError(result)

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