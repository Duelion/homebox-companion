/**
 * Markdown rendering utility using the unified ecosystem.
 * Supports GFM (tables, task lists, strikethrough) with sanitization.
 */
import { unified } from 'unified';
import remarkParse from 'remark-parse';
import remarkGfm from 'remark-gfm';
import remarkRehype from 'remark-rehype';
import rehypeSanitize from 'rehype-sanitize';
import rehypeExternalLinks from 'rehype-external-links';
import rehypeStringify from 'rehype-stringify';

// Pipeline order matters for security:
// 1. Sanitize first - removes malicious HTML before any attribute injection
// 2. Add external link attributes AFTER sanitization - these safe attributes
//    bypass the sanitizer entirely since it already ran
const processor = unified()
	.use(remarkParse)
	.use(remarkGfm)
	.use(remarkRehype)
	.use(rehypeSanitize)
	.use(rehypeExternalLinks, { target: '_blank', rel: ['noopener', 'noreferrer'] })
	.use(rehypeStringify);

/**
 * Render markdown to sanitized HTML.
 * Uses synchronous processing for reactive $derived compatibility.
 */
export function renderMarkdown(md: string): string {
	return processor.processSync(md).toString();
}
