# ADR-0012 — Les métiers sont une liste semée, que l'utilisateur peut étendre

- Statut : Accepté
- Date : 2026-09-11
- Concerne : [../DATA_MODEL.md](../DATA_MODEL.md) section `provider`,
  [../schema.sql](../schema.sql) tables `trade` et `provider`,
  [0008](0008-catalogue-en-fichier-versionne.md), [0011](0011-prestataires-table-a-part.md)

## Contexte

`provider.specialty` porte un slug de métier pris dans `catalog/trades.yaml`, une liste
versionnée avec l'application (adr/0008). Le fichier assume sa brièveté : la liste sert à
**regrouper** (« mes chauffagistes ») et à proposer le bon prestataire au moment d'assigner un
entretien, pas à décrire un annuaire professionnel. Son en-tête allait jusqu'à écrire que
« Autre » est « une réponse acceptable et non un aveu de manque ».

L'usage a montré que c'en était un quand même. Un vitrier, un cuisiniste, un antenniste, un
dépanneur de volets roulants : la liste ne les connaît pas, et « Autre » ne dit rien.
Or ce qu'on veut savoir en ouvrant une fiche, c'est **qui on appelle**. Deux fiches « Autre »
côte à côte ont perdu précisément l'information qui les distingue, et aucune ne remonte dans un
regroupement par métier.

La question n'est donc pas d'allonger la liste — elle ne couvrira jamais tout ce qu'on trouve
chez les gens — mais de savoir où va ce qu'elle ignore.

## Options envisagées

### Option A — Du texte libre dans `specialty`

Laisser l'utilisateur taper ce qu'il veut, stocké tel quel.

Le commentaire du schéma dit l'inverse depuis l'origine, et pour une bonne raison : « Vitrier »,
« vitrier » et « Vitrerie » deviendraient trois métiers, le filtre par métier de la 0.26 en
proposerait trois, et proposer un chauffagiste pour l'entretien d'une chaudière ne marcherait
plus dès qu'on aurait tapé « chauffage » une fois. Un identifiant de regroupement ne peut pas
être une frappe.

### Option B — Une colonne de précision à côté du slug

Garder `specialty = 'autre'` et ajouter `specialty_other`, du texte libre affiché à la place.

L'information n'est plus perdue, mais elle reste de seconde classe : deux colonnes pour un seul
concept, un métier qui s'affiche sans jamais regrouper, et un filtre qui continue d'annoncer
« Autre » pour des fiches qui n'ont rien à voir. On aurait résolu l'affichage sans résoudre le
besoin.

### Option C — Une table `trade`, semée depuis le fichier versionné

La liste versionnée devient un **seed** : une table `trade` reçoit les métiers intégrés au
démarrage, et l'utilisateur peut en ajouter. `provider.specialty` continue de porter le slug.

## Décision

**Option C.** C'est exactement le traitement déjà retenu pour `location_type` : une liste livrée
avec l'application, que l'utilisateur peut étendre parce que sa maison n'a pas demandé la
permission de ressembler au catalogue.

Trois points en font le prix d'entrée :

1. **Le seed est rejoué à chaque démarrage**, et n'insère que ce qui manque. Un métier ajouté à
   `trades.yaml` rejoint ainsi les installations existantes — ce qu'une insertion faite une fois
   dans une migration n'aurait pas permis. Le seed ne réécrit jamais un nom : un métier intégré
   renommé par l'utilisateur le reste.
2. **Un métier saisi deux fois reste un seul métier.** Le nom est réduit à un slug sans accents
   ni casse ; si ce slug existe déjà, la saisie retrouve le métier existant au lieu de lui faire
   un sosie. C'est la règle du didacticiel en 0.24, appliquée ici.
3. **`provider.specialty` reste un slug, sans clé étrangère.** Les fiches d'une base plus
   ancienne continuent de fonctionner sans migration de données, et un slug inconnu s'affiche
   brut plutôt que de faire perdre l'information.

`trades.yaml` garde donc son statut de contrat pour les métiers intégrés, et adr/0008 vaut
toujours pour ce qu'il visait : le contenu livré ne naît pas en base. Ce que cet ADR ajoute,
c'est que la base peut en accueillir *plus*.

## Conséquences

Positives :

- Un métier ajouté est un métier comme les autres : il regroupe les fiches, alimente le filtre
  de l'annuaire et le groupement de la liste d'assignation, sans code supplémentaire.
- `GET /api/trades` reste l'unique source du menu déroulant ; l'interface n'a pas à distinguer
  un métier intégré d'un métier ajouté.
- « Autre » garde son sens : le choix de ne pas répondre. Préciser reste facultatif.

Négatives, et comment elles sont traitées :

- `GET /trades` n'est plus servi sans base ni session, contrairement à ce que son commentaire
  annonçait. Le coût est une lecture d'une table de quinze lignes.
- Deux sources pour une même liste, le fichier et la table. Le fichier fait foi pour les
  intégrés, la table pour le reste ; le seed ne va que dans un sens, et jamais en écrasant.
- Un métier ajouté puis abandonné reste dans la liste. Sa suppression n'est pas exposée pour
  l'instant : une fiche pointant vers un slug disparu afficherait le slug brut, ce qui est
  lisible mais laid. À traiter quand le besoin se présentera, avec le renommage.
