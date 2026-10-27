import { useEffect, useRef, useState } from "react";
import { LoaderCircle, Search, X, ArrowRight, Library } from "lucide-react";
import { request } from "../../api";
import { Button } from "../motion/button/base";
import { Checkbox } from "../motion/checkbox";
import { emptySelection, resources, taskCopy, taskResources, taskPrompt, type GeoCatalog, type LibraryItem, type TaskId, type TaskSelection } from "../../lib/quick-tasks";
import type { Skill } from "../../api";

type Account = { id: number; account_name: string; platform: string; platform_name?: string; can_enqueue?: boolean };
type KeywordPage = { items: { id: number; keyword: string }[]; pagination?: { total_pages: number } };
const fieldsFor: Record<TaskId, string[]> = {
  brand: ["品牌名称", "目标客户", "核心优势"],
  keywords: ["拓展方向", "目标人群"],
  content: ["创作主题", "目标读者", "发布平台", "表达风格"],
  publish: ["发布主题", "发布目标"],
  media: ["投放渠道", "预算", "目标人群", "转化目标"],
  analysis: ["分析主题", "时间范围", "关注指标"],
};

export function TaskSetup({ task, availableSkills, initialSelection, initialFields, initialSkills, initialTemplate, initialPrompt, onClose, onApply }: {
  task: { id: TaskId; label: string; prompt: string }; onClose: () => void;
  initialSelection?: TaskSelection; initialFields?: Record<string, string>;
  availableSkills: Skill[]; initialSkills?: string[]; initialTemplate?: string; initialPrompt?: string;
  onApply: (prompt: string, selection: TaskSelection, labels: string[], catalog: GeoCatalog, fields: Record<string, string>, skills: string[], template: string, promptDraft: string) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [catalog, setCatalog] = useState<GeoCatalog | null>(null);
  const [selection, setSelection] = useState(initialSelection || emptySelection);
  const [fields, setFields] = useState<Record<string, string>>(initialFields || {});
  const [selectedSkills, setSelectedSkills] = useState<string[]>(initialSkills || []);
  const [template, setTemplate] = useState(initialTemplate || "");
  const [taskPromptText, setTaskPromptText] = useState(initialPrompt || task.prompt);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true), [error, setError] = useState(""), [retry, setRetry] = useState(0);
  const [accounts, setAccounts] = useState<Account[]>([]), [platforms, setPlatforms] = useState<{ key: string; name: string }[]>([]);
  const [platform, setPlatform] = useState(""), [socialError, setSocialError] = useState("");
  const [keywordLibrary, setKeywordLibrary] = useState(""), [page, setPage] = useState(1);
  const [keywordData, setKeywordData] = useState<KeywordPage | null>(null), [keywordLoading, setKeywordLoading] = useState(false), [keywordError, setKeywordError] = useState("");
  useEffect(() => { dialog.current?.showModal(); }, []);
  useEffect(() => {
    let cancelled = false;
    setLoading(true); setError(""); setSocialError("");
    const load = async () => {
      try {
        const data = await request<GeoCatalog>("/geoflow/catalog");
        if (!cancelled) setCatalog(data);
      } catch (e) { if (!cancelled) setError((e as Error).message); }
      if (task.id === "publish") {
        try {
          const [p, a] = await Promise.all([request<{ items: { key: string; name: string }[] }>("/geoflow/social/platforms"), request<{ items: Account[] }>("/geoflow/social/accounts")]);
          if (!cancelled) { setPlatforms(p.items); setAccounts(a.items); }
        } catch (e) { if (!cancelled) setSocialError((e as Error).message); }
      }
      if (!cancelled) setLoading(false);
    };
    void load();
    return () => { cancelled = true; };
  }, [task.id, retry]);
  useEffect(() => {
    let cancelled = false;
    setKeywordData(null); setKeywordError("");
    if (!keywordLibrary) { setKeywordLoading(false); return; }
    setKeywordLoading(true);
    request<KeywordPage>(`/geoflow/materials/keywords/${keywordLibrary}/items?page=${page}`)
      .then((data) => { if (!cancelled) setKeywordData(data); })
      .catch((e) => { if (!cancelled) setKeywordError(e.message); })
      .finally(() => { if (!cancelled) setKeywordLoading(false); });
    return () => { cancelled = true; };
  }, [keywordLibrary, page, retry]);
  const matches = (label: string) => label.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase());
  const labels = resources.flatMap((r) => selection[r.field].map((id) => {
    const item = (catalog?.[r.key] as LibraryItem[] | undefined)?.find((x) => Number(x.id) === id);
    return `${r.label} · ${item?.name || item?.title || id}`;
  })).concat(selection.keywords.map((x) => `关键词 · ${x.name}`), selection.social_account_ids.map((id) => {
    const account = accounts.find((a) => a.id === id);
    return `账号 · ${account?.platform_name || account?.platform} / ${account?.account_name}`;
  }));
  const canApply = !loading && !!catalog && (task.id !== "brand" || selection.knowledge_base_ids.length > 0) && (task.id !== "keywords" || selection.keywords.length > 0 || !!fields["种子关键词"]?.trim()) && (task.id !== "publish" || selection.social_account_ids.length > 0);
  const copy = taskCopy[task.id];
  return <dialog ref={dialog} onClose={onClose} className="task-dialog" aria-label={`${task.label}设置`}>
    <header><div><span className={`task-eyebrow task-eyebrow-${task.id}`}>{task.label} · 专属工作流</span><h2>{task.label}</h2><p className="task-lead">{copy.summary}</p></div><Button variant="ghost" size="icon" aria-label="关闭任务设置" onClick={onClose}><X size={18} /></Button></header>
    <div className={`task-stepper task-stepper-${task.id}`} aria-label={`${task.label}配置流程`}><span className="is-current">01 <small>选择资源</small></span><i /><span>02 <small>任务要求</small></span><i /><span>03 <small>提示词与技能</small></span></div>
    <p className="task-description">配置完成后会填入聊天输入框，检查无误再发送。</p>
    {loading && <div role="status" className="task-empty"><LoaderCircle size={20} className="animate-spin" />正在加载可用资源…</div>}
    {(error || socialError) && <div className="task-error" role="alert">{error || socialError}<Button variant="ghost" onClick={() => setRetry((x) => x + 1)}>重新加载</Button></div>}
    {!loading && catalog && <>
      <label className="task-search"><Search size={16} /><input aria-label="搜索资源" placeholder="搜索知识库、关键词、标题或账号" value={search} onChange={(e) => setSearch(e.target.value)} /></label>
      <div className="task-resource-sections">
        {taskResources[task.id].map((key) => {
          const r = resources.find((item) => item.key === key)!;
          const rows = ((catalog[key] || []) as LibraryItem[]).filter((item) => matches(item.name || item.title || String(item.id)));
          return <section className="task-resource" key={key}><h3><Library size={15} />{copy.resourceTitle} · {r.label}<small>已选 {selection[r.field].length} / {r.limit}</small></h3>
            <div className="task-options">{rows.map((item) => { const id = Number(item.id), checked = selection[r.field].includes(id); return <Checkbox key={id} label={item.name || item.title || String(id)} checked={checked} disabled={!checked && selection[r.field].length >= r.limit} onCheckedChange={(value) => setSelection((s) => ({ ...s, [r.field]: value ? [...s[r.field], id] : s[r.field].filter((x) => x !== id) }))} />; })}
            {!rows.length && <span className="task-empty">{search ? "没有匹配的资源" : `暂无${r.label}，请先在 GEOFlow 中添加`}</span>}</div>
          </section>;
        })}
        {task.id === "keywords" && <section className="task-resource"><h3>选择具体关键词<small>已选 {selection.keywords.length} / 20</small></h3>
          <label className="task-field">关键词来源<select value={keywordLibrary} onChange={(e) => { setKeywordLibrary(e.target.value); setPage(1); }}><option value="">请选择关键词库</option>{(catalog.keyword_libraries || []).map((item) => <option key={item.id} value={item.id}>{item.name || item.title}</option>)}</select></label>
          {keywordLoading && <div role="status" className="task-empty"><LoaderCircle className="animate-spin" size={16} />正在读取关键词…</div>}
          {keywordError && <div role="alert" className="task-error">{keywordError}<Button variant="ghost" onClick={() => setRetry((x) => x + 1)}>重试</Button></div>}
          <div className="task-options">{keywordData?.items.filter((item) => matches(item.keyword)).map((item) => {
            const checked = selection.keywords.some((x) => x.library_id === Number(keywordLibrary) && x.item_id === item.id);
            return <Checkbox key={item.id} label={item.keyword} checked={checked} disabled={!checked && selection.keywords.length >= 20} onCheckedChange={(value) => setSelection((s) => ({ ...s, keywords: value ? [...s.keywords, { library_id: Number(keywordLibrary), item_id: item.id, page, name: item.keyword }] : s.keywords.filter((x) => !(x.library_id === Number(keywordLibrary) && x.item_id === item.id)) }))} />;
          })}{keywordData && !keywordData.items.length && <span className="task-empty">该关键词库暂无关键词，可手动填写种子词。</span>}</div>
          {!!keywordData && <div className="task-pagination"><Button variant="ghost" disabled={page <= 1 || keywordLoading} onClick={() => setPage((p) => p - 1)}>上一页</Button><span>第 {page} / {keywordData.pagination?.total_pages || 1} 页</span><Button variant="ghost" disabled={page >= (keywordData.pagination?.total_pages || 1) || keywordLoading} onClick={() => setPage((p) => p + 1)}>下一页</Button></div>}
          <label className="task-field">种子关键词（也可手动输入）<input value={fields["种子关键词"] || ""} placeholder="多个关键词用逗号分隔" onChange={(e) => setFields((f) => ({ ...f, 种子关键词: e.target.value }))} /></label>
        </section>}
        {task.id === "publish" && <section className="task-resource"><h3>发布平台与账号<small>最多 3 个</small></h3><label className="task-field">平台<select value={platform} onChange={(e) => { setPlatform(e.target.value); setSelection((s) => ({ ...s, social_account_ids: [] })); }}><option value="">全部平台</option>{platforms.map((p) => <option key={p.key} value={p.key}>{p.name}</option>)}</select></label>
          <div className="task-options">{accounts.filter((a) => (!platform || a.platform === platform) && matches(a.account_name)).map((a) => <Checkbox key={a.id} label={`${a.platform_name || a.platform} · ${a.account_name}`} description={a.can_enqueue === false ? "未绑定可用执行节点，仅可准备文案" : "可准备待审核发布内容"} checked={selection.social_account_ids.includes(a.id)} disabled={!selection.social_account_ids.includes(a.id) && selection.social_account_ids.length >= 3} onCheckedChange={(value) => setSelection((s) => ({ ...s, social_account_ids: value ? [...s.social_account_ids, a.id] : s.social_account_ids.filter((id) => id !== a.id) }))} />)}
          {!accounts.some((a) => (!platform || a.platform === platform) && matches(a.account_name)) && <span className="task-empty">暂无可选账号，请在 GEOFlow 中配置社媒账号。</span>}</div>
        </section>}
      </div>
    </>}
    <section className={`task-resource task-fields-${task.id}`}><h3>{copy.fieldsTitle}<small>按需填写</small></h3><div className="task-fields">{fieldsFor[task.id].map((name) => <label className="task-field" key={name}>{name}<input value={fields[name] || ""} placeholder={`填写${name}`} onChange={(e) => setFields((f) => ({ ...f, [name]: e.target.value }))} /></label>)}</div></section>
    {labels.length > 0 && <div className="task-summary" aria-label="已选资源">{labels.map((label) => <span key={label}>{label}</span>)}</div>}
    <section className="task-resource"><h3>提示词与技能<small>最多选择 4 个技能</small></h3>
      <label className="task-field">提示词模板<select aria-label="GEOFlow 提示词模板" value={template} onChange={(e) => setTemplate(e.target.value)}><option value="">不使用模板</option>{(catalog?.prompts || []).map((item) => <option key={item.id} value={item.name}>{item.name}</option>)}</select></label>
      {!catalog?.prompts?.length && <p className="task-hint">GEOFlow 暂无可用内容提示词模板，可以直接编辑任务提示词。</p>}
      <div className="task-options">{availableSkills.map((skill) => <Checkbox key={skill.name} label={skill.display_name || skill.name} description={skill.description} checked={selectedSkills.includes(skill.name)} disabled={!selectedSkills.includes(skill.name) && selectedSkills.length >= 4} onCheckedChange={(checked) => setSelectedSkills((items) => checked ? [...items, skill.name] : items.filter((name) => name !== skill.name))} />)}{!availableSkills.length && <span className="task-empty">暂无可用技能</span>}</div>
      <label className="task-field task-prompt-field">任务提示词<textarea aria-label="任务提示词" value={taskPromptText} onChange={(e) => setTaskPromptText(e.target.value)} rows={5} /></label>
    </section>
    <footer className="task-footer"><span>{task.id === "brand" ? "请选择至少一个知识库" : task.id === "keywords" ? "选择关键词或填写种子词" : task.id === "publish" ? "请选择发布账号" : "任务内容会先填入输入框供你确认"}</span><Button disabled={!canApply || !taskPromptText.trim()} onClick={() => { if (catalog) onApply(taskPrompt(taskPromptText, fields, labels, template), selection, labels, catalog, fields, selectedSkills, template, taskPromptText); }}>{copy.action}<ArrowRight size={15} /></Button></footer>
  </dialog>;
}
