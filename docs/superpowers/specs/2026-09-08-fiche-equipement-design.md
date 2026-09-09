# Fiche équipement — morceau 1

- Date : 2026-09-08
- Statut : Approuvé, implémenté en 0.2.0
- Produit : MaBarak

## Objectif

Ouvrir la fiche d’un appareil et voir : nom, lieu, date de 1re mise en service,
liste des entretiens (dernier / prochain / état). Marquer un entretien fait,
ranger les lieux, lier optionnellement un appareil Home Assistant.

## Périmètre inclus

- Maison unique auto-créée (« Ma maison »)
- Lieux en arbre libre
- Appareils uniquement dans l’UI (`kind = equipment`)
- Bandeau + liste d’entretiens + détail (marque, série, garantie, HA)
- « Fait » / « préciser » ; ajout de tâche : nom, fréquence, dernier
- Tableau de bord et onglet Entretiens (liste à plat)
- `/api/ha/summary` alimenté par `v_task_status`
- Lien HA optionnel

## Hors périmètre

- Éléments de construction dans l’UI
- Documents / manuels PDF (issue à ouvrir)
- Coûts, problèmes, capteurs d’usure, calendrier HA

## Mise à jour d’une installation existante

L’add-on 0.1.0 n’a pas encore de tables métier. Au passage en 0.2.0, le
démarrage joue `mabarak-migrate` sur `/data` : le volume persistant n’est
pas effacé, le schéma est créé. Reconstruire l’add-on depuis le dépôt, puis
mettre à jour l’intégration HACS à la même version.
