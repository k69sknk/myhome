import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import type { TaskCalendarEntry, TaskStatus } from '../api/types'
import { formatDate } from '../lib/format'
import StatusBadge from './StatusBadge'

const WEEKDAYS = ['lun', 'mar', 'mer', 'jeu', 'ven', 'sam', 'dim']
const STATUS_PRIORITY: TaskStatus[] = ['overdue', 'due_soon', 'ok', 'unscheduled']

function toDayKey(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

interface DayCell {
  date: Date
  inMonth: boolean
  key: string
}

function buildMonthGrid(monthStart: Date): DayCell[] {
  const firstWeekday = (monthStart.getDay() + 6) % 7 // lundi = 0
  const gridStart = new Date(monthStart)
  gridStart.setDate(gridStart.getDate() - firstWeekday)

  const daysInMonth = new Date(
    monthStart.getFullYear(),
    monthStart.getMonth() + 1,
    0,
  ).getDate()
  const totalCells = Math.ceil((firstWeekday + daysInMonth) / 7) * 7

  return Array.from({ length: totalCells }, (_, index) => {
    const date = new Date(gridStart)
    date.setDate(date.getDate() + index)
    return { date, inMonth: date.getMonth() === monthStart.getMonth(), key: toDayKey(date) }
  })
}

export default function MiniCalendar({ tasks }: { tasks: TaskCalendarEntry[] }) {
  const today = useMemo(() => new Date(), [])
  const todayKey = toDayKey(today)
  const [viewDate, setViewDate] = useState(() => new Date(today.getFullYear(), today.getMonth(), 1))
  const [selectedDay, setSelectedDay] = useState<string | null>(
    tasks.some((task) => task.due_date === todayKey) ? todayKey : null,
  )

  const tasksByDay = useMemo(() => {
    const map = new Map<string, TaskCalendarEntry[]>()
    for (const task of tasks) {
      const bucket = map.get(task.due_date)
      if (bucket) bucket.push(task)
      else map.set(task.due_date, [task])
    }
    return map
  }, [tasks])

  const grid = useMemo(() => buildMonthGrid(viewDate), [viewDate])
  const monthLabel = viewDate.toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' })
  const selectedTasks = selectedDay ? (tasksByDay.get(selectedDay) ?? []) : []

  function changeMonth(delta: number) {
    setViewDate((current) => new Date(current.getFullYear(), current.getMonth() + delta, 1))
  }

  return (
    <div className="minical">
      <div className="minical__calendar">
        <div className="minical__header">
          <button
            type="button"
            className="btn btn--small"
            aria-label="Mois precedent"
            onClick={() => changeMonth(-1)}
          >
            ◀
          </button>
          <strong className="minical__month">{monthLabel}</strong>
          <button
            type="button"
            className="btn btn--small"
            aria-label="Mois suivant"
            onClick={() => changeMonth(1)}
          >
            ▶
          </button>
        </div>

        <div className="minical__grid">
          {WEEKDAYS.map((label) => (
            <div key={label} className="minical__weekday">
              {label}
            </div>
          ))}
          {grid.map((cell) => {
            const dayTasks = tasksByDay.get(cell.key) ?? []
            const statuses = STATUS_PRIORITY.filter((status) =>
              dayTasks.some((task) => task.status === status),
            )
            return (
              <button
                type="button"
                key={cell.key}
                className={[
                  'minical__day',
                  cell.inMonth ? '' : 'minical__day--outside',
                  cell.key === todayKey ? 'minical__day--today' : '',
                  cell.key === selectedDay ? 'minical__day--selected' : '',
                ]
                  .filter(Boolean)
                  .join(' ')}
                onClick={() => setSelectedDay(cell.key === selectedDay ? null : cell.key)}
              >
                <span>{cell.date.getDate()}</span>
                {statuses.length > 0 && (
                  <span className="minical__dots">
                    {statuses.map((status) => (
                      <span key={status} className={`minical__dot minical__dot--${status}`} />
                    ))}
                  </span>
                )}
              </button>
            )
          })}
        </div>
      </div>

      <div className="minical__day-detail">
        <strong className="minical__day-detail-title">
          {selectedDay ? formatDate(selectedDay) : 'Selectionnez un jour'}
        </strong>
        {selectedDay && selectedTasks.length === 0 && (
          <p className="muted">Aucun entretien ce jour-la.</p>
        )}
        {!selectedDay && <p className="muted">Cliquez sur un jour pour voir ses entretiens.</p>}
        {selectedTasks.length > 0 && (
          <ul className="rows">
            {selectedTasks.map((task) => (
              <li key={task.id}>
                <div className="rows__link">
                  <span>
                    {task.asset_id ? (
                      <Link to={`/equipements/${task.asset_id}`}>{task.name}</Link>
                    ) : (
                      task.name
                    )}
                    {task.asset_name && <span className="muted">{task.asset_name}</span>}
                  </span>
                  <StatusBadge status={task.status} />
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
