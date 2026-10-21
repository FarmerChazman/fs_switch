import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  base: '/assets/fs_switch/console/',
  build: {
    outDir: '../fs_switch/public/console',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: 'assets/app.js',
        chunkFileNames: 'assets/[name].js',
        assetFileNames: (assetInfo) =>
          assetInfo.name?.endsWith('.css') ? 'assets/app.css' : 'assets/[name][extname]',
      },
    },
  },
  server: {
    port: 5174,
    proxy: {
      '/api': 'http://fs-switch.localhost:8000',
      '/assets': 'http://fs-switch.localhost:8000',
    },
  },
})
