from src.database_config import get_connection, log_critical_error


class ClientsDAL:
    def get_by_id(self, id_client: int):
        conn = get_connection()
        if not conn:
            return None
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id_client, nom, prenom, est_vip, a_eu_retard_derniere_location
                    FROM clients
                    WHERE id_client = %s;
                    """,
                    (id_client,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return {
                    "id_client": row[0],
                    "nom": row[1],
                    "prenom": row[2],
                    "est_vip": row[3],
                    "a_eu_retard_derniere_location": row[4],
                }
        except Exception as e:
            log_critical_error("DAL Clients get_by_id", e)
            return None
        finally:
            conn.close()

    def get_all(self):
        conn = get_connection()
        if not conn:
            return []

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id_client, nom, prenom, est_vip, a_eu_retard_derniere_location
                    FROM clients
                    ORDER BY id_client;
                    """
                )
                rows = cur.fetchall()

            return [
                {
                    "id_client": r[0],
                    "nom": r[1],
                    "prenom": r[2],
                    "est_vip": r[3],
                    "a_eu_retard_derniere_location": r[4],
                }
                for r in rows
            ]
        except Exception as e:
            log_critical_error("DAL Clients get_all", e)
            return []
        finally:
            conn.close()

    def create_client(self, nom: str, prenom: str, est_vip: bool = False):
        conn = get_connection()
        if not conn:
            return False, "Connexion DB impossible"

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO clients (nom, prenom, est_vip, a_eu_retard_derniere_location)
                    VALUES (%s, %s, %s, FALSE)
                    RETURNING id_client;
                    """,
                    (nom, prenom, est_vip),
                )
                new_id = cur.fetchone()[0]
            conn.commit()
            return True, new_id
        except Exception as e:
            conn.rollback()
            log_critical_error("DAL Clients create_client", e)
            return False, "Erreur technique lors de la création client."
        finally:
            conn.close()
