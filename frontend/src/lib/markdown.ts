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

// Note: Order matters for security
// 1. Sanitize first to remove malicious HTML
// 2. Then add external link attributes (so they aren't stripped by sanitizer)
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
