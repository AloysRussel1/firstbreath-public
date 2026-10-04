import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/polices.css'
import './styles/theme.css'
import './styles/base.css'
import './styles/vitrine.css'
import './styles/application.css'
import './styles/conversation.css'
import './styles/dossiers.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
