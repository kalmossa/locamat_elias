from datetime import date
from src.database_config import get_connection, log_critical_error


class RetoursDAL:
    
    def enregistrer_retour(self, id_ligne, date_retour, etat_retour="Retourne"):
        conn = get_connection()
        if not conn:
            return False, "Connexion DB impossible"

        try:
            conn.autocommit = False

            with conn.cursor() as cur:
                # lock ligne + récup infos
                cur.execute("""
                    SELECT lc.id_article, lc.id_contrat, lc.etat_retour, c.statut
                    FROM lignes_contrat lc
                    JOIN contrats_location c ON c.id_contrat = lc.id_contrat
                    WHERE lc.id_ligne = %s FOR UPDATE OF lc;
                """, (id_ligne,))
                row = cur.fetchone()
                if not row:
                    conn.rollback()
                    return False, "Ligne introuvable."

                id_article, id_contrat, etat_actuel, statut_contrat = row

                # check contrat valide
                if statut_contrat != 'Valide':
                    conn.rollback()
                    return False, f"Contrat pas valide (statut={statut_contrat})."

                # check pas déjà retourné
                if etat_actuel != "NonRetourne":
                    conn.rollback()
                    return False, f"Déjà traité (etat={etat_actuel})."

                # maj ligne
                cur.execute("""
                    UPDATE lignes_contrat
                    SET date_retour_effective = %s, etat_retour = %s
                    WHERE id_ligne = %s;
                """, (date_retour, etat_retour, id_ligne))

                if cur.rowcount != 1:
                    conn.rollback()
                    return False, "Échec maj ligne."

                # lock article + remise dispo si possible
                cur.execute("SELECT statut FROM articles WHERE id_article = %s FOR UPDATE;", 
                          (id_article,))
                row_statut = cur.fetchone()
                if not row_statut:
                    conn.rollback()
                    return False, "Article introuvable."

                statut_article = row_statut[0]

                # si pas en maintenance/rebut, remettre dispo
                if statut_article not in ("EnMaintenance", "Rebut"):
                    cur.execute("UPDATE articles SET statut = 'Disponible' WHERE id_article = %s;",
                              (id_article,))

                # check si tout retourné -> clôture contrat
                cur.execute("""
                    SELECT 1 FROM lignes_contrat
                    WHERE id_contrat = %s AND etat_retour = 'NonRetourne'
                    LIMIT 1;
                """, (id_contrat,))
                if not cur.fetchone():
                    cur.execute("""
                        UPDATE contrats_location SET statut = 'Cloture'
                        WHERE id_contrat = %s AND statut = 'Valide';
                    """, (id_contrat,))

            conn.commit()
            return True, {
                "id_ligne": id_ligne,
                "id_contrat": id_contrat,
                "id_article": id_article,
                "date_retour_effective": date_retour.isoformat(),
                "etat_retour": etat_retour,
            }
        except Exception as e:
            conn.rollback()
            log_critical_error("retours enregistrer", e)
            return False, "Erreur technique."
        finally:
            conn.close()

    def get_non_retournes(self):
        """Liste lignes pas encore retournées"""
        conn = get_connection()
        if not conn:
            return []

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT DISTINCT lc.id_ligne, lc.id_contrat, a.id_article,
                           m.libelle, a.modele, a.numero_serie, c.date_fin_prevue
                    FROM lignes_contrat lc
                    JOIN contrats_location c ON c.id_contrat = lc.id_contrat
                    JOIN articles a ON a.id_article = lc.id_article
                    JOIN marques m ON m.id_marque = a.id_marque
                    WHERE lc.etat_retour = 'NonRetourne' AND c.statut = 'Valide'
                    ORDER BY c.date_fin_prevue ASC, lc.id_ligne ASC;
                """)
                rows = cur.fetchall()

            return [{
                "id_ligne": r[0], "id_contrat": r[1], "id_article": r[2],
                "marque": r[3], "modele": r[4], "numero_serie": r[5],
                "date_fin_prevue": r[6].isoformat() if r[6] else None,
            } for r in rows]
        except Exception as e:
            log_critical_error("retours get_non_retournes", e)
            return []
        finally:
            conn.close()