export type DocumentFormat = "markdown" | "json" | "text";

export function documentFormat(name: string, mediaType: string): DocumentFormat {
  if (/\.(md|markdown)$/i.test(name) || /^text\/(markdown|x-markdown)(;|$)/i.test(mediaType)) {
    return "markdown";
  }
  if (/\.json$/i.test(name) || /^application\/json(;|$)/i.test(mediaType)) return "json";
  return "text";
}
