# 第三方说明

本框架包含或依赖以下公共项目。安装时须保留依赖分发包中各自的版权和许可文件。

| 项目 | 用途 | 许可/来源 |
| --- | --- | --- |
| OpenAI Agents SDK | 通用 Agent 与工具调用 | MIT，https://github.com/openai/openai-agents-python |
| OpenAI Python | 模型协议客户端 | Apache-2.0，https://github.com/openai/openai-python |
| MCP Python SDK | MCP 客户端及示例服务 | MIT，https://github.com/modelcontextprotocol/python-sdk |
| FastAPI / Starlette | HTTP 与会话接口 | MIT / BSD-3-Clause，见依赖包 |
| React | 前端 | MIT，https://github.com/facebook/react |
| Vite | 构建 | MIT，https://github.com/vitejs/vite |
| BeUI | 输入框、按钮、卡片、复选框、提示浮层与对话输入区 | MIT，https://github.com/starc007/ui-components ，完整文本见 licenses/BeUI-LICENSE |
| Motion / Tailwind CSS / Floating UI | BeUI 的交互、样式与浮层定位依赖 | MIT，见各依赖包随附许可证 |
| Lucide | 机器人标识及工具图标 | ISC / 部分 Feather MIT，完整文本见 licenses/Lucide-LICENSE |
| NASA Apollo 8 | 登录静态摄影 | 公共领域政府作品及 NASA 媒体使用规定，见 docs/assets.md |
| python-docx / pypdf | 文档文字提取 | MIT / BSD-3-Clause，见依赖包 |
| Argon2-cffi / Pillow / PyYAML | 密码、图片与元数据处理 | 见各依赖包随附许可证 |

锁定的依赖版本以 `uv.lock`、`web/package-lock.json` 为准。这里不声称覆盖所有传递依赖的许可审查；公开分发时应针对实际安装版本生成 SBOM 并检查许可。

BeUI 组件来自官方公开 Registry，部分文件为适应附件、技能选择和中文界面做了调整。
