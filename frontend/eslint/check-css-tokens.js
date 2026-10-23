import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import { findCssTokenViolations } from './css-tokens.js';

async function check(directory) {
	for (const entry of await readdir(directory, { withFileTypes: true })) {
		const file = path.join(directory, entry.name);
		if (entry.isDirectory()) {
			await check(file);
		} else if (/\.(css|svelte)$/.test(file)) {
			const violations = findCssTokenViolations(await readFile(file, 'utf8'), {
				stylesheet: file.endsWith('.css'),
				theme: file === path.join('src', 'app.css'),
			});
			for (const { line, property } of violations) {
				console.error(`${file}:${line}: ${property} must reference a color token`);
				process.exitCode = 1;
			}
		}
	}
}

await check('src');
