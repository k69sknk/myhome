# ADR-0005 — Un monodépôt servant à la fois d'add-on et d'intégration HACS

- Statut : Accepté
- Date : 2026-09-08
- Concerne : [../ARCHITECTURE.md](../ARCHITECTURE.md) section 8, `repository.yaml`, `hacs.json`

## Contexte

L'architecture retenue (voir [../ARCHITECTURE.md](../ARCHITECTURE.md) section 2) produit deux
artefacts installables séparément dans Home Assistant :

- un **add-on**, installé depuis un dépôt d'add-ons, découvert par Home Assistant via un
  fichier `repository.yaml` à la racine du dépôt et un sous-répertoire par add-on ;
- une **intégration custom**, installée via HACS, découverte via un fichier `hacs.json` à la
  racine du dépôt et un répertoire `custom_components/<domain>/`.

Les deux mécanismes attendent des fichiers à la racine d'un dépôt Git. La question est de savoir
s'il faut un dépôt ou deux.

Ces artefacts sont fortement couplés par le contrat de l'endpoint `/api/ha/summary` : c'est
l'add-on qui calcule les compteurs et les statuts, et l'intégration qui les transpose en
entités. Toute évolution de ce contrat concerne les deux.

## Options envisagées

### Option A — Deux dépôts

`mabarak-addon` et `mabarak-integration`, chacun avec sa racine propre, ses issues, sa CI
et son versionnement.

Le découplage est net, mais le couplage réel du code ne disparaît pas pour autant : il devient
simplement invisible. Une modification du contrat `/api/ha/summary` demanderait deux pull
requests coordonnées dans deux dépôts, sans qu'aucune CI puisse valider l'ensemble. Aucun test
d'intégration bout en bout n'est possible sans faire cloner l'autre dépôt par la CI, ce qui
reconstitue le monodépôt à la main et de façon fragile. Pour un projet à un seul développeur,
c'est du coût de coordination sans bénéfice.

### Option B — Un monodépôt

Un seul dépôt contenant `repository.yaml`, `hacs.json`, `addon/mabarak/`, `backend/`,
`frontend/` et `custom_components/mabarak/`.

### Option C — Un monodépôt de développement plus deux dépôts de publication

Développer dans un dépôt unique et publier vers deux dépôts miroirs par CI. Donne les avantages
des deux options, au prix d'une chaîne de publication à écrire et à maintenir. Envisageable plus
tard si la distribution le justifie, injustifiable maintenant.

## Décision

**Option B.** Un monodépôt, avec les deux fichiers de découverte à la racine.

Les deux mécanismes coexistent sans conflit : Home Assistant lit `repository.yaml` et ignore
`custom_components/`, HACS lit `hacs.json` et ignore `addon/`. Aucun des deux n'exige d'être
seul à la racine.

Le raisonnement décisif est que le couplage entre l'add-on et l'intégration est **réel et
volontaire**. Le rendre visible dans un seul dépôt permet de le tester ; le répartir sur deux
dépôts ne le supprime pas, il le rend seulement plus difficile à vérifier.

## Conséquences

Positives :

- Une modification du contrat `/api/ha/summary` se fait en une seule pull request, avec la CI
  qui valide le backend et l'intégration ensemble.
- Un test d'intégration bout en bout est possible : lancer le backend et faire tourner le
  coordinator de l'intégration contre lui.
- Une seule chaîne CI, un seul jeu d'issues, une seule documentation.

Négatives, et comment elles sont traitées :

- **Version partagée.** L'add-on et l'intégration portent le même numéro de version, y compris
  quand une release ne touche qu'un seul des deux. C'est un compromis accepté : une version
  commune est plus simple à supporter que deux matrices de compatibilité.
- **Mises à jour désynchronisées chez l'utilisateur.** C'est la vraie conséquence. Un
  utilisateur met à jour l'add-on depuis le magasin d'add-ons et l'intégration depuis HACS, à
  des moments différents. Il faut donc supporter durablement le cas où les deux versions
  installées diffèrent. Mesure retenue : le coordinator lit un champ de version de schéma
  d'API au premier appel de `/api/ha/summary`, et l'intégration lève une entrée de réparation
  Home Assistant explicite si l'add-on est trop ancien, au lieu d'échouer de façon obscure. Le
  contrat n'introduit que des ajouts de champs entre versions majeures.
- **Racine chargée.** Deux fichiers de découverte plus quatre répertoires de composants. À
  compenser par un `README.md` qui explique la structure dès les premières lignes, sans quoi un
  contributeur ne saura pas où regarder.
- Le magasin d'add-ons de Home Assistant affichera le dépôt entier comme un dépôt d'add-ons, et
  HACS comme un dépôt d'intégration. Les descriptions des deux doivent donc être rédigées pour
  ne pas induire en erreur sur ce que l'utilisateur installe réellement.
