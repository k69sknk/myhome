/** Recherche texte des listes de l'application.
 *
 *  Deux regles, et elles viennent de la meme observation : ce qu'on tape dans un
 *  champ de recherche n'est pas un identifiant, c'est un souvenir approximatif.
 *
 *  1. Les accents ne comptent pas. Taper « refrigerateur » doit trouver
 *     « Réfrigérateur », et « electricien » trouver « Électricien ». Dans une
 *     application francaise, l'exiger reviendrait a demander a l'utilisateur de
 *     connaitre l'orthographe exacte de ce qu'il cherche — et souvent a taper des
 *     accents sur un clavier de telephone.
 *  2. Les mots comptent separement, et tous doivent etre presents. « clim 69 »
 *     trouve « Clim Services 69 » comme « Clim Services » du 69300, sans imposer
 *     l'ordre ni la ponctuation.
 */

/** Minuscules, sans accents ni signes diacritiques. */
export function normalize(text: string): string {
  return text
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '') // marques combinantes laissees par NFD
    .toLowerCase()
    .trim()
}

/** `query` correspond-elle a ces morceaux de texte, mot par mot ?
 *
 *  Les morceaux sont concatenes : un mot trouve dans le nom et un autre dans le
 *  metier suffisent, ce qui est exactement ce qu'on attend de « dupont chauff ».
 *  Une requete vide accepte tout : un filtre qu'on n'a pas rempli ne filtre pas.
 */
export function matches(parts: (string | null | undefined)[], query: string): boolean {
  const words = normalize(query).split(/\s+/).filter(Boolean)
  if (words.length === 0) return true
  const haystack = normalize(parts.filter(Boolean).join(' '))
  return words.every((word) => haystack.includes(word))
}
