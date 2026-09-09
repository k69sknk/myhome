# ADR-0007 — La V1 écrit `ha_link` (liaison manuelle assistée)

- Statut : Accepté
- Date : 2026-09-08
- Amende : [0006-liaison-aux-appareils-home-assistant.md](0006-liaison-aux-appareils-home-assistant.md)

## Contexte

L'ADR-0006 plaçait la liaison manuelle assistée en V2. La fiche équipement en
fait un geste de la V1 : préremplir nom / marque / modèle et proposer le lieu
depuis l'area Home Assistant.

## Décision

La V1 écrit et lit `ha_link` pour un lien `device` (ou `entity`) de rôle
`primary`. Les lieux MaBarak restent la source de vérité. L'usure
(`role = consumable`) reste V4.

## Conséquences

L'ADR-0006 reste la référence du modèle. Seul le découpage de version change.
