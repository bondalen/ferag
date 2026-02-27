import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
import { quasar, transformAssetUrls } from '@quasar/vite-plugin'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue({
      template: { transformAssetUrls },
    }),
    vueDevTools(),
    quasar({
      sassVariables: fileURLToPath(new URL('./src/quasar-variables.sass', import.meta.url)),
    }),
  ],
  base: '/ferag/',
  server: {
    proxy: {
      '/ferag/api': { target: 'http://localhost:47821', rewrite: (p) => p.replace('/ferag/api', '') },
      '/ferag/ws': { target: 'ws://localhost:47821', ws: true, rewrite: (p) => p.replace('/ferag/ws', '/ws') },
    },
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
})
