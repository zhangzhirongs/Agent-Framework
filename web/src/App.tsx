import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react";
import {
  ArrowRight,
  Bot,
  Check,
  ChevronLeft,
  Download,
  Eye,
  EyeOff,
  FileCode2,
  FileSpreadsheet,
  FileText,
  Library,
  KeyRound,
  LogOut,
  MessageSquare,
  Moon,
  Paperclip,
  Plug,
  Plus,
  Sun,
  Trash2,
  Upload,
  UserRound,
  WandSparkles,
  X,
} from "lucide-react";
import {
  request,
  setCSRF,
  type Attachment,
  type Detail,
  type Profile,
  type Run,
  type Skill,
  type Thread,
} from "./api";
import { Button } from "./components/motion/button/base";
import { Input } from "./components/motion/input";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
  CARD_TARGET_CLASS,
} from "./components/motion/card";
import { Checkbox } from "./components/motion/checkbox";
import { Tooltip } from "./components/motion/tooltip";
import {
  MorphPopover,
  MorphPopoverContent,
  MorphPopoverTrigger,
} from "./components/motion/popover-morph";
import { PromptInput } from "./components/agents/prompt-input";
import { cn } from "./lib/utils";

function IconButton({
  label,
  children,
  onClick,
  disabled,
  className = "",
}: {
  label: string;
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <Tooltip content={label}>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className={cn("icon-button", className)}
        aria-label={label}
        onClick={onClick}
        disabled={disabled}
      >
        {children}
      </Button>
    </Tooltip>
  );
}

function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
  }, []);
  return (
    <dialog ref={ref} onClose={onClose} aria-label={title}>
      <header>
        <h2>{title}</h2>
        <IconButton label="关闭" onClick={() => ref.current?.close()}>
          <X size={18} />
        </IconButton>
      </header>
      {children}
    </dialog>
  );
}

function Login({ accept }: { accept: (p: Profile) => void }) {
  const [name, setName] = useState("admin"),
    [password, setPassword] = useState("123");
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  return (
    <main className="login-page">
      <img className="login-cover" src="/covers/earthrise.jpg" alt="" />
      <header className="login-brand">
        <img src="/brand/robot.svg" alt="" />
        智能体
      </header>
      <div className="login-layout">
        <section className="login-copy">
          <h1>智能体</h1>
          <p>从一个问题开始。</p>
        </section>
        <form
          className="login-form"
          onSubmit={async (event) => {
            event.preventDefault();
            if (busy) return;
            setBusy(true);
            setError("");
            try {
              accept(
                await request<Profile>("/auth/login", "POST", {
                  username: name,
                  password,
                }),
              );
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <div className="login-form-heading">
            <span className="login-form-icon">
              <Bot size={23} />
            </span>
            <h2>欢迎回来</h2>
            <p>登录你的工作空间</p>
          </div>
          <Input
            label="账号"
            autoComplete="username"
            name="username"
            leftIcon={<UserRound />}
            value={name}
            onChange={setName}
            disabled={busy}
            required
          />
          <Input
            label="密码"
            type={showPassword ? "text" : "password"}
            autoComplete="current-password"
            name="password"
            leftIcon={<KeyRound />}
            value={password}
            onChange={setPassword}
            disabled={busy}
            required
            rightIcon={
              <Button
                variant="ghost"
                size="icon"
                aria-label={showPassword ? "隐藏密码" : "显示密码"}
                onClick={() => setShowPassword(!showPassword)}
              >
                {showPassword ? <EyeOff /> : <Eye />}
              </Button>
            }
          />
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
          <Button
            type="submit"
            className="login-submit"
            size="lg"
            disabled={busy}
          >
            {busy ? "正在登录…" : "登录"}
            <ArrowRight size={17} />
          </Button>
        </form>
      </div>
      <footer className="login-credit">Earthrise · NASA / Apollo 8</footer>
    </main>
  );
}

type FileKind = "pdf" | "word" | "sheet" | "slides" | "image" | "text" | "other";

function fileKind(file: Pick<Attachment, "name" | "media_type">): FileKind {
  const name = file.name.toLowerCase();
  const type = file.media_type.toLowerCase();
  if (type === "application/pdf" || name.endsWith(".pdf")) return "pdf";
  if (/(wordprocessingml|msword)/.test(type) || /\.(doc|docx|rtf)$/.test(name)) return "word";
  if (/(spreadsheetml|ms-excel|csv)/.test(type) || /\.(xls|xlsx|csv)$/.test(name)) return "sheet";
  if (/(presentationml|powerpoint)/.test(type) || /\.(ppt|pptx)$/.test(name)) return "slides";
  if (type.startsWith("image/")) return "image";
  if (type.startsWith("text/") || /\.(md|json|js|ts|css|html|xml|yaml|yml)$/.test(name)) return "text";
  return "other";
}

const fileKindLabel: Record<FileKind, string> = {
  pdf: "PDF 文档", word: "Word 文档", sheet: "Excel 表格", slides: "演示文稿",
  image: "图片", text: "文本文件", other: "文件",
};

function FileKindIcon({ kind, size = 18 }: { kind: FileKind; size?: number }) {
  if (kind === "sheet") return <FileSpreadsheet size={size} />;
  if (kind === "text") return <FileCode2 size={size} />;
  return <FileText size={size} />;
}

function Preview({
  file,
  onClose,
  tabs = [],
  onSelect,
  onCloseTab,
  onResizeStart,
  style,
}: {
  file: Attachment;
  onClose: () => void;
  tabs?: Attachment[];
  onSelect?: (file: Attachment) => void;
  onCloseTab?: (file: Attachment) => void;
  onResizeStart?: (event: ReactPointerEvent<HTMLDivElement>) => void;
  style?: CSSProperties;
}) {
  const [text, setText] = useState(""),
    [formatted, setFormatted] = useState(""),
    [error, setError] = useState("");
  const image = file.media_type.startsWith("image/");
  const kind = fileKind(file);
  const embedded =
    file.media_type === "application/pdf" || file.media_type === "text/html";
  useEffect(() => {
    let cancelled = false;
    setText("");
    setFormatted("");
    setError("");
    if (!image && !embedded && kind === "word")
      request<{ html: string }>(`/files/${file.id}/preview`)
        .then((r) => {
          if (!cancelled) setFormatted(r.html);
        })
        .catch((e) => {
          if (!cancelled) setError(e.message);
        });
    else if (!image && !embedded)
      request<{ text: string }>(`/files/${file.id}/text`)
        .then((r) => {
          if (!cancelled) setText(r.text);
        })
        .catch((e) => {
          if (!cancelled) setError(e.message);
        });
    return () => {
      cancelled = true;
    };
  }, [file.id, image, embedded, kind]);
  const url = `/api/files/${file.id}?preview=true`;
  const tabsBar = tabs.length > 1 && (
    <div className="file-preview-tabs" role="tablist" aria-label="打开的文件">
      {tabs.map((tab) => (
        <div className={cn("file-preview-tab", tab.id === file.id && "active")} key={tab.id}>
          <button type="button" role="tab" aria-selected={tab.id === file.id} title={tab.name} onClick={() => onSelect?.(tab)}>
            <FileKindIcon kind={fileKind(tab)} size={14} />
            <span>{tab.name}</span>
          </button>
          <IconButton label={`关闭 ${tab.name}`} onClick={() => onCloseTab?.(tab)}>
            <X size={12} />
          </IconButton>
        </div>
      ))}
    </div>
  );
  if (image)
    return (
      <Modal title={file.name} onClose={onClose}>
        {tabsBar}
        <img className="image-preview" src={url} alt={file.name} />
        <a className="download" href={`/api/files/${file.id}`} download>
          <Download size={16} />
          下载
        </a>
      </Modal>
    );
  return (
    <aside className={cn("file-preview", `file-preview-${kind}`)} style={style}>
      <div className="file-preview-resize" role="separator" aria-label="调整预览宽度" onPointerDown={onResizeStart} />
      {tabsBar}
      <header>
        <span className="file-preview-icon" aria-hidden="true">
          <FileKindIcon kind={kind} size={19} />
        </span>
        <span className="file-preview-type">{fileKindLabel[kind]}</span>
        <h2 title={file.name}>{file.name}</h2>
        <a
          className="icon-button"
          href={`/api/files/${file.id}`}
          title="下载"
          aria-label="下载"
        >
          <Download size={18} />
        </a>
        <IconButton label="关闭预览" onClick={onClose}>
          <X size={18} />
        </IconButton>
      </header>
      {embedded ? (
        file.media_type === "text/html" ? (
          <iframe src={url} title={file.name} sandbox="" />
        ) : (
          <iframe src={url} title={file.name} />
        )
      ) : error ? (
        <p className="error">
          {error}
          <a href={`/api/files/${file.id}`}>下载文件</a>
        </p>
      ) : formatted ? (
        <iframe className="formatted-document" srcDoc={formatted} title={file.name} sandbox="" />
      ) : (
        <pre>{text || "正在读取…"}</pre>
      )}
    </aside>
  );
}

function SkillsPage({
  admin,
  onError,
}: {
  admin: boolean;
  onError: (e: string) => void;
}) {
  const [skills, setSkills] = useState<Skill[]>([]),
    [detail, setDetail] = useState<Skill | null>(null),
    [busy, setBusy] = useState(false);
  const files = useRef<HTMLInputElement>(null),
    folder = useRef<HTMLInputElement>(null);
  const reload = () =>
    request<Skill[]>("/skills")
      .then(setSkills)
      .catch((e) => onError(e.message));
  useEffect(() => {
    void reload();
    folder.current?.setAttribute("webkitdirectory", "");
  }, []);
  const upload = async (selected: FileList | null) => {
    if (!selected?.length) return;
    setBusy(true);
    const body = new FormData();
    for (const file of Array.from(selected))
      body.append("files", file, file.webkitRelativePath || file.name);
    try {
      await request("/skills/import", "POST", body);
      await reload();
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
      if (files.current) files.current.value = "";
      if (folder.current) folder.current.value = "";
    }
  };
  return (
    <section className="settings-page">
      <div className="page-heading">
        <span className="collection-count">{skills.length} 个技能</span>
        {admin && (
          <div className="row">
            <Button
              variant="outline"
              size="sm"
              disabled={busy}
              onClick={() => files.current?.click()}
            >
              <Upload size={15} />
              导入文件
            </Button>
            <Button
              size="sm"
              disabled={busy}
              onClick={() => folder.current?.click()}
            >
              <Plus size={15} />
              导入目录
            </Button>
          </div>
        )}
      </div>
      <input
        hidden
        type="file"
        accept=".zip,.md"
        ref={files}
        onChange={(e) => void upload(e.target.files)}
      />
      <input
        hidden
        type="file"
        multiple
        ref={folder}
        onChange={(e) => void upload(e.target.files)}
      />
      <div className="skills-grid">
        {skills.map((s) => (
          <Card className="skill-card" interactive key={s.name}>
            <CardHeader>
              <span className="resource-icon">
                <WandSparkles size={20} />
              </span>
              <CardTitle as="h2">
                <button
                  type="button"
                  className={cn("skill-title", CARD_TARGET_CLASS)}
                  onClick={() =>
                    request<Skill>(`/skills/${s.name}`)
                      .then(setDetail)
                      .catch((e) => onError(e.message))
                  }
                >
                  {s.display_name || s.name}
                </button>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="skill-description">{s.description}</p>
            </CardContent>
            <CardFooter>
              <small title={s.author}>{s.author}</small>
              {admin && (
                <IconButton
                  className="relative z-10"
                  label={`移除 ${s.display_name || s.name}`}
                  onClick={async () => {
                    if (!confirm(`移除技能 ${s.display_name || s.name}？`)) return;
                    try {
                      await request(`/skills/${s.name}`, "DELETE");
                      await reload();
                    } catch (e) {
                      onError((e as Error).message);
                    }
                  }}
                >
                  <Trash2 size={16} />
                </IconButton>
              )}
            </CardFooter>
          </Card>
        ))}
      </div>
      {!skills.length && <p className="empty">暂无技能</p>}
      {detail && (
        <Modal title={detail.display_name || detail.name} onClose={() => setDetail(null)}>
          <p>{detail.description}</p>
          <small>作者：{detail.author}</small>
          <pre>{detail.content}</pre>
          <details>
            <summary>资源文件</summary>
            <ul>
              {detail.resources?.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          </details>
        </Modal>
      )}
    </section>
  );
}

function MCPPage({
  admin,
  onError,
}: {
  admin: boolean;
  onError: (e: string) => void;
}) {
  const [text, setText] = useState('{"mcpServers": {}}'),
    [busy, setBusy] = useState(false),
    [result, setResult] = useState("");
  const [servers, setServers] = useState<
    { name: string; enabled: boolean; transport: string }[]
  >([]);
  const reload = () => request<typeof servers>("/connectors").then(setServers);
  useEffect(() => {
    void reload().catch((e) => onError(e.message));
    if (admin)
      request("/connectors/config")
        .then((v) => setText(JSON.stringify(v, null, 2)))
        .catch((e) => onError(e.message));
  }, []);
  return (
    <section className="settings-page">
      <div className="page-heading">
        <span className="collection-count">{servers.length} 个连接器</span>
      </div>
      <div className="connector-list">
        {servers.map((s) => (
          <div className="connector" key={s.name}>
            <span className="resource-icon">
              <Plug size={18} />
            </span>
            <strong>{s.name}</strong>
            <span>{s.transport}</span>
            <small className={cn("status-badge", s.enabled && "enabled")}>
              {s.enabled ? "已启用" : "已停用"}
            </small>
          </div>
        ))}
      </div>
      {!servers.length && <p className="empty">暂无连接器</p>}
      {admin && (
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            if (busy) return;
            setBusy(true);
            setResult("");
            try {
              await request("/connectors/config", "PUT", JSON.parse(text));
              await reload();
              setResult("配置已保存");
            } catch (e) {
              onError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <label>
            MCP 配置
            <textarea
              className="config-editor"
              spellCheck={false}
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          </label>
          <p>
            将服务提供方的 JSON 配置粘贴到此处，保留顶层 mcpServers 对象。
            可在其中添加多个不同名称的服务（最多 32 个），新增时请保留已有服务，保存后点击“测试连接”。
            支持本地 stdio、远程 HTTP 和 SSE；密钥通过环境变量引用。
          </p>
          <div className="row">
            <Button type="submit" disabled={busy}>
              <Check size={16} />
              保存
            </Button>
            <Button
              variant="outline"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                setResult("");
                try {
                  setResult(
                    JSON.stringify(
                      await request("/connectors/test", "POST"),
                      null,
                      2,
                    ),
                  );
                } catch (e) {
                  onError((e as Error).message);
                } finally {
                  setBusy(false);
                }
              }}
            >
              <Plug size={16} />
              测试连接
            </Button>
          </div>
          {result && <pre role="status">{result}</pre>}
        </form>
      )}
    </section>
  );
}

function Workspace({
  profile,
  signOut,
}: {
  profile: Profile;
  signOut: () => void;
}) {
  const [view, setView] = useState("chat"),
    [threads, setThreads] = useState<Thread[]>([]),
    [current, setCurrent] = useState("");
  const [detail, setDetail] = useState<Detail | null>(null),
    [prompt, setPrompt] = useState(""),
    [pending, setPending] = useState<Attachment[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]),
    [selected, setSelected] = useState<string[]>([]),
    [toolsOpen, setToolsOpen] = useState(false);
  const [geoflowCatalog, setGeoflowCatalog] = useState<{
    knowledge_bases: { id: number | string; name?: string; title?: string }[];
    title_libraries: { id: number | string; name?: string; title?: string }[];
  } | null>(null);
  const [selectedKnowledge, setSelectedKnowledge] = useState<string[]>([]),
    [selectedTitles, setSelectedTitles] = useState<string[]>([]);
  const [active, setActive] = useState<Run | null>(null),
    [live, setLive] = useState(""),
    [activity, setActivity] = useState(""),
    [elapsed, setElapsed] = useState(0);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [preview, setPreview] = useState<Attachment | null>(null),
    [previewTabs, setPreviewTabs] = useState<Attachment[]>([]),
    [passwordOpen, setPasswordOpen] = useState(false);
  const [previewWidth, setPreviewWidth] = useState(42);
  const [dark, setDark] = useState(
    () => localStorage.getItem("agent-theme") === "dark",
  );
  const source = useRef<EventSource | null>(null),
    uploadInput = useRef<HTMLInputElement>(null),
    bottom = useRef<HTMLDivElement>(null),
    selection = useRef("");
  const [caps, setCaps] = useState<{
    model_ready: boolean;
    max_upload_mb: number;
    demo: boolean;
  } | null>(null);
  const reloadThreads = () => request<Thread[]>("/threads").then(setThreads);
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("agent-theme", dark ? "dark" : "light");
  }, [dark]);
  const follow = useCallback((run: Run, threadId: string) => {
    source.current?.close();
    setActive(run);
    setLive("");
    setActivity("正在处理");
    const stream = new EventSource(`/api/runs/${run.id}/events`);
    source.current = stream;
    stream.addEventListener("delta", (event) => {
      if (selection.current === threadId)
        setLive((v) => v + JSON.parse((event as MessageEvent).data).text);
    });
    stream.addEventListener("activity", (event) => {
      if (selection.current === threadId)
        setActivity(JSON.parse((event as MessageEvent).data).text);
    });
    stream.addEventListener("done", (event) => {
      stream.close();
      const result = JSON.parse((event as MessageEvent).data);
      if (selection.current !== threadId) return;
      if (result.error) setError(result.error);
      request<Detail>(`/threads/${threadId}`)
        .then((data) => {
          if (selection.current === threadId) {
            setDetail(data);
            setActive(null);
            setLive("");
          }
        })
        .catch((e) => setError(e.message));
      void reloadThreads().catch((e) => setError(e.message));
    });
    stream.onerror = () => {
      if (selection.current === threadId) setActivity("连接中断，正在恢复…");
    };
  }, []);
  const load = useCallback(
    async (id: string) => {
      const data = await request<Detail>(`/threads/${id}`);
      if (selection.current !== id) return;
      setDetail(data);
      const running = data.runs.find((r) =>
        ["queued", "running"].includes(r.status),
      );
      if (running) follow(running, id);
      else {
        setActive(null);
        setLive("");
      }
    },
    [follow],
  );
  useEffect(() => {
    void reloadThreads().catch((e) => setError(e.message));
    request<typeof caps>("/capabilities")
      .then(setCaps)
      .catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    request<Skill[]>("/skills")
      .then(setSkills)
      .catch((e) => setError(e.message));
  }, [view]);
  useEffect(() => {
    request<typeof geoflowCatalog>("/geoflow/catalog")
      .then(setGeoflowCatalog)
      .catch(() => setGeoflowCatalog(null));
  }, []);
  useEffect(() => {
    selection.current = current;
    source.current?.close();
    setDetail(null);
    setActive(null);
    setLive("");
    setPreview(null);
    setPreviewTabs([]);
    if (current) void load(current).catch((e) => setError(e.message));
    return () => source.current?.close();
  }, [current, load]);
  useEffect(() => {
    if (!active) return;
    const tick = () =>
      setElapsed(Math.max(0, Math.floor(Date.now() / 1000 - active.created)));
    tick();
    const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
  }, [active?.id]);
  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end" });
  }, [detail?.messages.length, live]);
  const ensureThread = async () => {
    if (current) return current;
    const t = await request<Thread>("/threads", "POST");
    selection.current = t.id;
    setCurrent(t.id);
    await reloadThreads();
    return t.id;
  };
  const send = async () => {
    if (
      busy ||
      active ||
      !caps?.model_ready ||
      (!prompt.trim() && !pending.length)
    )
      return;
    setBusy(true);
    setError("");
    try {
      const id = await ensureThread();
      await request(`/threads/${id}/messages`, "POST", {
        content: prompt,
        file_ids: pending.map((f) => f.id),
        skills: selected,
        geoflow_context: {
          knowledge_base_ids: selectedKnowledge.map(Number),
          title_library_ids: selectedTitles.map(Number),
        },
      });
      setPrompt("");
      setPending([]);
      setSelected([]);
      setSelectedKnowledge([]);
      setSelectedTitles([]);
      setToolsOpen(false);
      await load(id);
      await reloadThreads();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const upload = async (files: FileList | null) => {
    if (!files?.length) return;
    setBusy(true);
    setError("");
    try {
      if (pending.length + files.length > 8)
        throw new Error("每条消息最多 8 个附件");
      const id = await ensureThread();
      for (const file of Array.from(files)) {
        if (file.size > (caps?.max_upload_mb || 20) * 1024 * 1024)
          throw new Error("文件超过大小限制");
        const body = new FormData();
        body.append("file", file);
        const item = await request<Attachment>(
          `/threads/${id}/files`,
          "POST",
          body,
        );
        setPending((v) => [...v, item]);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      if (uploadInput.current) uploadInput.current.value = "";
    }
  };
  const pick = (id: string) => {
    setView("chat");
    setPrompt("");
    setPending([]);
    setSelected([]);
    setCurrent(id);
    setError("");
  };
  const fileButton = (file: Attachment) => {
    const kind = fileKind(file);
    return <Button
      variant="ghost"
      type="button"
      key={file.id}
      className={
        file.media_type.startsWith("image/")
          ? "attachment-image"
          : cn("attachment-file", `attachment-${kind}`)
      }
      title={file.name}
      onClick={() => {
        setPreview(file);
        setPreviewTabs((tabs) => tabs.some((tab) => tab.id === file.id) ? tabs : [...tabs, file]);
      }}
    >
      {file.media_type.startsWith("image/") ? (
        <img src={`/api/files/${file.id}?preview=true`} alt={file.name} />
      ) : (
        <>
          <span className="attachment-icon" aria-hidden="true">
            <FileKindIcon kind={kind} size={17} />
          </span>
          <span>{file.name}</span>
          <small>{fileKindLabel[kind]}</small>
        </>
      )}
    </Button>;
  };
  const beginPreviewResize = (event: React.PointerEvent<HTMLDivElement>) => {
    if (window.matchMedia("(max-width: 700px)").matches) return;
    event.preventDefault();
    const startX = event.clientX;
    const parent = event.currentTarget.parentElement?.parentElement;
    const panel = event.currentTarget.parentElement;
    if (!parent || !panel) return;
    const startWidth = panel.getBoundingClientRect().width;
    const move = (moveEvent: PointerEvent) => {
      const available = parent.getBoundingClientRect().width;
      const next = Math.min(650, Math.max(300, startWidth + startX - moveEvent.clientX));
      setPreviewWidth(Math.min(80, Math.max(25, (next / available) * 100)));
    };
    const end = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", end);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", end, { once: true });
  };
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <img src="/brand/robot.svg" alt="" />
          <strong>智能体</strong>
        </div>
        <Button variant="outline" className="new-chat" onClick={() => pick("")}>
          <Plus size={17} />
          新对话
        </Button>
        <nav aria-label="工作区">
          <Button
            variant="ghost"
            className={view === "skills" ? "selected" : ""}
            onClick={() => setView("skills")}
          >
            <WandSparkles size={17} />
            技能
          </Button>
          <Button
            variant="ghost"
            className={view === "mcp" ? "selected" : ""}
            onClick={() => setView("mcp")}
          >
            <Plug size={17} />
            MCP 连接器
          </Button>
        </nav>
        <div className="thread-list">
          {threads.map((t) => (
            <div
              className={`thread ${view === "chat" && current === t.id ? "selected" : ""}`}
              key={t.id}
            >
              <Button
                variant="ghost"
                title={t.title}
                onClick={() => pick(t.id)}
              >
                <MessageSquare size={15} />
                <span>{t.title}</span>
              </Button>
              <IconButton
                label={`删除 ${t.title}`}
                onClick={async () => {
                  if (!confirm("删除此对话及其附件？")) return;
                  try {
                    await request(`/threads/${t.id}`, "DELETE");
                    if (current === t.id) pick("");
                    await reloadThreads();
                  } catch (e) {
                    setError((e as Error).message);
                  }
                }}
              >
                <Trash2 size={14} />
              </IconButton>
            </div>
          ))}
        </div>
        <footer>
          <span title={profile.username}>{profile.username}</span>
          <div className="row">
            <IconButton label="修改密码" onClick={() => setPasswordOpen(true)}>
              <KeyRound size={16} />
            </IconButton>
            <IconButton
              label={dark ? "浅色模式" : "深色模式"}
              onClick={() => setDark(!dark)}
            >
              {dark ? <Sun size={16} /> : <Moon size={16} />}
            </IconButton>
            <IconButton
              label="退出登录"
              onClick={async () => {
                try {
                  await request("/auth/logout", "POST");
                  signOut();
                } catch (e) {
                  setError((e as Error).message);
                }
              }}
            >
              <LogOut size={16} />
            </IconButton>
          </div>
          <small>v0.1.0</small>
        </footer>
      </aside>
      <main className="workspace">
        <header className="workspace-header">
          <h1>
            {view === "chat"
              ? detail?.thread.title || "新对话"
              : view === "skills"
                ? "技能"
                : "MCP 连接器"}
          </h1>
          {view !== "chat" && (
            <IconButton label="返回对话" onClick={() => setView("chat")}>
              <ChevronLeft size={18} />
            </IconButton>
          )}
        </header>
        {error && (
          <div className="error-banner" role="alert">
            <span>{error}</span>
            <IconButton label="关闭提示" onClick={() => setError("")}>
              <X size={16} />
            </IconButton>
          </div>
        )}
        {view === "skills" ? (
          <SkillsPage admin={profile.is_admin} onError={setError} />
        ) : view === "mcp" ? (
          <MCPPage admin={profile.is_admin} onError={setError} />
        ) : (
          <div className="chat-layout">
            <section className="conversation">
              <div className="message-scroll">
                {!detail?.messages.length && !active && (
                  <div className="welcome">
                    <span className="welcome-mark">
                      <Bot size={30} />
                    </span>
                    <h2>今天想聊什么？</h2>
                  </div>
                )}
                {detail?.messages.map((message) => (
                  <article
                    key={message.id}
                    className={`message ${message.role}`}
                  >
                    <div className="message-content">
                      {message.skills.map((s) => (
                        <span className="skill-mention" key={s}>
                          @{skills.find((skill) => skill.name === s)?.display_name || s}{" "}
                        </span>
                      ))}
                      {message.content}
                    </div>
                    {message.file_ids.length > 0 && (
                      <div className="message-files">
                        {message.file_ids
                          .map((id) => detail.files.find((f) => f.id === id))
                          .filter((f): f is Attachment => !!f)
                          .map(fileButton)}
                      </div>
                    )}
                  </article>
                ))}
                {active && (
                  <article className="message assistant">
                    <div className="message-content">{live}</div>
                    <p className="run-status" role="status">
                      {activity} · {elapsed} 秒
                    </p>
                  </article>
                )}
                {!active && detail?.runs[0] && (
                  <p className="run-status">
                    {detail.runs[0].status === "completed"
                      ? "已完成"
                      : detail.runs[0].error || "已结束"}
                    {detail.runs[0].finished
                      ? ` · ${Math.max(0, Math.round(detail.runs[0].finished! - detail.runs[0].created))} 秒`
                      : ""}
                  </p>
                )}
                <div ref={bottom} />
              </div>
              <div className="composer-area">
                {!caps?.model_ready && caps && (
                  <p className="config-notice">模型尚未配置</p>
                )}
                <PromptInput
                  className="composer"
                  aria-label="消息"
                  value={prompt}
                  onValueChange={setPrompt}
                  placeholder={selected.length ? "" : "发送消息…"}
                  onSubmit={() => send()}
                  loading={!!active}
                  disabled={busy && !active}
                  submitDisabled={!caps?.model_ready}
                  allowEmptySubmit={pending.length > 0}
                  submitLabel="发送"
                  stopLabel="停止任务"
                  onStop={() => {
                    if (active)
                      void request(`/runs/${active.id}/cancel`, "POST").catch(
                        (e) => setError(e.message),
                      );
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Backspace" && !prompt)
                      setSelected((v) => v.slice(0, -1));
                  }}
                  header={
                    <>
                      {pending.length > 0 && (
                        <div className="pending-files">
                          {pending.map((f) => (
                            <div className="pending-file" key={f.id}>
                              {fileButton(f)}
                              <IconButton
                                label={`移除 ${f.name}`}
                                onClick={() =>
                                  setPending((v) =>
                                    v.filter((x) => x.id !== f.id),
                                  )
                                }
                              >
                                <X size={12} />
                              </IconButton>
                            </div>
                          ))}
                        </div>
                      )}
                      {selected.length > 0 && (
                        <div className="selected-skills">
                          {selected.map((s) => (
                            <span className="skill-mention" key={s}>
                              @{s}
                            </span>
                          ))}
                        </div>
                      )}
                      {(selectedKnowledge.length > 0 || selectedTitles.length > 0) && (
                        <div className="selected-skills">
                          {selectedKnowledge.map((id) => {
                            const item = geoflowCatalog?.knowledge_bases.find((x) => String(x.id) === id);
                            return <span className="library-mention" key={`k-${id}`}>知识库 · {item?.name || item?.title || id}</span>;
                          })}
                          {selectedTitles.map((id) => {
                            const item = geoflowCatalog?.title_libraries.find((x) => String(x.id) === id);
                            return <span className="title-mention" key={`t-${id}`}>标题库 · {item?.name || item?.title || id}</span>;
                          })}
                        </div>
                      )}
                    </>
                  }
                  leadingAction={
                    <MorphPopover open={toolsOpen} onOpenChange={setToolsOpen}>
                      <MorphPopoverTrigger>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label="附件与技能"
                          className="rounded-full"
                          disabled={busy || !!active}
                        >
                          <Plus size={19} />
                        </Button>
                      </MorphPopoverTrigger>
                      <MorphPopoverContent
                        side="top"
                        align="start"
                        radius={16}
                        className="tools-menu"
                      >
                        <Button
                          variant="ghost"
                          className="upload-action"
                          disabled={pending.length >= 8}
                          onClick={() => {
                            uploadInput.current?.click();
                            setToolsOpen(false);
                          }}
                        >
                          <Paperclip size={16} />
                          上传附件
                        </Button>
                        {geoflowCatalog && (
                          <>
                            <hr />
                            <div className="skills-options library-options">
                              <strong><Library size={14} /> GEOFlow 知识库</strong>
                              {geoflowCatalog.knowledge_bases.map((item) => {
                                const id = String(item.id);
                                return <Checkbox key={id} label={item.name || item.title || `知识库 ${id}`} checked={selectedKnowledge.includes(id)} onCheckedChange={(checked) => setSelectedKnowledge((v) => checked ? [...v, id] : v.filter((x) => x !== id))} />;
                              })}
                              {!geoflowCatalog.knowledge_bases.length && <span>暂无知识库</span>}
                              <strong><FileText size={14} /> GEOFlow 标题库</strong>
                              {geoflowCatalog.title_libraries.map((item) => {
                                const id = String(item.id);
                                return <Checkbox key={id} label={item.name || item.title || `标题库 ${id}`} checked={selectedTitles.includes(id)} onCheckedChange={(checked) => setSelectedTitles((v) => checked ? [...v, id] : v.filter((x) => x !== id))} />;
                              })}
                              {!geoflowCatalog.title_libraries.length && <span>暂无标题库</span>}
                            </div>
                          </>
                        )}
                        <hr />
                        <div className="skills-options">
                          {skills.map((s) => (
                            <Checkbox
                              key={s.name}
                              label={s.display_name || s.name}
                              checked={selected.includes(s.name)}
                              disabled={
                                !selected.includes(s.name) &&
                                selected.length >= 4
                              }
                              onCheckedChange={(checked) =>
                                setSelected((v) =>
                                  checked
                                    ? [...v, s.name]
                                    : v.filter((n) => n !== s.name),
                                )
                              }
                            />
                          ))}
                          {!skills.length && <span>暂无技能</span>}
                        </div>
                      </MorphPopoverContent>
                    </MorphPopover>
                  }
                />
                <input
                  type="file"
                  multiple
                  hidden
                  ref={uploadInput}
                  accept=".txt,.md,.json,.csv,.html,.htm,.pdf,.docx,.png,.jpg,.jpeg,.webp,.gif"
                  onChange={(e) => void upload(e.target.files)}
                />
              </div>
            </section>
            {preview && (
              <Preview
                file={preview}
                tabs={previewTabs}
                onSelect={setPreview}
                onClose={() => {
                  setPreview(null);
                  setPreviewTabs([]);
                }}
                onCloseTab={(tab) => {
                  const next = previewTabs.filter((item) => item.id !== tab.id);
                  setPreviewTabs(next);
                  if (tab.id === preview.id) setPreview(next.at(-1) || null);
                }}
                onResizeStart={beginPreviewResize}
                style={{ flexBasis: `${previewWidth}%`, width: `${previewWidth}%` }}
              />
            )}
          </div>
        )}
      </main>
      {passwordOpen && (
        <PasswordDialog
          onClose={() => setPasswordOpen(false)}
          onChanged={signOut}
        />
      )}
    </div>
  );
}

function PasswordDialog({
  onClose,
  onChanged,
}: {
  onClose: () => void;
  onChanged: () => void;
}) {
  const [old, setOld] = useState(""),
    [password, setPassword] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <Modal title="修改密码" onClose={onClose}>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          try {
            await request("/auth/password", "POST", {
              current_password: old,
              new_password: password,
            });
            onChanged();
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <Input
          label="原密码"
          type="password"
          autoComplete="current-password"
          value={old}
          onChange={setOld}
          required
        />
        <Input
          label="新密码"
          type="password"
          minLength={8}
          autoComplete="new-password"
          value={password}
          onChange={setPassword}
          required
        />
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <Button type="submit" disabled={busy}>
          保存并重新登录
        </Button>
      </form>
    </Modal>
  );
}

export function App() {
  const [profile, setProfile] = useState<Profile | null>(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState("");
  const accept = (p: Profile) => {
    setCSRF(p.csrf_token);
    setProfile(p);
  };
  const clear = () => {
    setCSRF("");
    setProfile(null);
  };
  const refresh = () => {
    setLoading(true);
    setError("");
    request<Profile>("/auth/me")
      .then(accept)
      .catch((e) => {
        if (e.message !== "请先登录") setError(e.message);
      })
      .finally(() => setLoading(false));
  };
  useEffect(() => {
    refresh();
    window.addEventListener("signed-out", clear);
    return () => window.removeEventListener("signed-out", clear);
  }, []);
  if (loading) return <main className="loading">正在加载…</main>;
  if (error)
    return (
      <main className="loading">
        <p role="alert">{error}</p>
        <Button variant="outline" onClick={refresh}>
          重试
        </Button>
      </main>
    );
  return profile ? (
    <Workspace profile={profile} signOut={clear} />
  ) : (
    <Login accept={accept} />
  );
}
