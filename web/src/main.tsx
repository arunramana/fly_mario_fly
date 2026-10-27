import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, HashRouter } from 'react-router-dom'
import '@fontsource/press-start-2p/latin-400.css'
import '@fontsource/pixelify-sans/latin-400.css'
import '@fontsource/pixelify-sans/latin-600.css'
import './theme.css'
import App from './App'
import { DraftProvider } from './DraftProvider'
import { FEATURES } from './features'

// GitHub Pages cannot rewrite /run/abc to index.html, so the hosted copy keeps its route after a # (it needs no server rules).
const Router = FEATURES.lite ? HashRouter : BrowserRouter
const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 30_000 } } })

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <Router>
        <DraftProvider>
          <App />
        </DraftProvider>
      </Router>
    </QueryClientProvider>
  </StrictMode>,
)
