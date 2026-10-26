import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { test } from "node:test";
import { runInNewContext } from "node:vm";
import { build } from "esbuild";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

const built = await build({
  entryPoints: ["src/components/document-content.tsx"],
  bundle: true,
  format: "cjs",
  platform: "node",
  external: ["react", "react/jsx-runtime"],
  write: false,
});
const module = { exports: {} };
runInNewContext(built.outputFiles[0].text, {
  module,
  exports: module.exports,
  require: createRequire(import.meta.url),
  URL,
  console,
});
const { DocumentContent, documentFormat } = module.exports;
const render = (text, format = "markdown", source = false) =>
  renderToStaticMarkup(createElement(DocumentContent, { text, format, source }));

test("document format detection handles Markdown extensions and MIME types", () => {
  assert.equal(documentFormat("REPORT.MD", "application/octet-stream"), "markdown");
  assert.equal(documentFormat("report.markdown", "text/plain"), "markdown");
  assert.equal(documentFormat("report", "text/markdown; charset=utf-8"), "markdown");
  assert.equal(documentFormat("report", "text/x-markdown"), "markdown");
  assert.equal(documentFormat("report.JSON", "text/plain"), "json");
  assert.equal(documentFormat("report.txt", "text/plain"), "text");
});

test("Markdown renders article headings, emphasis, lists, quotes and fenced code", () => {
  const html = render(`# 标题\n\n## 小节\n\n**加粗** *斜体* ~~删除~~\n\n> 引用\n\n1. 第一项\n2. 第二项\n\n- 项目\n\n\`行内代码\`\n\n\`\`\`js\nconst value = '<tag>';\n\`\`\``);
  for (const expected of [
    '<h1>标题</h1>', '<h2>小节</h2>', '<strong>加粗</strong>', '<em>斜体</em>',
    '<del>删除</del>', '<blockquote>', '<ol>', '<ul>', '<code>行内代码</code>',
    'class="language-js"', '&lt;tag&gt;',
  ]) assert.ok(html.includes(expected), expected);
});

test("GFM tables, tasks, autolinks, footnotes and images retain their formatting", () => {
  const html = render(`| 指标 | 数量 |\n| :--- | ---: |\n| 阅读 | 12 |\n\n- [x] 完成\n- [ ] 待办\n\nhttps://example.com\n\n![示意图](https://example.com/image.png)\n\n正文[^note]\n\n[^note]: 注释`);
  for (const expected of [
    'class="document-table-wrap"', '<table>', '<th style="text-align:right">数量</th>',
    'type="checkbox"', 'disabled=""', 'checked=""', 'href="https://example.com"',
    'target="_blank"', 'rel="noopener noreferrer"', 'alt="示意图"',
    'loading="lazy"', 'referrerPolicy="no-referrer"', 'data-footnotes="true"',
  ]) assert.ok(html.includes(expected), expected);
  assert.ok(!html.includes('node="'));
});

test("Markdown strips raw HTML and blocks script links and image handlers", () => {
  const html = render(`<script>alert('x')</script>\n\n<img src=x onerror="alert(1)">\n\n[危险](javascript:alert%281%29)\n\n![危险](javascript:alert%281%29)`);
  assert.ok(!html.includes("<script"));
  assert.ok(!html.includes("onerror"));
  assert.ok(!html.includes("javascript:"));
});

test("source, plain text, empty files and invalid JSON are readable without rendering markup", () => {
  assert.ok(render("# 原文\n\n<strong>标签</strong>", "markdown", true).includes("&lt;strong&gt;标签&lt;/strong&gt;"));
  assert.ok(!render("# 原文", "markdown", true).includes("<h1>"));
  assert.ok(render("<script>text</script>", "text").includes("&lt;script&gt;"));
  assert.ok(render("").includes("此文件内容为空"));
  assert.ok(render('{"value":1}', "json").includes('\n  &quot;value&quot;: 1\n'));
  assert.ok(render('{"value":', "json").includes('{&quot;value&quot;:'));
  assert.ok(render('{"value":1}', "json", true).includes('{&quot;value&quot;:1}'));
});
