import react from '@vitejs/plugin-react'
import { defineConfig, type Plugin } from 'vite'

/**
 * Marqueur remplace par le backend a chaque requete, dans la balise `<base>`.
 * Doit rester identique a `BASE_PLACEHOLDER` cote Python
 * (backend/src/mabarak_api/ingress.py).
 */
const BASE_PLACEHOLDER = '__MABARAK_BASE__'

/**
 * En developpement, Vite sert `index.html` directement, sans passer par le
 * backend : le marqueur ne serait donc pas remplace et toutes les URL relatives
 * se resoudraient contre `/__MABARAK_BASE__`.
 */
function devIngressBase(): Plugin {
  return {
    name: 'mabarak-dev-ingress-base',
    apply: 'serve',
    transformIndexHtml(html) {
      return html.replaceAll(BASE_PLACEHOLDER, '/')
    },
  }
}

export default defineConfig({
  // Chemins relatifs obligatoires : le prefixe d'ingress Home Assistant n'est
  // connu qu'a l'execution. Combine a la balise `<base>`, cela permet de servir
  // la meme application sous n'importe quel prefixe.
  base: './',

  plugins: [react(), devIngressBase()],

  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false,
  },

  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
