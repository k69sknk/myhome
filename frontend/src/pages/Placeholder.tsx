interface PlaceholderProps {
  title: string
  description: string
  reference: string
}

/**
 * Ecran d'attente des fonctionnalites de la V1. Le cahier des charges impose de
 * valider l'architecture des donnees avant d'ecrire la moindre logique metier.
 */
export default function Placeholder({ title, description, reference }: PlaceholderProps) {
  return (
    <section className="page">
      <h1 className="page__title">{title}</h1>
      <p className="page__lead">{description}</p>
      <div className="notice">
        <strong>Pas encore implemente.</strong>
        <p>
          Cette section fait partie de la V1. Le modele de donnees correspondant est fige et
          documente, l'implementation vient apres sa validation.
        </p>
        <p className="notice__ref">{reference}</p>
      </div>
    </section>
  )
}
