# Décisions d'architecture (ADR)

Un ADR (Architecture Decision Record) documente une décision structurante : son contexte, les
options envisagées, le choix retenu et ses conséquences. L'objectif est qu'un lecteur qui
découvre le code six mois plus tard comprenne pourquoi il est fait ainsi, plutôt que de refaire
le raisonnement ou, pire, de « corriger » une décision volontaire.

Un ADR n'est jamais modifié après acceptation. Si la décision change, un nouvel ADR est écrit et
l'ancien passe en statut `Remplacé par ADR-XXXX`.

## Index

| ADR | Titre | Statut |
| --- | --- | --- |
| [0001](0001-table-asset-unique.md) | Une seule table pour les équipements et les éléments de construction | Accepté |
| [0002](0002-document-a-trois-modes-de-stockage.md) | Un document, trois modes de stockage, une seule table | Accepté |
| [0003](0003-historique-derive.md) | L'historique est une vue dérivée, pas une table | Accepté |
| [0004](0004-ancrage-de-recurrence.md) | La récurrence porte un ancrage explicite | Accepté |
| [0005](0005-monodepot-addon-et-hacs.md) | Un monodépôt servant à la fois d'add-on et d'intégration HACS | Accepté |
| [0006](0006-liaison-aux-appareils-home-assistant.md) | Lier les fiches aux appareils Home Assistant | Accepté |
| [0007](0007-v1-ecrit-ha-link.md) | La V1 écrit `ha_link` (liaison manuelle assistée) | Accepté |

Le choix de l'architecture hybride add-on plus intégration est documenté directement dans
[../ARCHITECTURE.md](../ARCHITECTURE.md), section 2, avec les options écartées.
