# HomeKeeper

Gestion et entretien de la maison, en local, dans Home Assistant.

HomeKeeper centralise tout ce qui concerne votre maison : équipements, éléments de
construction, entretiens récurrents, interventions, problèmes, documents, garanties et coûts.
Vous ouvrez la fiche d'un appareil et vous savez immédiatement ce que c'est, où il est, quand il
a été installé et entretenu, ce qui a été réparé, combien il a coûté, où sont la facture et la
notice, et s'il est encore sous garantie.

> Cette version est un squelette d'architecture. Les fonctionnalités décrites ci-dessous
> correspondent à la V1 visée et ne sont pas encore implémentées.

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

## Installation

> Le dépôt GitHub ne contient pas encore ce code tant qu'il n'a pas été poussé.
> Sans ce push, l'étape 2 ci-dessous ne trouvera pas l'add-on.

1. Dans Home Assistant, allez dans **Paramètres → Modules complémentaires → Boutique**.
2. Menu en haut à droite, **Dépôts**, puis ajoutez `https://github.com/k69sknk/myhome`.
3. Rechargez la boutique, cherchez **HomeKeeper**, installez-le, puis démarrez-le.
4. Activez **Afficher dans la barre latérale**.

Le premier démarrage construit l'image **sur votre machine Home Assistant**. Comptez
plusieurs minutes, parfois plus de dix sur un Raspberry Pi. Le journal de l'add-on
doit finir par « HomeKeeper est pret » puis le démarrage de l'API.

Cette version est un squelette : le panneau s'ouvre, mais il n'y a pas encore de
fiches ni d'entretiens. C'est normal.

Pour les capteurs Home Assistant, installez ensuite l'intégration via HACS depuis
le même dépôt. Ce n'est pas nécessaire pour tester le panneau.

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
sur une base incohérente. Restaurez une sauvegarde et signalez le problème avec le journal.

**L'intégration ne se propose pas automatiquement.** Vérifiez que l'add-on est bien démarré,
puis ajoutez l'intégration manuellement depuis **Paramètres → Appareils et services → Ajouter une
intégration → HomeKeeper**.

## Support

Signalez les problèmes sur [le dépôt GitHub](https://github.com/k69sknk/myhome/issues).
