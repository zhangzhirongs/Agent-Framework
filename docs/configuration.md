# 配置说明

实际配置由接收者在 `.env` 中维护，交付文件只有空模板。环境变量优先于 `.env`。更改模型或联网配置后需要重启后端。

## 模型

| 变量 | 含义 |
| --- | --- |
| `AGENT_BASE_URL` | 供应商 API 根路径，不能为空 |
| `AGENT_MODEL` | 接收者自己的模型 ID，不能为空 |
| `AGENT_API_KEY` | 接收者自己的 API Key，不能为空 |
| `AGENT_API_MODE` | `chat` 对应 Chat Completions，`responses` 对应 Responses |
| `AGENT_VISION_ENABLED` | 默认 `false`，确认模型支持图片后设为 `true` |
| `AGENT_MODEL_TIMEOUT` | 单次模型请求超时秒数，默认 120 |
| `AGENT_MAX_TURNS` | SDK 单次任务工具调用轮数上限，默认 12 |
| `AGENT_MAX_CONCURRENT_RUNS` | 本进程同时执行任务上限，默认 2 |

不内置供应商账号、实际模型列表或付费路由。模型必须支持所选协议及工具调用；视觉支持需要单独确认。默认不自动重试付费请求，也不在异常提示里返回供应商原始正文。SDK tracing 默认关闭。

### 上下文和用量预算

一次发送可能包含多次模型请求：工具调用后模型需要再次读取上下文。界面的请求次数包含这些步骤。

普通聊天只提供 `find_tools` 一个工具入口，不发送完整文件、GEOFlow、联网、MCP 工具定义或技能目录。需要能力时，一次搜索最多启用 3 个匹配工具；精确名称只加载该工具。MCP 工具仍执行原来的允许名单和审批要求，目录在本轮内缓存。旧的 MCP 列表与加载两步入口已经移除。

所选技能只注入一次说明，重复读取仅返回已加载提示。文件与技能资源支持 `offset`、`limit` 分页，文件另支持 `query` 定位关键词。`write_text_file` 成功后，后续模型输入会将长正文参数替换为已保存的文件引用；执行时的正文和存储文件不变，失败的写入也不压缩，便于重试。

| 变量 | 默认值与含义 |
| --- | --- |
| `AGENT_HISTORY_TURNS` | 4，仅回放最近的用户问题与助手正文 |
| `AGENT_HISTORY_MESSAGE_CHARS` | 4000，每条历史消息的正文长度上限 |
| `AGENT_MAX_INPUT_BYTES` | 128000，单次请求的指令、工具定义及消息 UTF-8 字节预算 |
| `AGENT_MAX_TOOL_OUTPUT_CHARS` | 12000，单条工具返回内容的预览长度上限 |
| `AGENT_MAX_OUTPUT_TOKENS` | 4096，单次请求最大输出 token 数 |
| `AGENT_MAX_RUN_INPUT_BYTES` | 512000，一次发送包含的所有模型请求累计输入字节预算 |

历史工具参数、工具返回值、推理记录和图片不会在后续用户轮次中重放；当前轮的工具调用仍保留完整配对。历史正文超过上限时明确标注缩短，原始记录与文件仍保存在本地。需要精确引用旧文件时重新使用文件工具。

字节预算不是 token 数，也不是费用估算。运行记录使用供应商返回的 token 用量，缓存输入是输入的子集，推理输出是输出的子集，不能再次相加。`request_input_bytes` 记录每次模型请求的输入大小。未返回用量时界面明确显示未知，不伪造为零消耗。

修改 `.env` 或更新运行时代码后需要重启后端；前端改动需要重新构建。旧运行若没有 `usage` 字段或为空，无法追溯其真实 token 消耗，需与供应商账单核对。

## 联网

默认 `AGENT_SEARCH_PROVIDER=none`，不产生搜索调用。

| 选择 | 配置 |
| --- | --- |
| `tavily` | 设置 `AGENT_SEARCH_API_KEY`；可选自定义 `AGENT_SEARCH_BASE_URL` |
| `brave` | 设置 `AGENT_SEARCH_API_KEY`；可选自定义 `AGENT_SEARCH_BASE_URL` |
| `searxng` | 设置 `AGENT_SEARCH_BASE_URL`，例如自己的 `/search` 接口，服务应支持 JSON 输出 |

启用后 `web_search` 才会进入工具清单。用户可以要求智能体联网查询，也可以让技能说明指导智能体使用。每次搜索最多返回有限长度的结果；服务可用性、费用和授权由接收者自行维护。

## GEOFlow

配置完成后，智能体 Framework 会在对话中提供只读的 GEOFlow 工具：读取目录、搜索文章和读取文章详情。Token 只在后端使用，不会发送给浏览器。

```dotenv
AGENT_GEOFLOW_BASE_URL=https://geoflow.example.com
AGENT_GEOFLOW_API_TOKEN=
AGENT_GEOFLOW_TIMEOUT=30
AGENT_GEOFLOW_VERIFY_TLS=true
```

建议使用 GEOFlow API Token，并只授予 `catalog:read`、`articles:read` scope。文章创建、更新、审核和发布属于写操作，应在加入明确的用户确认和幂等键流程后再开放。

## 路径和账号

- `AGENT_HOST`：后端监听地址，默认 `127.0.0.1`；局域网访问可设为 `0.0.0.0`。
- `AGENT_PORT`：后端监听端口，默认 `8787`。
- `AGENT_SECURE_COOKIE`：登录 Cookie 是否只通过 HTTPS 发送。生产环境必须为 `true`；使用普通 HTTP 的可信局域网临时测试必须为 `false`，否则登录后接口会返回 `401`。

- `AGENT_DATA_DIR`：数据库与 SDK 对话历史，默认 `data/`。
- `AGENT_SKILLS_DIR`：技能根目录，默认 `skills/`。
- `AGENT_MCP_CONFIG`：MCP 配置路径，默认 `mcp.json`。
- `AGENT_MAX_UPLOAD_MB`：单文件上传上限，默认 20 MB。
- `AGENT_DEMO_ACCOUNT=true`：仅在全新开发数据库创建 `admin / 123`，不重置已有账号。
- `AGENT_DEPLOYMENT_MODE=production`：要求关闭体验账号，并开启 `AGENT_SECURE_COOKIE=true`。

路径可以设置为项目相对路径或绝对路径。不要将自己的 `.env`、数据库或私钥打包转交给别人。

## MCP 密钥

把 MCP 使用的变量也写入自己的 `.env`。`python -m app` 启动时会加载这些变量。

```dotenv
YOUR_MCP_AUTHORIZATION=
YOUR_MCP_API_KEY=
```

在 MCP 配置中用 `${YOUR_MCP_AUTHORIZATION}` 等引用变量。不要将真实密钥写进 JSON、命令行参数或技能说明。
