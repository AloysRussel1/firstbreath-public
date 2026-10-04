import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
// shared/ (statuts et seuil de question) est lu directement : le serveur de développement doit pouvoir le servir.
export default defineConfig({
  plugins: [react()],
  server: { fs: { allow: ['.', '../shared'] } },
})
