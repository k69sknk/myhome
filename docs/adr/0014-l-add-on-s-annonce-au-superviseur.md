# ADR-0014 — L'add-on s'annonce au Supervisor, plutôt que l'intégration ne devine son adresse

- Statut : Accepté
- Date : 2026-09-12
- Concerne : `backend/src/mabarak_api/services/discovery.py` et son appel au démarrage
  (`main.py`) ; `custom_components/mabarak/const.py` (`DEFAULT_HOST`) ;
  `addon/mabarak/config.yaml` clés `discovery` et `hassio_api` ; complète
  [0013](0013-pilotage-par-agent-externe.md), dont rien n'était utilisable tant que
  l'intégration ne joignait pas l'add-on

## Contexte

L'intégration doit joindre l'add-on en HTTP sur le réseau interne de Home Assistant. Elle a
besoin pour cela d'un nom d'hôte, et jusqu'ici elle en proposait un en dur :

```python
DEFAULT_HOST = "a0d7b954-mabarak"
```

Cette valeur ne peut pas être correcte. Le Supervisor résout un add-on par son **slug**, tirets
à la place des soulignés — c'est exactement ce que fait
`homeassistant.components.hassio.hostname_from_addon_slug` :

```python
def hostname_from_addon_slug(addon_slug: str) -> str:
    return addon_slug.replace("_", "-")
```

Or ce slug porte en préfixe un **hash du dépôt d'origine**. `a0d7b954` est celui du dépôt
Community Add-ons ; MaBarak est distribué depuis `github.com/k69sknk/myhome`, qui en a un autre.
La valeur par défaut était donc fausse pour tout le monde, tout le temps.

Le symptôme, côté utilisateur : « L'add-on est injoignable. Vérifiez qu'il est démarré » — un
message qui désigne la mauvaise cause, et envoie chercher une panne là où il n'y en a pas.

## Ce qui n'est PAS le problème

La tentation est de corriger le hash. Elle est doublement fausse : il dépend de l'URL du dépôt,
donc changerait si le dépôt déménageait ou si quelqu'un installait depuis un miroir ; et surtout
elle laisserait l'utilisateur devant un écran de saisie pour une information que le système
connaît déjà.

Ce n'est pas non plus un manque de documentation qu'on réglerait en expliquant où lire le slug.
Expliquer comment contourner, c'est admettre que le défaut reste.

## Décision

**L'add-on s'annonce lui-même.** Il est le seul des deux à connaître son nom d'hôte avec
certitude : le Supervisor le lui donne sur `/addons/self/info`. Au démarrage, il publie donc un
message de découverte :

```
POST http://supervisor/discovery
{"service": "mabarak", "config": {"host": "<hostname>", "port": 8099}}
```

Home Assistant propose alors l'intégration d'elle-même, et `async_step_hassio` reçoit l'adresse
sans que personne ait à la taper.

Le plus frappant est que **tout était déjà en place sauf l'émission** : `config.yaml` déclarait
`discovery: [mabarak]` et `hassio_api: true` depuis l'origine, et `config_flow.py` savait
recevoir l'annonce. Il ne manquait que la moitié qui parle. C'est un rappel utile : une clé de
configuration déclarée n'est pas un comportement, et rien dans la CI ne pouvait le signaler.

Le port publié est **8099**, celui de nginx, et non le 8000 d'uvicorn : l'intégration passe par
nginx, qui filtre les adresses IP. Un test vérifie que la constante et le `listen` de
`nginx.conf` ne divergent pas.

L'échec de l'annonce est **silencieux et sans conséquence** : hors d'un add-on — en
développement, dans les tests — il n'y a pas de Supervisor, et l'add-on doit démarrer quand
même. L'interface fonctionne sans intégration.

## Le second défaut, découvert en corrigeant le premier

Une fois le bon nom d'hôte saisi, l'erreur a changé : l'add-on **répondait**, et refusait. nginx
n'autorisait que `172.30.32.2` — le proxy d'ingress — et renvoyait 403 à tout le reste, y compris
à Home Assistant Core. L'intégration ne pouvait donc pas joindre l'add-on, quelle que soit
l'adresse utilisée.

Les deux défauts se masquaient l'un l'autre, et masquaient surtout le fait que **l'intégration
n'a jamais fonctionné** : ses capteurs et son calendrier, présents dans le dépôt depuis des
versions, n'ont jamais existé chez un utilisateur. L'ingress fonctionnant parfaitement, rien ne
le signalait.

Le filtrage est donc élargi au `/23` du réseau interne du Supervisor, qui porte le proxy
d'ingress **et** Home Assistant Core. Ce réseau est créé et géré par Home Assistant, et le port
reste fermé sur l'hôte (`ports: 8099/tcp: null`) : rien n'est exposé au LAN. Le filtrage garde
son rôle — l'add-on n'est joignable que de l'intérieur — mais cesse d'exclure l'appelant pour
lequel il existe.

L'échec remontait par ailleurs en « Unknown error occurred », parce que le flux de configuration
ne connaissait pas ce cas. Une clé d'erreur `refused` le nomme désormais et dit quoi faire.

## Options envisagées

**Corriger le hash en dur.** Écartée : faux dès que le dépôt change d'URL, et laisse une saisie
manuelle pour une information déjà connue du système.

**Faire résoudre le nom d'hôte par l'intégration**, en interrogeant le Supervisor pour trouver
l'add-on dont le slug se termine par `_mabarak`. Écartée : plus de code, dépendance à des
détails internes du composant `hassio`, et le résultat serait le même que l'annonce — qui, elle,
est le mécanisme prévu par Home Assistant pour exactement ce besoin.

**Supprimer la saisie manuelle** une fois la découverte en place. Écartée : la découverte peut
échouer (Supervisor indisponible au démarrage, installation atypique), et la retirer laisserait
l'utilisateur sans recours. Elle reste, mais son texte dit désormais où trouver la vraie valeur
au lieu d'en suggérer une fausse avec assurance.

## Conséquences

`DEFAULT_HOST` reste comme repli, corrigé à `b34ff0a4-mabarak` — le hash réel de
`github.com/k69sknk/myhome`, relevé sur une installation. Il vaut donc pour toute installation
faite depuis ce dépôt, et changerait si le dépôt déménageait ; le commentaire le dit. Mais c'est
la découverte qui doit servir : un défaut juste par coïncidence de dépôt reste un défaut.

Les installations existantes qui ont déjà une entrée de configuration ne sont pas touchées :
l'adresse saisie à la main continue de fonctionner. L'annonce ne sert qu'aux nouvelles
installations et à celles qui reconfigurent.
