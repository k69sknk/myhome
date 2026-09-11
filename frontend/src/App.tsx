import { Navigate, Route, Routes } from 'react-router-dom'

import Layout from './components/Layout'
import { ToastProvider } from './components/Toast'
import AssetDetail from './pages/AssetDetail'
import AssetNew from './pages/AssetNew'
import Assets from './pages/Assets'
import Dashboard from './pages/Dashboard'
import Documents from './pages/Documents'
import HouseElementNew from './pages/HouseElementNew'
import HouseElements from './pages/HouseElements'
import Locations from './pages/Locations'
import Members from './pages/Members'
import Onboarding from './pages/Onboarding'
import Providers from './pages/Providers'
import Settings from './pages/Settings'
import Tasks from './pages/Tasks'

export default function App() {
  return (
    <ToastProvider>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/demarrage" element={<Onboarding />} />
          <Route path="/equipements" element={<Assets />} />
          <Route path="/equipements/nouveau" element={<AssetNew />} />
          <Route path="/equipements/:id" element={<AssetDetail />} />
          <Route path="/elements" element={<HouseElements />} />
          <Route path="/elements/nouveau" element={<HouseElementNew />} />
          <Route path="/elements/:id" element={<AssetDetail />} />
          <Route path="/entretiens" element={<Tasks />} />
          <Route path="/lieux" element={<Locations />} />
          <Route path="/membres" element={<Members />} />
          <Route path="/prestataires" element={<Providers />} />
          <Route path="/parametres" element={<Settings />} />
          <Route path="/documents" element={<Documents />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </ToastProvider>
  )
}
