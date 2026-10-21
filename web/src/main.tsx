import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import '@fontsource/press-start-2p/latin-400.css'
import '@fontsource/pixelify-sans/latin-400.css'
import '@fontsource/pixelify-sans/latin-600.css'
import './theme.css'
import App from './App'
import { DraftProvider } from './DraftProvider'

const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 30_000 } } })

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <DraftProvider>
          <App />
        </DraftProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
