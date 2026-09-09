/**
 * Icone (emoji) representant une categorie d'equipement, indexee par `category.slug`.
 * Les categories creees a la volee (CategorySelect) n'ont pas de slug connu : repli
 * generique. Pas de lib d'icones ici, volontairement : le frontend n'en depend d'aucune.
 */
const CATEGORY_ICONS: Record<string, string> = {
  heating: '🔥',
  ventilation: '🌀',
  water: '💧',
  electricity: '⚡',
  outdoor: '🌳',
  appliances: '🔌',
  structure: '🏠',

  heat_pump: '♨️',
  boiler: '🔥',
  radiator: '♨️',
  stove: '🔥',
  air_conditioning: '❄️',

  vmc: '🌀',
  extractor: '🌬️',
  air_purifier: '🌬️',

  water_heater: '🚿',
  pump: '💧',
  water_softener: '💧',
  filtration: '🚰',

  electrical_panel: '⚡',
  solar_inverter: '☀️',
  battery: '🔋',
  generator: '⚙️',

  gate: '🚪',
  pool: '🏊',
  spa: '🛁',
  robot_mower: '🤖',
  irrigation: '💦',

  vacuum: '🧹',
  washing_machine: '🧺',
  dishwasher: '🍽️',
  fridge: '🧊',
  oven: '🔥',
}

const DEFAULT_ICON = '📦'

export function categoryIcon(slug: string | null | undefined): string {
  if (!slug) return DEFAULT_ICON
  return CATEGORY_ICONS[slug] ?? DEFAULT_ICON
}
