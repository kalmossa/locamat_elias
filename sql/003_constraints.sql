-- ============================================================
-- 003_constraints.sql
-- Contraintes SGBD (intégrité) - LOCA-MAT
-- ============================================================

BEGIN;

-- ------------------------------------------------------------
-- A) Trigger : passage vers "Loue" uniquement si "Disponible"
-- ------------------------------------------------------------

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname = 'trg_articles_location_guard'
    ) THEN
        DROP TRIGGER trg_articles_location_guard ON articles;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_proc
        WHERE proname = 'fn_articles_location_guard'
    ) THEN
        DROP FUNCTION fn_articles_location_guard();
    END IF;
END $$;

CREATE FUNCTION fn_articles_location_guard()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.statut IS DISTINCT FROM OLD.statut THEN
        IF NEW.statut = 'Loue' AND OLD.statut <> 'Disponible' THEN
            RAISE EXCEPTION
                'Changement statut interdit: un article ne peut passer à "Loue" que s''il est "Disponible" (actuel=%).',
                OLD.statut
            USING ERRCODE = '23514';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_articles_location_guard
BEFORE UPDATE OF statut ON articles
FOR EACH ROW
EXECUTE FUNCTION fn_articles_location_guard();

-- ------------------------------------------------------------
-- B) Un article ne peut avoir qu'une seule ligne "NonRetourne"
-- ------------------------------------------------------------

CREATE UNIQUE INDEX IF NOT EXISTS uq_lignes_article_non_retourne
ON lignes_contrat(id_article)
WHERE etat_retour = 'NonRetourne';

COMMIT;
