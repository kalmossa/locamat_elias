from psycopg2 import errors
from src.database_config import get_connection, log_critical_error


class ArticlesDAL:  # couche d'accès aux données pour les articles et logique SQL liée au parc
    STATUTS = {"Disponible", "Loue", "EnMaintenance", "Rebut"} 

    def get_all_with_location(self):
        # Retourne tous les articles et si location en cours on récupère la date de fin prévue ;
        conn = get_connection()
        if not conn:
            return []

        try:
            with conn.cursor() as cur:
                # DISTINCT ON pour éviter doublons
                cur.execute("""
                    SELECT DISTINCT ON (a.id_article)
                        a.id_article, cat.libelle, m.libelle, a.modele, a.numero_serie,
                        a.prix_journalier_actuel, a.statut, c.date_fin_prevue, lc.id_ligne
                    FROM articles a
                    JOIN marques m ON m.id_marque = a.id_marque
                    JOIN categories cat ON cat.id_categorie = a.id_categorie
                    LEFT JOIN lignes_contrat lc ON lc.id_article = a.id_article
                        AND lc.etat_retour = 'NonRetourne'
                    LEFT JOIN contrats_location c ON c.id_contrat = lc.id_contrat
                        AND c.statut = 'Valide'
                    ORDER BY a.id_article, lc.id_ligne DESC NULLS LAST;
                """)
                rows = cur.fetchall()

            return [{
                "id_article": r[0], "categorie": r[1], "marque": r[2],
                "modele": r[3], "numero_serie": r[4],
                "prix_journalier_actuel": float(r[5]), "statut": r[6],
                "date_fin_prevue": r[7].isoformat() if r[7] else None,
                "id_ligne": r[8],
            } for r in rows]
        except Exception as e:
            log_critical_error("articles get_all_with_location", e)
            return []
        finally:
            conn.close()

    def get_disponibles(self):         # Articles dispo seulement
        conn = get_connection()
        if not conn:
            return []

        try:
            with conn.cursor() as cur:  # lock articles
                cur.execute("""
                    SELECT a.id_article, c.libelle, m.libelle, a.modele,
                           a.numero_serie, a.prix_journalier_actuel
                    FROM articles a
                    JOIN categories c ON c.id_categorie = a.id_categorie
                    JOIN marques m ON m.id_marque = a.id_marque
                    WHERE a.statut = 'Disponible'
                    ORDER BY a.id_article;
                """)
                rows = cur.fetchall()

            return [{
                "id_article": r[0], "categorie": r[1], "marque": r[2],
                "modele": r[3], "numero_serie": r[4],
                "prix_journalier_actuel": float(r[5]),
            } for r in rows]
        except Exception as e:
            log_critical_error("articles get_disponibles", e)
            return []
        finally:
            conn.close()

    def get_by_ids(self, article_ids): # Récup articles par liste d'ids
        if not article_ids:
            return []

        conn = get_connection()
        if not conn:
            return []

        try:
            with conn.cursor() as cur:  # lock articles
                cur.execute("""
                    SELECT id_article, prix_journalier_actuel
                    FROM articles
                    WHERE id_article = ANY(%s)
                    ORDER BY id_article;
                """, (article_ids,))
                rows = cur.fetchall()

            return [{"id_article": r[0], "prix_journalier_actuel": float(r[1])} for r in rows]
        except Exception as e:
            log_critical_error("articles get_by_ids", e)
            return []
        finally:
            conn.close()

    def delete_if_possible(self, id_article): # Supprime article si pas lié à contrat
        conn = get_connection()
        if not conn:
            return False, "Connexion DB impossible"

        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM articles WHERE id_article = %s;", (id_article,))
                if cur.rowcount == 0:
                    conn.rollback()
                    return False, "Article introuvable."

            conn.commit()
            return True, "Article supprimé."
        except errors.ForeignKeyViolation:
            conn.rollback()
            return False, "Suppression impossible : article lié à un contrat."
        except Exception as e:
            conn.rollback()
            log_critical_error("articles delete", e)
            return False, "Erreur technique."
        finally:
            conn.close()

    def update_statut(self, id_article, new_statut): # Met à jour le statut d'un article
        if new_statut not in self.STATUTS:
            return False, "Statut invalide."

        conn = get_connection()
        if not conn:
            return False, "Connexion DB impossible"

        try:
            conn.autocommit = False
            with conn.cursor() as cur:
                # lock article
                cur.execute("SELECT statut FROM articles WHERE id_article = %s FOR UPDATE;", (id_article,))  # lock
                row = cur.fetchone()
                if not row:
                    conn.rollback()
                    return False, "Article introuvable."

                # check pas loué actuellement
                cur.execute("""
                    SELECT 1 FROM lignes_contrat
                    WHERE id_article = %s AND etat_retour = 'NonRetourne'
                    LIMIT 1;
                """, (id_article,))
                if cur.fetchone():
                    conn.rollback()
                    return False, "Impossible : article loué."

                # update statut
                cur.execute("UPDATE articles SET statut = %s WHERE id_article = %s;",
                          (new_statut, id_article))

            conn.commit()
            return True, "Statut mis à jour."
        except Exception as e:
            conn.rollback()
            log_critical_error("articles update_statut", e)
            return False, "Erreur technique."
        finally:
            conn.close()

    def stock_resume(self):      # Résumé du stock par statut
        conn = get_connection()
        if not conn:
            return {"Disponible": 0, "Loue": 0, "EnMaintenance": 0, "Rebut": 0}

        try:
            with conn.cursor() as cur:
                cur.execute("SELECT statut, COUNT(*) FROM articles GROUP BY statut;")
                rows = cur.fetchall()

            stock = {"Disponible": 0, "Loue": 0, "EnMaintenance": 0, "Rebut": 0}
            for statut, cnt in rows:
                if statut in stock:
                    stock[statut] = int(cnt)
            return stock
        except Exception as e: # Erreur 
            log_critical_error("articles stock_resume", e)
            return {"Disponible": 0, "Loue": 0, "EnMaintenance": 0, "Rebut": 0}
        finally:
            conn.close()