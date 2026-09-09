# Frontend MaBarak

Interface web de l'add-on, affichée dans le panneau latéral de Home Assistant. React 19,
TypeScript, Vite, React Router.

Les écrans 0.2.0 : tableau de bord, lieux, liste et fiche d'équipement, entretiens.
L'onglet Documents reste un placeholder.

## Développement

```bash
npm install
npm run dev
```

L'interface est sur <http://localhost:5173>. Le serveur Vite relaie `/api` vers le backend sur
le port 8000, qui doit donc tourner en parallèle.

```bash
npm run build       # tsc --noEmit puis vite build
npm run typecheck
```

## Le point à ne pas casser : le chemin de base d'ingress

Home Assistant sert l'add-on sous `/api/hassio_ingress/<token>/`, où le token change à chaque
instance et à chaque redémarrage. Le préfixe est donc **inconnu à la compilation**. C'est la
cause de la quasi-totalité des add-ons ingress qui affichent une page blanche ou des 404.

Trois mécanismes le résolvent ensemble, et ils doivent rester cohérents :

1. `vite.config.ts` fixe `base: './'`, donc tous les assets sont référencés relativement. **Une
   seule URL absolue commençant par `/` suffit à tout casser.**
2. `index.html` contient `<base href="__MABARAK_BASE__">`. Le backend remplace ce marqueur
   par l'en-tête `X-Ingress-Path` à chaque requête. Les URL relatives se résolvent alors contre
   le bon préfixe, y compris quand l'utilisateur recharge une route profonde comme
   `/equipements/7`.
3. `src/base-path.ts` lit `document.baseURI` pour en déduire le `basename` de React Router et le
   préfixe des appels API.

En développement, un plugin Vite remplace le marqueur par `/`, puisque Vite sert `index.html`
sans passer par le backend.

Le marqueur `__MABARAK_BASE__` est dupliqué dans trois fichiers : `index.html`,
`vite.config.ts` et `backend/src/mabarak_api/ingress.py`. Le modifier impose de le changer
partout. Le test `test_index_injecte_le_chemin_ingress` côté backend échouera si la chaîne se
rompt.

## Structure

- `src/base-path.ts` : résolution du préfixe d'ingress
- `src/api/client.ts` : appels HTTP et gestion d'erreurs
- `src/api/types.ts` : types du contrat de l'API, en `snake_case` comme le JSON du backend
- `src/components/Layout.tsx` : en-tête et navigation
- `src/pages/` : tableau de bord, lieux, équipements, entretiens

## Conventions

Aucun appel réseau sortant. L'application ne doit joindre que son propre backend : c'est une
exigence de confidentialité du projet, pas une préférence. Pas de police distante, pas de CDN,
pas de télémétrie.
