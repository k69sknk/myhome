# MaBarak

Gestion et entretien de la maison, en local, dans Home Assistant.

MaBarak centralise tout ce qui concerne votre maison : équipements, éléments de
construction, entretiens récurrents, interventions, problèmes, documents, garanties et coûts.
Vous ouvrez la fiche d'un appareil et vous savez immédiatement ce que c'est, où il est, quand il
a été installé et entretenu, ce qui a été réparé, combien il a coûté, où sont la facture et la
notice, et s'il est encore sous garantie.

Cette version couvre les fiches d'appareils et d'éléments de construction, les lieux, les
entretiens récurrents, l'historique des interventions, l'annuaire des membres et des
prestataires, et les documents — ceux d'une fiche, ceux d'un entretien, et les papiers de la
maison elle-même comme l'acte ou l'assurance. La page **Documents** les rassemble tous, avec
recherche et filtres.

## Confidentialité

L'add-on ne communique avec aucun serveur extérieur. Toutes vos données restent sur votre
machine, dans le répertoire `/data` de l'add-on, qui est inclus dans les sauvegardes Home
Assistant.

Pour les documents sensibles comme les factures, qui contiennent souvent votre nom et votre
adresse, trois modes sont proposés et vous choisissez librement pour chaque document :

- **Fichier local** : le document est stocké dans l'add-on, chez vous.
- **Lien externe** : vous enregistrez seulement une URL vers votre Nextcloud, votre Drive ou
  votre NAS. L'add-on ne stocke pas le fichier.
- **Référence simple** : vous notez juste où le retrouver, par exemple « e-mail du 12/05/2024 »
  ou « classeur chauffage au garage ».

Vous pouvez changer de mode à tout moment sans perdre le document ni ses rattachements.

## Mise à jour depuis 0.1.0

Si l'add-on 0.1.0 est déjà installé :

1. **Paramètres → Modules complémentaires → Boutique → MaBarak → Mettre à jour**.
   Home Assistant reconstruit l'image en local : plusieurs minutes, parfois plus de
   dix sur un Raspberry Pi.
2. Redémarrez l'add-on. Le volume `/data` est conservé. Au démarrage,
   `mabarak-migrate` crée le schéma métier (la 0.1.0 n'avait pas encore de tables).
3. Mettez aussi à jour l'intégration HACS **MaBarak** à la **même** version 0.2.0.

Le contrat `/api/ha/summary` reste `api_schema_version = 1` : les capteurs existants
continuent de fonctionner. Videz le cache du navigateur si le panneau reste sur
l'ancien écran « squelette ».

## Installation

1. Dans Home Assistant, allez dans **Paramètres → Modules complémentaires → Boutique**.
2. Menu en haut à droite, **Dépôts**, puis ajoutez `https://github.com/k69sknk/myhome`.
3. Rechargez la boutique, cherchez **MaBarak**, installez-le, puis démarrez-le.
4. Activez **Afficher dans la barre latérale**.

Le premier démarrage (ou une mise à jour) construit l'image **sur votre machine
Home Assistant**. Comptez plusieurs minutes, parfois plus de dix sur un Raspberry Pi.
Le journal de l'add-on doit finir par « MaBarak est pret » puis le démarrage de l'API.

Pour les capteurs Home Assistant, installez ensuite l'intégration via HACS depuis
le même dépôt, à la même version que l'add-on.

## Configuration

### Option `log_level`

Niveau de détail du journal de l'add-on. Valeurs possibles, de la plus bavarde à la plus
silencieuse : `trace`, `debug`, `info`, `notice`, `warning`, `error`, `fatal`.

Par défaut `info`. Passez en `debug` uniquement pour diagnostiquer un problème.

```yaml
log_level: info
```

## Accès à l'interface

L'interface s'ouvre depuis la barre latérale de Home Assistant. Elle utilise l'ingress, ce qui
signifie que votre session Home Assistant sert d'authentification : il n'y a pas de second mot
de passe à gérer, et l'add-on n'est joignable que par Home Assistant.

Le port direct `8099` est volontairement fermé. L'ouvrir exposerait l'interface **sans aucune
authentification** à toute personne ayant accès à votre réseau local. Ne le faites qu'en
développement.

## Piloter MaBarak depuis un assistant

Depuis la 0.30.0, MaBarak est pilotable par la voix, par une automatisation, ou par un agent
conversationnel branché sur Home Assistant. « Note que le ramonage a été fait », « ajoute la
nouvelle chaudière dans la cave » : l'entretien est enregistré et sa prochaine échéance
recalculée, sans ouvrir l'interface.

**Cela exige l'intégration MaBarak**, pas seulement l'add-on. L'add-on seul n'expose aucun
service. Si votre assistant vous répond qu'il ne trouve aucun service `mabarak.*`, c'est presque
toujours que l'intégration n'est pas installée : ajoutez-la via HACS depuis le même dépôt, puis
**Paramètres → Appareils et services → Ajouter une intégration → MaBarak**.

### Ce que vous pouvez demander

| Action | Exemple |
| --- | --- |
| `mabarak.apercu` | « Qu'est-ce qui est en retard dans la maison ? » |
| `mabarak.chercher_equipement` | « Quand la VMC a-t-elle été entretenue ? » |
| `mabarak.valider_entretien` | « Note que le ramonage a été fait hier par Dupont. » |
| `mabarak.creer_entretien` | « Ajoute un changement de filtre tous les six mois sur la PAC. » |
| `mabarak.creer_equipement` | « Ajoute un lave-linge Bosch dans la buanderie. » |
| `mabarak.consigner_intervention` | « J'ai fait réparer le lave-linge, 210 euros. » |

### Selon la façon dont votre assistant est branché

**Par le serveur MCP de Home Assistant** (le cas le plus courant pour un agent externe) : les six
actions apparaissent comme des outils nommés `MaBarakApercu`, `MaBarakValiderEntretien`, etc.
Rien à configurer de plus — elles sont exposées avec l'API « Assist », que le serveur MCP publie
par défaut.

**Par l'API REST avec un jeton de longue durée** : appelez les services `mabarak.*` directement.
Pour les deux actions de lecture, ajoutez `?return_response=true` afin de récupérer le résultat.

**Par une automatisation ou un script** : les services figurent dans l'éditeur d'actions, avec
leurs champs.

### Ce qu'il faut en savoir

**Les fiches se désignent par leur nom**, jamais par un numéro. Les accents et la casse n'ont pas
d'importance, et vous pouvez être plus bavard que la fiche : « la chaudière gaz de la cave »
trouve « Chaudière gaz ».

**En cas de doute, rien n'est écrit.** Si deux équipements ont un entretien du même nom, la
demande est refusée avec la liste des candidats, et l'assistant vous demande lequel. C'est
volontaire : une écriture dans la mauvaise fiche ne se remarque pas avant des mois.

**Un lieu inconnu est refusé**, avec la liste des pièces existantes, pour qu'un nom mal compris
ne crée pas une pièce en double. Vous pouvez passer outre en le demandant explicitement.

**Ce qu'un assistant écrit est marqué comme tel** dans la base. Si une ligne d'historique vous
paraît fausse un jour, vous pourrez savoir si elle vient de vous ou d'un agent.

**Si votre assistant gère les « skills »**, le dépôt en contient une dans
[`skills/mabarak/`](https://github.com/k69sknk/myhome/tree/main/skills/mabarak). Elle lui
apprend à commencer par l'aperçu pour connaître le vocabulaire de votre maison, à ne pas
trancher une ambiguïté à votre place, et à distinguer un entretien planifié qu'on valide d'une
réparation qu'on consigne. Ce n'est pas obligatoire — les actions fonctionnent sans — mais les
échanges y gagnent.

**Une limite connue** : les entretiens rattachés à la maison entière plutôt qu'à un équipement
— « tester les détecteurs de fumée » — ne peuvent pas encore être marqués comme faits. C'est
aussi vrai dans l'interface. L'assistant vous le dira clairement plutôt que de chercher ailleurs.

## Sauvegarde

Tout est dans `/data` : la base de données et les documents importés. Une sauvegarde Home
Assistant de l'add-on suffit donc à tout restaurer.

Si vous importez beaucoup de PDF volumineux, vos sauvegardes grossiront d'autant. Dans ce cas,
préférez le mode « lien externe » pour les gros documents.

## Résolution de problèmes

**L'interface affiche une page blanche ou une erreur 404.** Redémarrez l'add-on, puis rechargez
la page avec un vidage du cache. Si le problème persiste, consultez le journal de l'add-on.

**L'add-on ne démarre pas et le journal mentionne les migrations.** L'add-on refuse
volontairement de démarrer si les migrations de base de données échouent, pour ne pas travailler
sur une base incohérente. Sur une **mise à jour 0.1.0 → 0.2.0** (pas encore de données métier),
vous pouvez supprimer le fichier SQLite dans `/data` de l'add-on puis redémarrer : le schéma
sera recréé. Sinon, restaurez une sauvegarde et signalez le problème avec le journal.

**L'intégration ne se propose pas automatiquement.** Vérifiez que l'add-on est bien démarré,
puis ajoutez l'intégration manuellement depuis **Paramètres → Appareils et services → Ajouter une
intégration → MaBarak**.

**Mon assistant ne voit aucun service `mabarak.*`.** L'add-on seul n'en expose aucun : c'est
l'intégration qui les fournit. Si vous ne voyez que des entités `update.*` au nom de MaBarak,
elles viennent du Supervisor et signalent justement que l'intégration n'est pas installée. Voir
« Piloter MaBarak depuis un assistant » plus haut.

**Mon assistant trouve les services mais pas mes équipements.** Faites-lui appeler `mabarak.apercu`
en premier : cette action lui donne la liste des pièces et le nombre d'équipements, c'est-à-dire
le vocabulaire de votre maison. Sans elle, il invente des noms de pièces.

## Support

Signalez les problèmes sur [le dépôt GitHub](https://github.com/k69sknk/myhome/issues).
