import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';
import { visualizer } from 'rollup-plugin-visualizer';

const isAnalyze = process.env.ANALYZE === 'true';

export default defineConfig(({ mode }) => ({
	plugins: [
		tailwindcss(),
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
	// Mocked browser tests must never reach a real backend, including during page teardown.
	preview: mode === 'browser-test' ? { proxy: {} } : undefined,
	server: {
		proxy: {
			'/api': {
				target: 'http://localhost:8000',
				changeOrigin: true,
			},
		},
	},
}));
