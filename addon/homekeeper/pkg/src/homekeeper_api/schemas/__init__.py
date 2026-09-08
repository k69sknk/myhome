"""Modeles Pydantic d'entree et de sortie.

Distincts des tables SQLAlchemy : le schema autorise des combinaisons que le
metier refuse. Par exemple, rien n'empeche en base de renseigner un numero de
serie sur une toiture, puisque `asset` est une table unique (ADR-0001). C'est
ici que ces validations dependantes du `kind` sont appliquees.
"""
