# ADR-0001 — Une seule table pour les équipements et les éléments de construction

- Statut : Accepté
- Date : 2026-09-08
- Concerne : [../DATA_MODEL.md](../DATA_MODEL.md) section 2.5, [../schema.sql](../schema.sql) table `asset`

## Contexte

Le cahier des charges décrit deux familles d'objets dans deux sections distinctes.

La section 6 décrit les **équipements** : pompe à chaleur, VMC, chauffe-eau, robot tondeuse.
Ils ont une marque, un modèle, une référence, un numéro de série, une date d'installation, une
garantie.

La section 8 insiste sur le fait que l'application « ne doit pas gérer uniquement des
appareils » et introduit les **éléments de construction** : joints de salle de bain, toiture,
gouttières, terrasse, façade, volets, fenêtres, clôture. Ils n'ont généralement ni numéro de
série ni garantie constructeur, mais ils ont besoin d'un suivi d'entretien.

La lecture naïve de ces deux sections conduit à créer deux tables.

## Options envisagées

### Option A — Deux tables `equipment` et `building_element`

Chaque table porte ses propres champs, ce qui évite les colonnes nullables.

Le problème apparaît dès qu'on regarde les satellites. Les deux familles ont besoin
d'exactement les mêmes : tâches d'entretien, interventions, problèmes, documents, coûts,
localisation. Il faudrait donc, pour chacune des six tables satellites, soit la dupliquer, soit
lui donner deux clés étrangères nullables mutuellement exclusives, soit passer par une relation
polymorphe sans intégrité référentielle.

Conséquences concrètes : le tableau de bord de la section 19 devrait faire l'union de deux
arbres de requêtes, la recherche globale de la section 25 devrait indexer deux tables, le
calcul des échéances devrait être écrit deux fois ou paramétré par type, et l'endpoint
`/api/ha/summary` devrait fusionner deux sources. Chaque nouvelle fonctionnalité paierait cette
dualité.

### Option B — Une table `asset` avec un discriminant `kind`

Une seule table, avec `kind` valant `equipment` ou `building_element`. Les champs propres aux
appareils (`manufacturer_id`, `brand`, `model`, `reference`, `serial_number`, `purchase_date`)
sont nullables.

### Option C — Héritage par table (`asset` plus `equipment_details`)

Une table de base et une table d'extension en un-à-un pour les champs d'appareil. Élimine les
colonnes nullables mais ajoute une jointure sur le chemin de lecture le plus fréquent de
l'application, pour un gain purement cosmétique sur une poignée de colonnes.

## Décision

**Option B.** Une table `asset` unique avec le discriminant `kind`.

Le raisonnement décisif est que la nature d'un objet n'est pas ce qui structure ce modèle : ce
qui le structure, c'est le fait qu'un objet ait une localisation, un historique, des entretiens,
des documents et des coûts. Un joint de salle de bain et une pompe à chaleur diffèrent par les
champs qu'ils remplissent, pas par leur comportement dans l'application. Le discriminant est une
information d'affichage et de filtrage, pas une frontière structurelle.

Cette lecture est confirmée par le cahier des charges lui-même : la section 26 place
`EQUIPMENT` et `HOUSE ELEMENTS` au même niveau, et l'exemple de fiche « Joints salle de bain »
de la section 8 a exactement la même forme qu'une fiche d'équipement.

## Conséquences

Positives :

- Les six tables satellites ont une seule clé étrangère, avec une intégrité référentielle réelle.
- Une seule implémentation du calcul d'échéances, du tableau de bord, de la recherche et de
  la timeline.
- Un utilisateur qui hésite sur la catégorisation d'un objet (un portail est-il un équipement ou
  un élément de construction ?) peut changer d'avis sans migration de données : c'est un simple
  `UPDATE` d'une colonne.

Négatives, et comment elles sont traitées :

- Six colonnes nullables qui n'ont pas de sens pour un élément de construction. Acceptable :
  SQLite ne stocke pas les `NULL` de manière coûteuse, et l'interface masque les champs non
  pertinents selon `kind`.
- Rien n'empêche en base de renseigner un numéro de série sur une toiture. La validation
  incombe donc à la couche Pydantic, pas au schéma. C'est un déplacement de responsabilité
  assumé, pas une absence de validation.
- Le nom `asset` est un terme technique en anglais qui n'apparaît pas dans l'interface : côté
  utilisateur, on parle d'« équipements » et d'« éléments de la maison ».

## Note d'implémentation

Les catégories (table `category`) servent les deux familles. Les catégories intégrées liées au
bâti sont regroupées sous la catégorie racine `structure`, ce qui donne à l'interface un moyen
naturel de proposer les bonnes catégories selon le `kind` choisi, sans contrainte en base.
