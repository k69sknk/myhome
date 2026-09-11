# ADR-0010 — La saisonnalité est une fenêtre sur la récurrence, pas un type de récurrence

- Statut : Accepté
- Date : 2026-09-11
- Concerne : [../schema.sql](../schema.sql) colonnes `maintenance_task.season_start_month` et
  `season_end_month` ; `backend/src/mabarak_api/services/recurrence.py` ;
  [0004](0004-ancrage-de-recurrence.md), qu'il complète sans le modifier

## Contexte

En testant le catalogue de démarrage en conditions réelles, un manque saute aux yeux :
**« passer la tondeuse » n'est pas proposé** pour la pelouse. C'est pourtant l'entretien de
pelouse le plus évident, celui que tout le monde attend.

Il avait été écarté sciemment à la rédaction du catalogue, et ce n'était pas un oubli : le
modèle ne savait pas l'exprimer.

La tonte est **saisonnière**. Toutes les semaines de mars à octobre, jamais en hiver. Or le
modèle ne connaît que « tous les X jours / mois / ans », « chaque année à date fixe » et « date
ponctuelle ». Aucune de ces formes ne dit « toutes les semaines, mais seulement une partie de
l'année » :

- en « tous les 7 jours », la tonte génère une échéance en novembre, puis une tâche affichée en
  retard pendant quatre mois, qui noie tout le reste du planning ;
- en « chaque année le 1er avril », on perd la répétition, qui est justement ce qui compte.

Le cas dépasse largement la tonte. Le nettoyage hebdomadaire du bassin d'une piscine, l'entretien
courant d'une terrasse, la taille d'une haie : tout l'extérieur suit ce rythme.

## Ce qui n'est PAS le problème

La tentation est de voir là un type de récurrence manquant, et d'en ajouter un —
`seasonal_weekly`, ou une récurrence portant sa propre liste de mois.

C'est une mauvaise lecture. La tonte revient bien **toutes les semaines** : l'intervalle est
correct, la façon de le compter est correcte, l'ancrage sur la date de réalisation (ADR-0004)
est correct — une tonte faite avec trois jours de retard décale bien la suivante d'autant.

Ce qui manque n'est pas *comment* l'échéance se calcule, mais **quand ce calcul a un sens**. Ce
sont deux questions distinctes, et les mélanger dans un même champ multiplierait les
combinaisons : six types de récurrence × deux ancrages × saisonnier ou non.

## Options envisagées

### Option A — Un type de récurrence `seasonal_days`

Un septième type, avec ses propres colonnes de mois.

Écartée. Il faudrait le décliner pour `months` et `years` — la piscine mensuelle d'été existe —
et le `CHECK` de cohérence entre type et colonnes, déjà lourd, doublerait. Surtout, cela
ferait croire que la saisonnalité et l'intervalle sont le même axe, alors qu'ils se combinent
librement.

### Option B — Une liste de mois actifs par entretien

Une table `maintenance_month`, ou une colonne texte `'3,4,5,6,7,8,9,10'`.

Plus expressive : elle permettrait « avril, juillet et octobre ». Écartée pour deux raisons.
Aucun cas d'usage domestique réel ne demande des mois non contigus — on dirait alors « tous les
3 mois », ce que le modèle sait déjà faire. Et une table de plus, ou une colonne texte à parser,
pour deux entiers, est un coût permanent payé pour un besoin hypothétique.

### Option C — Une fenêtre de saison, deux colonnes, appliquée après le calcul

`season_start_month` et `season_end_month`, bornes incluses. La récurrence reste ce qu'elle est ;
si l'échéance calculée tombe hors saison, elle est repoussée à l'ouverture de la saison suivante.

## Décision

**Option C.**

```sql
season_start_month  INTEGER CHECK (season_start_month IS NULL
                                   OR season_start_month BETWEEN 1 AND 12),
season_end_month    INTEGER CHECK (season_end_month IS NULL
                                   OR season_end_month BETWEEN 1 AND 12),

CHECK ((season_start_month IS NULL) = (season_end_month IS NULL)),
CHECK (season_start_month IS NULL
       OR recurrence_type IN ('days', 'months', 'years')),
```

Trois conséquences tiennent dans ces contraintes.

**La fenêtre peut enjamber le nouvel an.** `start = 11, end = 2` décrit un entretien d'hiver.
La comparaison est `start <= month <= end` quand la fenêtre ne passe pas l'an, et
`month >= start OR month <= end` sinon.

**La saison ne s'applique qu'aux récurrences à intervalle.** `annual_fixed` porte déjà son mois :
lui ajouter une saison, c'est dire deux fois la même chose ou se contredire. Une date ponctuelle
n'a rien à repousser.

**On repousse, on ne décale pas de proche en proche.** Une tonte hebdomadaire interrompue fin
octobre reprend le 1er mars — une seule échéance, pas les vingt que l'hiver a sautées. La
fonction s'appelle `in_season_or_next_opening` pour que ce soit lisible à l'appel.

L'articulation avec l'ADR-0004 est la partie qui compte : **la saison s'applique en dernier, sur
le résultat**. `compute_next_due` calcule exactement comme avant — ancrage sur la réalisation ou
sur la date théorique, rattrapage compris — puis passe le résultat dans la fenêtre. L'ancrage
n'est ni contourné ni dupliqué, et l'ADR-0004 reste vrai mot pour mot.

## Conséquences

Positives :

- « Passer la tondeuse » entre au catalogue, et avec lui le nettoyage hebdomadaire du bassin.
- Un entretien saisonnier disparaît du planning hors saison au lieu d'y rester en rouge. C'est
  exactement ce qui rendait la fonctionnalité impossible à livrer jusqu'ici.
- Deux entiers nullables, aucune table, aucune combinatoire ajoutée aux types de récurrence.
- La fenêtre se combine librement avec les deux ancrages et les trois intervalles.

Négatives, et comment elles sont traitées :

- **Les `CHECK` ne sont pas rétroactifs.** SQLite ne sait pas ajouter une contrainte à une table
  existante, et la recréer déclencherait la cascade décrite dans la migration 0004. Les bases
  déjà installées n'ont donc que les colonnes. Les trois règles sont rejouées intégralement par
  `_validate_recurrence` et `TaskIn`/`TaskPatch`, seul chemin d'écriture, et par
  `CatalogRecurrence` pour le catalogue.
- **Les mois non contigus restent inexprimables.** C'est le prix de l'option C, assumé : aucun
  entretien domestique identifié n'en a besoin, et « tous les 3 mois » couvre le cas qui s'en
  approche.
- **La saison ignore le climat local.** Mars-octobre convient à la France métropolitaine, pas au
  nord de la Suède. Les bornes sont modifiables entretien par entretien dans le formulaire ;
  celles du catalogue ne sont qu'une proposition, comme toutes les fréquences qu'il porte
  (ADR-0008).
- **`piscine_filtre` change de fréquence dans le catalogue.** Elle devient saisonnière (mai à
  septembre). Conformément à l'ADR-0008, cela ne touche aucune installation existante : le
  catalogue n'est jamais relu pour mettre à jour ce que l'utilisateur a déjà validé.
- **Le formulaire gagne un champ.** « Tous les X jours » manquait d'ailleurs à la liste des
  fréquences — l'interface convertissait silencieusement en « tous les X mois » un entretien
  exprimé en jours dès qu'on l'ouvrait pour le modifier. Corrigé au passage, la tonte étant le
  premier entretien du catalogue à l'exposer.
