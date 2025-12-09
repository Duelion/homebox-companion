import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		proxy: {
			'/api': {
				target: 'http://localhost:8000',
				changeOrigin: true,
			},
		},
	},
	build: {
		// Ensure assets are properly hashed for cache busting
		rollupOptions: {
			output: {
				// Add hash to filenames for cache busting
				entryFileNames: '_app/immutable/entry/[name]-[hash].js',
				chunkFileNames: '_app/immutable/chunks/[name]-[hash].js',
				assetFileNames: '_app/immutable/assets/[name]-[hash].[ext]'
			}
		}
	}
});
