# ADR-0008 — Le catalogue de démarrage est un fichier versionné, jamais des données en base

- Statut : Accepté
- Date : 2026-09-10
- Concerne : [../../backend/src/mabarak_api/catalog/](../../backend/src/mabarak_api/catalog/), endpoint `GET /api/catalog`

## Contexte

Une installation fraîche présente une liste vide et un lien « Créer la première fiche ».
L'utilisateur doit inventer seul toute la structure : quelles pièces, quels objets y sont
rattachés, quels entretiens leur appliquer et à quelle fréquence. Deviner les fréquences est
précisément la partie difficile, et c'est là qu'on abandonne ce type d'application.

Le didacticiel de démarrage « Configurer MaBarak » répond à ce problème en faisant faire à
l'utilisateur le tour de son logement pièce par pièce, en lui proposant des objets à cocher,
puis en lui proposant les entretiens correspondants avec des fréquences par défaut.

Cela suppose un **catalogue** : type de pièce → objets typiques → entretiens et fréquences par
défaut. Ce catalogue est destiné à s'enrichir à chaque version, au fil des retours et des
oublis constatés. La question tranchée ici est : **où vit-il ?**

## Options envisagées

### Option A — Données de référence en base, comme les catégories

Le catalogue serait inséré par `schema.sql` à la création, et enrichi par des migrations
Alembic successives, sur le modèle des catégories et des types de lieux intégrés
(`is_builtin = 1`).

C'est le motif déjà en place dans le projet, donc le réflexe naturel. Il pose trois problèmes
dans ce cas précis :

- **Chaque enrichissement demande une migration.** Ajouter trois objets à la cuisine en 0.17
  imposerait d'écrire une migration, alors qu'il s'agit de contenu éditorial, pas d'un
  changement de structure.
- **Le risque d'écrasement est réel.** Une migration qui met à jour des lignes déjà présentes
  doit se protéger de ce que l'utilisateur a modifié entre-temps. C'est exactement le problème
  rencontré en 0.15.0 sur les accents des catégories, où chaque `UPDATE` a dû être conditionné à
  la valeur d'origine. Multiplier ce motif à chaque version est une source de bugs silencieux.
- **Le catalogue n'est pas une donnée de l'utilisateur.** Le stocker dans sa base revient à lui
  faire porter une copie d'un contenu qui appartient à l'application, avec la charge de le
  maintenir synchronisé.

### Option B — Fichier versionné dans le dépôt, lu à l'exécution (retenue)

Le catalogue vit dans `backend/src/mabarak_api/catalog/*.yaml`, à l'intérieur du paquet Python
pour les mêmes raisons que `schema.sql` et les migrations : seul le paquet installé existe dans
le conteneur de l'add-on. Il est lu et validé au premier appel, puis mis en cache.

Il n'est **jamais écrit en base**. La base ne reçoit que ce que l'utilisateur crée réellement :
ses lieux, ses fiches, ses entretiens, créés à partir des modèles proposés. Une fois créées, ces
lignes lui appartiennent entièrement.

## Décision

Option B.

La propriété qui décide est la suivante : **une fois une fiche ou un entretien créé depuis un
modèle, le lien avec le catalogue est rompu.** L'utilisateur peut renommer, changer la fréquence,
supprimer — enrichir le catalogue en 0.17, 0.18 et au-delà ne touchera jamais à ce qu'il a fait.
Aucune migration n'est nécessaire, et aucun écrasement n'est possible, par construction.

Conventions qui en découlent :

- **`key` est un contrat.** Chaque pièce, objet et entretien type porte une clé stable. On n'en
  renomme jamais aucune : on ajoute une entrée, ou on marque `deprecated: true` pour la retirer
  des propositions sans casser ce qui la référençait.
- **Les objets sont définis une seule fois** et référencés par clé depuis les pièces, parce
  qu'un même objet apparaît dans plusieurs pièces (un siphon, des volets, un chauffe-eau).
- **La validation est stricte et se fait au chargement.** Les modèles Pydantic rejouent les
  contraintes du schéma SQL, notamment la cohérence entre type de récurrence et champs exigés.
  Un test parcourt le catalogue livré et vérifie que chaque slug de catégorie et de type de lieu
  existe réellement en base. Un catalogue mal formé casse la CI, jamais l'utilisateur.
- **YAML plutôt que JSON**, parce que le catalogue est un contenu éditorial relu et discuté en
  revue : les commentaires y justifient les fréquences (obligation légale, période de
  nidification, purge avant gel), et c'est cette justification qui fait sa valeur.

## Conséquences

Une dépendance d'exécution est ajoutée, `pyyaml`, déclarée explicitement plutôt que reprise de
celles d'`uvicorn[standard]`.

Le catalogue n'est pas modifiable par l'utilisateur depuis l'interface, et c'est volontaire :
sa personnalisation vit dans les fiches et les entretiens qu'il crée, pas dans le catalogue.

Le catalogue devient un révélateur pour la taxonomie. Cinq objets du premier lot n'ont aucune
catégorie qui leur convienne : l'évier et le siphon de douche (rien ne couvre la plomberie), la
bouche d'extraction (la ventilation n'existe que côté équipements), le sèche-linge (absent de
l'électroménager) et la haie (rien ne couvre le végétal). Ces manques sont laissés visibles,
`category` étant simplement absent, plutôt que de ranger une fiche au mauvais endroit. Ils
constituent la matière première, tirée de cas réels, de la prochaine révision des catégories.

Enfin, le même catalogue servira au-delà du didacticiel : la reconnaissance d'étiquette (V3)
cherchera à faire correspondre une marque et un modèle à un objet type, et la maintenance par
capteurs (V4) à savoir quelle logique de capteur s'applique à quel entretien.
