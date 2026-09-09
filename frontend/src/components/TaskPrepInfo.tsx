import type { Task } from '../api/types'

export default function TaskPrepInfo({ task }: { task: Task }) {
  return (
    <>
      {task.replacement_parts.length > 0 && (
        <p className="task__prep">
          Piece{task.replacement_parts.length > 1 ? 's' : ''} a remplacer :{' '}
          {task.replacement_parts.map((part, index) => (
            <span key={part.id}>
              {index > 0 && ', '}
              {part.name}
              {part.source && (
                <>
                  {' ('}
                  {/^https?:\/\//.test(part.source) ? (
                    <a href={part.source} target="_blank" rel="noreferrer">
                      lien d'achat
                    </a>
                  ) : (
                    part.source
                  )}
                  {')'}
                </>
              )}
            </span>
          ))}
        </p>
      )}
      {task.assignee_name && <p className="muted">Assigne a : {task.assignee_name}</p>}
      {task.preparation_notes && <p className="muted">A prevoir : {task.preparation_notes}</p>}
      {task.notes && <p className="muted">Notes : {task.notes}</p>}
    </>
  )
}
