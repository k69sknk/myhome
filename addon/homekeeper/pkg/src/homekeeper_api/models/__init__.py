"""Tables SQLAlchemy.

Volontairement vide a ce stade. Le cahier des charges impose de valider
l'architecture des donnees avant de coder ; le modele fige se trouve dans
docs/DATA_MODEL.md et docs/schema.sql, et sera traduit ici une fois valide.

Rappel des points a ne pas perdre a la traduction :

* `asset` porte le discriminant `kind` (ADR-0001) ;
* les trois modes de stockage de `document` sont exclusifs, garantis par CHECK
  (ADR-0002) ;
* l'historique est une vue, pas une table (ADR-0003) ;
* `maintenance_task.recurrence_anchor` conditionne tout le calcul d'echeances
  (ADR-0004).
"""
