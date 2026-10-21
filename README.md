# 智能体

一个可自行配置模型、联网服务、标准技能和 MCP 的轻量开发框架。

接收者提供自己的模型服务地址、模型 ID 和 API Key 后，即可开始对话。模型可按需读取技能说明、读取附件、创建文本文件，以及调用启用的 MCP 工具。

## 包含什么

- 登录和会话鉴权、CSRF 校验、用户数据隔离、修改密码。
- 持久化对话、流式回复、工具执行、停止任务、执行耗时。
- 标准 `skills/<name>/SKILL.md`，支持文件、文件夹或 ZIP 导入，查看正文和资源。
- 标准 `mcpServers` 配置，支持 stdio、Streamable HTTP、SSE，以及工具白名单。
- 可选 Tavily、Brave、SearXNG 联网搜索，全部使用接收者自己的服务。
- 上传和读取文本、Word、PDF、图片；预览与下载；生成 Markdown、HTML 等文本文件。
- 静态登录封面、Lucide 通用机器人图标、明暗主题，无流动背景或文字动效。
- BeUI 官方基础组件与对话输入区，保留组件交互动效，支持系统减少动态效果偏好。

## 本地启动

需要 Python 3.11+、[uv](https://docs.astral.sh/uv/getting-started/installation/)、Node.js 22.12+。

```sh
cp .env.example .env
uv sync --frozen
cd web
npm ci
npm run build
cd ..
uv run python -m app
```

打开 <http://127.0.0.1:8787>。全新本地数据库会创建体验账号 **admin / 123**，登录表单已预填。即使暂未配置模型，也能登录、查看技能和设置 MCP；实际对话需要先填写模型配置并重启后端。

`.env` 中填写自己的值，不要把真实密钥提交到仓库：

```dotenv
AGENT_BASE_URL=
AGENT_MODEL=
AGENT_API_KEY=
AGENT_API_MODE=chat
```

`BASE_URL` 填供应商提供的 API 根路径，通常包含 `/v1`，不填具体的 `/chat/completions`。模型 ID 以供应商文档为准；支持 Chat Completions 或 Responses 的模型服务均可按相应模式配置。需要模型支持工具调用。

## 文档

- [配置说明](docs/configuration.md)：模型、联网、MCP 环境变量。
- [开发与架构](docs/development.md)：目录结构、工具扩展、测试。
- [技能与 MCP](docs/skills-and-mcp.md)：标准格式、导入、连接测试。
- [接口说明](docs/api.md)：登录、流式对话、附件和扩展接口。
- [运行与维护](docs/operations.md)：正式运行、账号、数据和限制。
- [资源来源](docs/assets.md)：图标、静态封面的许可与来源。
- [验证与打包](docs/export-report.md)：检查命令、验证结果与打包方式。

## 使用许可

本项目尚未指定公开发布的开源许可证，使用授权见 [LICENSE](LICENSE)。第三方依赖及公共资源保留各自许可证，见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
