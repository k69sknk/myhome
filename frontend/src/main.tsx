import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import App from './App'
import { routerBasename } from './base-path'
import './index.css'

const container = document.getElementById('root')
if (!container) {
  throw new Error("L'element racine #root est introuvable dans index.html")
}

createRoot(container).render(
  <StrictMode>
    <BrowserRouter basename={routerBasename()}>
      <App />
    </BrowserRouter>
  </StrictMode>,
)
