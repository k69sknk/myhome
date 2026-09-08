# Journal des modifications

L'add-on et l'intégration HomeKeeper partagent le même numéro de version
(voir [ADR-0005](../../docs/adr/0005-monodepot-addon-et-hacs.md)).

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
