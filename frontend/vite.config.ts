import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { federation } from '@module-federation/vite'

export default defineConfig({
  base: './',
  plugins: [vue(), federation({
    name: 'MppgdonTest', filename: 'assets/remoteEntry.js', dts: false,
    exposes: {'./Page': './src/Page.vue', './AppPage': './src/AppPage.vue', './Config': './src/Config.vue'},
    shared: {vue: {requiredVersion: false, import: false, singleton: true}},
  })],
  build: {
    outDir: '../plugins.v3/mppgdontest/dist', emptyOutDir: true,
    target: 'esnext', cssCodeSplit: true, minify: true,
  },
})
