"""Regles metier.

Point d'entree unique pour tout ce que l'interface et l'integration Home Assistant
doivent voir de facon identique :

* calcul de `next_due_on` selon `recurrence_type` et `recurrence_anchor`,
  y compris le rattrapage d'intervalles pour l'ancrage sur date theorique
  (ADR-0004) ;
* derivation des statuts `ok` / `due_soon` / `overdue` ;
* agregation des couts par equipement ;
* resolution des documents selon leur mode de stockage (ADR-0002).

Ecrire ces regles ici, en Python, est la raison du choix de la stack backend :
l'integration les consomme via `/api/ha/summary` au lieu de les reimplementer.
"""
