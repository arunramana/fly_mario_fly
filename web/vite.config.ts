import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// `vite build --mode lite` makes the hosted lite copy (see features.ts); VITE_BASE is where it is served from
// (a GitHub Pages project site: /fly_mario_fly/) and VITE_API_URL the lite server.
// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [react()],
  base: mode === 'lite' ? (process.env.VITE_BASE ?? './') : '/',
  define: mode === 'lite' ? { 'import.meta.env.VITE_LITE': JSON.stringify('1') } : {},
}))
