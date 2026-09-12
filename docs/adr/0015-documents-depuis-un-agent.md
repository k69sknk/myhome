# ADR-0015 — MaBarak va chercher le document, sur le réseau local et nulle part ailleurs

- Statut : Accepté
- Date : 2026-09-12
- Concerne : `backend/src/mabarak_api/services/fetch.py` ; action `joindre_document` de
  `custom_components/mabarak/actions.py` ; route `POST /api/agent/documents` ; prolonge
  [0013](0013-pilotage-par-agent-externe.md) et applique
  [0002](0002-document-a-trois-modes-de-stockage.md)

## Contexte

Un utilisateur transfère une facture à son assistant conversationnel et lui demande de la ranger
dans MaBarak. L'assistant détient le fichier ; il tourne sur une autre machine que Home
Assistant. Les octets doivent donc voyager.

Deux des trois modes de stockage d'[ADR-0002](0002-document-a-trois-modes-de-stockage.md) ne
posent aucun problème : un **lien externe** et une **note de référence** sont du texte, et un
appel de service les transporte très bien. Le troisième — le **fichier local** — est le sujet de
cette décision.

## Ce qui n'est PAS la solution

**Faire voyager le fichier encodé dans l'appel de service.** C'est la piste évidente, et elle est
à écarter pour une raison vérifiable dans le code de Home Assistant : son enregistreur écoute
`MATCH_ALL` et n'exclut aucun type d'événement par défaut. `_process_one_event` range donc chaque
appel de service dans la base, **avec ses données**. Une facture de 2 Mo deviendrait environ
2,7 Mo de base64 écrits dans le SQLite de l'utilisateur, à chaque document. Le défaut serait
invisible jusqu'au jour où sa base devient ingérable.

**Un dossier partagé.** L'add-on gagnerait un `map:` vers `/share`, l'agent y déposerait le
fichier. Cela suppose un système de fichiers commun, que deux machines distinctes n'ont pas — et
ajouterait au produit une dépendance à la topologie de l'installation.

**Une API d'import ouverte sur le réseau.** C'est exactement ce qu'[ADR-0013](0013-pilotage-par-agent-externe.md)
a écarté : l'add-on n'a aucune authentification, et lui en construire une pour ce seul besoin
reviendrait à ouvrir une seconde porte sur les données de la maison.

## Décision

**L'agent expose le fichier à une adresse, MaBarak va le chercher.** L'inversion est ce qui rend
le reste possible : les octets ne traversent jamais Home Assistant, l'add-on garde sa porte
fermée, et l'agent n'a besoin d'aucun droit supplémentaire.

Une seule règle gouverne `services/fetch.py` : **l'adresse visée doit être privée.** Sans elle,
cette route deviendrait un moyen de faire sortir des données de la maison, ou d'aller chercher
n'importe quoi sur Internet au nom de l'add-on — et le local-first du produit cesserait d'être
une propriété du code pour n'être plus qu'une intention.

Trois détails en découlent, et chacun vaut par ce qu'il refuse :

- **toutes** les adresses résolues sont vérifiées, pas la première : un nom qui pointe à la fois
  vers une adresse privée et une publique ne passe pas, sinon l'ordre de résolution suffirait à
  contourner la règle ;
- les **redirections ne sont pas suivies** : une redirection peut sortir du réseau local après la
  vérification, et la revalider à chaque saut compliquerait le code pour un cas que personne n'a
  demandé ;
- la **taille est vérifiée pendant la lecture**, bloc par bloc, et non sur l'en-tête
  `Content-Length` : un serveur peut mentir sur la taille qu'il annonce, ou n'en annoncer aucune.

Le refus n'est jamais muet : il dit pourquoi, et propose le mode `lien`, qui garde le document
retrouvable sans copie.

## Ce que cette décision ne garantit pas

Entre la vérification de l'adresse et la requête, le nom est résolu une seconde fois par la
bibliothèque HTTP. Une réponse DNS qui changerait entre les deux passerait au travers. Fermer
cette fenêtre demanderait de se connecter à l'adresse vérifiée en forçant l'en-tête `Host`, ce
qui casse la vérification du certificat en HTTPS.

Le compromis est assumé : l'attaquant devrait déjà contrôler la résolution de noms du réseau
local, auquel cas il a de bien meilleures cibles que l'import de documents d'une application
d'entretien. Ce n'est pas une raison de l'ignorer, c'en est une de l'écrire.

## Conséquences

Les trois modes restent également accessibles à l'agent, et le choix lui est laissé comme il est
laissé à l'utilisateur dans l'interface. La skill l'invite à poser la question quand elle n'est
pas tranchée : copier fait entrer le document dans les sauvegardes de Home Assistant, garder un
lien laisse l'original où il est, avec le risque qu'il disparaisse.

C'est la première requête sortante du backend en fonctionnement normal. La section 7 de
[ARCHITECTURE.md](../ARCHITECTURE.md) disait qu'il n'en émettait aucune ; elle dit désormais
qu'il en émet une, vers le réseau local seulement, et à la demande explicite de l'utilisateur.
