import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false, // Вимкнути sourcemaps в production для безпеки
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/react-dom') || id.includes('node_modules/react/') || id.includes('node_modules/react-router-dom')) {
            return 'vendor';
          }
          if (id.includes('node_modules/axios')) {
            return 'axios';
          }
          if (id.includes('node_modules/i18next') || id.includes('node_modules/react-i18next')) {
            return 'i18n';
          }
        },
      },
    },
    // Видаляємо console.log в production
    oxc: {
      transform: {
        define: {
          'console.log': 'void 0',
          'console.debug': 'void 0',
        },
      },
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
