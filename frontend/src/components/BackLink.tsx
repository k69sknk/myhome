import { Link } from 'react-router-dom'

export default function BackLink({ to, label }: { to: string; label: string }) {
  return (
    <p className="page__crumb">
      <Link to={to}>&larr; {label}</Link>
    </p>
  )
}
