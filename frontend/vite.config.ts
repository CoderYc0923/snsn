import { svelte } from '@sveltejs/vite-plugin-svelte'
import { defineConfig } from 'vite'

// Backend defaults to :8001 in local dev (Windows often blocks :8000).
const apiTarget = process.env.VITE_API_PROXY || 'http://127.0.0.1:8001'

export default defineConfig({
  plugins: [svelte()],
  server: {
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
      },
    },
  },
})
