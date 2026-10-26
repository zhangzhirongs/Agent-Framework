import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { DocumentFormat } from "../lib/document-format";
export { documentFormat } from "../lib/document-format";

export function DocumentContent({
  text,
  format,
  source = false,
}: {
  text: string;
  format: DocumentFormat;
  source?: boolean;
}) {
  if (!text) return <p className="document-status">此文件内容为空</p>;
  if (format === "markdown" && !source) {
    return (
      <div className="document-reader">
        <article className="document-prose">
          <Markdown
            remarkPlugins={[remarkGfm]}
            skipHtml
            components={{
              a: ({ node: _node, children, href, ...props }) => (
                <a {...props} href={href} target={href?.startsWith("#") ? undefined : "_blank"} rel="noopener noreferrer">{children}</a>
              ),
              img: ({ node: _node, src, alt, ...props }) => (
                src ? <img {...props} src={src} alt={alt} loading="lazy" decoding="async" referrerPolicy="no-referrer" /> : <span>{alt}</span>
              ),
              table: ({ node: _node, children, ...props }) => (
                <div className="document-table-wrap" tabIndex={0} role="region" aria-label="文档表格">
                  <table {...props}>{children}</table>
                </div>
              ),
            }}
          >
            {text}
          </Markdown>
        </article>
      </div>
    );
  }
  let value = text;
  if (format === "json" && !source) {
    try {
      value = JSON.stringify(JSON.parse(text), null, 2);
    } catch {
      // Preserve the original when a file is incomplete or not valid JSON.
    }
  }
  return <pre className="document-source"><code>{value}</code></pre>;
}
