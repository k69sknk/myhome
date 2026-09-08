# ADR-0003 — L'historique est une vue dérivée, pas une table

- Statut : Accepté
- Date : 2026-09-08
- Concerne : [../DATA_MODEL.md](../DATA_MODEL.md) section 3.1, [../schema.sql](../schema.sql) vue `v_asset_timeline`

## Contexte

La section 11 du cahier des charges demande que chaque équipement possède un historique
complet, illustré par une frise chronologique :

```text
12/05/2024   Installation
15/01/2025   Entretien annuel
03/04/2025   Remplacement d'une piece
15/01/2026   Entretien annuel
```

et précise que l'utilisateur doit pouvoir consulter facilement toutes les interventions, tous
les entretiens, tous les problèmes et tous les coûts. La section 26 fait par ailleurs apparaître
`HISTORY` comme un nœud à part entière de la structure conceptuelle.

Cette présentation suggère fortement une table `history`. C'est un piège classique : la
structure conceptuelle décrit ce que l'utilisateur voit, pas nécessairement ce qu'il faut
stocker.

Les événements de cette frise existent déjà, chacun dans sa table métier : la date
d'installation est sur `asset`, les entretiens et réparations dans `intervention`, les problèmes
dans `issue`, les dépenses dans `cost`, la fin de garantie dans `warranty`.

## Options envisagées

### Option A — Table `history` alimentée par l'application

Chaque écriture métier écrit aussi une ligne d'historique. C'est une **double écriture**, avec
les défauts habituels : tout chemin de code qui oublie d'écrire l'historique crée une
divergence, une correction sur une intervention doit être reportée manuellement, une suppression
doit être propagée, et rien ne garantit que les deux représentations restent d'accord. La
divergence est de plus silencieuse : personne ne s'aperçoit qu'un historique est incomplet avant
d'en avoir besoin, c'est-à-dire trop tard.

### Option B — Table `history` alimentée par des triggers SQL

Les triggers suppriment le risque d'oubli côté application, mais déplacent la logique métier
dans le schéma, où elle est difficile à tester, à faire évoluer et à migrer. Il faudrait un
trigger `INSERT`, `UPDATE` et `DELETE` par table source, soit une quinzaine de triggers à
maintenir cohérents. Et la donnée reste dupliquée.

### Option C — Table `history` comme source de vérité unique

Renverser la logique : l'historique devient la table principale, et les interventions ne sont
qu'une projection. C'est un modèle événementiel, cohérent en soi, mais très coûteux pour ce
projet : chaque lecture de « la dernière date d'entretien de cette tâche » devient une
agrégation, et les mises à jour simples que l'utilisateur attend (corriger une date, changer un
coût) deviennent des compensations d'événements. Disproportionné pour une application de
maintenance domestique.

### Option D — Vue SQL dérivée

Une vue `v_asset_timeline` qui unifie les tables sources par `UNION ALL`.

## Décision

**Option D.** L'historique est une vue.

```sql
CREATE VIEW v_asset_timeline AS
    SELECT ... FROM asset        WHERE install_date IS NOT NULL   -- installation
    UNION ALL SELECT ... FROM intervention                        -- entretiens, reparations
    UNION ALL SELECT ... FROM issue                               -- ouverture de probleme
    UNION ALL SELECT ... FROM issue WHERE resolved_on IS NOT NULL -- resolution
    UNION ALL SELECT ... FROM cost  WHERE intervention_id IS NULL -- couts autonomes
    UNION ALL SELECT ... FROM warranty                            -- fin de garantie
```

Le raisonnement décisif : l'historique n'est pas une donnée, c'est une **lecture**. Il ne
contient aucune information qui n'existe pas déjà ailleurs. Le stocker créerait une seconde
copie sans ajouter de connaissance, et donc uniquement du risque d'incohérence. Une vue est par
construction toujours d'accord avec les tables sources, y compris après une correction ou une
suppression.

## Conséquences

Positives :

- Aucune désynchronisation possible. Corriger la date d'une intervention corrige l'historique.
- Aucun code d'écriture d'historique à maintenir, donc aucun chemin de code à oublier.
- Ajouter un type d'événement à la frise est une modification de la vue dans une migration, pas
  une reprise de données.
- Les types d'événements sont explicites (`installation`, `intervention`, `issue_opened`,
  `issue_resolved`, `cost`, `warranty_end`), ce qui permet à l'interface de choisir une icône et
  une couleur par type.

Négatives, et comment elles sont traitées :

- Une vue avec six branches `UNION ALL` est plus lourde qu'un simple `SELECT` sur une table.
  Sans importance à l'échelle visée : quelques centaines d'événements par maison au plus, et
  toutes les branches filtrent sur un `asset_id` indexé.
- Une vue n'est pas modifiable. C'est en réalité souhaitable : on corrige l'intervention, pas la
  ligne d'historique.
- Les événements sans date ne peuvent pas apparaître. C'est cohérent : une frise chronologique
  est ordonnée par date, un événement non daté n'y a pas de place.
- Les coûts rattachés à une intervention sont volontairement exclus de la branche `cost`, car
  la ligne d'intervention les représente déjà. Sans ce filtre, valider un entretien avec un coût
  produirait deux entrées pour un seul événement réel.

## Conséquence sur la modélisation des coûts

Cette décision explique pourquoi `cost.intervention_id` est nullable plutôt que d'avoir une
table de coûts séparée par origine. Quand l'utilisateur saisit un coût en validant un entretien
(section 10), une seule ligne `cost` est créée et rattachée à l'intervention. Le coût apparaît
dans le total de l'équipement (section 18) et dans la frise via son intervention, sans être
compté deux fois.
