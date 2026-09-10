# Journal des modifications

L'add-on et l'intégration MaBarak partagent le même numéro de version
(voir [ADR-0005](../../docs/adr/0005-monodepot-addon-et-hacs.md)).

## 0.13.0

- **Notifications de confirmation** : un toast confirme desormais chaque
  action qui aboutit (equipement ajoute, entretien ajoute ou marque comme
  fait, document supprime, lieu deplace, membre modifie...), au lieu de
  laisser deviner si l'action a reussi. Disparait tout seul apres quelques
  secondes, ou se ferme d'un clic.

## 0.12.1

Correctif : la 0.12.0 avait le bon numero de version mais les artefacts
statiques de l'add-on (`addon/mabarak/pkg`, `addon/mabarak/www`) n'avaient
pas ete regeneres via `scripts/stage-addon.sh` avant la release — l'image
construite par le Supervisor embarquait donc encore l'ancien code. Aucun
changement fonctionnel : cette version regenere simplement ces artefacts.

## 0.12.0

- Priorité des entretiens (faible / normale / haute / urgente) : tri par
  défaut de la liste par priorité décroissante puis échéance croissante,
  édition rapide en un clic depuis la liste des entretiens et la fiche
  équipement, badge "urgente" forcé côté affichage pour un entretien en
  retard quelle que soit la priorité enregistrée.

## 0.11.0

- Mini-calendrier du tableau de bord : mise en page compacte, detail du jour
  selectionne affiche a cote du calendrier (plus besoin de scroller).
- Entretiens ponctuels : la frequence "Ponctuel" porte desormais une vraie
  date et apparait sur les calendriers (tableau de bord, calendrier HA).
- Edition d'un entretien existant (nom, frequence, pieces, notes,
  assignation) sans avoir a le supprimer et le recreer.
- Plusieurs pieces a remplacer possibles par entretien (au lieu d'une seule).
- Delegation : nouvel onglet "Membres" pour deleguer un entretien a une
  personne du foyer, un ami ou une entreprise, avec lien facultatif vers une
  personne Home Assistant et notification optionnelle (reglable dans
  Parametres) a l'assignation, via un service `notify.*` Home Assistant.

## 0.10.1

Correctif : `httpx` (utilisé par le nouvel accès REST à Home Assistant depuis
la version 0.10.0) manquait des dépendances installées dans l'image de
l'add-on — il n'était déclaré que comme dépendance de développement, jamais
embarqué dans le conteneur. L'API ne démarrait plus (`ModuleNotFoundError:
No module named 'httpx'`).

## 0.10.0

- Mini-calendrier mensuel sur le tableau de bord : les entretiens à venir et
  en retard s'affichent directement sur un calendrier, avec le détail du jour
  sélectionné.
- L'intégration HACS expose désormais un calendrier Home Assistant natif
  (`calendar.mabarak_entretiens`), en lecture seule, ajoutable à n'importe
  quelle vue Calendrier.
- Nouveau réglage "Calendrier Home Assistant" : possibilité de pousser
  manuellement les entretiens à venir vers un calendrier HA existant (Local
  Calendar, CalDAV...) via un bouton "Synchroniser maintenant".

## 0.9.0

L'application s'appelle desormais **MaBarak** (avant : HomeKeeper) — partout :
interface, add-on, integration HACS, documentation.

**Ceci change le slug de l'add-on (`homekeeper` -> `mabarak`) et le domain de
l'integration HACS (`homekeeper` -> `mabarak`).** Home Assistant identifie un
add-on et une integration par ces valeurs, pas par leur nom affiche : une
install existante ne se met donc PAS a jour automatiquement, elle devient une
install a part avec des donnees vides. Marche a suivre pour conserver
l'historique :

1. Avant de mettre a jour, recuperer sur l'add-on actuel (via l'add-on
   Terminal & SSH, ou le partage Samba) le fichier `/data/homekeeper.db`
   (et `-shm`/`-wal` s'ils existent) ainsi que le dossier `/data/documents/`.
2. Mettre a jour le depot (`git pull` ou reinstallation depuis GitHub) : le
   Supervisor propose alors l'add-on **MaBarak** comme un nouvel add-on,
   distinct de l'ancien "HomeKeeper".
3. L'installer, le laisser demarrer une fois (il cree son `/data` avec une
   base vide), puis l'arreter.
4. Copier le dossier `documents/` recupere a l'etape 1 dans `/data/documents/`
   du nouvel add-on.
5. Renommer le fichier recupere `homekeeper.db` en `mabarak.db`, le placer
   dans `/data/` du nouvel add-on (ecraser celui cree a l'etape 3).
6. Redemarrer l'add-on MaBarak : l'historique, les equipements et les
   entretiens sont de retour.
7. Verifier que tout est present, puis desinstaller l'ancien add-on
   "HomeKeeper".
8. Si l'integration HACS "HomeKeeper" etait configuree (liens vers des
   appareils Home Assistant) : la supprimer dans Parametres > Appareils et
   services, puis ajouter "MaBarak" (decouverte automatique une fois l'add-on
   demarre). Les liens equipement <-> appareil enregistres dans la base
   survivent au changement d'integration ; seule l'entree de configuration
   HA doit etre recreee.

## 0.8.2

- **Onglets de navigation reordonnes** : Tableau de bord, Equipements,
  Entretiens, Lieux, Documents, Parametres.
- **Retours** plus clairs pour naviguer entre les pages : les fiches
  equipement (existante et nouvelle) affichent desormais un lien "← Equipements"
  explicite plutot qu'un simple lien texte.

## 0.8.1

Un document de type "Autre" gardait le nom du fichier tel quel (souvent
illisible, ex. IMG_20260909.pdf).

- **Nom personnalise** pour les documents "Autre" : un champ apparait pour
  le nommer soi-meme (ex. "Certificat de conformite gaz") au moment de
  l'ajouter.

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
