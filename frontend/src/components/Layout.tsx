import { NavLink, Outlet } from 'react-router-dom'

const NAV_ITEMS = [
  { to: '/', label: 'Tableau de bord', end: true },
  { to: '/equipements', label: 'Équipements', end: false },
  { to: '/elements', label: 'Éléments de la maison', end: false },
  { to: '/entretiens', label: 'Entretiens', end: false },
  { to: '/lieux', label: 'Lieux', end: false },
  { to: '/membres', label: 'Membres', end: false },
  { to: '/documents', label: 'Documents', end: false },
  { to: '/parametres', label: 'Paramètres', end: false },
]

export default function Layout() {
  return (
    <div className="app">
      <header className="app__header">
        <span className="app__brand">MaBarak</span>
        <nav className="app__nav">
          {NAV_ITEMS.map(({ to, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                isActive ? 'app__nav-link app__nav-link--active' : 'app__nav-link'
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>
      </header>

      <main className="app__main">
        <Outlet />
      </main>
    </div>
  )
}
