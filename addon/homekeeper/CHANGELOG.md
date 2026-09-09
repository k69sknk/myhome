# Journal des modifications

L'add-on et l'intégration HomeKeeper partagent le même numéro de version
(voir [ADR-0005](../../docs/adr/0005-monodepot-addon-et-hacs.md)).

## 0.8.0

Deux correctifs et une coherence retrouvee autour de "marquer un entretien
comme fait".

- **Historique bloque sur "Chargement..."** : marquer un entretien fait ou
  enregistrer une modification alors que son historique etait deja ouvert le
  laissait bloque indefiniment sur "Chargement..." (rien ne relancait la
  requete). Corrige : l'historique se rafraichit desormais immediatement.
- **Badge "Bientot" qui ne bougeait jamais** sur les entretiens frequents
  (mensuels, hebdomadaires) : le seuil de 30 jours coincidait avec leur
  propre frequence, donc marquer fait ne changeait jamais rien a l'oeil. Le
  seuil se resserre maintenant automatiquement selon la frequence de chaque
  entretien ; le reglage de la maison (Parametres) sert desormais de plafond
  ajustable, et peut resserrer davantage les entretiens moins frequents.
- **"Fait" et "Editer" fusionnes** : un seul bouton "Marquer comme fait" qui
  ouvre directement le formulaire (qui, quand, note) — dire qu'un entretien a
  ete realise est une etape importante, elle ne doit pas se limiter a un
  clic sans consequence.

## 0.7.1

La fiche equipement gagne des onglets (Entretiens, Details, Documents) pour
rester lisible a mesure que les infos s'accumulent, plutot que tout empiler
sur une seule page.

## 0.7.0

Joindre la facture d'achat d'un equipement, pratique pour la garantie.

- **Facture d'achat** : nouveau type de document sur la fiche equipement,
  aux cotes du manuel d'utilisation. Un lien "Facture" apparait directement
  a cote de la garantie des qu'une facture est jointe.

## 0.6.3

Correctif : supprimer une intervention deja supprimee (double-tap, ou liste
pas encore rafraichie) affichait "Intervention introuvable" au lieu de
simplement faire disparaitre la ligne, aussi bien dans l'historique global
de la page Entretiens que dans l'historique d'un entretien.

## 0.6.2

Le selecteur d'equipement du formulaire "Ajouter un entretien" n'avait pas
de moyen rapide de revenir en arriere apres une selection : il fallait
effacer le texte affiche caractere par caractere pour en choisir un autre.

- **Bouton effacer (×)** dans le champ Equipement : un tap vide la
  selection et rouvre aussitot la liste complete pour en choisir un autre.

## 0.6.1

Correctif : le selecteur d'equipement du formulaire "Ajouter un entretien"
proposait de creer un equipement pourtant deja selectionne, des qu'il avait
une categorie ou un lieu (la verification comparait le texte affiche a son
nom seul, jamais au texte avec categorie/lieu).

## 0.6.0

Preparation des entretiens : ne plus perdre l'info d'une echeance a l'autre,
parfois espacees de plusieurs mois ou annees. Et une page Entretiens enfin
claire : ajouter, voir ce qui est planifie, consulter l'historique.

- **Piece a remplacer** : case a cocher sur un entretien, avec nom de la
  piece et lien ou magasin d'achat. Affiche sur la fiche equipement et la
  page Entretiens des que l'entretien revient a echeance.
- **A prevoir lors de l'entretien** : outils specifiques, produits ou autres
  a preparer avant de s'y mettre.
- **Notes** : remarque libre sur l'entretien.
- **Page Entretiens reorganisee** en trois sections : ajouter un entretien
  (avec choix de l'equipement, sans repasser par sa fiche), a faire (groupe
  par en retard / bientot / a jour / non planifie), et un historique global
  de toutes les interventions passees, tous equipements confondus, avec
  pagination (nouvel endpoint `GET /api/interventions`).
- **Recherche d'equipement** dans le formulaire "Ajouter un entretien" :
  on tape pour filtrer, les equipements sont regroupes en arbre par lieu
  (categorie affichee en complement), et si l'equipement cherche n'existe
  pas encore, un bouton propose de le creer a la volee.

## 0.5.0

Boutons Modifier/Supprimer homogenes, et suppression enfin possible sur les
entretiens et l'historique.

- **Boutons Modifier/Supprimer homogenes** : partout dans l'application
  (lieux, types de lieux, photo et documents d'equipement, entretiens),
  memes pilules ovales teintees (bleu clair pour editer, rouge clair pour
  supprimer), meme icone. Les boutons « Supprimer » n'etaient auparavant
  visuellement pas distingues d'une action neutre.
- **Entretiens** : un entretien (tache recurrente) peut desormais etre
  supprime depuis la liste ou la fiche equipement (`DELETE /api/tasks/{id}`).
  Son historique existant est conserve (detache, non supprime).
- **Historique** : chaque intervention passee peut desormais etre supprimee
  individuellement (`DELETE /api/interventions/{id}`), y compris ses
  documents joints.

## 0.4.0

La fiche équipement gagne une photo, une alerte de garantie et ses propres
documents.

- **Photo d'équipement** : repli automatique sur un emoji selon la catégorie
  (visible dans la liste et la fiche) ; possibilité d'uploader une petite
  image qui la remplace, comme un avatar. Réutilise la table `document`
  existante (`doc_type = 'photo'`), aucune migration necessaire.
- **Garantie** : le champ « Début de garantie » du formulaire Nouvel
  équipement devient « Date d'achat (début de garantie) », une durée de
  24 mois est proposée par défaut, et la fin de garantie estimée s'affiche
  en direct pendant la saisie. Un badge « Garantie bientôt expirée » /
  « Garantie expirée » apparaît sur la fiche et dans la liste des
  équipements dès qu'il reste moins de 6 mois.
- **Documents d'équipement** : possibilité d'attacher un manuel
  d'utilisation (ou tout autre document) directement sur la fiche —
  liste, téléchargement, suppression — sans passer par un entretien.
  Nouveaux endpoints `POST/GET /api/assets/{id}/documents` et
  `DELETE /api/documents/{id}`.

## 0.3.0

Lieux, catégories et entretiens gagnent en souplesse.

- **Lieux** : le champ de lieu parent est renommé et explicité (indentation
  selon la profondeur, texte d'aide), et un lieu existant peut désormais être
  déplacé dans l'arborescence — la protection anti-cycle déjà présente côté
  API est maintenant utilisable depuis l'interface.
- **Types de lieux personnalisables** : nouvel onglet **Paramètres**
  regroupant le nom de la maison et la gestion des types de lieux (ajouter,
  renommer, supprimer un type ; les six types intégrés restent protégés
  contre la suppression). Migration `0002_location_types` : la colonne texte
  `location.location_type` devient une référence vers une nouvelle table
  `location_type`, sans perte de données sur une install existante.
- **Catégories d'équipement à la volée** : le champ Catégorie du formulaire
  Nouvel équipement devient un champ texte avec prédiction ; une catégorie
  absente de la liste peut être créée directement depuis ce champ
  (`POST /api/categories`).
- **Entretiens** :
  - la fréquence « une fois par an, à date fixe » utilise maintenant un
    unique champ date (jour/mois) au lieu de deux champs séparés ;
  - le bouton **Préciser** devient **Éditer** (et **Annuler** une fois
    ouvert), avec un formulaire plus lisible ;
  - possibilité de consigner qu'un entretien a été réalisé par un pro
    (entreprise, montant, facture/document joint) ; nouvelles tables
    exploitées côté API : `cost` et `document` (déjà présentes dans le
    schéma, jusqu'ici inutilisées) ;
  - un bouton **Historique** affiche les entretiens passés d'une tâche
    (date, qui, note, montant, documents téléchargeables).

## 0.2.1

Correctif : `GET /locations` renvoyait une erreur 500 (« Internal Server Error »)
au chargement de la liste des lieux, par exemple depuis le formulaire
« Nouvel équipement ». En cause, `dict(session.execute(...).tuples())` : `dict()`
traitait le résultat SQLAlchemy comme un mapping au lieu de l'itérer comme une
séquence de paires. Aucune migration de données requise.

## 0.2.0

Premier morceau métier : fiche équipement, lieux, entretiens.

- Maison unique créée au démarrage (« Ma maison »)
- Lieux en arbre libre
- Fiches d'appareils (nom, lieu, mise en service, catégorie, garantie)
- Entretiens récurrents, boutons **Fait** et **Préciser**
- Tableau de bord aligné sur `/api/ha/summary` (mêmes compteurs que les capteurs HA)
- Lien optionnel vers un appareil Home Assistant
- Architecture **armv7 retirée** : Home Assistant ne la supporte plus depuis 2025.12, et
  `uvicorn[standard]` (uvloop/httptools) ne se construit plus sous QEMU 32 bits
- Migration `0001_schema` au démarrage : une install 0.1.0 se met à jour sans perdre `/data`

## 0.1.0

Squelette d'architecture. Aucune fonctionnalité métier.

- Architecture hybride add-on plus intégration, documentée dans
  [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md)
- Modèle de données complet et validé, dans [docs/DATA_MODEL.md](../../docs/DATA_MODEL.md) et
  [docs/schema.sql](../../docs/schema.sql)
- Add-on avec ingress, filtrage d'adresse IP sur `172.30.32.2` et services s6-overlay
- Backend FastAPI réduit à son point de santé, sans logique métier
- Frontend Vite plus React résolvant le chemin de base d'ingress à l'exécution
- Intégration en config flow avec un coordinator branché sur `/api/ha/summary`
