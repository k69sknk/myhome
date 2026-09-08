# ADR-0004 — La récurrence porte un ancrage explicite

- Statut : Accepté
- Date : 2026-09-08
- Concerne : [../DATA_MODEL.md](../DATA_MODEL.md) section 2.7, [../schema.sql](../schema.sql) colonne `maintenance_task.recurrence_anchor`

## Contexte

La section 9 du cahier des charges énumère les types de fréquence attendus : tous les X jours,
tous les X mois, tous les X ans, une fois par an, date personnalisée, ou pas de fréquence
automatique. Chaque tâche porte une date de dernier entretien et une prochaine échéance.

Ce que le cahier des charges ne précise pas, c'est **à partir de quoi la prochaine échéance est
calculée quand un entretien est réalisé en retard ou en avance**. C'est pourtant la question la
plus lourde de conséquences de tout le modèle de planification, et elle n'a pas une seule bonne
réponse.

Deux exemples tirés du cahier des charges lui-même, avec une fréquence de trois mois et une
échéance au 1er mars, entretien réellement effectué le 20 mars :

**Nettoyage des filtres de VMC.** Ce qui compte est le temps d'usage écoulé depuis le dernier
nettoyage. Les filtres ont été nettoyés le 20 mars, ils se re-saliront à partir de cette date.
La prochaine échéance doit être le 20 juin.

**Entretien annuel obligatoire de la pompe à chaleur.** Ce qui compte est le respect d'une
périodicité contractuelle ou réglementaire, indépendante de la date réelle. L'entretien reste dû
au début de chaque période. La prochaine échéance doit être le 1er juin, pas le 20.

Ces deux comportements sont incompatibles, et les deux sont nécessaires.

## Le problème de la dérive

Si l'on n'implémente que le calcul depuis la date de réalisation, un entretien réglementaire
dérive de façon cumulative. Avec un retard moyen de trois semaines sur un entretien annuel, la
date théorique glisse de trois semaines par an : au bout de quatre ans, l'entretien de janvier
se retrouve en février, et au bout de dix ans en mars. L'application aurait progressivement
désaligné l'utilisateur de son obligation contractuelle, sans jamais rien signaler.

Si l'on n'implémente que le calcul depuis la date théorique, le problème inverse apparaît sur
les entretiens d'usage. Une tâche trimestrielle en retard de quatre mois génère une échéance
déjà dépassée dès la validation, et l'utilisateur reste bloqué en rouge en boucle alors qu'il
vient de faire le travail.

Aucune des deux règles ne peut donc être choisie comme règle unique.

## Options envisagées

### Option A — Une seule règle, celle depuis la réalisation

La plus intuitive, celle que retiennent la plupart des applications de rappel. Introduit la
dérive décrite ci-dessus sur toutes les tâches à date fixe.

### Option B — Déduire le comportement du type de récurrence

Traiter `annual_fixed` comme ancré sur la date théorique, et `days` / `months` / `years` comme
ancrés sur la réalisation.

Séduisant, mais faux. Un entretien de chaudière peut être exprimé comme « tous les 12 mois »
tout en devant garder sa date théorique, et un remplacement de joints peut être exprimé comme
« une fois par an » tout en devant partir de la date réelle. Le type de fréquence décrit un
intervalle, pas une intention. Lier les deux revient à retirer à l'utilisateur un choix qui lui
appartient.

### Option C — Un champ d'ancrage explicite

Ajouter `recurrence_anchor` valant `from_completion` ou `from_due_date`, indépendant du type de
récurrence.

## Décision

**Option C.**

```sql
recurrence_anchor TEXT NOT NULL DEFAULT 'from_completion'
                  CHECK (recurrence_anchor IN ('from_completion', 'from_due_date')),
```

Règle de calcul, à implémenter dans la couche service :

- `from_completion` : `next_due_on = last_completed_on + intervalle`
- `from_due_date` : `next_due_on = ancienne next_due_on + intervalle`, puis, si le résultat est
  déjà dépassé, on avance par pas d'un intervalle jusqu'à obtenir une date future. C'est ce
  rattrapage qui évite le blocage en rouge décrit plus haut, tout en préservant l'alignement sur
  la date théorique.

La valeur par défaut est `from_completion`, qui correspond au cas le plus fréquent en usage
domestique et à l'attente intuitive de l'utilisateur. L'ancrage sur date théorique est un choix
délibéré, à faire à la création de la tâche.

## Conséquences

Positives :

- Les deux comportements légitimes sont représentables, et l'utilisateur choisit celui qui
  correspond à son besoin réel.
- Pas de dérive cumulative sur les entretiens réglementaires.
- Pas de blocage en état « en retard » après une validation tardive sur les entretiens d'usage.
- Le champ est indépendant du type de récurrence, donc combinable librement avec les six types
  de fréquence de la section 9.

Négatives, et comment elles sont traitées :

- Un champ de plus dans le formulaire de création d'une tâche, sur un concept que l'utilisateur
  n'a jamais eu à formuler explicitement. L'interface ne doit donc pas l'exposer comme une
  énumération technique, mais comme un choix en langage naturel, du type « recalculer à partir
  de la date de réalisation » contre « garder la date prévue chaque année ». Le libellé compte
  autant que le champ.
- La règle de rattrapage de `from_due_date` doit être testée sur les cas limites : retard
  supérieur à plusieurs intervalles, mois de longueurs différentes, 29 février, changements
  d'heure. Ces tests sont un prérequis de la V1.
- `annual_fixed` combiné à `from_completion` est une combinaison contradictoire mais autorisée
  en base. La couche service la normalise plutôt que de la refuser, `annual_fixed` portant déjà
  sa date de référence dans `fixed_month` et `fixed_day`.

## Note sur `next_due_on`

Cette décision justifie que `next_due_on` soit une colonne stockée et indexée plutôt qu'un
calcul à la volée. Avec deux règles d'ancrage, un rattrapage d'intervalles et six types de
fréquence, le calcul n'est pas exprimable raisonnablement en SQL. Il vit dans la couche service,
qui écrit son résultat. La contrepartie est qu'il faut recalculer à chaque validation
d'entretien et à chaque modification de la planification, ce qui est couvert par un point
d'entrée unique dans le service.
