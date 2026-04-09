import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false, // Вимкнути sourcemaps в production для безпеки
    minify: 'esbuild', // Швидша мініфікація з esbuild
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          axios: ['axios'],
          i18n: ['i18next', 'react-i18next'],
        },
      },
    },
    // Видаляємо console.log в production
    esbuild: {
      drop: ['console', 'debugger'],
    },
  },
  server: {
    port: 5173,
    host: true, // Доступ ззовні для Docker
  },
  preview: {
    port: 4173,
    host: true,
  },
})
