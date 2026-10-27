import assert from "node:assert/strict";
import { test } from "node:test";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import { build } from "esbuild";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

async function bundled(path) {
  const built = await build({ entryPoints: [path], bundle: true, format: "cjs", platform: "node", external: ["react", "react/jsx-runtime"], write: false });
  const module = { exports: {} };
  runInNewContext(built.outputFiles[0].text, { module, exports: module.exports, require: createRequire(import.meta.url), URL, console, process, queueMicrotask, setTimeout, clearTimeout, performance });
  return module.exports;
}
const { emptySelection, taskResources, taskPrompt, taskCopy } = await bundled("src/lib/quick-tasks.ts");
const { TaskSetup } = await bundled("src/components/agents/task-setup.tsx");

test("each quick task maps to its own resources", () => {
  assert.deepEqual(Array.from(taskResources.brand), ["knowledge_bases"]);
  assert.ok(taskResources.keywords.includes("keyword_libraries"));
  for (const task of ["content", "publish", "media"]) assert.ok(taskResources[task].includes("image_libraries"));
  assert.ok(taskResources.analysis.includes("knowledge_bases"));
  const a = emptySelection(), b = emptySelection();
  a.keywords.push({ item_id: 7 });
  assert.equal(b.keywords.length, 0);
});

test("each task has a distinct workflow description, section title and action", () => {
  const ids = ["brand", "keywords", "content", "publish", "media", "analysis"];
  assert.equal(new Set(ids.map((id) => taskCopy[id].summary)).size, ids.length);
  assert.equal(new Set(ids.map((id) => taskCopy[id].fieldsTitle)).size, ids.length);
  assert.equal(new Set(ids.map((id) => taskCopy[id].action)).size, ids.length);
});

test("task draft retains chosen resources and supplied requirements with a review step", () => {
  const prompt = taskPrompt("创作初稿", { 品牌名称: " 测试品牌 ", 预算: "" }, ["知识库 · 品牌资料", "关键词 · 产品词"]);
  assert.ok(prompt.includes("品牌名称：测试品牌"));
  assert.ok(prompt.includes("知识库 · 品牌资料；关键词 · 产品词"));
  assert.ok(!prompt.includes("预算："));
  assert.ok(prompt.includes("等待用户明确确认"));
  assert.ok(taskPrompt("撰写内容", {}, [], "品牌内容框架").includes("采用 GEOFlow 提示词模板：品牌内容框架"));
});

test("all six task dialogs expose matching requirements and prevent applying while loading", () => {
  const cases = { brand: "品牌名称", keywords: "拓展方向", content: "创作主题", publish: "发布主题", media: "投放渠道", analysis: "分析主题" };
  for (const [id, field] of Object.entries(cases)) {
    const html = renderToStaticMarkup(createElement(TaskSetup, { task: { id, label: "任务", prompt: "任务提示词" }, availableSkills: [{ name: "research", display_name: "研究", description: "检索信息" }], onClose() {}, onApply() {} }));
    assert.ok(html.includes(field), id);
    assert.ok(html.includes('role="status"'), id);
    assert.ok(html.includes("提示词模板"), id);
    assert.ok(html.includes("任务提示词"), id);
    assert.ok(html.includes("研究"), id);
    assert.match(html, /<button[^>]*disabled=""[^>]*>准备/);
    assert.ok(html.includes(taskCopy[id].summary));
    assert.ok(html.includes(taskCopy[id].action));
  }
});
