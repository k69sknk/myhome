# ADR-0006 — Lier les fiches HomeKeeper aux appareils Home Assistant

- Statut : Accepté
- Date : 2026-09-08
- Concerne : [../DATA_MODEL.md](../DATA_MODEL.md) section 2.12, [../schema.sql](../schema.sql) table `ha_link`, [../ARCHITECTURE.md](../ARCHITECTURE.md)

## Contexte

Quand un équipement existe déjà dans Home Assistant — robot aspirateur Roborock, pompe à chaleur
connectée, VMC pilotée, onduleur solaire — l'utilisateur doit pouvoir relier sa fiche
HomeKeeper à cet appareil. L'exemple qui a déclenché cette décision est l'aspirateur robot :
l'intégration officielle Roborock n'expose pas une seule entité, mais un **appareil** qui porte
une vingtaine d'entités, dont plusieurs sont directement utiles à l'entretien :

- temps restant avant remplacement du filtre, de la brosse principale, de la brosse latérale ;
- temps restant avant nettoyage des capteurs ;
- surface et durée de nettoyage cumulées.

Le modèle ne prévoyait qu'une colonne `asset.ha_entity_id`. Relier une fiche à une seule
`entity_id` perdrait justement ce qui a de la valeur pour la maintenance, et casserait le lien
dès que l'utilisateur renomme l'entité.

Les fonctions concrètes (affichage d'usure, tâches déclenchées par un capteur) seront discutées
plus tard. Cette décision ne porte que sur **le sens de l'accès**, **la cible du lien**, et **ce
qu'il faut stocker** pour que ces fonctions puissent arriver sans migration douloureuse.

Faits vérifiés, pas supposés :

- Un add-on lit Home Assistant Core via `homeassistant_api: true`, le jeton `SUPERVISOR_TOKEN`,
  l'API REST `http://supervisor/core/api/` et le WebSocket `ws://supervisor/core/websocket`.
  Source : [Communication with Home Assistant](https://developers.home-assistant.io/docs/add-ons/communication/).
- `homeassistant_api: true` **n'apparaît pas** dans le tableau officiel de la note de sécurité
  ni dans `rating_security()` du Supervisor. La note actuelle (ingress, pas de privilèges
  host) n'est donc pas dégradée par cet accès. Sources :
  [présentation des add-ons](https://developers.home-assistant.io/docs/add-ons/presentation/)
  et [supervisor/addons/utils.py](https://github.com/home-assistant/supervisor/blob/main/supervisor/addons/utils.py).
- Le registre des appareils n'est pas exposé par l'API REST. Il se liste par la commande
  WebSocket `config/device_registry/list`. Le registre des entités se liste par
  `config/entity_registry/list`. L'état courant se lit ensuite en REST (`/api/states/<entity_id>`).
- Un `entity_id` (`vacuum.roborock_s8`) est **renommable** par l'utilisateur. L'entrée de
  registre porte un `id` UUID stable, distinct du `unique_id` fourni par l'intégration source.
  C'est cet `id` de registre qu'il faut stocker. Source : discussions du cœur Home Assistant
  autour de `config/entity_registry/list`.
- Si l'intégration source est supprimée, les entrées de registre deviennent orphelines puis
  peuvent disparaître. Un nouvel appairage produit de nouveaux identifiants de registre. Le
  lien HomeKeeper ne peut donc pas « se réparer tout seul » : il doit se marquer comme
  invalide, avec un libellé encore lisible.

## Options envisagées

### Option A — Laisser l'intégration pousser, sans que l'add-on lise Home Assistant

L'intégration custom a déjà accès au registre. Elle pourrait écrire les identifiants dans
l'add-on. Cela évite `homeassistant_api`.

Mais la fiche se consulte **dans l'add-on**. C'est là que l'utilisateur choisit « lier à
l'aspirateur du salon ». Faire ce choix dans les réglages de l'intégration, puis revenir dans
l'add-on pour voir le résultat, casse le flux. Et l'intégration n'a aucune raison d'être le
propriétaire d'un lien qui appartient à une fiche.

### Option B — Une colonne `ha_entity_id` sur `asset`

C'est le modèle actuel. Une fiche, une chaîne. Incapable de représenter un appareil et ses
entités d'usure, incapable de distinguer un `entity_id` renommé d'un identifiant de registre,
aucun libellé conservé si l'appareil disparaît.

### Option C — L'add-on lit Home Assistant, et une table de liaisons porte appareils et entités

L'add-on active `homeassistant_api`, liste les appareils via le WebSocket, et stocke les liens
dans une table dédiée. Chaque ligne vise soit un appareil, soit une entité, avec un rôle, un
libellé figé au moment de la liaison, et un horodatage de dernière résolution réussie.

## Décision

**Option C.**

Le sens de l'accès pour cette exigence est **add-on vers Home Assistant**. L'intégration
continue de projeter les compteurs HomeKeeper vers le cœur ; elle ne devient pas le lieu où
l'on relie une fiche à un robot. Les deux directions coexistent, elles ne se remplacent pas.

La cible primaire du lien est l'**appareil** (`device` du registre). Les entités utiles
(filtre, brosses, commande vacuum) sont liées en plus, chacune avec un `role`. Quand un
équipement n'a pas d'appareil dans Home Assistant — une entité orpheline, un capteur MQTT
saisi à la main — on autorise un lien `entity` sans `ha_device_id`.

On stocke l'`id` de registre, jamais l'`entity_id` comme clé. L'`entity_id` et le nom amical
sont copiés au moment de la liaison (`entity_id_at_link`, `name_at_link`) pour que la fiche
reste lisible si le lien casse.

`asset.ha_entity_id` est retirée.

## Découpage par version

Le schéma est figé **maintenant**, avant la première migration métier. Ajouter cette table plus
tard imposerait une migration alors que le besoin est déjà connu.

La **liaison manuelle assistée** (lister les appareils HA, rattacher, afficher un lien cassé)
relève de la V2 : elle n'est pas dans les dix points de la V1, mais c'est un geste utilisateur
simple, sans intelligence.

Exploiter un capteur d'usure pour proposer ou déclencher une tâche d'entretien relève de la
**V4** du cahier des charges (« maintenance intelligente basée sur les données Home
Assistant »). Le champ `role = 'consumable'` existe déjà pour ne pas avoir à le recoller
après.

La V1 n'écrit ni ne lit cette table.

## Conséquences

Positives :

- Un robot aspirateur se lie comme un tout, puis ses consommables se qualifient sans nouvelle
  table.
- Renommer `vacuum.roborock_s8` en `vacuum.salon` ne casse pas le lien : la clé est l'UUID de
  registre.
- Si l'appareil disparaît, la fiche affiche encore « Roborock S8 (lien invalide depuis …) »
  grâce aux instantanés, au lieu d'un identifiant mort.
- L'accès reste local : `http://supervisor/core/…` ne sort pas de la machine. Aucune donnée de
  fiche n'est envoyée vers un cloud.

Négatives, et comment elles sont traitées :

- L'add-on obtient le droit de **lire tout l'état de Home Assistant**, pas seulement les
  appareils liés. C'est le modèle d'autorisation de `homeassistant_api` : tout ou rien. À
  documenter clairement pour l'utilisateur. La note de sécurité n'en est pas baissée, mais le
  contrat de confiance oui.
- Un WebSocket est obligatoire pour lister les appareils. Plus fragile qu'un GET REST. La
  couche service devra reconnexion et timeout, et l'UI devra proposer un mode dégradé
  (saisie manuelle d'identifiant) si le registre est injoignable.
- Un appareil remplacé (nouveau Roborock) produit un nouvel UUID. L'ancien lien passe en
  invalide ; l'utilisateur rattache le nouveau. Pas de fusion automatique : trop de faux
  positifs (deux robots dans la même maison).
- nginx n'autorise aujourd'hui que `172.30.32.2`. Ça n'empêche pas l'add-on d'**appeler** le
  cœur : le flux est sortant depuis le conteneur, vers `supervisor`. Le filtre IP ne s'applique
  qu'aux connexions **entrantes**. Rien à changer de ce côté pour cette exigence.

## Modification hors schéma, à appliquer sur l'add-on

Dans `addon/homekeeper/config.yaml`, ajouter :

```yaml
homeassistant_api: true
```

`hassio_api: true` est déjà présent (discovery). Les deux drapeaux sont distincts : l'un parle
au Supervisor, l'autre au Core. Le WebSocket Core exige `homeassistant_api`.
