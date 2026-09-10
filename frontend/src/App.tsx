import { Navigate, Route, Routes } from 'react-router-dom'

import Layout from './components/Layout'
import { ToastProvider } from './components/Toast'
import AssetDetail from './pages/AssetDetail'
import AssetNew from './pages/AssetNew'
import Assets from './pages/Assets'
import Dashboard from './pages/Dashboard'
import HouseElementNew from './pages/HouseElementNew'
import HouseElements from './pages/HouseElements'
import Locations from './pages/Locations'
import Members from './pages/Members'
import Placeholder from './pages/Placeholder'
import Settings from './pages/Settings'
import Tasks from './pages/Tasks'

export default function App() {
  return (
    <ToastProvider>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/equipements" element={<Assets />} />
          <Route path="/equipements/nouveau" element={<AssetNew />} />
          <Route path="/equipements/:id" element={<AssetDetail />} />
          <Route path="/elements" element={<HouseElements />} />
          <Route path="/elements/nouveau" element={<HouseElementNew />} />
          <Route path="/elements/:id" element={<AssetDetail />} />
          <Route path="/entretiens" element={<Tasks />} />
          <Route path="/lieux" element={<Locations />} />
          <Route path="/membres" element={<Members />} />
          <Route path="/parametres" element={<Settings />} />
          <Route
            path="/documents/*"
            element={
              <Placeholder
                title="Documents"
                description="Factures, notices et garanties arriveront dans un prochain morceau. Pour l'instant, les fiches d'equipement portent deja l'essentiel."
                reference="Cahier des charges, sections 13 et 14 — hors perimetre de cette version"
              />
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </ToastProvider>
  )
}
