# src/dal/contrats_dal.py
from __future__ import annotations

from src.database_config import get_connection, log_critical_error


class ContratsDAL:
    def valider_contrat_transaction(
        self,
        id_client: int,
        date_debut,
        date_fin_prevue,
        article_ids: list[int],
        prix_final: float,
        lignes: list[dict],
    ):
        """
        Transaction atomique :
        - verrouille les articles (FOR UPDATE) pour éviter double location
        - refuse si déjà loué (statut != 'Disponible')
        - refuse si une ligne NonRetourne existe pour l'article
        - crée le contrat (statut = 'Valide')
        - crée les lignes (etat_retour = 'NonRetourne')
        - passe les articles en 'Loue'
        """
        conn = get_connection()
        if not conn:
            return False, "Connexion DB impossible"

        try:
            conn.autocommit = False
            with conn.cursor() as cur:
                if not article_ids:
                    conn.rollback()
                    return False, "Aucun article sélectionné."

                # 1) Lock + vérif statut articles
                cur.execute(
                    """
                    SELECT id_article, statut
                    FROM articles
                    WHERE id_article = ANY(%s)
                    FOR UPDATE;
                    """,
                    (article_ids,),
                )
                rows = cur.fetchall()

                if len(rows) != len(article_ids):
                    conn.rollback()
                    return False, "Un ou plusieurs articles sont introuvables."

                for (id_article, statut) in rows:
                    if statut != "Disponible":
                        conn.rollback()
                        return False, f"Conflit: l'article {id_article} n'est plus disponible (statut={statut})."

                # 2) Aucune ligne NonRetourne ne doit exister
                cur.execute(
                    """
                    SELECT id_article, id_ligne
                    FROM lignes_contrat
                    WHERE id_article = ANY(%s)
                      AND etat_retour = 'NonRetourne'
                    LIMIT 1
                    FOR UPDATE;
                    """,
                    (article_ids,),
                )
                conflict = cur.fetchone()
                if conflict:
                    id_article_conflict, id_ligne_conflict = conflict
                    conn.rollback()
                    return False, (
                        f"Conflit: l'article {id_article_conflict} a déjà une location non retournée "
                        f"(ligne={id_ligne_conflict})."
                    )

                # 3) Insert contrat
                cur.execute(
                    """
                    INSERT INTO contrats_location (id_client, date_debut, date_fin_prevue, prix_final, statut)
                    VALUES (%s, %s, %s, %s, 'Valide')
                    RETURNING id_contrat;
                    """,
                    (id_client, date_debut, date_fin_prevue, prix_final),
                )
                id_contrat = cur.fetchone()[0]

                # 4) Insert lignes (NOTE: PAS de date_retour_effective ici)
                for l in lignes:
                    cur.execute(
                        """
                        INSERT INTO lignes_contrat (
                            id_contrat, id_article,
                            prix_journalier_applique, nombre_jours,
                            remise_duree_pct, remise_vip_pct, surcharge_retard_pct,
                            prix_total_ligne,
                            etat_retour
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'NonRetourne');
                        """,
                        (
                            id_contrat,
                            l["id_article"],
                            l["prix_journalier_applique"],
                            l["nombre_jours"],
                            l.get("remise_duree_pct", 0),
                            l.get("remise_vip_pct", 0),
                            l.get("surcharge_retard_pct", 0),
                            l["prix_total_ligne"],
                        ),
                    )

                # 5) Update articles -> Loue
                cur.execute(
                    """
                    UPDATE articles
                    SET statut = 'Loue'
                    WHERE id_article = ANY(%s)
                      AND statut = 'Disponible';
                    """,
                    (article_ids,),
                )

                if cur.rowcount != len(article_ids):
                    conn.rollback()
                    return False, "Conflit: mise à jour article impossible (statut inattendu)."

            conn.commit()
            return True, id_contrat

        except Exception as e:
            conn.rollback()
            log_critical_error("DAL Contrats valider_contrat_transaction", e)
            return False, "Erreur technique lors de la validation du contrat."
        finally:
            conn.close()

    def client_a_location_en_retard(self, id_client: int) -> bool:
        conn = get_connection()
        if not conn:
            return False

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1
                    FROM contrats_location c
                    JOIN lignes_contrat lc ON lc.id_contrat = c.id_contrat
                    WHERE c.id_client = %s
                      AND c.statut = 'Valide'
                      AND lc.etat_retour = 'NonRetourne'
                      AND c.date_fin_prevue < CURRENT_DATE
                    LIMIT 1;
                    """,
                    (id_client,),
                )
                return cur.fetchone() is not None
        except Exception as e:
            log_critical_error("DAL Contrats client_a_location_en_retard", e)
            return False
        finally:
            conn.close()
