import { expect, test } from '@playwright/test'

import { LARGEURS, aucunDebordementHorizontal, creerFiche, nomUnique } from './aide'

/**
 * Un invariant, joue sur tous les ecrans et toutes les largeurs : rien ne sort
 * de la fenetre.
 *
 * C'est la regression qui est passee deux fois. `tsc` compile un nom
 * d'equipement de soixante caracteres sans rien dire ; le build aussi. Seul un
 * navigateur voit que la fiche se met alors a defiler de gauche a droite.
 *
 * Le test est volontairement generique plutot que pointu : il ne connait pas la
 * cause, il constate le symptome et nomme les elements fautifs. Une mise en
 * page cassee par un ecran ajoute plus tard tombera donc ici, sans que
 * personne ait eu a y penser.
 */

const ECRANS = [
  { nom: 'tableau de bord', chemin: '/' },
  { nom: 'equipements', chemin: '/equipements' },
  { nom: 'elements de la maison', chemin: '/elements' },
  { nom: 'entretiens', chemin: '/entretiens' },
  { nom: 'lieux', chemin: '/lieux' },
  { nom: 'membres', chemin: '/membres' },
  { nom: 'prestataires', chemin: '/prestataires' },
  { nom: 'documents', chemin: '/documents' },
  { nom: 'parametres', chemin: '/parametres' },
] as const

for (const largeur of LARGEURS) {
  test.describe(`${largeur.nom} (${largeur.width} px)`, () => {
    test.use({ viewport: { width: largeur.width, height: largeur.height } })

    for (const ecran of ECRANS) {
      test(`${ecran.nom} ne deborde pas`, async ({ page }) => {
        await page.goto(ecran.chemin)
        // Les ecrans chargent leurs listes apres le premier rendu : attendre le
        // reseau evite de mesurer une page a moitie peinte.
        await page.waitForLoadState('networkidle')
        await aucunDebordementHorizontal(page)
      })
    }

    test('une fiche au nom long ne deborde pas', async ({ page, request }) => {
      // Le cas exact du defaut : un flex refuse de descendre sous la largeur de
      // son contenu, et le nom pousse toute la page.
      const fiche = await creerFiche(request, {
        nom: nomUnique('Chaudiere gaz a condensation de la buanderie du sous-sol nord'),
        entretiens: ['Entretien annuel par un professionnel qualifie'],
      })
      await page.goto(`/equipements/${fiche.id}`)
      await page.waitForLoadState('networkidle')
      await aucunDebordementHorizontal(page)
    })

    test('les quatre onglets d une fiche ne debordent pas', async ({ page, request }) => {
      const fiche = await creerFiche(request)
      await page.goto(`/equipements/${fiche.id}`)

      for (const onglet of ['Entretiens', 'Chronologie', 'Details', 'Documents']) {
        await page.getByRole('tab', { name: onglet }).click()
        await page.waitForLoadState('networkidle')
        await aucunDebordementHorizontal(page)
      }
    })

    test('un nom sans espace ou se couper ne deborde pas', async ({ page, request }) => {
      // Une reference de modele saisie comme nom : aucun espace, donc aucun
      // endroit ou le texte peut revenir a la ligne tout seul.
      const fiche = await creerFiche(request, {
        nom: nomUnique('REF-XKZ9930012345678901234567890ABCDEFGH'),
      })
      await page.goto(`/equipements/${fiche.id}`)
      await page.waitForLoadState('networkidle')
      await aucunDebordementHorizontal(page)
    })
  })
}

test.describe('Le piege du chemin de base', () => {
  test("l'application se peint, et ne reste pas blanche", async ({ page }) => {
    // Home Assistant sert l'add-on sous un prefixe d'ingress inconnu a la
    // construction. C'est la cause de la quasi-totalite des add-ons qui
    // affichent une page blanche, et trois mecanismes doivent rester d'accord
    // pour l'eviter (voir docs/ARCHITECTURE.md section 4). La CI verifie deja
    // le fichier construit ; seul un navigateur verifie que React a bien
    // demarre derriere.
    const echecs: string[] = []
    page.on('requestfailed', (requete) => echecs.push(requete.url()))
    page.on('console', (message) => {
      if (message.type() === 'error') echecs.push(`console: ${message.text()}`)
    })

    await page.goto('/equipements')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { name: 'Équipements' })).toBeVisible()
    expect(echecs, 'des ressources ou des scripts ont echoue').toEqual([])
  })
})
