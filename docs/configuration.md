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
