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
                # 1) Lock ligne + récup infos
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

                # 2) Refus si déjà traité
                if etat_actuel != "NonRetourne":
                    conn.rollback()
                    return False, f"Retour déjà traité (etat_retour={etat_actuel})."

                # 3) MAJ ligne : retour
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

                # 4) Lock article + contrôle statut
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

                # Si article en maintenance/rebut, on ne force pas Disponible
                if statut_article not in ("EnMaintenance", "Rebut"):
                    cur.execute(
                        """
                        UPDATE articles
                        SET statut = 'Disponible'
                        WHERE id_article = %s;
                        """,
                        (id_article,),
                    )

                # 5) Si plus aucune ligne NonRetourne sur le contrat => Cloture
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

    def get_non_retournes(self) -> list[dict]:
        conn = get_connection()
        if not conn:
            return []

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        lc.id_ligne,
                        lc.id_contrat,
                        a.id_article,
                        m.libelle AS marque,
                        a.modele,
                        a.numero_serie,
                        c.date_fin_prevue
                    FROM lignes_contrat lc
                    JOIN contrats_location c ON c.id_contrat = lc.id_contrat
                    JOIN articles a ON a.id_article = lc.id_article
                    JOIN marques m ON m.id_marque = a.id_marque
                    WHERE lc.etat_retour = 'NonRetourne'
                      AND c.statut = 'Valide'
                    ORDER BY c.date_fin_prevue ASC, lc.id_ligne ASC;
                    """
                )
                rows = cur.fetchall()

            return [
                {
                    "id_ligne": r[0],
                    "id_contrat": r[1],
                    "id_article": r[2],
                    "marque": r[3],
                    "modele": r[4],
                    "numero_serie": r[5],
                    "date_fin_prevue": r[6].isoformat() if r[6] else None,
                }
                for r in rows
            ]
        except Exception as e:
            log_critical_error("DAL Retours get_non_retournes", e)
            return []
        finally:
            conn.close()
