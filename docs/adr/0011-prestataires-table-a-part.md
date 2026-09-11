# ADR-0011 — Les prestataires sont une table à part, pas un type de membre

- Statut : Accepté
- Date : 2026-09-11
- Concerne : [../schema.sql](../schema.sql) table `provider`, colonnes
  `maintenance_task.assignee_provider_id` et `intervention.performed_by_provider_id` ;
  `backend/src/mabarak_api/routers/providers.py` ; remplace l'usage de
  `member.member_type = 'company'` introduit en 0.22.0

## Contexte

La version 0.22.0 a rendu une entreprise assignable à un entretien, et la 0.23.0 l'a reliée à
l'historique des interventions. Les deux se sont appuyées sur la table `member`, qui portait déjà
un discriminant `member_type` avec la valeur `company`. C'était le chemin le plus court, et il a
tenu le temps de deux versions.

À l'usage, les deux profils ne se ressemblent pas.

Un **membre du foyer** est quelqu'un qu'on **notifie**. Il porte `ha_person_entity_id` et
`ha_notify_service` : c'est ce qui permet d'envoyer « la VMC t'attend » sur son téléphone.

Un **prestataire** est quelqu'un qu'on **appelle**, et qu'on paie. Il a un métier, un numéro de
téléphone qu'on veut cliquable, un numéro de client qu'on cherche en panique, une adresse, un
site. Il n'a pas de personne Home Assistant, et il n'en aura jamais.

Le symptôme était visible à l'écran : le formulaire « ajouter un membre » proposait « Personne
Home Assistant » et « Service de notification » pour une entreprise. Ces champs n'étaient pas
vides faute d'être remplis, ils étaient **faux** : la question n'a pas de sens.

## Ce qui n'est PAS le problème

La tentation est de voir là un manque de champs, et de continuer à empiler des colonnes
nullables sur `member` : téléphone, métier, numéro de client. La table finit par décrire deux
choses à la fois, et chaque écran doit savoir quelles colonnes ignorer selon le type.

Ce n'est pas non plus un problème d'affichage qu'on réglerait en masquant les champs Home
Assistant quand `member_type = 'company'`. Masquer un champ qui n'a pas de sens, c'est admettre
que le type le décide déjà — donc que ce sont deux entités, avec une table pour les deux.

## Options envisagées

### Option A — Un annuaire unique, plus un satellite 1-1 pour les entreprises

`member` garde l'identité, une table `company_profile(member_id UNIQUE, …)` porte ce qui diverge,
comme `warranty` est un satellite de `asset`.

Séduisante parce qu'elle préserve une clé unique dans `maintenance_task` et `intervention` :
`assignee_id` continue de pointer vers `member`, sans exclusivité à tenir.

Écartée. Elle règle le problème des colonnes vides mais pas celui du vocabulaire : l'utilisateur
n'a pas un annuaire de personnes dont certaines sont des entreprises, il a **ses proches** d'un
côté et **ses artisans** de l'autre. Il ne les consulte ni au même moment ni pour la même raison.
Un modèle qui les réunit oblige chaque écran à les séparer de nouveau.

### Option B — Deux tables, et deux clés exclusives là où une référence existe

`member` reste le foyer. `provider` naît pour les entreprises. Les deux tables sont pointées par
deux colonnes nullables dont une seule est renseignée.

### Option C — Une table `contact` générique avec des sous-types

Le modèle « classe abstraite » : une table d'identité, deux tables de spécialisation.

Écartée. C'est l'option A avec une indirection de plus, et deux jointures pour afficher un nom.
Le gain théorique — un `contact_id` unique dans les références — ne se matérialise que si l'on
accepte que la table d'identité ne contienne presque rien.

## Décision

**Option B.**

```sql
CREATE TABLE provider (
    id           INTEGER PRIMARY KEY,
    home_id      INTEGER REFERENCES home(id) ON DELETE CASCADE,
    name         TEXT NOT NULL,
    specialty    TEXT,   -- slug d'un metier, liste versionnee (ADR-0008)
    phone        TEXT,
    email        TEXT,
    website      TEXT,
    address      TEXT,
    customer_ref TEXT,   -- numero de client ou de contrat
    notes        TEXT,
    ...
);
```

Et sur les deux seuls endroits qui désignaient un « qui » :

```sql
-- maintenance_task
assignee_id          INTEGER REFERENCES member(id)   ON DELETE SET NULL,
assignee_provider_id INTEGER REFERENCES provider(id) ON DELETE SET NULL,
CHECK (assignee_id IS NULL OR assignee_provider_id IS NULL),

-- intervention
performed_by_member_id   INTEGER REFERENCES member(id)   ON DELETE SET NULL,
performed_by_provider_id INTEGER REFERENCES provider(id) ON DELETE SET NULL,
CHECK (performed_by_member_id IS NULL OR performed_by_provider_id IS NULL),
```

Deux clés exclusives plutôt qu'une clé polymorphe : **le patron existe déjà dans ce schéma**.
`document` porte cinq clés de rattachement mutuellement exclusives, et l'ADR-0002 explique
pourquoi — une liaison polymorphe achète la souplesse au prix de l'intégrité référentielle, et
un document orphelin est exactement la perte silencieuse que ce projet refuse. Le raisonnement
vaut mot pour mot ici.

La contrainte est bornée : **deux références dans tout le schéma**, pas une par table.

`member_type` perd la valeur `company` et ne garde que `household` et `friend`.

## Conséquences

Positives :

- La fiche prestataire devient une vraie fiche : téléphone cliquable, métier, numéro de client,
  et les deux blocs qui n'existaient pas — ce qui lui est confié, ce qu'il a facturé.
- Le formulaire d'un membre ne demande plus que ce qui le concerne, et réciproquement.
- Le métier est un slug pris dans une liste versionnée, jamais du texte libre : c'est ce qui
  permettra de proposer un chauffagiste au moment d'assigner l'entretien d'une chaudière.
- Chaque table peut évoluer sans traîner l'autre.

Négatives, et comment elles sont traitées :

- **Les données existantes doivent déménager.** Les entreprises créées en 0.22 et 0.23 sont des
  lignes de `member`, référencées par des entretiens et des interventions. La migration 0012 les
  recopie dans `provider`, réécrit les deux références, puis supprime les lignes d'origine. Le
  champ `contact`, texte libre, part dans `email` s'il contient une arobase et dans `phone`
  sinon : la seule heuristique de toute la migration, appliquée à un champ qui ne contenait de
  toute façon qu'une chose.
- **Les `CHECK` d'exclusivité ne sont pas rétroactifs**, comme en ADR-0010 : SQLite ne sait pas
  ajouter une contrainte à une table existante, et la recréer déclencherait la cascade décrite
  en migration 0004 — d'autant plus dangereuse ici que `member` est justement une cible de clé
  étrangère. Les bases déjà installées n'ont donc que les colonnes ; l'exclusivité est tenue par
  `TaskIn`, `TaskPatch` et `CompleteIn`, seuls chemins d'écriture. Même remède pour le `CHECK`
  de `member_type`, qui garde `'company'` sur les bases migrées sans qu'aucun écrit ne puisse
  plus produire cette valeur.
- **Un prestataire ne reçoit pas de notification.** Il n'a pas de service `notify.*`, et c'est
  voulu : MaBarak ne démarche pas les entreprises. Un entretien qui lui est confié suit le repli
  déjà en place — le rappel part vers le service par défaut de la maison, pour que l'échéance ne
  disparaisse pas du radar de celui qui devra passer le coup de fil.
- **Deux listes à interroger là où il y en avait une.** Le sélecteur « assigné à » et le champ
  « qui l'a fait » présentent les deux ensembles en deux groupes, avec une valeur étiquetée
  (`member:3`, `provider:7`) : l'utilisateur tape un nom, il ne choisit pas d'abord un type.
- **Un troisième profil coûterait une troisième table.** Un syndic, une assurance ou un voisin
  rémunéré entreraient aujourd'hui dans `provider` faute de mieux. C'est accepté : tant que le
  profil est « on l'appelle, il facture », la table convient. Le jour où un profil demande autre
  chose, cet ADR sera remplacé plutôt qu'étiré.
