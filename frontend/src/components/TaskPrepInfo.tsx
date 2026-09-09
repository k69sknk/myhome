import type { Task } from '../api/types'

export default function TaskPrepInfo({ task }: { task: Task }) {
  return (
    <>
      {task.needs_part_replacement && (
        <p className="task__prep">
          Piece a remplacer
          {task.replacement_part_name ? ` : ${task.replacement_part_name}` : ''}
          {task.replacement_part_source && (
            <>
              {' — '}
              {/^https?:\/\//.test(task.replacement_part_source) ? (
                <a href={task.replacement_part_source} target="_blank" rel="noreferrer">
                  lien d'achat
                </a>
              ) : (
                task.replacement_part_source
              )}
            </>
          )}
        </p>
      )}
      {task.preparation_notes && <p className="muted">A prevoir : {task.preparation_notes}</p>}
      {task.notes && <p className="muted">Notes : {task.notes}</p>}
    </>
  )
}
