import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  // Relative base so one build works at "/" or behind any reverse-proxy prefix.
  base: './',
  plugins: [vue()],
  server: {
    proxy: {
      '/geo-dataset': 'http://127.0.0.1:8955',
      '/locations': 'http://127.0.0.1:8955',
      '/images': 'http://127.0.0.1:8955',
      '/evaluate': 'http://127.0.0.1:8955',
      '/world': 'http://127.0.0.1:8955',
      '/scaled': 'http://127.0.0.1:8955',
    },
  },
})
