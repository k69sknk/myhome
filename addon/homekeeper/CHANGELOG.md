# Journal des modifications

L'add-on et l'intégration HomeKeeper partagent le même numéro de version
(voir [ADR-0005](../../docs/adr/0005-monodepot-addon-et-hacs.md)).

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
