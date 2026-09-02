import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  // Relative base so one build works at "/" or behind any reverse-proxy prefix.
  base: './',
  plugins: [vue()],
  build: {
    // maplibre-gl alone is ~1.07 MB minified and cannot be split further. It
    // gets its own chunk (below) and is only fetched when a map is shown, so
    // the size warning is raised just above it to flag real regressions.
    chunkSizeWarningLimit: 1200,
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            { name: 'maplibre', test: /node_modules[\\/](maplibre-gl|@nazka)[\\/]/ },
            { name: 'vue', test: /node_modules[\\/]@?vue[\\/]/ },
          ],
        },
      },
    },
  },
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
