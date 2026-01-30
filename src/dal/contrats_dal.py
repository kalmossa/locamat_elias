from src.database_config import get_connection, log_critical_error


class ContratsDAL:
    
    def valider_contrat_transaction(self, id_client, date_debut, date_fin_prevue, 
                                    article_ids, prix_final, lignes):
        """
        Transaction atomique pour créer contrat:
        - lock articles (FOR UPDATE)
        - check dispo
        - insert contrat + lignes
        - maj statut articles
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

                # lock + check statut articles
                cur.execute("""
                    SELECT id_article, statut FROM articles
                    WHERE id_article = ANY(%s) FOR UPDATE;
                """, (article_ids,))
                rows = cur.fetchall()

                if len(rows) != len(article_ids):
                    conn.rollback()
                    return False, "Un ou plusieurs articles introuvables."

                for (id_article, statut) in rows:
                    if statut != "Disponible":
                        conn.rollback()
                        return False, f"Conflit: article {id_article} pas dispo (statut={statut})."

                # check pas de loc active existante
                cur.execute("""
                    SELECT lc.id_article, lc.id_ligne, c.id_contrat
                    FROM lignes_contrat lc
                    JOIN contrats_location c ON c.id_contrat = lc.id_contrat
                    WHERE lc.id_article = ANY(%s)
                      AND lc.etat_retour = 'NonRetourne'
                      AND c.statut = 'Valide'
                    LIMIT 1 FOR UPDATE OF lc;
                """, (article_ids,))
                conflict = cur.fetchone()
                if conflict:
                    id_art, id_lig, id_con = conflict
                    conn.rollback()
                    return False, f"Conflit: article {id_art} déjà loué (ligne={id_lig}, contrat={id_con})."

                # insert contrat
                cur.execute("""
                    INSERT INTO contrats_location (id_client, date_debut, date_fin_prevue, prix_final, statut)
                    VALUES (%s, %s, %s, %s, 'Valide') RETURNING id_contrat;
                """, (id_client, date_debut, date_fin_prevue, prix_final))
                id_contrat = cur.fetchone()[0]

                # insert lignes
                for l in lignes:
                    cur.execute("""
                        INSERT INTO lignes_contrat (
                            id_contrat, id_article, prix_journalier_applique, nombre_jours,
                            remise_duree_pct, remise_vip_pct, surcharge_retard_pct,
                            prix_total_ligne, etat_retour
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'NonRetourne');
                    """, (id_contrat, l["id_article"], l["prix_journalier_applique"],
                          l["nombre_jours"], l.get("remise_duree_pct", 0),
                          l.get("remise_vip_pct", 0), l.get("surcharge_retard_pct", 0),
                          l["prix_total_ligne"]))

                # maj articles -> Loue
                cur.execute("""
                    UPDATE articles SET statut = 'Loue'
                    WHERE id_article = ANY(%s) AND statut = 'Disponible';
                """, (article_ids,))

                if cur.rowcount != len(article_ids):
                    conn.rollback()
                    return False, "Conflit: maj article impossible."

            conn.commit()
            return True, id_contrat
        except Exception as e:
            conn.rollback()
            log_critical_error("contrats valider_transaction", e)
            return False, "Erreur technique."
        finally:
            conn.close()

    def client_a_location_en_retard(self, id_client):
        """Check si client a loc en retard"""
        conn = get_connection()
        if not conn:
            return False

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 1 FROM contrats_location c
                    JOIN lignes_contrat lc ON lc.id_contrat = c.id_contrat
                    WHERE c.id_client = %s AND c.statut = 'Valide'
                      AND lc.etat_retour = 'NonRetourne'
                      AND c.date_fin_prevue < CURRENT_DATE
                    LIMIT 1;
                """, (id_client,))
                return cur.fetchone() is not None
        except Exception as e:
            log_critical_error("contrats check_retard", e)
            return False
        finally:
            conn.close()