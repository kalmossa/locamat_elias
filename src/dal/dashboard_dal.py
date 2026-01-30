from src.database_config import get_connection, log_critical_error
class DashboardDAL:  # couche DAL dédiée aux requêtes décisionnelles (dashboard)
    
    def top5_rentables_mois(self):  # retourne les 5 articles qui ont généré le plus de revenu sur le mois en cours
        conn = get_connection()
        if not conn:
            return []
        try:
            with conn.cursor() as cur:  # agrégation SQL : somme des prix par article sur le mois courant
                cur.execute("""
                    SELECT a.id_article, m.libelle, a.modele, a.numero_serie,
                           SUM(lc.prix_total_ligne) AS revenu_mois
                    FROM lignes_contrat lc
                    JOIN contrats_location c ON c.id_contrat = lc.id_contrat
                    JOIN articles a ON a.id_article = lc.id_article
                    JOIN marques m ON m.id_marque = a.id_marque
                    WHERE c.date_debut >= date_trunc('month', CURRENT_DATE)
                      AND c.date_debut < date_trunc('month', CURRENT_DATE) + interval '1 month'
                    GROUP BY a.id_article, m.libelle, a.modele, a.numero_serie
                    ORDER BY revenu_mois DESC LIMIT 5;
                """)
                rows = cur.fetchall()

                return [{  # mapping SQL -> dictionnaires python pour la couche BLL / UI
                    "id_article": r[0], "marque": r[1], "modele": r[2],
                    "numero_serie": r[3], "revenu_mois": float(r[4]),   # float pour JSON
                } for r in rows]
        except Exception as e: # log erreur
            log_critical_error("dashboard top5", e) 
            return []
        finally:
            conn.close() 

    def ca_30_derniers_jours(self): #   calcul ca 30j
        """CA des 30 derniers jours"""
        conn = get_connection()
        if not conn:
            return 0.0
        try:
            with conn.cursor() as cur: # SUM protégée par COALESCE pour éviter None si aucune ligne
                cur.execute("""
                    SELECT COALESCE(SUM(prix_final), 0) AS ca_30j
                    FROM contrats_location
                    WHERE statut = 'Valide'
                      AND date_debut >= CURRENT_DATE - interval '30 days';
                """)
                row = cur.fetchone()
                return float(row[0]) if row else 0.0
        except Exception as e:
            log_critical_error("dashboard ca_30j", e)
            return 0.0
        finally:
            conn.close()

    def alertes_retards(self):  # liste tous les articles en retard de restitution (contrat valide + date dépassée)
        conn = get_connection()
        if not conn:
            return []
        try: 
            with conn.cursor() as cur: # jointure large pour afficher client + article + contrat
                cur.execute("""
                    SELECT c.id_contrat, c.date_fin_prevue, cl.nom, cl.prenom,
                           a.id_article, m.libelle, a.modele, a.numero_serie, a.statut
                    FROM lignes_contrat lc
                    JOIN contrats_location c ON c.id_contrat = lc.id_contrat
                    JOIN clients cl ON cl.id_client = c.id_client
                    JOIN articles a ON a.id_article = lc.id_article
                    JOIN marques m ON m.id_marque = a.id_marque
                    WHERE c.statut = 'Valide' AND c.date_fin_prevue < CURRENT_DATE
                      AND (lc.date_retour_effective IS NULL OR lc.etat_retour = 'NonRetourne')
                    ORDER BY c.date_fin_prevue ASC, c.id_contrat ASC;
                """)
                rows = cur.fetchall()

                return [{  # formatage des résultats pour affichage UI
                    "id_contrat": r[0],
                    "date_fin_prevue": r[1].isoformat() if r[1] else None,
                    "client_nom": r[2], "client_prenom": r[3],
                    "id_article": r[4], "marque": r[5], "modele": r[6],
                    "numero_serie": r[7], "statut_article": r[8],
                } for r in rows]
        except Exception as e:      
            log_critical_error("dashboard alertes_retards", e) 
            return []
        finally:
            conn.close()