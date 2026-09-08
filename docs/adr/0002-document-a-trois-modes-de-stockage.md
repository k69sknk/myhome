# ADR-0002 — Un document, trois modes de stockage, une seule table

- Statut : Accepté
- Date : 2026-09-08
- Concerne : [../DATA_MODEL.md](../DATA_MODEL.md) section 2.11, [../schema.sql](../schema.sql) table `document`

## Contexte

La section 14 du cahier des charges qualifie la confidentialité des documents de « point
fondamental du projet ». Une facture d'artisan contient le nom, le prénom et l'adresse de
l'utilisateur. L'application ne doit donc pas contraindre l'utilisateur à confier ces fichiers à
quoi que ce soit.

Trois méthodes doivent coexister :

1. **Stockage local** : le fichier est déposé dans l'application, qui le garde chez
   l'utilisateur.
2. **Lien externe** : l'utilisateur enregistre une URL vers son Nextcloud, son Drive, son NAS.
   L'application ne stocke pas le fichier.
3. **Référence simple** : l'utilisateur note simplement où trouver le document, par exemple
   « e-mail du 12/05/2024 » ou « dossier papier : garage / classeur chauffage ».

Le troisième mode est le plus intéressant à modéliser, parce qu'il n'a aucun contenu
exploitable par la machine. C'est du texte destiné à un humain. Il serait tentant de le traiter
comme un cas dégénéré, voire de le reléguer dans le champ « notes » d'un équipement.

## Options envisagées

### Option A — Trois tables séparées

`document_file`, `document_link`, `document_reference`.

Chaque table a exactement les colonnes qu'il lui faut, sans nullable. Mais tout ce qui consomme
des documents devrait faire l'union des trois : afficher la liste des documents d'un équipement,
compter les factures, chercher un document par son nom, rattacher un document à une
intervention. Et surtout, **changer de mode deviendrait une migration de ligne**.

Or changer de mode est un cas d'usage central, pas un cas limite. Un utilisateur commence par
noter « facture dans l'e-mail du 12 mai », puis retrouve le PDF et l'importe. Ou inversement,
décide de sortir ses factures de l'application et de ne garder que des liens vers son NAS. Avec
trois tables, chacun de ces gestes casse l'identité du document : il perd son `id`, donc ses
rattachements.

### Option B — Une table avec un champ texte polyvalent

Une seule colonne `content` qui contient tantôt un chemin, tantôt une URL, tantôt une note, plus
un champ `storage_mode` pour savoir comment l'interpréter.

Compact, mais rend le contenu inexploitable en SQL : impossible de contraindre, d'indexer
utilement, ou de vérifier la cohérence. Le sens d'une colonne dépendrait d'une autre colonne,
sans que la base puisse l'imposer.

### Option C — Une table, trois colonnes de contenu exclusives, cohérence garantie par `CHECK`

Une table `document` avec `storage_mode` et trois colonnes `file_path`, `url`,
`reference_note`, dont une seule est renseignée, avec une contrainte `CHECK` qui lie le mode à
la colonne utilisée.

## Décision

**Option C.**

```sql
CHECK (
       (storage_mode = 'local_file'
        AND file_path      IS NOT NULL AND url IS NULL AND reference_note IS NULL)
    OR (storage_mode = 'external_link'
        AND url            IS NOT NULL AND file_path IS NULL AND reference_note IS NULL)
    OR (storage_mode = 'reference_note'
        AND reference_note IS NOT NULL AND file_path IS NULL AND url IS NULL)
)
```

Le point décisif est qu'un document est **une même entité quel que soit son mode de
stockage**. Ce qui l'identifie, c'est son nom, son type (facture, notice, certificat) et
l'objet auquel il est rattaché. L'endroit où se trouve son contenu est un attribut, pas une
nature. Le mode de stockage doit donc pouvoir changer par un simple `UPDATE`, sans que le
document perde son identité ni ses rattachements.

C'est ce qui rend le local-first réellement optionnel plutôt que subi : les trois modes sont des
citoyens de première classe, et l'utilisateur peut circuler entre eux librement.

## Conséquences

Positives :

- Une seule requête pour lister les documents d'un équipement, tous modes confondus.
- Changer de mode est un `UPDATE`, l'identité du document est préservée.
- La contrainte `CHECK` rend impossible un document incohérent, par exemple en mode
  `local_file` sans chemin de fichier. Vérifié par les tests du schéma.
- Les deux modes non locaux ne consomment aucun espace disque et n'entrent pas dans les
  sauvegardes, ce qui répond directement à la préoccupation de confidentialité.

Négatives, et comment elles sont traitées :

- Deux colonnes sur trois sont toujours nulles. Coût de stockage négligeable en SQLite.
- La couche service doit gérer la transition entre modes, et notamment supprimer le fichier
  physique quand un document passe de `local_file` à un autre mode. Un fichier orphelin dans
  `/data/documents/` ne serait pas une fuite de données, mais resterait une occupation disque
  inutile. À couvrir par un test.
- L'interface doit rendre les trois modes également visibles à la saisie. Si le mode fichier est
  présenté comme le choix par défaut et les autres comme des options secondaires, la décision
  n'aura servi à rien sur le plan de la confidentialité.

## Note sur le rattachement

Un document est rattaché à exactement une entité, par l'une des cinq clés étrangères nullables
`home_id`, `asset_id`, `maintenance_task_id`, `intervention_id`, `issue_id`, avec une contrainte
d'exclusivité.

Une table de liaison polymorphe aurait autorisé les rattachements multiples, mais au prix de
l'intégrité référentielle : un document orphelin après suppression de son équipement est
exactement le type de perte silencieuse que ce projet doit éviter. Une facture rattachée à une
intervention reste de toute façon accessible depuis l'équipement par jointure.
