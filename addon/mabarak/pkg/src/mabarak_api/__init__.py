"""MaBarak — backend de gestion et d'entretien de la maison.

L'add-on et l'integration Home Assistant partagent ce numero de version
(cf. docs/adr/0005-monodepot-addon-et-hacs.md). Il est ecrit ici en toutes
lettres, et non lu depuis les metadonnees du paquet : un `pip install -e`
fige la version au moment de l'installation, et le backend annoncerait alors
en developpement une version peremee. `scripts/check-versions.py` verifie en
CI que les cinq fichiers qui le portent restent d'accord.
"""

__version__ = "0.32.0"

__all__ = ["__version__"]
