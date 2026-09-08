/**
 * Resolution du prefixe sous lequel l'application est servie.
 *
 * Home Assistant expose l'add-on derriere `/api/hassio_ingress/<token>/`, ou le
 * token change a chaque instance et a chaque redemarrage. Le prefixe est donc
 * inconnu a la compilation : le backend l'injecte dans la balise `<base>` de la
 * page, a partir de l'en-tete `X-Ingress-Path`.
 *
 * Voir docs/ARCHITECTURE.md section 4.
 */

const BASE_PLACEHOLDER = '__HOMEKEEPER_BASE__'
const INGRESS_PATTERN = /^(\/api\/hassio_ingress\/[^/]+)/

function ensureTrailingSlash(path: string): string {
  return path.endsWith('/') ? path : `${path}/`
}

/** Prefixe de l'application, toujours termine par `/`. */
export function resolveBasePath(): string {
  const fromBaseTag = new URL(document.baseURI).pathname

  if (!fromBaseTag.includes(BASE_PLACEHOLDER)) {
    return ensureTrailingSlash(fromBaseTag)
  }

  // Le marqueur n'a pas ete remplace : le build est servi sans le backend.
  // On retombe sur le chemin courant, qui contient le prefixe en contexte
  // d'ingress, puis sur la racine.
  const match = window.location.pathname.match(INGRESS_PATTERN)
  return match ? `${match[1]}/` : '/'
}

/** Valeur attendue par React Router, donc sans `/` final. */
export function routerBasename(base: string = resolveBasePath()): string {
  const trimmed = base.replace(/\/+$/, '')
  return trimmed === '' ? '/' : trimmed
}

/** URL absolue d'une route de l'API, prefixe d'ingress compris. */
export function apiUrl(path: string, base: string = resolveBasePath()): string {
  return `${base}api/${path.replace(/^\/+/, '')}`
}
