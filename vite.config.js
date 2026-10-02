import glsl from 'vite-plugin-glsl';
import { defineConfig } from 'vite';
import { localPerformancePlugin } from './scripts/local-performance-plugin.js';

export default defineConfig({
  plugins: [glsl(), localPerformancePlugin()],
  build: { rollupOptions: { input: { main: 'index.html', sugarShellGlutton: 'works/sugar-shell-glutton/index.html' } } },
});
