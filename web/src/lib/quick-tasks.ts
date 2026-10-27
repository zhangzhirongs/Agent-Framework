export type LibraryItem = { id: number | string; name?: string; title?: string };
export type GeoCatalog = Record<"knowledge_bases" | "title_libraries" | "keyword_libraries" | "image_libraries", LibraryItem[]> & { prompts?: { id: number | string; name: string; type?: string }[] };
export type ResourceKey = keyof GeoCatalog;
export type TaskId = "brand" | "keywords" | "content" | "publish" | "media" | "analysis";
export const taskCopy: Record<TaskId, { summary: string; resourceTitle: string; fieldsTitle: string; action: string }> = {
  brand: { summary: "从品牌资料中提炼定位、人群与差异化表达。", resourceTitle: "品牌知识依据", fieldsTitle: "品牌定位信息", action: "准备品牌方案" },
  keywords: { summary: "从关键词库选择词条，扩展搜索意图与长尾词。", resourceTitle: "关键词来源与目标词", fieldsTitle: "拓词方向", action: "准备关键词拓展" },
  content: { summary: "结合标题选题和素材，生成可编辑的内容初稿。", resourceTitle: "创作素材", fieldsTitle: "内容 brief", action: "准备内容初稿" },
  publish: { summary: "选择发布平台和账号，准备待审核的发布文案。", resourceTitle: "发布账号与素材", fieldsTitle: "发布信息", action: "准备发布文案" },
  media: { summary: "根据渠道、预算和目标人群整理投放计划。", resourceTitle: "投放参考素材", fieldsTitle: "投放 brief", action: "准备投放方案" },
  analysis: { summary: "基于 GEOFlow 资料和选定主题，整理有依据的分析。", resourceTitle: "分析数据范围", fieldsTitle: "分析条件", action: "准备 GEO 分析" },
};
export type KeywordChoice = { library_id: number; item_id: number; page: number; name: string };
export type TaskSelection = {
  knowledge_base_ids: number[]; title_library_ids: number[];
  keyword_library_ids: number[]; image_library_ids: number[];
  social_account_ids: number[]; keywords: KeywordChoice[];
};
export const emptySelection = (): TaskSelection => ({ knowledge_base_ids: [], title_library_ids: [], keyword_library_ids: [], image_library_ids: [], social_account_ids: [], keywords: [] });
export const resources: { key: ResourceKey; field: "knowledge_base_ids" | "title_library_ids" | "keyword_library_ids" | "image_library_ids"; label: string; limit: number }[] = [
  { key: "knowledge_bases", field: "knowledge_base_ids", label: "知识库", limit: 5 },
  { key: "keyword_libraries", field: "keyword_library_ids", label: "关键词库", limit: 3 },
  { key: "title_libraries", field: "title_library_ids", label: "标题库", limit: 3 },
  { key: "image_libraries", field: "image_library_ids", label: "图片库", limit: 3 },
];
export const taskResources: Record<TaskId, ResourceKey[]> = {
  brand: ["knowledge_bases"],
  keywords: ["keyword_libraries", "knowledge_bases"],
  content: ["title_libraries", "knowledge_bases", "keyword_libraries", "image_libraries"],
  publish: ["title_libraries", "knowledge_bases", "image_libraries"],
  media: ["knowledge_bases", "image_libraries"],
  analysis: ["knowledge_bases", "keyword_libraries", "title_libraries"],
};
export function taskPrompt(base: string, fields: Record<string, string>, labels: string[], template = "") {
  const details = Object.entries(fields).filter(([, value]) => value.trim()).map(([label, value]) => `${label}：${value.trim()}`);
  return [base, ...(template ? [`采用 GEOFlow 提示词模板：${template}`] : []), ...details, ...(labels.length ? [`所选资源：${labels.join("；")}`] : []), "请优先使用已选择的资源，不要重复询问已填写的信息。涉及发布或投放时先生成待审核方案，等待用户明确确认。"].join("\n");
}
