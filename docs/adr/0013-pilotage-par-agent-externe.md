# ADR-0013 — Un agent externe pilote MaBarak par Home Assistant, jamais en direct

- Statut : Accepté
- Date : 2026-09-12
- Concerne : `custom_components/mabarak/actions.py`, `services.py`, `intents.py` ;
  `backend/src/mabarak_api/routers/agent.py`, `services/resolve.py`, `services/agent.py` ;
  colonne `created_via` sur `asset`, `maintenance_task` et `intervention`
  ([../schema.sql](../schema.sql), migration `0014_provenance_ecriture`) ;
  réalise le service `mabarak.complete_task` annoncé dans
  [../ARCHITECTURE.md](../ARCHITECTURE.md) section 6

## Contexte

Les assistants personnels branchés sur Home Assistant se généralisent. Un utilisateur de MaBarak
dont l'agent pilote déjà sa maison voudrait lui dire « note que le ramonage a été fait » ou
« ajoute la nouvelle chaudière », sans ouvrir l'interface.

Jusqu'ici c'était impossible, et pour deux raisons distinctes qu'il faut séparer :

1. l'intégration ne faisait que **lire**. Elle expose des capteurs et un calendrier depuis
   `/api/ha/summary` ; aucun service `mabarak.*` n'existait ;
2. l'add-on, lui, sait déjà tout faire — son API REST crée des fiches, planifie des entretiens,
   les valide — mais il **n'a aucune authentification**. Sa seule protection est de n'être
   joignable que depuis le réseau interne de Home Assistant, port direct fermé, avec un filtrage
   d'adresse IP dans nginx (voir ARCHITECTURE.md section 4).

La question n'est donc pas « comment ajouter des écritures », elles existent, mais **par où un
agent extérieur y accède**.

## Ce qui n'est PAS le problème

La tentation est d'ouvrir le port de l'add-on et de laisser l'agent appeler l'API REST
directement. C'est le chemin le plus court, et c'est celui qu'il faut écarter : il faudrait
construire de zéro un système de jetons, de portée et d'expiration, pour une application dont
tout le modèle de sécurité repose aujourd'hui sur le fait de n'être joignable par personne.
Home Assistant a déjà ce système, éprouvé, et l'utilisateur l'a déjà configuré.

Ce n'est pas non plus un problème de vocabulaire d'API qu'on réglerait en documentant mieux les
routes existantes. Un agent ne bute pas sur la forme des requêtes — il bute sur les
**identifiants**. `POST /api/tasks/42/complete` suppose de connaître `42`. L'agent, lui, dit
« le ramonage ».

## Décision

**Toute écriture venue de l'extérieur passe par l'intégration Home Assistant.** L'add-on garde
sa porte fermée. L'intégration devient le seul chemin d'écriture, et hérite de ce fait de
l'authentification de Home Assistant, de ses permissions, et de son journal.

Trois conséquences structurent le code.

### 1. Deux surfaces, une seule définition

Les actions sont exposées à la fois en **services** `mabarak.*` et en **intentions**. Ce n'est
pas de la redondance de confort : le serveur MCP de Home Assistant n'expose que l'API « Assist »,
c'est-à-dire les intentions enregistrées, et **jamais** les services. Un agent branché en MCP ne
verrait donc aucun service, quel que soit leur nombre. Inversement, un agent qui parle à l'API
REST de Home Assistant avec un jeton appelle des services et ignore les intentions.

Les deux surfaces sont donc obligatoires, et les deux lisent la même table dans
`custom_components/mabarak/actions.py`. Ni `services.py` ni `intents.py` ne portent de logique.

Un détail qui coûtera une soirée à qui l'ignore : l'attribut `platforms` des intentions doit
rester à `None`. L'API Assist ne garde que les intentions dont `platforms` recoupe les domaines
d'entités exposées à l'assistant ; `mabarak` n'étant pas un domaine d'entités, toute autre valeur
rendrait les outils invisibles.

### 2. Résoudre les noms, et refuser de deviner

Un routeur `/api/agent` est ajouté au backend, distinct de celui de l'interface. Ses routes
prennent des **noms** et non des identifiants, et font en un appel ce que l'interface fait en
deux : retrouver la fiche, puis agir.

La règle qui gouverne `services/resolve.py` est qu'**en cas de doute, on n'écrit rien**. Une
correspondance approximative qui se trompe de fiche écrit dans l'historique de la maison, et
personne ne s'en aperçoit ; le mensonge est découvert des mois plus tard, quand il est trop tard
pour le corriger. Une ambiguïté signalée, elle, se rattrape immédiatement.

Concrètement, la résolution accepte les accents et la casse, tolère qu'on soit plus bavard que la
fiche (« la chaudière gaz de la cave » trouve « Chaudière gaz »), mais dès que deux fiches
correspondent elle **échoue en nommant les candidats**. Un agent sait quoi faire d'une liste de
choix ; il ne sait pas défaire une écriture silencieuse. Le message d'erreur est la vraie sortie
de ce module — il est rédigé pour être relu tel quel à l'utilisateur.

Le même raisonnement vaut pour la création : un lieu inconnu est refusé, avec la liste des lieux
existants, sauf demande explicite de le créer. Sans cela, un nom de pièce mal orthographié
peuplerait l'arbre des lieux de doublons invisibles.

### 3. La provenance est écrite

Une colonne `created_via` est ajoutée à `asset`, `maintenance_task` et `intervention`. `NULL`
signifie l'interface, ou une ligne antérieure à la question ; `'agent'` signifie une écriture
venue de cette surface.

Elle ne sert à rien dans le fonctionnement normal, et c'est voulu : elle sert le jour où une
ligne d'historique est fausse et où la première question est « qui a écrit ça ? ». Sans elle,
l'utilisateur n'a aucun moyen de distinguer ce qu'il a saisi de ce qu'un agent a déduit d'une
phrase mal comprise. Laisser les deux se mélanger, c'est rendre l'historique inutilisable comme
preuve — or c'est sa seule raison d'être.

## Options envisagées

**Ouvrir l'API REST de l'add-on avec un jeton.** Écartée. Demande de construire
authentification, portée et révocation là où Home Assistant les fournit déjà, et ouvre une
seconde porte sur les données de la maison — alors que le local-first du produit repose sur le
fait qu'il n'y en a aucune.

**Un serveur MCP dans l'add-on.** Écartée pour l'instant, pour la même raison : un serveur MCP
exposé à un agent externe a besoin de la même authentification. Le jour où il se justifierait, il
appellerait ces mêmes routes `/api/agent` ; la décision d'aujourd'hui ne le ferme pas.

**Des services seulement, sans intentions.** Écartée : invisible depuis le serveur MCP, donc
inutilisable par la moitié des agents, dont celui qui a motivé ce travail.

**Réutiliser les routes de l'interface en y ajoutant la recherche par nom.** Écartée. Les routes
de l'interface répondent à un écran qui vient d'afficher une liste et connaît ses identifiants ;
les charger d'une résolution floue les rendrait ambiguës pour leur premier usager. Deux
vocabulaires, deux surfaces.

**Laisser l'agent choisir la meilleure correspondance.** Écartée, et c'est la décision la plus
importante du lot. Un agent optimiste écrit dans la mauvaise fiche sans jamais le signaler.

## Conséquences

L'add-on et l'intégration doivent être mis à jour **ensemble** : les routes `/api/agent` sont
appelées par l'intégration, une intégration à jour devant un add-on ancien recevra des 404. C'est
la contrainte habituelle du monodépôt ([0005](0005-monodepot-addon-et-hacs.md)), et elle n'est pas
couverte par la négociation de version de `/api/ha/summary`, qui ne porte que sur le résumé.

La liste des services est décrite à trois endroits — `actions.py`, `services.yaml`, et les
traductions — que rien dans Home Assistant ne compare entre eux. `scripts/check-integration.py`
comble ce trou et tourne en CI.

Enfin, une limitation antérieure devient visible par cette surface : un entretien rattaché à la
maison plutôt qu'à un équipement (« tester les détecteurs de fumée ») ne peut pas être validé,
parce que `intervention.asset_id` est `NOT NULL`. Ce n'est pas propre au pilotage — l'interface ne
le peut pas davantage — mais l'agent le rencontrera plus souvent. La route le dit franchement
plutôt que de laisser croire à un échec de résolution du nom. La lever demande de rendre
`intervention.asset_id` nullable, ce qui relève d'une décision à part.
