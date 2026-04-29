const BUFFER_SIZE = 50;
const INCOMPLETE_CODE_BLOCK_REGEX = /```[a-z]*\n([\s\S]*?)?(?!```)$/;
const INCOMPLETE_INLINE_CODE = /`[^`]*$/;

export function shouldBufferUpdate(content: string, buffered: string): boolean {
  const combined = buffered + content;
  return combined.length >= BUFFER_SIZE;
}

export function hasIncompleteMarkdown(text: string): boolean {
  return (
    INCOMPLETE_CODE_BLOCK_REGEX.test(text) ||
    INCOMPLETE_INLINE_CODE.test(text)
  );
}

export function preprocessCitations(text: string): string {
  return text.replace(/\{\{cite:(\d+)\}\}/g, "[$1]");
}

export function postprocessCitations(html: string, citations: any[]): string {
  return html.replace(
    /\[(\d+)\]/g,
    (match, num) => `__CITATION_${num}__`
  );
}
