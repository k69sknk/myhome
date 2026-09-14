import { defineConfig, devices } from '@playwright/test'

/**
 * Tests de bout en bout, joues contre la VRAIE pile.
 *
 * Pas de serveur de developpement Vite ici : le backend sert lui-meme le build,
 * exactement comme dans l'add-on. C'est ce qui permet aux tests de couvrir ce
 * que le typage ne voit pas — la mise en page, les chemins relatifs, et le
 * comportement reel des ecrans a une largeur donnee.
 *
 * Deux regressions d'interface sont passees en deux versions parce que rien ne
 * regardait l'ecran : un menu qui sortait de la fenetre sur telephone, et un nom
 * d'appareil qui faisait defiler la fiche horizontalement. Ni `tsc` ni le build
 * ne pouvaient les voir. C'est le trou que ces tests comblent.
 */

// Un port qui ne croise ni le backend de developpement (8000), ni Vite (5173),
// ni l'ingress de l'add-on (8099).
const PORT = 8188
const BASE = `http://127.0.0.1:${PORT}`

export default defineConfig({
  testDir: './e2e',
  // Chaque test cree ses propres fiches, sous des noms qui lui sont propres :
  // ils peuvent donc tourner ensemble sur une meme base.
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI ? [['github'], ['list']] : [['list']],

  use: {
    baseURL: BASE,
    // Une capture et une trace seulement sur echec : c'est ce qu'on regarde en
    // premier quand un test de mise en page tombe, et voir l'ecran vaut mieux
    // que lire des coordonnees.
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },

  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],

  // `scripts/e2e-server.sh` construit le frontend, repart d'une base vide et
  // lance le backend dessus. Le meme chemin est emprunte en local et en CI :
  // un test qui passe ici passe la-bas.
  webServer: {
    command: 'bash ../scripts/e2e-server.sh',
    url: `${BASE}/api/health`,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
    stdout: 'pipe',
    stderr: 'pipe',
    env: { MABARAK_E2E_PORT: String(PORT) },
  },
})
