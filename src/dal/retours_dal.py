from __future__ import annotations
from datetime import date
from src.database_config import get_connection, log_critical_error


class RetoursDAL:
    def enregistrer_retour(self, id_ligne: int, date_retour: date, etat_retour: str = "Retourne"):
        conn = get_connection()
        if not conn:
            return False, "Connexion DB impossible"

        try:
            conn.autocommit = False

            with conn.cursor() as cur:
                # 1) Lock ligne
                cur.execute(
                    """
                    SELECT id_article, id_contrat, etat_retour
                    FROM lignes_contrat
                    WHERE id_ligne = %s
                    FOR UPDATE;
                    """,
                    (id_ligne,),
                )
                row = cur.fetchone()
                if not row:
                    conn.rollback()
                    return False, "Ligne de contrat introuvable."

                id_article, id_contrat, etat_actuel = row

                if etat_actuel != "NonRetourne":
                    conn.rollback()
                    return False, f"Retour déjà traité (etat_retour={etat_actuel})."

                # 2) MAJ ligne
                cur.execute(
                    """
                    UPDATE lignes_contrat
                    SET date_retour_effective = %s,
                        etat_retour = %s
                    WHERE id_ligne = %s;
                    """,
                    (date_retour, etat_retour, id_ligne),
                )

                if cur.rowcount != 1:
                    conn.rollback()
                    return False, "Échec mise à jour ligne de contrat."

                # 3) Lock article
                cur.execute(
                    """
                    SELECT statut
                    FROM articles
                    WHERE id_article = %s
                    FOR UPDATE;
                    """,
                    (id_article,),
                )
                row_statut = cur.fetchone()
                if not row_statut:
                    conn.rollback()
                    return False, "Article introuvable (incohérence DB)."

                statut_article = row_statut[0]

                if statut_article in ("EnMaintenance", "Rebut"):
                    conn.rollback()
                    return False, f"Retour impossible : article en statut '{statut_article}'."

                # 4) Remise en stock
                cur.execute(
                    """
                    UPDATE articles
                    SET statut = 'Disponible'
                    WHERE id_article = %s;
                    """,
                    (id_article,),
                )

                # 5) Clôture contrat si plus aucune ligne active
                cur.execute(
                    """
                    SELECT 1
                    FROM lignes_contrat
                    WHERE id_contrat = %s
                      AND etat_retour = 'NonRetourne'
                    LIMIT 1;
                    """,
                    (id_contrat,),
                )

                if cur.fetchone() is None:
                    cur.execute(
                        """
                        UPDATE contrats_location
                        SET statut = 'Cloture'
                        WHERE id_contrat = %s
                          AND statut <> 'Cloture';
                        """,
                        (id_contrat,),
                    )

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
            log_critical_error("DAL Retours enregistrer_retour", e)
            return False, "Erreur technique lors de l'enregistrement du retour."
        finally:
            conn.close()
