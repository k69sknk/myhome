import { useEffect, type ReactNode } from 'react'

/** Boîte modale minimale : le didacticiel doit pouvoir ouvrir une fiche complète
 *  sans quitter la page, sinon on perdrait les cases cochées et les fréquences
 *  déjà ajustées. */
export default function Modal({
  title,
  onClose,
  children,
}: {
  title: string
  onClose: () => void
  children: ReactNode
}) {
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    // Sans cela le recapitulatif defile derriere la boite, ce qui est
    // particulierement desagreable sur telephone.
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = previous
    }
  }, [onClose])

  return (
    <div className="modal" role="dialog" aria-modal="true" aria-label={title}>
      <button type="button" className="modal__backdrop" aria-label="Fermer" onClick={onClose} />
      <div className="modal__panel">
        <div className="modal__header">
          <h2 className="card__title">{title}</h2>
          <button type="button" className="btn btn--small" onClick={onClose}>
            Fermer
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}
