import { api } from '../api/client'
import type { Trade } from '../api/types'
import Field from './Field'

/** Le metier qui n'en est pas un : le choix de ne pas repondre. */
export const OTHER_SLUG = 'autre'

/**
 * Le slug de metier a enregistrer sur la fiche.
 *
 * Si l'utilisateur a precise un metier que la liste ignore, celui-ci la rejoint
 * avant d'etre pose sur la fiche — ou retrouve celui qui existe deja, parce que
 * « Vitrier » saisi sur deux fiches doit rester un seul metier.
 */
export async function resolveTrade(slug: string | null, other: string): Promise<string | null> {
  if (slug !== OTHER_SLUG || other.trim() === '') return slug
  const trade = await api.createTrade(other.trim())
  return trade.slug
}

/**
 * Le metier d'un prestataire : la liste, et une porte pour ce qu'elle ignore.
 *
 * La liste integree est volontairement courte — elle sert a regrouper, pas a
 * decrire un annuaire professionnel. Mais courte veut dire incomplete : un
 * vitrier, un cuisiniste, un antenniste n'y sont pas, et les ranger sous
 * « Autre » revient a oublier qui on appelle. Choisir « Autre » ouvre donc un
 * champ libre, et le metier saisi devient un metier comme les autres.
 */
export default function TradeSelect({
  trades,
  value,
  other,
  onChange,
  onOther,
}: {
  trades: Trade[]
  value: string | null
  other: string
  onChange: (slug: string | null) => void
  onOther: (label: string) => void
}) {
  // Le conteneur s'efface de la grille (`display: contents`) : le menu garde sa
  // case, et la precision prend une ligne entiere juste en dessous. Sans cela
  // elle se retrouverait sous le champ voisin, loin du menu qu'elle complete, et
  // sa hauteur decalerait toute la ligne.
  return (
    <div className="trade-select">
      <Field label="Metier">
        <select
          value={value ?? ''}
          onChange={(event) => {
            onChange(event.target.value || null)
            if (event.target.value !== OTHER_SLUG) onOther('')
          }}
        >
          <option value="">Non precise</option>
          {trades.map((trade) => (
            <option key={trade.slug} value={trade.slug}>
              {trade.label}
            </option>
          ))}
        </select>
      </Field>
      {value === OTHER_SLUG && (
        <div className="trade-select__other">
          <Field
            label="Lequel ? (facultatif)"
            hint="Il rejoindra la liste des métiers, pour vos prochaines fiches."
          >
            <input
              value={other}
              onChange={(event) => onOther(event.target.value)}
              placeholder="Vitrier, cuisiniste, antenniste..."
            />
          </Field>
        </div>
      )}
    </div>
  )
}
