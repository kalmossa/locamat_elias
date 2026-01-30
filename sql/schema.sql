DROP TABLE IF EXISTS retours CASCADE;
DROP TABLE IF EXISTS lignes_contrat CASCADE;
DROP TABLE IF EXISTS contrats_location CASCADE;
DROP TABLE IF EXISTS articles CASCADE;
DROP TABLE IF EXISTS marques CASCADE;
DROP TABLE IF EXISTS categories CASCADE;
DROP TABLE IF EXISTS clients CASCADE;

-- 1) TABLES 2 ref

CREATE TABLE clients (
    id_client SERIAL PRIMARY KEY,
    nom VARCHAR(100) NOT NULL,
    prenom VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE,
    telephone VARCHAR(30),
    est_vip BOOLEAN NOT NULL DEFAULT FALSE,  -- metier
    a_eu_retard_derniere_location BOOLEAN NOT NULL DEFAULT FALSE -- metier
);

CREATE TABLE categories (
    id_categorie SERIAL PRIMARY KEY,
    libelle VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE marques (
    id_marque SERIAL PRIMARY KEY,
    libelle VARCHAR(100) NOT NULL UNIQUE
);


-- 2) parc

CREATE TABLE articles (
    id_article SERIAL PRIMARY KEY,
    id_categorie INT NOT NULL,
    id_marque INT NOT NULL,

    modele VARCHAR(120) NOT NULL,
    numero_serie VARCHAR(120) NOT NULL UNIQUE,
    date_achat DATE,

    statut VARCHAR(20) NOT NULL DEFAULT 'Disponible',   -- statut métier
    prix_journalier_actuel NUMERIC(10,2) NOT NULL DEFAULT 0,     -- prix locs

    CONSTRAINT fk_articles_categorie
        FOREIGN KEY (id_categorie) REFERENCES categories(id_categorie)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_articles_marque
        FOREIGN KEY (id_marque) REFERENCES marques(id_marque)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT ck_articles_statut     -- contraintes métier
        CHECK (statut IN ('Disponible','Loue','EnMaintenance','Rebut')),

    CONSTRAINT ck_articles_prix_non_negatif
        CHECK (prix_journalier_actuel >= 0)
);

-- 3) contrats + lignes

CREATE TABLE contrats_location (
    id_contrat SERIAL PRIMARY KEY,
    id_client INT NOT NULL,

    date_debut DATE NOT NULL,
    date_fin_prevue DATE NOT NULL,

    prix_final NUMERIC(12,2) NOT NULL DEFAULT 0,
    statut VARCHAR(20) NOT NULL DEFAULT 'Brouillon',
    date_creation TIMESTAMP NOT NULL DEFAULT NOW(),
    commentaire VARCHAR(255),

    CONSTRAINT fk_contrat_client
        FOREIGN KEY (id_client) REFERENCES clients(id_client)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT ck_contrats_dates
        CHECK (date_fin_prevue >= date_debut),

    CONSTRAINT ck_contrat_statut
        CHECK (statut IN ('Brouillon','Valide','Cloture','Annule')),    -- contraintes métier

    CONSTRAINT ck_contrat_prix_non_negatif
        CHECK (prix_final >= 0)
);

CREATE TABLE lignes_contrat (
    id_ligne SERIAL PRIMARY KEY,
    id_contrat INT NOT NULL,
    id_article INT NOT NULL,

    prix_journalier_applique NUMERIC(10,2) NOT NULL,
    nombre_jours INT NOT NULL,

    remise_duree_pct NUMERIC(5,2) NOT NULL DEFAULT 0,
    remise_vip_pct NUMERIC(5,2) NOT NULL DEFAULT 0,
    surcharge_retard_pct NUMERIC(5,2) NOT NULL DEFAULT 0,

    prix_total_ligne NUMERIC(12,2) NOT NULL,

    -- gestion du retour
    etat_retour VARCHAR(20) NOT NULL DEFAULT 'NonRetourne',
    date_retour_effective DATE,

    CONSTRAINT fk_ligne_contrat
        FOREIGN KEY (id_contrat) REFERENCES contrats_location(id_contrat)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    CONSTRAINT fk_ligne_article
        FOREIGN KEY (id_article) REFERENCES articles(id_article)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT uq_ligne_unique_article_par_contrat --  article unique...
        UNIQUE (id_contrat, id_article),

    CONSTRAINT ck_ligne_nombre_jours
        CHECK (nombre_jours > 0),

    CONSTRAINT ck_ligne_prix_non_negatif
        CHECK (prix_journalier_applique >= 0 AND prix_total_ligne >= 0),

    CONSTRAINT ck_ligne_pourcentages
        CHECK (remise_duree_pct >= 0 AND remise_vip_pct >= 0 AND surcharge_retard_pct >= 0),

    CONSTRAINT ck_lignes_etat_retour
        CHECK (etat_retour IN ('NonRetourne','Retourne'))
);
-- 4) RETOURS optionnel et séparé

CREATE TABLE retours (
    id_retour SERIAL PRIMARY KEY,
    id_ligne INT NOT NULL UNIQUE,

    date_retour_effective DATE NOT NULL,
    etat_retour VARCHAR(20) NOT NULL DEFAULT 'Retourne',
    commentaire VARCHAR(255),

    CONSTRAINT fk_retour_ligne
        FOREIGN KEY (id_ligne) REFERENCES lignes_contrat(id_ligne)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT ck_retour_etat
        CHECK (etat_retour IN ('Retourne','Litige','Casse'))
);


CREATE INDEX idx_contrats_date_fin_prevue ON contrats_location(date_fin_prevue);
CREATE INDEX idx_contrats_statut ON contrats_location(statut);

CREATE INDEX idx_lignes_contrat_id_contrat ON lignes_contrat(id_contrat);
CREATE INDEX idx_lignes_contrat_id_article ON lignes_contrat(id_article);

CREATE INDEX idx_articles_statut ON articles(statut);
