import type { TaskStatus } from '../api/types'
import { statusLabel } from '../lib/format'

export default function StatusBadge({ status }: { status: TaskStatus }) {
  return <span className={`badge badge--${status}`}>{statusLabel(status)}</span>
}
