from __future__ import annotations
from psycopg2 import errors
from src.database_config import get_connection, log_critical_error


class ArticlesDAL:
    STATUTS = {"Disponible", "Loue", "EnMaintenance", "Rebut"}

    def get_all_with_location(self) -> list[dict]:
        conn = get_connection()
        if not conn:
            return []

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        a.id_article,
                        cat.libelle AS categorie,
                        m.libelle AS marque,
                        a.modele,
                        a.numero_serie,
                        a.prix_journalier_actuel,
                        a.statut,
                        c.date_fin_prevue,
                        lc.id_ligne
                    FROM articles a
                    JOIN marques m ON m.id_marque = a.id_marque
                    JOIN categories cat ON cat.id_categorie = a.id_categorie
                    LEFT JOIN lignes_contrat lc
                      ON lc.id_article = a.id_article
                     AND lc.etat_retour = 'NonRetourne'
                    LEFT JOIN contrats_location c
                      ON c.id_contrat = lc.id_contrat
                     AND c.statut = 'Valide'
                    ORDER BY a.id_article;
                """)
                rows = cur.fetchall()

            return [
                {
                    "id_article": r[0],
                    "categorie": r[1],
                    "marque": r[2],
                    "modele": r[3],
                    "numero_serie": r[4],
                    "prix_journalier_actuel": float(r[5]),
                    "statut": r[6],
                    "date_fin_prevue": r[7].isoformat() if r[7] else None,
                    "id_ligne": r[8],
                }
                for r in rows
            ]

        except Exception as e:
            log_critical_error("DAL Articles get_all_with_location", e)
            return []
        finally:
            conn.close()

    def get_disponibles(self) -> list[dict]:
        conn = get_connection()
        if not conn:
            return []

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        a.id_article,
                        c.libelle AS categorie,
                        m.libelle AS marque,
                        a.modele,
                        a.numero_serie,
                        a.prix_journalier_actuel
                    FROM articles a
                    JOIN categories c ON c.id_categorie = a.id_categorie
                    JOIN marques m ON m.id_marque = a.id_marque
                    WHERE a.statut = 'Disponible'
                    ORDER BY a.id_article;
                """)
                rows = cur.fetchall()

            return [
                {
                    "id_article": r[0],
                    "categorie": r[1],
                    "marque": r[2],
                    "modele": r[3],
                    "numero_serie": r[4],
                    "prix_journalier_actuel": float(r[5]),
                }
                for r in rows
            ]
        except Exception as e:
            log_critical_error("DAL Articles get_disponibles", e)
            return []
        finally:
            conn.close()

    def get_by_ids(self, article_ids: list[int]) -> list[dict]:
        if not article_ids:
            return []

        conn = get_connection()
        if not conn:
            return []

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id_article, prix_journalier_actuel
                    FROM articles
                    WHERE id_article = ANY(%s)
                    ORDER BY id_article;
                """, (article_ids,))
                rows = cur.fetchall()

            return [{"id_article": r[0], "prix_journalier_actuel": float(r[1])} for r in rows]
        except Exception as e:
            log_critical_error("DAL Articles get_by_ids", e)
            return []
        finally:
            conn.close()

    def delete_if_possible(self, id_article: int):
        conn = get_connection()
        if not conn:
            return False, "Connexion DB impossible"

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM articles
                    WHERE id_article = %s;
                """, (id_article,))

                if cur.rowcount == 0:
                    conn.rollback()
                    return False, "Article introuvable."

            conn.commit()
            return True, "Article supprimé."

        except errors.ForeignKeyViolation:
            conn.rollback()
            return False, "Suppression impossible : article lié à un contrat passé ou en cours."
        except Exception as e:
            conn.rollback()
            log_critical_error("DAL Articles delete_if_possible", e)
            return False, "Erreur technique lors de la suppression."
        finally:
            conn.close()

    def update_statut(self, id_article: int, new_statut: str):
            """Change le statut d'un article avec règles de cohérence simples."""
            if new_statut not in self.STATUTS:
                return False, "Statut invalide."

            conn = get_connection()
            if not conn:
                return False, "Connexion DB impossible"

            try:
                conn.autocommit = False
                with conn.cursor() as cur:
                    # lock article
                    cur.execute(
                        """
                        SELECT statut
                        FROM articles
                        WHERE id_article = %s
                        FOR UPDATE;
                        """,
                        (id_article,),
                    )
                    row = cur.fetchone()
                    if not row:
                        conn.rollback()
                        return False, "Article introuvable."

                    statut_actuel = row[0]

                    # Règle : interdit de passer EnMaintenance/Rebut si l'article est loué
                    if statut_actuel == "Loue" and new_statut in {"EnMaintenance", "Rebut"}:
                        conn.rollback()
                        return False, "Impossible : l'article est actuellement loué."

                    # Règle : interdit de repasser Disponible si une location non retournée existe
                    if new_statut == "Disponible":
                        cur.execute(
                            """
                            SELECT 1
                            FROM lignes_contrat lc
                            JOIN contrats_location c ON c.id_contrat = lc.id_contrat
                            WHERE lc.id_article = %s
                              AND lc.etat_retour = 'NonRetourne'
                              AND c.statut = 'Valide'
                            LIMIT 1;
                            """,
                            (id_article,),
                        )
                        if cur.fetchone():
                            conn.rollback()
                            return False, "Impossible : une location en cours existe pour cet article."

                    cur.execute(
                        """
                        UPDATE articles
                        SET statut = %s
                        WHERE id_article = %s;
                        """,
                        (new_statut, id_article),
                    )

                conn.commit()
                return True, "Statut mis à jour."
            except Exception as e:
                conn.rollback()
                log_critical_error("DAL Articles update_statut", e)
                return False, "Erreur technique lors de la mise à jour du statut."
            finally:
                conn.close()

    def update_statut_if_allowed(self, id_article: int, new_statut: str):
        conn = get_connection()
        if not conn:
            return False, "Connexion DB impossible"
    
        try:
            with conn.cursor() as cur:
                # Refuse si location en cours
                cur.execute("""
                    SELECT 1
                    FROM lignes_contrat
                    WHERE id_article = %s
                      AND etat_retour = 'NonRetourne'
                    LIMIT 1;
                """, (id_article,))
                if cur.fetchone():
                    conn.rollback()
                    return False, "Changement interdit : location en cours pour cet article."
    
                cur.execute("""
                    UPDATE articles
                    SET statut = %s
                    WHERE id_article = %s;
                """, (new_statut, id_article))
    
                if cur.rowcount != 1:
                    conn.rollback()
                    return False, "Article introuvable."
    
            conn.commit()
            return True, "Statut mis à jour."
        except Exception as e:
            conn.rollback()
            log_critical_error("DAL Articles update_statut_if_allowed", e)
            return False, "Erreur technique lors de la mise à jour du statut."
        finally:
            conn.close()
    

    def stock_resume(self) -> dict:
        conn = get_connection()
        if not conn:
            # clés attendues par le template
            return {"Disponible": 0, "Loue": 0, "EnMaintenance": 0, "Rebut": 0}
    
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT statut, COUNT(*)
                    FROM articles
                    GROUP BY statut;
                """)
                rows = cur.fetchall()
    
            stock = {"Disponible": 0, "Loue": 0, "EnMaintenance": 0, "Rebut": 0}
            for statut, cnt in rows:
                if statut in stock:
                    stock[statut] = int(cnt)
            return stock
    
        except Exception as e:
            log_critical_error("DAL Articles stock_resume", e)
            return {"Disponible": 0, "Loue": 0, "EnMaintenance": 0, "Rebut": 0}
        finally:
            conn.close()
