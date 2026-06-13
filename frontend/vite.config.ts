import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';
import { visualizer } from 'rollup-plugin-visualizer';

const isAnalyze = process.env.ANALYZE === 'true';

export default defineConfig({
	plugins: [
		sveltekit(),
		// Bundle analyzer - generates stats.html when ANALYZE=true
		isAnalyze &&
		visualizer({
			filename: 'stats.html',
			open: false,
			gzipSize: true,
			brotliSize: true,
		}),
	].filter(Boolean),
	server: {
		proxy: {
			'/api': {
				target: 'http://localhost:8000',
				changeOrigin: true,
			},
		},
	},
});
