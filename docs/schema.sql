-- =============================================================================
-- HomeKeeper — schema de reference SQLite
-- =============================================================================
--
-- Ce fichier est la reference du modele de donnees. Il est documente dans
-- docs/DATA_MODEL.md et les decisions structurantes sont justifiees dans docs/adr/.
--
-- La revision Alembic `0001_schema` execute la copie packagée
-- `backend/src/homekeeper_api/schema.sql`, qui doit rester identique a ce fichier.
--
-- Conventions :
--   * dates seules      -> TEXT 'YYYY-MM-DD'
--   * horodatages       -> TEXT 'YYYY-MM-DDTHH:MM:SSZ' (UTC)
--   * montants          -> INTEGER en centimes (jamais de flottant, cf. table cost)
--   * booleens          -> INTEGER 0 / 1
--   * enumerations      -> TEXT contraint par CHECK, et miroir en enum Python
--
-- Verification rapide :
--   sqlite3 /tmp/homekeeper_check.db < docs/schema.sql
-- =============================================================================

PRAGMA foreign_keys = ON;      -- OBLIGATOIRE a chaque connexion : SQLite ne l'active
                               -- pas par defaut, et sans lui aucune des regles
                               -- ON DELETE ci-dessous ne s'applique.
PRAGMA journal_mode = WAL;     -- lectures concurrentes pendant les ecritures


-- =============================================================================
-- 1. home — la maison
-- =============================================================================
-- Une seule ligne est exposee en V1. La table existe pour ne pas avoir a
-- introduire une cle etrangere partout si le multi-maisons devient necessaire.

CREATE TABLE home (
    id                      INTEGER PRIMARY KEY,
    name                    TEXT    NOT NULL,

    -- Facultatif, jamais transmis nulle part. N'existe que pour le confort de
    -- l'utilisateur (principe local-first).
    address                 TEXT,

    -- Devise par defaut proposee a la saisie d'un cout. Chaque cout conserve sa
    -- propre devise pour ne pas corrompre l'historique en cas de changement.
    currency                TEXT    NOT NULL DEFAULT 'EUR',

    -- Seuil global de passage en statut 'due_soon'. Surchargeable par tache.
    due_soon_threshold_days INTEGER NOT NULL DEFAULT 30
                            CHECK (due_soon_threshold_days >= 0),

    created_at              TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at              TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);


-- =============================================================================
-- 1b. location_type — types de lieux personnalisables
-- =============================================================================
-- Purement indicatif : sert a choisir une icone et grouper l'affichage, jamais
-- a contraindre la hierarchie. Pre-alimente avec is_builtin = 1 (voir la
-- section 'Donnees de reference' en fin de fichier) ; l'utilisateur peut en
-- creer d'autres et renommer ou supprimer les siens.

CREATE TABLE location_type (
    id         INTEGER PRIMARY KEY,
    slug       TEXT    NOT NULL UNIQUE,   -- stable, sert aux mises a jour du seed
    name       TEXT    NOT NULL,

    -- Les types integres ne sont pas supprimables (evite qu'une mise a jour ne
    -- les recree), mais peuvent etre renommes.
    is_builtin INTEGER NOT NULL DEFAULT 0 CHECK (is_builtin IN (0, 1)),

    sort_order INTEGER NOT NULL DEFAULT 0,

    created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);


-- =============================================================================
-- 2. location — arborescence des lieux
-- =============================================================================
-- Auto-referencee, profondeur libre : couvre 'Maison > Rez-de-chaussee > Cuisine'
-- comme les cas plats ('Jardin').

CREATE TABLE location (
    id                INTEGER PRIMARY KEY,
    home_id           INTEGER NOT NULL REFERENCES home(id) ON DELETE CASCADE,
    parent_id         INTEGER          REFERENCES location(id) ON DELETE RESTRICT,

    name              TEXT    NOT NULL,

    -- RESTRICT : un type utilise par au moins un lieu ne peut pas etre supprime
    -- sans reaffecter ces lieux au prealable.
    location_type_id  INTEGER NOT NULL REFERENCES location_type(id) ON DELETE RESTRICT,

    sort_order        INTEGER NOT NULL DEFAULT 0,   -- ordre explicite, pas alphabetique
    notes             TEXT,

    created_at        TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at        TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),

    -- Un lieu ne peut pas etre son propre parent. Les cycles plus longs ne sont
    -- pas detectables par CHECK : la couche service les refuse.
    CHECK (parent_id IS NULL OR parent_id <> id),

    UNIQUE (home_id, parent_id, name)
);

CREATE INDEX ix_location_home          ON location(home_id);
CREATE INDEX ix_location_parent        ON location(parent_id);
CREATE INDEX ix_location_location_type ON location(location_type_id);


-- =============================================================================
-- 3. category — categories d'equipements
-- =============================================================================
-- Hierarchiques ('Chauffage > Pompe a chaleur'). Les categories de la section 7
-- du cahier des charges sont pre-alimentees avec is_builtin = 1 (voir la section
-- 'Donnees de reference' en fin de fichier).

CREATE TABLE category (
    id         INTEGER PRIMARY KEY,
    parent_id  INTEGER          REFERENCES category(id) ON DELETE RESTRICT,

    name       TEXT    NOT NULL,
    slug       TEXT    NOT NULL UNIQUE,   -- stable, sert aux mises a jour du seed
    icon       TEXT,                      -- identifiant mdi:, ex. 'mdi:heat-pump'

    -- Les categories integrees ne sont pas supprimables (evite qu'une mise a jour
    -- ne les recree), mais peuvent etre masquees par l'utilisateur.
    is_builtin INTEGER NOT NULL DEFAULT 0 CHECK (is_builtin IN (0, 1)),
    is_hidden  INTEGER NOT NULL DEFAULT 0 CHECK (is_hidden  IN (0, 1)),

    sort_order INTEGER NOT NULL DEFAULT 0,

    created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),

    CHECK (parent_id IS NULL OR parent_id <> id)
);

CREATE INDEX ix_category_parent ON category(parent_id);


-- =============================================================================
-- 4. manufacturer — fiche constructeur
-- =============================================================================
-- Mutualisee entre plusieurs equipements. Le cahier des charges (section 16)
-- distingue les liens generiques du constructeur (ici) des liens propres a un
-- equipement, qui sont portes par asset.

CREATE TABLE manufacturer (
    id                INTEGER PRIMARY KEY,
    name              TEXT    NOT NULL UNIQUE,
    website_url       TEXT,
    support_url       TEXT,
    support_phone     TEXT,
    documentation_url TEXT,
    parts_url         TEXT,
    notes             TEXT,

    created_at        TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at        TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);


-- =============================================================================
-- 5. asset — equipements ET elements de construction
-- =============================================================================
-- Table centrale. Le discriminant `kind` distingue les deux natures d'objets des
-- sections 6 et 8 du cahier des charges. Voir adr/0001-table-asset-unique.md :
-- les deux partagent exactement les memes satellites (entretiens, interventions,
-- documents, couts, localisation), les separer imposerait de dupliquer six
-- relations et toute la logique d'echeances.

CREATE TABLE asset (
    id              INTEGER PRIMARY KEY,
    home_id         INTEGER NOT NULL REFERENCES home(id) ON DELETE CASCADE,

    kind            TEXT    NOT NULL
                    CHECK (kind IN ('equipment',          -- pompe a chaleur, VMC, spa...
                                    'building_element')),  -- toiture, joints, volets...

    name            TEXT    NOT NULL,          -- nom personnalise par l'utilisateur
    category_id     INTEGER          REFERENCES category(id)     ON DELETE RESTRICT,
    location_id     INTEGER          REFERENCES location(id)     ON DELETE RESTRICT,

    -- Un equipement retire reste en base : son historique et ses couts font partie
    -- de l'histoire de la maison. L'interface privilegie 'removed' a la suppression.
    status          TEXT    NOT NULL DEFAULT 'active'
                    CHECK (status IN ('planned', 'active', 'inactive', 'removed')),

    -- ---- Champs propres aux appareils, tous nullables ----
    manufacturer_id INTEGER          REFERENCES manufacturer(id) ON DELETE RESTRICT,

    -- `brand` coexiste volontairement avec manufacturer_id : la plupart des
    -- equipements seront saisis vite, avec une marque en texte libre. La fiche
    -- constructeur peut etre creee et rattachee plus tard.
    brand           TEXT,
    model           TEXT,
    reference       TEXT,
    serial_number   TEXT,

    purchase_date   TEXT,
    install_date    TEXT,

    -- Liens propres a cet equipement precis (section 16).
    manual_url      TEXT,
    support_url     TEXT,
    parts_url       TEXT,

    notes           TEXT,

    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX ix_asset_home         ON asset(home_id);
CREATE INDEX ix_asset_kind         ON asset(kind);
CREATE INDEX ix_asset_location     ON asset(location_id);
CREATE INDEX ix_asset_category     ON asset(category_id);
CREATE INDEX ix_asset_manufacturer ON asset(manufacturer_id);


-- =============================================================================
-- 5b. ha_link — liaison d'une fiche a un appareil ou une entite Home Assistant
-- =============================================================================
-- Remplace l'ancienne colonne asset.ha_entity_id. Voir
-- adr/0006-liaison-aux-appareils-home-assistant.md.
--
-- Un robot aspirateur est un APPAREIL qui porte une dizaine d'entites (commande,
-- filtre, brosses...). Une colonne unique perdait cette structure et cassait
-- au premier renommage d'entity_id.
--
-- On stocke l'UUID de registre (stable), jamais l'entity_id comme cle.
-- L'entity_id et le nom amical sont copies au moment de la liaison pour que la
-- fiche reste lisible si l'appareil disparait de Home Assistant.

CREATE TABLE ha_link (
    id                    INTEGER PRIMARY KEY,
    asset_id              INTEGER NOT NULL REFERENCES asset(id) ON DELETE CASCADE,

    -- device : le rattachement vise l'appareil (cas normal, Roborock, PAC...).
    -- entity : rattachement a une entite isolee, avec ou sans appareil parent
    --          (capteur MQTT orphelin, consommable d'un appareil deja lie).
    link_kind             TEXT    NOT NULL
                          CHECK (link_kind IN ('device', 'entity')),

    -- UUID du device registry. Obligatoire pour link_kind = 'device'.
    -- Recopie facultative sur un lien d'entite, pour regrouper sans jointure HA.
    ha_device_id          TEXT,

    -- UUID du entity registry (champ `id`, PAS unique_id d'integration, PAS
    -- entity_id). Obligatoire pour link_kind = 'entity'.
    ha_entity_registry_id TEXT,

    -- Instantanes : ce que l'utilisateur a vu au moment de lier. Survivent a
    -- un renommage, a une suppression d'integration, a un remplacement physique.
    entity_id_at_link     TEXT,     -- ex. vacuum.roborock_s8
    name_at_link          TEXT    NOT NULL,  -- ex. 'Roborock S8 salon'
    domain_at_link        TEXT,     -- vacuum, sensor, binary_sensor...

    -- Qualifie l'usage HomeKeeper de cette cible, independamment du domain HA.
    --   primary     : l'appareil ou l'entite principale de la fiche
    --   command     : entite de commande (vacuum.start, climate.set_hvac_mode)
    --   consumable  : usure d'un consommable (filtre, brosse) — prevu pour la V4
    --   diagnostic  : etat utile a afficher (batterie, erreur, surface nettoye)
    --   other
    role                  TEXT    NOT NULL DEFAULT 'primary'
                          CHECK (role IN ('primary', 'command', 'consumable',
                                          'diagnostic', 'other')),

    -- Precision facultative quand role = 'consumable'.
    consumable_kind       TEXT
                          CHECK (consumable_kind IS NULL OR consumable_kind IN (
                              'filter', 'main_brush', 'side_brush', 'sensor',
                              'other'
                          )),

    -- Derniere fois ou le registre HA a confirme que cette cible existait encore.
    -- NULL = jamais resolu depuis la saisie (lien importe, HA injoignable).
    last_resolved_at      TEXT,

    -- ok : vu dans le registre. missing : plus dans le registre.
    -- unresolved : pas encore verifie.
    resolution_status     TEXT    NOT NULL DEFAULT 'unresolved'
                          CHECK (resolution_status IN ('ok', 'missing', 'unresolved')),

    created_at            TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at            TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),

    CHECK (
           (link_kind = 'device'
            AND ha_device_id IS NOT NULL
            AND ha_entity_registry_id IS NULL)
        OR (link_kind = 'entity'
            AND ha_entity_registry_id IS NOT NULL)
    ),

    CHECK (
           (role = 'consumable' AND consumable_kind IS NOT NULL)
        OR (role <> 'consumable' AND consumable_kind IS NULL)
    )
);

-- Un appareil HA ne se rattache qu'a une seule fiche.
CREATE UNIQUE INDEX ux_ha_link_device
    ON ha_link(ha_device_id) WHERE link_kind = 'device';

-- Une entite HA ne se rattache qu'a une seule fiche.
CREATE UNIQUE INDEX ux_ha_link_entity
    ON ha_link(ha_entity_registry_id) WHERE ha_entity_registry_id IS NOT NULL;

-- Au plus un lien 'primary' par fiche.
CREATE UNIQUE INDEX ux_ha_link_primary
    ON ha_link(asset_id) WHERE role = 'primary';

CREATE INDEX ix_ha_link_asset ON ha_link(asset_id);
CREATE INDEX ix_ha_link_status ON ha_link(resolution_status) WHERE resolution_status <> 'ok';


-- =============================================================================
-- 6. warranty — garanties
-- =============================================================================
-- Relation un-a-un avec asset.

CREATE TABLE warranty (
    id              INTEGER PRIMARY KEY,
    asset_id        INTEGER NOT NULL UNIQUE REFERENCES asset(id) ON DELETE CASCADE,

    -- Point de depart REEL de la garantie : pas toujours la date d'achat, certains
    -- constructeurs la font courir a partir de l'installation. L'application propose
    -- la date d'achat par defaut et laisse corriger.
    start_date      TEXT    NOT NULL,
    duration_months INTEGER CHECK (duration_months IS NULL OR duration_months > 0),

    -- Colonne GENEREE : traduction directe de la section 17 ('date de fin calculee
    -- automatiquement'). Garantit que la date de fin ne peut jamais deriver de la
    -- duree saisie, ce qu'une colonne maintenue par l'application ne garantit pas.
    -- VIRTUAL et non STORED : indexable en SQLite, sans cout de stockage.
    end_date        TEXT    GENERATED ALWAYS AS (
                        CASE WHEN duration_months IS NULL THEN NULL
                             ELSE date(start_date, '+' || duration_months || ' months')
                        END
                    ) VIRTUAL,

    provider        TEXT,      -- installateur, revendeur, assureur...
    terms_url       TEXT,
    notes           TEXT,

    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- Utilise par le rappel 'garantie expirant dans 30 jours' (section 21).
CREATE INDEX ix_warranty_end_date ON warranty(end_date);


-- =============================================================================
-- 7. maintenance_task — taches d'entretien
-- =============================================================================

CREATE TABLE maintenance_task (
    id                  INTEGER PRIMARY KEY,

    -- Exactement l'un des deux est renseigne : une tache est soit rattachee a un
    -- equipement, soit globale a la maison ('verifier les detecteurs de fumee').
    asset_id            INTEGER          REFERENCES asset(id) ON DELETE CASCADE,
    home_id             INTEGER          REFERENCES home(id)  ON DELETE CASCADE,

    name                TEXT    NOT NULL,
    description         TEXT,   -- affiche cote UI comme "Notes"

    priority            TEXT    NOT NULL DEFAULT 'normal'
                        CHECK (priority IN ('low', 'normal', 'high', 'critical')),

    -- ---- Preparation (facultatif, pas d'invariant impose : remplissable
    -- meme si needs_part_replacement = 0) ----
    needs_part_replacement  INTEGER NOT NULL DEFAULT 0 CHECK (needs_part_replacement IN (0, 1)),
    replacement_part_name   TEXT,   -- ex. 'Filtre a eau 10 pouces'
    replacement_part_source TEXT,   -- lien d'achat OU nom d'enseigne
    preparation_notes       TEXT,   -- outils specifiques, produits, autres a prevoir

    -- ---- Planification (section 9) ----
    recurrence_type     TEXT    NOT NULL DEFAULT 'none'
                        CHECK (recurrence_type IN ('none',          -- pas de recurrence auto
                                                   'days',          -- tous les X jours
                                                   'months',        -- tous les X mois
                                                   'years',         -- tous les X ans
                                                   'annual_fixed',  -- chaque annee a date fixe
                                                   'custom_date')), -- date ponctuelle
    recurrence_interval INTEGER,      -- le X de 'tous les X ...'

    -- LE champ le plus important du modele. Voir adr/0004-ancrage-de-recurrence.md.
    --   from_completion : la prochaine echeance part de la date REELLE de realisation
    --                     (nettoyage de filtres fait en retard -> le suivant decale).
    --   from_due_date   : la prochaine echeance part de la date THEORIQUE
    --                     (entretien annuel contractuel : reste du a la meme periode).
    -- Sans cette distinction, un entretien reglementaire derive de plusieurs mois
    -- au bout de quelques annees.
    recurrence_anchor   TEXT    NOT NULL DEFAULT 'from_completion'
                        CHECK (recurrence_anchor IN ('from_completion', 'from_due_date')),

    fixed_month         INTEGER CHECK (fixed_month IS NULL OR fixed_month BETWEEN 1 AND 12),
    fixed_day           INTEGER CHECK (fixed_day   IS NULL OR fixed_day   BETWEEN 1 AND 31),
    custom_due_date     TEXT,

    last_completed_on   TEXT,

    -- DENORMALISATION ASSUMEE : recalculee par la couche service a chaque validation
    -- d'entretien et a chaque modification de la planification. Indexee car le
    -- tableau de bord et /api/ha/summary la trient et la filtrent a chaque appel du
    -- coordinator Home Assistant.
    next_due_on         TEXT,

    -- Surcharge locale du seuil 'bientot' de la maison.
    lead_time_days      INTEGER CHECK (lead_time_days IS NULL OR lead_time_days >= 0),

    is_active           INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),

    created_at          TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at          TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),

    -- Rattachement exclusif : equipement OU maison.
    CHECK ((asset_id IS NOT NULL) + (home_id IS NOT NULL) = 1),

    -- Coherence entre le type de recurrence et les champs qu'il exige.
    CHECK (
           (recurrence_type = 'none')
        OR (recurrence_type IN ('days', 'months', 'years')
            AND recurrence_interval IS NOT NULL AND recurrence_interval >= 1)
        OR (recurrence_type = 'annual_fixed'
            AND fixed_month IS NOT NULL AND fixed_day IS NOT NULL)
        OR (recurrence_type = 'custom_date'
            AND custom_due_date IS NOT NULL)
    )
);

CREATE INDEX ix_task_asset    ON maintenance_task(asset_id);
CREATE INDEX ix_task_home     ON maintenance_task(home_id);
CREATE INDEX ix_task_next_due ON maintenance_task(next_due_on) WHERE is_active = 1;


-- =============================================================================
-- 8. issue — problemes et reparations (section 12)
-- =============================================================================
-- Declaree avant intervention car intervention y fait reference.

CREATE TABLE issue (
    id          INTEGER PRIMARY KEY,
    asset_id    INTEGER NOT NULL REFERENCES asset(id) ON DELETE CASCADE,

    title       TEXT    NOT NULL,     -- 'La VMC fait beaucoup de bruit'
    description TEXT,
    action_taken TEXT,                -- 'Nettoyage effectue'
    result      TEXT,                 -- 'Probleme resolu'

    status      TEXT    NOT NULL DEFAULT 'open'
                CHECK (status IN ('open', 'in_progress', 'resolved')),
    severity    TEXT    NOT NULL DEFAULT 'normal'
                CHECK (severity IN ('low', 'normal', 'high', 'critical')),

    opened_on   TEXT    NOT NULL,
    resolved_on TEXT,

    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),

    -- resolved_on renseigne si et seulement si le probleme est resolu.
    CHECK ((status =  'resolved' AND resolved_on IS NOT NULL)
        OR (status <> 'resolved' AND resolved_on IS NULL))
);

CREATE INDEX ix_issue_asset  ON issue(asset_id);
CREATE INDEX ix_issue_status ON issue(status) WHERE status <> 'resolved';


-- =============================================================================
-- 9. intervention — toute action datee sur un equipement
-- =============================================================================
-- Alimente l'historique (vue v_asset_timeline).

CREATE TABLE intervention (
    id                INTEGER PRIMARY KEY,
    asset_id          INTEGER NOT NULL REFERENCES asset(id) ON DELETE CASCADE,

    -- Nullable : une intervention peut decouler d'une tache planifiee (bouton
    -- 'entretien effectue') ou etre saisie librement.
    task_id           INTEGER          REFERENCES maintenance_task(id) ON DELETE SET NULL,

    -- Nullable : relie l'intervention au probleme qu'elle traite.
    issue_id          INTEGER          REFERENCES issue(id) ON DELETE SET NULL,

    intervention_type TEXT    NOT NULL DEFAULT 'maintenance'
                      CHECK (intervention_type IN ('maintenance', 'repair', 'installation',
                                                   'inspection', 'replacement', 'other')),

    performed_on      TEXT    NOT NULL,
    performed_by      TEXT,            -- texte libre : 'moi', 'Dupont Chauffage'
    notes             TEXT,

    created_at        TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at        TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX ix_intervention_asset ON intervention(asset_id, performed_on DESC);
CREATE INDEX ix_intervention_task  ON intervention(task_id);
CREATE INDEX ix_intervention_issue ON intervention(issue_id);


-- =============================================================================
-- 10. cost — depenses (section 18)
-- =============================================================================

CREATE TABLE cost (
    id              INTEGER PRIMARY KEY,
    asset_id        INTEGER NOT NULL REFERENCES asset(id) ON DELETE CASCADE,

    -- Nullable. Quand l'utilisateur saisit un cout en validant un entretien, UNE
    -- seule ligne est creee et rattachee a l'intervention : pas de double saisie,
    -- et le cout reste visible depuis les deux entrees.
    -- SET NULL et non CASCADE : supprimer une intervention par erreur ne doit pas
    -- effacer la facture.
    intervention_id INTEGER          REFERENCES intervention(id) ON DELETE SET NULL,

    cost_type       TEXT    NOT NULL
                    CHECK (cost_type IN ('purchase', 'installation', 'maintenance',
                                         'repair', 'parts', 'subscription', 'other')),
    label           TEXT,

    -- ENTIER EN CENTIMES, jamais un flottant : additionner des flottants pour
    -- afficher un total a l'utilisateur produit des erreurs d'arrondi visibles,
    -- et la section 18 affiche explicitement un total par equipement.
    amount_cents    INTEGER NOT NULL,

    -- Stockee par ligne pour ne pas corrompre l'historique si l'utilisateur change
    -- la devise de la maison.
    currency        TEXT    NOT NULL DEFAULT 'EUR',

    incurred_on     TEXT    NOT NULL,
    notes           TEXT,

    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX ix_cost_asset        ON cost(asset_id);
CREATE INDEX ix_cost_intervention ON cost(intervention_id);


-- =============================================================================
-- 11. document — documents et liens (sections 13 et 14)
-- =============================================================================
-- Trois modes de stockage dans une seule table. Voir
-- adr/0002-document-a-trois-modes-de-stockage.md.

CREATE TABLE document (
    id                  INTEGER PRIMARY KEY,

    -- ---- Rattachement : EXACTEMENT une des cinq cles ----
    -- Une table de liaison polymorphe aurait permis les rattachements multiples,
    -- au prix de l'integrite referentielle. Un document orphelin apres suppression
    -- d'un equipement est exactement la perte silencieuse que ce projet doit eviter.
    -- Une facture rattachee a une intervention reste accessible depuis l'equipement
    -- par jointure.
    home_id             INTEGER REFERENCES home(id)             ON DELETE CASCADE,
    asset_id            INTEGER REFERENCES asset(id)            ON DELETE CASCADE,
    maintenance_task_id INTEGER REFERENCES maintenance_task(id) ON DELETE CASCADE,
    intervention_id     INTEGER REFERENCES intervention(id)     ON DELETE CASCADE,
    issue_id            INTEGER REFERENCES issue(id)            ON DELETE CASCADE,

    name                TEXT    NOT NULL,
    doc_type            TEXT    NOT NULL DEFAULT 'other'
                        CHECK (doc_type IN ('invoice', 'manual', 'user_guide', 'certificate',
                                            'warranty', 'service_contract', 'photo', 'other')),

    -- ---- Mode de stockage (section 14) ----
    --   local_file     : le fichier est chez l'utilisateur, sous /data/documents/
    --   external_link  : Nextcloud, Drive, OneDrive, NAS... l'app ne stocke que l'URL
    --   reference_note : simple note, 'e-mail du 12/05/2024', 'classeur au garage'
    -- C'est ce qui rend le local-first reellement optionnel plutot que subi.
    storage_mode        TEXT    NOT NULL
                        CHECK (storage_mode IN ('local_file', 'external_link', 'reference_note')),

    file_path           TEXT,      -- relatif a /data/documents/, ex. '7/a1b2c3.pdf'
    file_size           INTEGER,
    mime_type           TEXT,
    url                 TEXT,
    reference_note      TEXT,

    -- Photo principale de l'equipement (section 24).
    is_primary_photo    INTEGER NOT NULL DEFAULT 0 CHECK (is_primary_photo IN (0, 1)),

    notes               TEXT,
    created_at          TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at          TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),

    -- Rattachement exclusif. En SQLite, (x IS NOT NULL) vaut 0 ou 1.
    CHECK ((home_id             IS NOT NULL)
         + (asset_id            IS NOT NULL)
         + (maintenance_task_id IS NOT NULL)
         + (intervention_id     IS NOT NULL)
         + (issue_id            IS NOT NULL) = 1),

    -- Coherence entre le mode de stockage et la colonne de contenu utilisee.
    CHECK (
           (storage_mode = 'local_file'
            AND file_path      IS NOT NULL AND url IS NULL AND reference_note IS NULL)
        OR (storage_mode = 'external_link'
            AND url            IS NOT NULL AND file_path IS NULL AND reference_note IS NULL)
        OR (storage_mode = 'reference_note'
            AND reference_note IS NOT NULL AND file_path IS NULL AND url IS NULL)
    ),

    -- Une photo principale est necessairement rattachee a un equipement.
    CHECK (is_primary_photo = 0 OR (asset_id IS NOT NULL AND doc_type = 'photo'))
);

CREATE INDEX ix_document_asset        ON document(asset_id);
CREATE INDEX ix_document_intervention ON document(intervention_id);
CREATE INDEX ix_document_issue        ON document(issue_id);
CREATE INDEX ix_document_task         ON document(maintenance_task_id);
CREATE INDEX ix_document_type         ON document(doc_type);

-- Au plus une photo principale par equipement.
CREATE UNIQUE INDEX ux_document_primary_photo
    ON document(asset_id) WHERE is_primary_photo = 1;


-- =============================================================================
-- VUES DERIVEES
-- =============================================================================

-- -----------------------------------------------------------------------------
-- v_asset_timeline — historique unifie (section 11)
-- -----------------------------------------------------------------------------
-- L'historique est une VUE, pas une table. Voir adr/0003-historique-derive.md :
-- une table `history` alimentee en parallele des tables metier serait une double
-- ecriture, donc une source permanente de desynchronisation. Une vue est par
-- construction toujours coherente.

CREATE VIEW v_asset_timeline AS

    -- Installation de l'equipement
    SELECT a.id                AS asset_id,
           'installation'      AS event_type,
           a.install_date      AS occurred_on,
           'Installation'      AS title,
           a.name              AS detail,
           NULL                AS amount_cents,
           'asset'             AS source_table,
           a.id                AS source_id
    FROM   asset a
    WHERE  a.install_date IS NOT NULL

    UNION ALL

    -- Interventions : entretiens, reparations, inspections...
    SELECT i.asset_id,
           'intervention',
           i.performed_on,
           i.intervention_type,
           COALESCE(i.notes, i.performed_by),
           NULL,
           'intervention',
           i.id
    FROM   intervention i

    UNION ALL

    -- Ouverture d'un probleme
    SELECT s.asset_id,
           'issue_opened',
           s.opened_on,
           s.title,
           s.description,
           NULL,
           'issue',
           s.id
    FROM   issue s

    UNION ALL

    -- Resolution d'un probleme
    SELECT s.asset_id,
           'issue_resolved',
           s.resolved_on,
           s.title,
           COALESCE(s.result, s.action_taken),
           NULL,
           'issue',
           s.id
    FROM   issue s
    WHERE  s.resolved_on IS NOT NULL

    UNION ALL

    -- Couts autonomes uniquement : ceux rattaches a une intervention sont deja
    -- representes par la ligne d'intervention, on evite le doublon dans la timeline.
    SELECT c.asset_id,
           'cost',
           c.incurred_on,
           c.cost_type,
           c.label,
           c.amount_cents,
           'cost',
           c.id
    FROM   cost c
    WHERE  c.intervention_id IS NULL

    UNION ALL

    -- Fin de garantie (passee ou a venir)
    SELECT w.asset_id,
           'warranty_end',
           w.end_date,
           'Fin de garantie',
           w.provider,
           NULL,
           'warranty',
           w.id
    FROM   warranty w
    WHERE  w.end_date IS NOT NULL;


-- -----------------------------------------------------------------------------
-- v_task_status — statut derive de chaque tache
-- -----------------------------------------------------------------------------
-- Source UNIQUE du tableau de bord (section 19) et du contrat /api/ha/summary.
-- Les couleurs de l'interface et les etats des capteurs Home Assistant derivent
-- donc des memes valeurs, ce qui les empeche de diverger.

CREATE VIEW v_task_status AS
    SELECT t.id                AS task_id,
           t.asset_id,
           t.home_id,
           t.name,
           t.priority,
           t.next_due_on,
           t.last_completed_on,

           -- Seuil effectif : surcharge de la tache, sinon seuil de la maison.
           COALESCE(t.lead_time_days, h.due_soon_threshold_days) AS effective_lead_time_days,

           -- Negatif = en retard de N jours.
           CAST(julianday(t.next_due_on) - julianday(date('now')) AS INTEGER) AS days_until_due,

           CASE
               WHEN t.next_due_on IS NULL THEN 'unscheduled'
               WHEN julianday(t.next_due_on) < julianday(date('now')) THEN 'overdue'
               WHEN julianday(t.next_due_on) - julianday(date('now'))
                    <= COALESCE(t.lead_time_days, h.due_soon_threshold_days) THEN 'due_soon'
               ELSE 'ok'
           END AS status

    FROM       maintenance_task t
    LEFT JOIN  asset a ON a.id = t.asset_id
    -- La maison provient soit de l'equipement, soit du rattachement direct.
    LEFT JOIN  home  h ON h.id = COALESCE(a.home_id, t.home_id)
    WHERE      t.is_active = 1;


-- =============================================================================
-- DONNEES DE REFERENCE — types de lieux
-- =============================================================================
-- Pre-alimentes avec is_builtin = 1 : renommables mais jamais supprimables.
-- L'utilisateur peut en creer d'autres avec is_builtin = 0.

INSERT INTO location_type (slug, name, is_builtin, sort_order) VALUES
    ('room',      'Piece',      1, 10),
    ('floor',     'Etage',      1, 20),
    ('zone',      'Zone',       1, 30),
    ('building',  'Batiment',   1, 40),
    ('outdoor',   'Exterieur',  1, 50),
    ('technical', 'Technique',  1, 60);


-- =============================================================================
-- DONNEES DE REFERENCE — categories de la section 7
-- =============================================================================
-- Pre-alimentees avec is_builtin = 1. L'utilisateur peut les masquer mais pas les
-- supprimer, et en creer d'autres avec is_builtin = 0.
-- Les sous-categories sont rattachees par slug pour rester independantes des id.

INSERT INTO category (slug, name, icon, is_builtin, sort_order) VALUES
    ('heating',     'Chauffage',    'mdi:radiator',        1, 10),
    ('ventilation', 'Ventilation',  'mdi:air-filter',      1, 20),
    ('water',       'Eau',          'mdi:water-pump',      1, 30),
    ('electricity', 'Electricite',  'mdi:flash',           1, 40),
    ('outdoor',     'Exterieur',    'mdi:home-outline',    1, 50),
    ('appliances',  'Electromenager','mdi:fridge-outline', 1, 55),
    ('structure',   'Batiment',     'mdi:home-roof',       1, 60);

INSERT INTO category (parent_id, slug, name, icon, is_builtin, sort_order)
SELECT p.id, v.slug, v.name, v.icon, 1, v.sort_order
FROM (
    SELECT 'heating'     AS parent, 'heat_pump'        AS slug, 'Pompe a chaleur'      AS name, 'mdi:heat-pump'          AS icon, 10 AS sort_order
    UNION ALL SELECT 'heating',     'boiler',            'Chaudiere',             'mdi:water-boiler',        20
    UNION ALL SELECT 'heating',     'radiator',          'Radiateur',             'mdi:radiator',            30
    UNION ALL SELECT 'heating',     'stove',             'Poele',                 'mdi:fireplace',           40
    UNION ALL SELECT 'heating',     'air_conditioning',  'Climatisation',         'mdi:air-conditioner',     50

    UNION ALL SELECT 'ventilation', 'vmc',               'VMC',                   'mdi:hvac',                10
    UNION ALL SELECT 'ventilation', 'extractor',         'Extracteur',            'mdi:fan',                 20
    UNION ALL SELECT 'ventilation', 'air_purifier',      'Purificateur d''air',   'mdi:air-purifier',        30

    UNION ALL SELECT 'water',       'water_heater',      'Chauffe-eau',           'mdi:water-boiler',        10
    UNION ALL SELECT 'water',       'pump',              'Pompe',                 'mdi:water-pump',          20
    UNION ALL SELECT 'water',       'water_softener',    'Adoucisseur',           'mdi:water-opacity',       30
    UNION ALL SELECT 'water',       'filtration',        'Filtration',            'mdi:filter',              40

    UNION ALL SELECT 'electricity', 'electrical_panel',  'Tableau electrique',    'mdi:electric-switch',     10
    UNION ALL SELECT 'electricity', 'solar_inverter',    'Onduleur solaire',      'mdi:solar-power',         20
    UNION ALL SELECT 'electricity', 'battery',           'Batterie',              'mdi:battery',             30
    UNION ALL SELECT 'electricity', 'generator',         'Groupe electrogene',    'mdi:engine',              40

    UNION ALL SELECT 'outdoor',     'gate',              'Portail',               'mdi:gate',                10
    UNION ALL SELECT 'outdoor',     'pool',              'Piscine',               'mdi:pool',                20
    UNION ALL SELECT 'outdoor',     'spa',               'Spa',                   'mdi:hot-tub',             30
    UNION ALL SELECT 'outdoor',     'robot_mower',       'Robot tondeuse',        'mdi:robot-mower',         40
    UNION ALL SELECT 'outdoor',     'irrigation',        'Arrosage automatique',  'mdi:sprinkler-variant',   50

    UNION ALL SELECT 'appliances',  'vacuum',            'Aspirateur',            'mdi:robot-vacuum',        10
    UNION ALL SELECT 'appliances',  'washing_machine',   'Lave-linge',            'mdi:washing-machine',     20
    UNION ALL SELECT 'appliances',  'dishwasher',        'Lave-vaisselle',        'mdi:dishwasher',          30
    UNION ALL SELECT 'appliances',  'fridge',            'Refrigerateur',         'mdi:fridge',              40
    UNION ALL SELECT 'appliances',  'oven',              'Four',                  'mdi:stove',               50

    -- Elements de construction (section 8) : meme table category, utilises par les
    -- assets de kind = 'building_element'.
    UNION ALL SELECT 'structure',   'roof',              'Toiture',               'mdi:home-roof',           10
    UNION ALL SELECT 'structure',   'gutters',           'Gouttieres',            'mdi:water-outline',       20
    UNION ALL SELECT 'structure',   'facade',            'Facade',                'mdi:wall',                30
    UNION ALL SELECT 'structure',   'terrace',           'Terrasse',              'mdi:floor-plan',          40
    UNION ALL SELECT 'structure',   'windows',           'Fenetres',              'mdi:window-closed',       50
    UNION ALL SELECT 'structure',   'shutters',          'Volets',                'mdi:window-shutter',      60
    UNION ALL SELECT 'structure',   'fence',             'Cloture',               'mdi:fence',               70
    UNION ALL SELECT 'structure',   'sealant',           'Joints',                'mdi:blur-linear',         80
) v
JOIN category p ON p.slug = v.parent;
