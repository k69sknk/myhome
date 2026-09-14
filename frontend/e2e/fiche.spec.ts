import { expect, test } from '@playwright/test'

import { LARGEURS, creerFiche, nomUnique, tientDansLaFenetre } from './aide'

/**
 * Les deux sorties d'une fiche : retirer, qui se defait, et supprimer, qui ne
 * se defait pas.
 *
 * Ces tests existent parce que les deux actions ont ete mal placees deux fois
 * de suite : enterrees au bas d'un onglet ou personne ne les trouvait, puis
 * remontees dans un menu qui sortait de l'ecran sur telephone. Le typage ne
 * voyait ni l'un ni l'autre.
 */

test.describe('Menu de sortie de la fiche', () => {
  test("s'ouvre depuis l'onglet d'accueil, sans changer d'onglet", async ({ page, request }) => {
    const fiche = await creerFiche(request, { entretiens: ['Entretien annuel'] })
    await page.goto(`/equipements/${fiche.id}`)

    // L'onglet actif au chargement est « Entretiens » : c'est de la que
    // l'utilisateur doit pouvoir sortir la fiche.
    await expect(page.getByRole('tab', { name: 'Entretiens' })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    await page.getByRole('button', { name: 'Autres actions' }).click()

    await expect(page.getByRole('menuitem', { name: /Retirer de la maison/ })).toBeVisible()
    await expect(page.getByRole('menuitem', { name: /Supprimer définitivement/ })).toBeVisible()
  })

  for (const largeur of LARGEURS) {
    test(`tient dans la fenetre — ${largeur.nom} (${largeur.width} px)`, async ({
      page,
      request,
    }) => {
      // Un nom long decale le moment ou l'en-tete passe a la ligne, donc la
      // position du bouton : c'est ce cas qui avait fait sortir le panneau de
      // 106 px hors de l'ecran.
      const fiche = await creerFiche(request, {
        nom: nomUnique('Chaudiere gaz a condensation de la buanderie du sous-sol'),
      })
      await page.setViewportSize({ width: largeur.width, height: largeur.height })
      await page.goto(`/equipements/${fiche.id}`)
      await page.getByRole('button', { name: 'Autres actions' }).click()

      await expect(page.getByRole('menu')).toBeVisible()
      await tientDansLaFenetre(page, '.menu__panel')
    })
  }

  test('se ferme a Echap et au clic exterieur', async ({ page, request }) => {
    const fiche = await creerFiche(request)
    await page.goto(`/equipements/${fiche.id}`)
    const bouton = page.getByRole('button', { name: 'Autres actions' })

    await bouton.click()
    await expect(page.getByRole('menu')).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.getByRole('menu')).toBeHidden()

    await bouton.click()
    await expect(page.getByRole('menu')).toBeVisible()
    await page.mouse.click(5, 500)
    await expect(page.getByRole('menu')).toBeHidden()
  })
})

test.describe('Retirer une fiche', () => {
  test('sort les entretiens du planning, garde la fiche, et se defait', async ({
    page,
    request,
  }) => {
    const fiche = await creerFiche(request, { entretiens: [nomUnique('Entretien annuel')] })
    await page.goto(`/equipements/${fiche.id}`)

    await page.getByRole('button', { name: 'Autres actions' }).click()
    await page.getByRole('menuitem', { name: /Retirer de la maison/ }).click()

    // Sans ce badge, rien ne dirait pourquoi les entretiens ont disparu.
    await expect(page.getByText('Retiré', { exact: true })).toBeVisible()

    const planning = await request.get('/api/tasks')
    const entretiens = (await planning.json()) as { asset_id: number | null }[]
    expect(entretiens.filter((tache) => tache.asset_id === fiche.id)).toEqual([])

    // Reversible : c'est ce qui justifie que l'action soit immediate.
    await page.getByRole('button', { name: 'Autres actions' }).click()
    await page.getByRole('menuitem', { name: /Remettre en service/ }).click()
    await expect(page.getByText('Retiré', { exact: true })).toBeHidden()
  })
})

test.describe('Supprimer une fiche', () => {
  test('annonce ce qui va disparaitre avant de le faire', async ({ page, request }) => {
    const fiche = await creerFiche(request, {
      entretiens: [nomUnique('Entretien annuel'), nomUnique('Nettoyage')],
      documents: [nomUnique('Notice')],
    })
    await page.goto(`/equipements/${fiche.id}`)

    await page.getByRole('button', { name: 'Autres actions' }).click()
    await page.getByRole('menuitem', { name: /Supprimer définitivement/ }).click()

    const boite = page.getByRole('dialog')
    await expect(boite).toContainText('2 entretiens et leur historique')
    await expect(boite).toContainText('1 document')
    await expect(boite).toContainText('ne peut pas être annulée')
    // La boite propose le retrait, parce que c'est presque toujours ce qu'on
    // voulait vraiment.
    await expect(boite).toContainText('Retirer de la maison')
  })

  test("Echap referme sans rien supprimer", async ({ page, request }) => {
    const fiche = await creerFiche(request)
    await page.goto(`/equipements/${fiche.id}`)

    await page.getByRole('button', { name: 'Autres actions' }).click()
    await page.getByRole('menuitem', { name: /Supprimer définitivement/ }).click()
    await expect(page.getByRole('dialog')).toBeVisible()
    await page.keyboard.press('Escape')

    await expect(page.getByRole('dialog')).toBeHidden()
    expect((await request.get(`/api/assets/${fiche.id}`)).status()).toBe(200)
  })

  test('emporte la fiche et renvoie a la liste', async ({ page, request }) => {
    const fiche = await creerFiche(request, { entretiens: [nomUnique('Entretien annuel')] })
    await page.goto(`/equipements/${fiche.id}`)

    await page.getByRole('button', { name: 'Autres actions' }).click()
    await page.getByRole('menuitem', { name: /Supprimer définitivement/ }).click()
    await page.getByRole('button', { name: 'Oui, tout supprimer' }).click()

    // La redirection suit la reponse du serveur : attendre la liste plutot que
    // l'URL evite de mesurer l'instant ou le routeur n'a pas encore rendu.
    await expect(page.getByRole('heading', { name: 'Équipements' })).toBeVisible()
    await expect(page).toHaveURL(/\/equipements$/)
    expect((await request.get(`/api/assets/${fiche.id}`)).status()).toBe(404)
  })

  test('la boite tient dans la fenetre sur telephone', async ({ page, request }) => {
    const fiche = await creerFiche(request)
    await page.setViewportSize({ width: 320, height: 800 })
    await page.goto(`/equipements/${fiche.id}`)

    await page.getByRole('button', { name: 'Autres actions' }).click()
    await page.getByRole('menuitem', { name: /Supprimer définitivement/ }).click()

    await tientDansLaFenetre(page, '.modal__panel')
  })
})
