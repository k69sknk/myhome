import type { APIRequestContext, Page } from '@playwright/test'
import { expect } from '@playwright/test'

/**
 * De quoi fabriquer l'etat d'une fiche sans passer par l'interface.
 *
 * Monter un decor en cliquant rendrait chaque test long et fragile : il
 * tomberait pour une raison sans rapport avec ce qu'il verifie. Les tests
 * posent donc leurs donnees par l'API, et ne cliquent que sur ce qu'ils
 * examinent.
 *
 * Les noms portent un suffixe unique : la campagne tourne en parallele sur une
 * base commune, et deux tests ne doivent pas se marcher dessus.
 */

let compteur = 0

export function nomUnique(base: string): string {
  compteur += 1
  return `${base} ${process.pid}-${compteur}`
}

export interface FicheCreee {
  id: number
  nom: string
}

export async function creerFiche(
  api: APIRequestContext,
  options: {
    nom?: string
    install_date?: string | null
    entretiens?: string[]
    documents?: string[]
  } = {},
): Promise<FicheCreee> {
  const nom = options.nom ?? nomUnique('Pompe a chaleur')
  const reponse = await api.post('/api/assets', {
    data: { name: nom, install_date: options.install_date ?? '2019-04-10' },
  })
  expect(reponse.ok(), await reponse.text()).toBeTruthy()
  const { id } = (await reponse.json()) as { id: number }

  for (const entretien of options.entretiens ?? []) {
    const cree = await api.post(`/api/assets/${id}/tasks`, {
      data: { name: entretien, recurrence_type: 'years', recurrence_interval: 1 },
    })
    expect(cree.ok(), await cree.text()).toBeTruthy()
  }

  for (const document of options.documents ?? []) {
    const joint = await api.post(`/api/assets/${id}/documents`, {
      multipart: {
        storage_mode: 'reference_note',
        doc_type: 'manual',
        name: document,
        reference_note: 'classeur bleu',
      },
    })
    expect(joint.ok(), await joint.text()).toBeTruthy()
  }

  return { id, nom }
}

/**
 * Rien ne doit deborder de la largeur de la fenetre.
 *
 * C'est l'invariant qu'aucun test de typage ne peut porter, et c'est celui qui
 * manquait : un nom d'appareil un peu long faisait defiler toute la fiche de
 * gauche a droite. La verification nomme les elements fautifs — sans cela, un
 * echec dirait seulement « la page defile » et laisserait chercher.
 */
export async function aucunDebordementHorizontal(page: Page): Promise<void> {
  const coupables = await page.evaluate(() => {
    const largeur = document.documentElement.clientWidth
    const defile = document.documentElement.scrollWidth > largeur
    if (!defile) return []
    return [...document.querySelectorAll<HTMLElement>('body *')]
      .filter((element) => {
        const boite = element.getBoundingClientRect()
        if (boite.width === 0) return false
        // Un conteneur qui defile en interne (rangee d'onglets, tableau large)
        // est legitime : c'est justement ce qui protege la page.
        const parentDefilant = element.parentElement
          ? getComputedStyle(element.parentElement).overflowX
          : 'visible'
        if (parentDefilant === 'auto' || parentDefilant === 'scroll') return false
        return boite.right > largeur + 1 || boite.left < -1
      })
      .slice(0, 5)
      .map((element) => {
        const boite = element.getBoundingClientRect()
        const classe = element.className?.toString?.() ?? ''
        return `${element.tagName.toLowerCase()}.${classe.slice(0, 40)} ` +
          `(${Math.round(boite.left)}..${Math.round(boite.right)}) ` +
          `« ${(element.textContent ?? '').trim().slice(0, 30)} »`
      })
  })
  expect(coupables, 'des elements sortent de la fenetre').toEqual([])
}

/**
 * La boite d'un element tient-elle entierement dans la fenetre ?
 *
 * Le message d'echec porte les trois nombres qui comptent : sans eux, un
 * « depasse a gauche » n'apprend pas de combien, et c'est la premiere question
 * qu'on se pose (le menu de la fiche sortait de 106 px).
 */
export async function tientDansLaFenetre(page: Page, selecteur: string): Promise<void> {
  const boite = await page.locator(selecteur).boundingBox()
  expect(boite, `${selecteur} est introuvable`).not.toBeNull()

  const fenetre = page.viewportSize()?.width ?? 0
  const gauche = Math.round(boite!.x)
  const droite = Math.round(boite!.x + boite!.width)
  const ou = `${selecteur} occupe ${gauche}..${droite} dans une fenetre de ${fenetre} px`

  expect(gauche, ou).toBeGreaterThanOrEqual(0)
  expect(droite, ou).toBeLessThanOrEqual(fenetre)
}

/** Les largeurs sur lesquelles la mise en page est verifiee. */
export const LARGEURS = [
  { nom: 'petit telephone', width: 320, height: 800 },
  { nom: 'telephone', width: 390, height: 844 },
  { nom: 'tablette', width: 768, height: 1024 },
  { nom: 'bureau', width: 1280, height: 800 },
] as const
