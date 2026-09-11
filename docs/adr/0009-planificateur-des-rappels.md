# ADR-0009 — Le planificateur des rappels vit dans le processus de l'API

- Statut : Accepté
- Date : 2026-09-11
- Concerne : [../schema.sql](../schema.sql) colonnes `home.reminder_hour`,
  `home.last_reminder_run_on`, `maintenance_task.last_reminded_on` ;
  `backend/src/mabarak_api/services/scheduler.py` et `services/reminders.py`

## Contexte

Jusqu'ici, MaBarak ne notifiait qu'au moment de l'assignation d'un entretien à quelqu'un. Rien
ne prévenait à l'approche de l'échéance : il fallait penser à ouvrir l'application pour
découvrir ce qui était dû.

Le didacticiel de démarrage (ADR-0008) a rendu ce manque décisif. Il crée en quelques clics des
dizaines d'échéances récurrentes. Un planning de trente lignes qu'il faut se souvenir d'aller
consulter n'est pas un planning : c'est une liste qu'on oublie. C'est ce qui décide si
l'application sert au quotidien ou si elle est abandonnée après trois semaines.

Notifier suppose quelque chose que l'add-on n'avait pas : **un déclencheur temporel**. Toute la
logique existante est synchrone, déclenchée par une requête HTTP de l'utilisateur.

## Question 1 — Où vit le planificateur

L'add-on tourne sous s6-overlay, avec trois unités : `init-mabarak` (migrations), `mabarak-api`
(uvicorn) et `nginx`.

### Option A — Un service s6 supplémentaire

Un quatrième service, lancé au démarrage du conteneur, qui dort et se réveille.

Propre sur le papier : le planificateur survit à un plantage de l'API, et son cycle de vie est
visible dans les logs du superviseur au même titre que les autres.

Mais il paie cher. C'est un second interpréteur Python, un second jeu d'imports SQLAlchemy et
FastAPI, une seconde connexion SQLite en écriture sur la même base — donc une source de
verrous concurrents là où il n'y en avait aucune. Sur un Raspberry Pi, qui est la cible réelle
de ce projet, doubler l'empreinte mémoire de l'add-on pour une tâche qui s'exécute une fois par
jour est un mauvais échange.

### Option B — Une tâche asyncio dans le cycle de vie de FastAPI

Créée dans le `lifespan` de `main.py`, annulée à l'arrêt.

Aucun processus supplémentaire, aucune connexion supplémentaire, le même `session_factory` que
les requêtes HTTP. Le défaut, réel, est qu'elle meurt avec le processus de l'API.

### Option C — Déclencher depuis Home Assistant

Une automatisation côté HA appelant une route de l'add-on à heure fixe.

Écartée : elle déporte chez l'utilisateur une configuration qui devrait être invisible, et rend
la fonctionnalité dépendante d'un travail manuel que la plupart des gens ne feront pas. Un
rappel qui n'existe que si on l'a soi-même câblé ne répond pas au problème posé.

## Décision 1

**Option B.** Le planificateur est une tâche asyncio du processus de l'API.

Le défaut de l'option B — mourir avec l'API — est plus théorique que pratique : s6 relance
`mabarak-api` s'il tombe, et `nginx` en dépend, donc une API morte est de toute façon une
application morte, rappels ou pas. Ce qu'il faut éviter n'est pas l'interruption elle-même, mais
qu'une interruption **fasse sauter un rappel**. C'est l'objet de la question suivante.

## Question 2 — Quand le passage a lieu

Un passage par jour suffit largement pour des entretiens domestiques. Mais « une fois par
jour » n'est pas une spécification suffisante : il faut une heure, et il faut décider ce qui se
passe quand l'add-on était éteint à cette heure-là.

Une tâche qui dort jusqu'au prochain 8h00 puis vingt-quatre heures à chaque tour est la forme
naïve, et elle perd le passage à chaque redémarrage tombant après l'heure.

## Décision 2

Le planificateur se réveille toutes les **15 minutes** et pose une question qui ne porte pas sur
son propre rythme :

> Un passage a-t-il déjà eu lieu aujourd'hui, et l'heure choisie est-elle atteinte ?

`home.last_reminder_run_on` retient la date du dernier passage effectué, `home.reminder_hour`
l'heure voulue (8h par défaut, heure locale). Le rattrapage en découle sans code dédié : un
add-on éteint toute la matinée et démarré à 14h constate qu'aucun passage n'a eu lieu ce jour-là
et que 14h dépasse 8h, et rappelle immédiatement.

La date est notée **même quand rien n'est parti** — notifications coupées, aucun entretien dû,
Home Assistant injoignable. Sans cela, une installation aux notifications désactivées rouvrirait
la base tous les quarts d'heure pour reprendre la même décision.

L'heure est une heure **locale**, pas UTC : recevoir « les entretiens de la semaine » à 8h du
matin n'a de sens que dans le fuseau de celui qui les lit. Le Supervisor propage le fuseau de
Home Assistant au conteneur de l'add-on.

## Question 3 — Ne pas devenir du bruit

C'est le vrai risque de cette fonctionnalité, et il est plus grave que l'absence de rappel : un
rappel qu'on apprend à ignorer ne rappelle plus rien, et il a en prime discrédité tous les
suivants.

Deux façons d'y tomber, toutes deux atteignables avec un didacticiel qui crée trente échéances.

**Un message par entretien.** Le jour où cinq échéances tombent ensemble, c'est cinq
notifications d'affilée sur le téléphone. C'est le comportement qui fait désinstaller.

**Une relance quotidienne.** Un entretien en retard qui notifie tous les matins devient un
réveil qu'on met en sourdine — et la sourdine vaut pour tout le reste.

## Décision 3

**Un message par personne et par passage**, jamais un par entretien. Les entretiens y sont
listés, le plus en retard en tête, plafonnés à huit lignes, le reste compté (« … et 3 autres »).

**Un entretien déjà signalé se tait une semaine.** `maintenance_task.last_reminded_on` porte la
date du dernier rappel pour l'échéance en cours. La colonne est remise à `NULL` dès que
`next_due_on` est recalculée — validation d'entretien, changement de planification — donc une
nouvelle échéance a toujours droit à la parole. C'est la même règle que la dénormalisation de
`next_due_on` décrite dans l'ADR-0004 : une valeur dérivée, avec un point d'entrée unique.

Le destinataire est la personne assignée si elle a un service de notification, sinon
`home.default_notify_service`. Ce repli vaut aussi quand l'entretien **est** assigné mais que la
personne n'a pas de service renseigné : se taire ferait disparaître l'entretien du radar sans
que personne ne s'en aperçoive. Les entretiens que ce repli ne sauve pas — pas de service par
défaut non plus — sont comptés et affichés dans les réglages, parce qu'un rappel silencieux qui
se croit envoyé est pire qu'un rappel absent.

## Conséquences

Positives :

- Le planning devient actif. C'était la condition pour que l'application serve au quotidien.
- Aucune empreinte supplémentaire : pas de processus, pas de connexion, pas de dépendance.
- Le rattrapage est une propriété de la formulation, pas un mécanisme de plus à maintenir.
- Le calcul des messages (`plan_reminders`) est séparé de l'envoi : il se teste sans Home
  Assistant, et l'interface peut dire ce qu'un passage ferait.

Négatives, et comment elles sont traitées :

- **Le planificateur meurt avec l'API.** s6 la relance, et le premier passage suivant rattrape.
  Il ne rattrape en revanche pas *plusieurs* jours manqués : un add-on éteint trois jours envoie
  un seul message au retour, celui du jour. C'est le comportement voulu — les trois messages
  auraient porté la même information.
- **Un seul interrupteur** (`home.task_notifications_enabled`) commande à la fois les
  notifications d'assignation et les rappels quotidiens. Deux cases distinctes auraient été plus
  fins, mais « notifications » est ce que l'utilisateur cherche dans les réglages ; en scinder
  la notion l'obligerait à comprendre une distinction qui nous appartient, pas à lui.
- **Le statut vient de `v_task_status`, qui compare à `date('now')` en UTC**, alors que l'heure
  du passage est locale. L'écart se voit au plus sur un jour, sur un rappel dont la fenêtre
  « bientôt » se compte en semaines. Aligner les deux demanderait de porter le fuseau dans la
  vue SQL, pour un gain nul.
- **L'envoi est best-effort.** Home Assistant injoignable ne fait pas échouer le passage : la
  trace n'est pas écrite sur les entretiens concernés, qui repartent au passage suivant.
