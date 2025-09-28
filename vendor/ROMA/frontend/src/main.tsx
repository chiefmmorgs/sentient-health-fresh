import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'
import { webSocketService } from './services/websocketService'

// Initialize WebSocket connection before rendering
console.log('🚀 Initializing WebSocket connection at app startup')
webSocketService.connect()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
) 