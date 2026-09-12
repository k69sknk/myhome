---
name: mabarak
description: Consulter et tenir à jour le carnet d'entretien de la maison dans MaBarak, via Home Assistant — équipements, entretiens récurrents, échéances, réparations, garanties, coûts. Utilise cette skill dès que l'utilisateur parle d'entretien, de révision, de ramonage, de filtre à changer, de chaudière, de VMC, de pompe à chaleur, de toiture, d'électroménager, de garantie, d'artisan ou de dépannage — y compris quand il raconte simplement ce qu'il a fait ou fait faire (« le plombier est passé », « j'ai vidangé la chaudière », « la tondeuse est tombée en panne »), car ces phrases sont à consigner. Déclenche aussi sur « qu'est-ce qui est en retard », « qu'est-ce qui arrive bientôt dans la maison », ou toute question sur l'âge, la marque, le modèle ou l'historique d'un appareil.
---

# MaBarak — le carnet d'entretien de la maison

MaBarak est une application locale qui centralise les équipements d'une maison, leurs entretiens
récurrents, l'historique des interventions, les garanties et les coûts. Elle est branchée sur
Home Assistant, qui expose six outils pour la lire et l'écrire.

L'enjeu de cette skill : ces outils **écrivent dans les archives d'une maison réelle**. Une
ligne d'historique fausse ne se remarque pas avant des mois, quand quelqu'un cherche à savoir
quand la chaudière a été révisée pour la dernière fois. Mieux vaut poser une question de plus
que consigner une approximation.

## Commence toujours par l'aperçu

Appelle `MaBarakApercu` avant toute autre chose, même si la demande semble évidente.

Il rend l'état de la maison — ce qui est en retard, ce qui arrive, les garanties qui expirent —
mais surtout **le vocabulaire de cette maison-là** : la liste des pièces et le nombre
d'équipements. Sans lui tu inventeras des noms de pièces (« buanderie » alors que la maison dit
« cellier ») et tes écritures seront refusées.

Si tu as besoin du détail d'un appareil — sa marque, son numéro de série, quand il a été
entretenu, la fréquence de ses entretiens — c'est `MaBarakChercherEquipement`, avec ou sans
terme de recherche.

## Les six outils

| Outil | Quand |
| --- | --- |
| `MaBarakApercu` | l'état général, et le vocabulaire de la maison |
| `MaBarakChercherEquipement` | la fiche complète d'un ou plusieurs appareils |
| `MaBarakValiderEntretien` | un entretien **planifié** a été fait → replanifie la prochaine échéance |
| `MaBarakConsignerIntervention` | une **panne, réparation ou contrôle** hors planning → consigne seulement |
| `MaBarakCreerEntretien` | ajouter un entretien récurrent à un appareil existant |
| `MaBarakCreerEquipement` | créer la fiche d'un appareil |
| `MaBarakJoindreDocument` | ranger une facture, une notice, une garantie sur une fiche |

### Valider ou consigner : la distinction qui compte

`MaBarakValiderEntretien` suppose qu'un entretien **récurrent existe déjà** et recalcule sa
prochaine échéance. C'est ce qui fait vivre le planning.

`MaBarakConsignerIntervention` note un événement ponctuel — une panne, une réparation — sans
rien replanifier.

Si l'utilisateur dit « j'ai fait la révision annuelle de la chaudière », c'est *valider*. S'il
dit « le lave-linge a été réparé, 210 € », c'est *consigner*. En cas de doute, regarde avec
`MaBarakChercherEquipement` si un entretien de ce nom existe : s'il existe, valide-le.

## Si tu écris par les services, lis avant et vérifie après

Ce paragraphe ne concerne que les appels par services (`mabarak.…`) ; avec les outils
`MaBarak…`, la réponse te revient et tu peux sauter cette section.

Les écritures par services **agissent bien**, mais ne te renvoient rien : ni confirmation, ni
raison en cas de refus. Home Assistant ne sait pas transmettre le message d'un service qui
refuse par cette voie — tu recevrais une erreur 500 sans explication, alors que MaBarak avait
rédigé une phrase utile. Deux réflexes règlent le problème :

**Avant d'écrire, lis.** Les entités MaBarak portent le nom exact de chaque équipement et de
chacun de ses entretiens. Repère-les, puis écris en nommant **les deux** — l'équipement *et*
l'entretien. Tu supprimes ainsi l'ambiguïté au lieu d'attendre qu'elle te soit signalée, et
c'est de loin le plus sûr.

**Après avoir écrit, relis.** L'état de l'entité concernée dit si l'écriture a eu lieu :
`dernier_entretien` et `prochaine_echeance` auront changé. C'est ta seule confirmation, et elle
est fiable. Ne dis jamais à l'utilisateur qu'une écriture a réussi sans l'avoir vérifiée ainsi.

### Le code d'erreur te dit où chercher

C'est la seule information que le refus te laisse, et elle vaut d'être lue :

- **400** — tes **arguments** sont mal formés, et MaBarak n'a rien vu de ta demande. Un nom de
  champ inexistant (`note` au lieu de `notes`), une date qui n'est pas au format `AAAA-MM-JJ`,
  une valeur hors de la liste attendue. Ne soupçonne pas les données de la maison : relis les
  champs de l'action.
- **500** — tes arguments étaient bons, et c'est **MaBarak** qui refuse : un nom ambigu, un lieu
  inconnu, un doublon. Là, le problème est bien dans ce que tu as désigné. Lis les entités pour
  retrouver le nom exact, puis réessaie.

Se tromper de diagnostic entre les deux fait perdre beaucoup de temps : un 400 attribué à un nom
de pièce envoie chercher une panne là où il n'y a qu'une faute de frappe dans un nom de champ.

### Les dates, quand tu ne sais pas tout

Une date se donne complète ou pas du tout. Si l'utilisateur dit « installée en 2023 », **n'invente
pas de mois ni de jour** : laisse le champ de côté et écris « installée en 2023 » dans `notes`.
Une date fabriquée devient une vérité dans les archives de la maison, et personne ne saura
qu'elle a été devinée.

## On désigne par le nom, jamais par un numéro

Tous les outils prennent des noms en français. Les accents et la casse n'ont aucune importance,
et tu peux être plus bavard que la fiche : « la chaudière gaz de la cave » retrouve
« Chaudière gaz ».

**En cas d'ambiguïté, l'outil refuse d'écrire et te rend la liste des candidats.** Par exemple :

> Plusieurs entretiens portent exactement le nom « changer le filtre » :
> Changer le filtre (PAC), Changer le filtre (VMC). Précisez lequel.

C'est volontaire, et c'est une aide, pas un échec. **Ne choisis pas à la place de
l'utilisateur** : reprends la liste et demande-lui lequel. Écrire dans la mauvaise fiche est
précisément ce que ce refus existe pour éviter.

Quand l'outil dit qu'il n'a rien trouvé, il énumère ce qui existe. Lis cette liste avant de
conclure : le nom cherché s'y trouve souvent sous une autre forme.

## Ce qu'il faut savoir avant d'écrire

**Les champs obligatoires ne sont pas marqués comme tels** dans le schéma que tu reçois — Home
Assistant ne transmet pas cette information. Fie-toi à la mention « Obligatoire. » en tête de la
description de chaque champ :

- `MaBarakValiderEntretien` → `entretien`
- `MaBarakCreerEntretien` → `equipement` et `nom`
- `MaBarakCreerEquipement` → `nom`
- `MaBarakConsignerIntervention` → `equipement`

**Les dates s'écrivent `AAAA-MM-JJ`.** « Hier », « la semaine dernière », « en mars » doivent
être convertis avant l'appel. Sans date, c'est aujourd'hui — ce qui est faux si l'utilisateur
raconte quelque chose de passé. Dans le doute, demande quand.

**Les montants sont en euros**, décimales comprises : `montant_euros: 149.90`.

**La fréquence s'exprime d'une seule façon à la fois** dans `MaBarakCreerEntretien` :

- `tous_les: 6` + `unite: "mois"` — les unités sont `jours`, `mois`, `ans`
- ou `chaque_annee_le: "15-09"` (JJ-MM) pour une date fixe annuelle
- ou `le: "2026-03-15"` pour un entretien ponctuel

Mélanger deux formes est refusé. Sans aucune, l'entretien existe mais n'a pas d'échéance.

Pour un entretien saisonnier — la tonte revient toutes les semaines, mais de mars à octobre —
ajoute `saison_du_mois: 3` et `saison_au_mois: 10`. Sans ces bornes, l'entretien s'afficherait
en retard tout l'hiver.

**Un lieu inconnu est refusé**, avec la liste des pièces existantes. C'est un garde-fou : un nom
mal orthographié créerait une pièce en double. Tu peux passer outre avec `creer_le_lieu: true`,
mais seulement si l'utilisateur a confirmé que cette pièce n'existe pas encore.

**`fait_par` accepte du texte libre.** Si le nom correspond à un membre du foyer ou à un
prestataire de l'annuaire, il y est rattaché automatiquement ; sinon il reste tel quel. « Le
voisin » est une réponse parfaitement valable.

## Ranger un document

`MaBarakJoindreDocument` couvre les factures, notices, garanties et contrats. Trois façons de
garder un document, et **il en faut exactement une** :

- **`fichier_a_telecharger`** — MaBarak va chercher le fichier à cette adresse et en garde une
  copie. L'adresse doit être **sur le réseau local** : MaBarak ne télécharge rien depuis
  Internet, c'est ce qui garantit que les documents de la maison restent chez elle. Si tu
  détiens le fichier, expose-le sur ton réseau et donne cette adresse. Formats : pdf, jpg, png,
  heic, doc, docx ; 10 Mo au plus.
- **`lien`** — l'adresse est gardée telle quelle, sans copie. Le bon choix pour un document qui
  vit déjà ailleurs, ou qui est trop gros, ou qui est sur Internet.
- **`note`** — du texte qui dit où chercher : « classeur bleu, intercalaire 3 ». Pour un papier
  qui n'existe qu'en papier.

Le choix appartient à l'utilisateur, et il vaut la peine de lui poser la question quand elle
n'est pas tranchée. Copier un document dans MaBarak le fait entrer dans les sauvegardes de Home
Assistant ; garder un lien laisse l'original où il est, avec le risque qu'il disparaisse.

Si le téléchargement est refusé parce que l'adresse est publique, ne t'obstine pas :
enregistre-la en `lien`. Le document sera retrouvable, sans copie.

## Deux limites connues

**Les entretiens rattachés à la maison entière** — « tester les détecteurs de fumée », le
ramonage quand il n'est lié à aucun appareil — **ne peuvent pas encore être marqués comme
faits**. L'outil te le dira franchement. Ce n'est pas un problème de nom : transmets l'explication
à l'utilisateur plutôt que de chercher ailleurs.

**Si aucun outil `MaBarak*` n'apparaît**, l'intégration MaBarak n'est pas chargée dans Home
Assistant. L'add-on seul n'expose rien. Dis-le : c'est à l'utilisateur d'ajouter l'intégration,
tu ne peux rien faire depuis ton côté.

## Rends compte en français, avec la phrase de l'outil

Chaque outil répond par une phrase complète, déjà rédigée pour être relue telle quelle :

> « Entretien annuel » sur « Chaudière gaz » est noté comme fait le 2026-03-10.
> Prochaine échéance le 2027-03-10.

Reprends-la. Elle contient ce que l'utilisateur veut vérifier — l'appareil visé et la prochaine
échéance —, ce qui lui permet de repérer immédiatement une erreur de fiche. Les données
structurées qui l'accompagnent servent à toi, pas à lui.

## Lire sans rien appeler

Chaque équipement publie aussi une **entité Home Assistant** dont l'état vaut `ok`, `due_soon`,
`overdue` ou `unscheduled`, et dont les attributs portent tout le reste :

```yaml
nom: VMC            lieu: Combles          marque: Aldes        modele: EasyHOME
dernier_entretien: '2026-03-01'            prochaine_echeance: '2026-09-01'
garantie_jusqu_au: null
entretiens:
  - nom: Nettoyer les bouches
    statut: overdue
    echeance: '2026-09-01'
    derniere_fois: '2026-03-01'
    frequence: tous les 6 mois
```

C'est le chemin de lecture le plus simple, et le seul qui marche quel que soit ton connecteur :
un état se lit toujours. Si tu sais lire un état Home Assistant, tu peux répondre « quand la VMC
a-t-elle été entretenue ? » sans appeler quoi que ce soit.

Trois entités d'ensemble complètent le tableau : le nombre d'entretiens en retard, le nombre à
échéance proche, et la date du prochain — cette dernière portant en attributs le nom de
l'entretien et celui de l'équipement.

`MaBarakApercu` et `MaBarakChercherEquipement` restent plus riches et mieux tournés pour une
réponse en français. Mais si les appels échouent, les entités sont là.

## Deux portes, et une seule est confortable

Les six actions existent sous deux formes, et **il faut préférer la première** :

**Les outils `MaBarak…`** — `MaBarakApercu`, `MaBarakChercherEquipement`, etc. Si ta liste
d'outils les contient, sers-toi d'eux exclusivement. Ils rendent la réponse directement, sans
rien de particulier à faire.

**Les services `mabarak.…`** — `mabarak.apercu`, `mabarak.chercher_equipement`,
`mabarak.valider_entretien`, `mabarak.creer_entretien`, `mabarak.creer_equipement`,
`mabarak.consigner_intervention`, `mabarak.joindre_document`. Mêmes paramètres, mais ce sont des
services Home Assistant,
et les services de lecture ne rendent leur résultat que si l'appelant le demande explicitement. Concrètement, l'URL doit porter
le paramètre :

```
POST /api/services/mabarak/apercu?return_response
```

Sans lui, Home Assistant refuse l'appel avec un **400** et ce message :

> Service call requires responses but caller did not ask for responses.
> Add ?return_response to query parameters.

Si tu rencontres ce 400 et que ton connecteur ne sait pas ajouter ce paramètre à l'URL, ne
t'acharne pas : **regarde si tu as les outils `MaBarak…`**, qui n'ont pas cette contrainte. Ils
sont exposés dès que l'intégration est chargée. Si tu n'as ni l'un ni l'autre de façon
utilisable, dis-le franchement à l'utilisateur en nommant ce que tu as essayé — c'est un
problème de configuration de ton connecteur, pas de MaBarak, et lui seul peut le régler.

Les actions d'écriture, elles, fonctionnent par les deux portes sans précaution : elles n'ont pas
besoin de rendre de résultat pour agir.
