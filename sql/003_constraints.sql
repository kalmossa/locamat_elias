-- ============================================================
-- 003_constraints.sql
-- Contraintes SGBD (intégrité) - LOCA-MAT
-- ============================================================

BEGIN;


-- ------------------------------------------------------------
-- B) Règle d'intégrité 2 : passage vers "Loue" uniquement si "Disponible"
-- -> Trigger BEFORE UPDATE sur articles
-- ------------------------------------------------------------

-- 1) supprime trigger si déjà présent
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

-- 2) supprime fonction si déjà présente
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

-- 3) crée fonction
CREATE FUNCTION fn_articles_location_guard()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    -- On contrôle uniquement les changements de statut
    IF NEW.statut IS DISTINCT FROM OLD.statut THEN

        -- Interdiction de passer à Loue si on n'était pas Disponible
        IF NEW.statut = 'Loue' AND OLD.statut <> 'Disponible' THEN
            RAISE EXCEPTION
                'Changement statut interdit: un article ne peut passer à "Loue" que s''il est "Disponible" (actuel=%).',
                OLD.statut
            USING ERRCODE = '23514'; -- check_violation
        END IF;

        -- (Optionnel mais logique) Interdire de revenir à Disponible si on est en Rebut
        -- Décommente si tu veux durcir :
        -- IF NEW.statut = 'Disponible' AND OLD.statut = 'Rebut' THEN
        --     RAISE EXCEPTION 'Changement statut interdit: un article "Rebut" ne peut pas redevenir Disponible.'
        --     USING ERRCODE = '23514';
        -- END IF;

    END IF;

    RETURN NEW;
END;
$$;

-- 4) crée trigger
CREATE TRIGGER trg_articles_location_guard
BEFORE UPDATE OF statut ON articles
FOR EACH ROW
EXECUTE FUNCTION fn_articles_location_guard();

COMMIT;
