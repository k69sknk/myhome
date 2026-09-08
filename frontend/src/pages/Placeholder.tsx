interface PlaceholderProps {
  title: string
  description: string
  reference: string
}

/**
 * Ecran d'attente des fonctionnalites pas encore livrees.
 */
export default function Placeholder({ title, description, reference }: PlaceholderProps) {
  return (
    <section className="page">
      <h1 className="page__title">{title}</h1>
      <p className="page__lead">{description}</p>
      <div className="notice">
        <strong>Pas encore dans cette version.</strong>
        <p>
          Le modele de donnees est deja en place. Cette section arrivera dans un prochain
          morceau.
        </p>
        <p className="notice__ref">{reference}</p>
      </div>
    </section>
  )
}
