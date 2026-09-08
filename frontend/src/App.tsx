import { Navigate, Route, Routes } from 'react-router-dom'

import Layout from './components/Layout'
import Placeholder from './pages/Placeholder'
import Dashboard from './pages/Dashboard'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route
          path="/equipements/*"
          element={
            <Placeholder
              title="Equipements"
              description="Fiches des equipements et des elements de construction : marque, modele, numero de serie, localisation, garantie, documents et historique."
              reference="Cahier des charges, sections 6 a 8"
            />
          }
        />
        <Route
          path="/entretiens/*"
          element={
            <Placeholder
              title="Entretiens"
              description="Taches recurrentes, validation d'un entretien realise et planification de la prochaine echeance."
              reference="Cahier des charges, sections 9 et 10"
            />
          }
        />
        <Route
          path="/lieux/*"
          element={
            <Placeholder
              title="Lieux"
              description="Arborescence de la maison : etages, pieces, zones et exterieur."
              reference="Cahier des charges, section 5"
            />
          }
        />
        <Route
          path="/documents/*"
          element={
            <Placeholder
              title="Documents"
              description="Factures, notices, certificats et garanties, en fichier local, en lien externe ou en simple reference."
              reference="Cahier des charges, sections 13 et 14"
            />
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
