# 开发与架构

## 目录

```text
app/
  api.py           HTTP、登录、CSRF、所有权校验、SSE、附件接口
  config.py        空配置与环境变量读取
  store.py         SQLite、账号、会话、消息、事件、附件
  runtime.py       通用 SDK Agent、工具与流式执行
  skills.py        标准 SKILL.md、资源读取、导入校验
  connectors.py    标准 MCP 配置、连接生命周期
  files.py         附件存储与文本提取
  __main__.py      本地入口、创建账号
web/
  src/             React 登录、对话、技能、MCP、预览
    components/    BeUI 官方公开组件及对话输入区的轻量适配
    lib/           BeUI 工具函数与交互辅助
  public/          公开授权的图标与静态封面
  tests/           前端请求行为测试
skills/            每个技能直接作为一级子目录
examples/          不访问外网的示例 MCP 服务
tests/             SDK 协议模拟、真实 stdio MCP、鉴权测试
scripts/           交付检查和安全打包
docs/              开发者文档
```

## 执行流程

1. 浏览器使用 HttpOnly Cookie 登录；写请求携带 CSRF Token。
2. 后端校验对话、附件所有权及模型配置，保存用户消息和任务。
3. SDK Agent 读取可用技能目录，按需调用技能加载、联网、附件或 MCP 工具。
4. SDK SQLiteSession 持久化模型与工具历史；SSE 输出回复片段和执行状态。
5. 任务结束后保存回复、文件引用和耗时；异常、取消和重启均有明确结束状态。

执行过程采用 SDK 工具调用循环。技能资源不会自动执行；需要命令执行时，应接入经过审核且有适当隔离的 MCP 服务。

## 开发服务器

```sh
uv run python -m app --port 8787
```

另一终端：

```sh
cd web
npm ci
npm run dev
```

前端开发地址通常为 <http://127.0.0.1:5173>，Vite 将 `/api` 代理到本机 8787。同源 Cookie 和 CSRF 仍通过前端地址使用。正式静态构建后由 FastAPI 提供页面。

## 检查

```sh
uv run pytest -q
uv run ruff check app tests examples scripts
cd web
npm test
npm run build
```

后端测试使用本地模拟模型，无需真实密钥或付费调用；MCP 测试会启动 `examples/echo_mcp.py`，不会控制浏览器。

## 界面组件

前端使用 BeUI 官方组件源码、Tailwind CSS 4、Motion 和 Lucide。`vite.config.ts` 与 `tsconfig.json` 均将 `@/` 指向 `src/`。主题色在 `src/style.css` 的语义变量统一配置，避免使用全局原生按钮或输入框规则覆盖组件内部样式。

BeUI 来源为 <https://beui.dev/registry.json> 和该站点的 `/r/<组件名>.json`。已接入 Input、Button、Card、Checkbox、Tooltip、MorphPopover 与 PromptInput，保留组件自带动效，并通过 MotionConfig 尊重系统减少动态效果的偏好。登录背景和标题保持静态。

PromptInput 增加了附件和技能内容插槽、纯附件提交支持、独立提交禁用状态及中文按钮标签。模型、附件和技能调用使用统一接口。BeUI 的 MIT 许可保留在 `licenses/BeUI-LICENSE`。

新增工具可以在 `Runtime.tools()` 使用 SDK `function_tool` 注册，并通过闭包绑定当前对话。工具接收文件 ID 时必须使用已绑定的对话查询文件，不允许直接接受任意服务器路径。
