# 技能与 MCP

## 技能标准

```text
skills/
  your-skill/
    SKILL.md
    references/
    scripts/
    assets/
```

只要求根目录有 `SKILL.md`，其余目录按技能需要提供，不再加分类目录。

```markdown
---
name: your-skill
description: 说明什么时候应该使用此技能，以及能帮助完成什么工作。
metadata:
  display_name: 中文技能名称
  author: 作者或项目名称
---

# 技能说明

在这里编写步骤、约束和资源引用。
```

名称使用小写英文、数字和短横线，并与技能文件夹名称一致。作者从 `metadata.author` 或 `author` 读取；未声明时明确显示“未标注”。框架附带 `example-note` 示例，可按同一格式添加其他技能。

界面名称优先读取 `metadata.display_name`，可填写中文；未填写时读取正文首个一级标题，再回退到 `name`。技能列表、选择菜单和聊天记录使用此名称，接口调用和目录仍使用 `name`。

管理员可以在技能页面导入单个 `SKILL.md`、完整目录或一个技能 ZIP。一次最多 300 个文件、20 MB，总包必须包含根级 `SKILL.md`；压缩包可以带一层目录。同名技能不会被静默覆盖。路径穿越、隐藏文件和符号链接会被拒绝。

所有已安装技能可供本地平台用户使用。输入框加号菜单可选择本轮技能；智能体也能按任务自行调用 `load_skill`。发送成功后清空本轮选择；技能名称随用户消息保留。`read_skill_resource` 按需读取技能内 UTF-8 资源，`scripts/` 可保留但不会自动执行。

## MCP 标准

支持通用 `mcpServers` 对象，示例见根目录 `mcp.example.json`。默认注册表为空，不自动安装或连接第三方服务。

管理员进入 MCP 页面，将服务提供方的 JSON 配置粘贴到配置框，点击“保存”，再点击“测试连接”。也可以直接编辑后端使用的 `mcp.json`。配置保存会替换整个注册表，新增时应保留现有服务。一个 `mcpServers` 对象内最多可配置 32 个不同名称的服务，每个服务可单独设置 `enabled`；每次任务会连接全部已启用的服务，但不会把全部工具定义自动发送给模型。

```json
{
  "mcpServers": {
    "your-server": {
      "type": "streamable_http",
      "url": "https://your-server.example/mcp",
      "headers": {"Authorization": "${YOUR_MCP_AUTHORIZATION}"},
      "allowed_tools": ["search"],
      "enabled": true
    }
  }
}
```

- stdio 使用 `command`、`args`、`env`。
- HTTP 使用 `type: streamable_http`，SSE 使用 `type: sse`。
- `allowed_tools` 限制可见工具；空数组不开放工具，省略时开放服务提供的全部工具。
- 模型先通过 `list_mcp_tools` 按名称或说明搜索目录（每页 10 项），再通过 `load_mcp_tool` 加载需要的单个工具定义。加载后仍使用 SDK 原生 MCP 调用、白名单和审批机制；普通聊天不加载业务工具定义。
- 管理员保存后可以手动测试连接，显示服务和工具名称。
- `env` 和 `headers` 必须引用环境变量，实际值不会出现在注册表中。
- 连接由任务创建和清理；任一已启用服务连接失败时，本次任务会报告异常，不假装已成功执行。

stdio 服务是本机程序，以后端进程用户的权限运行；MCP 不是自动沙箱。仅管理员可配置服务和导入技能。接入来源、工具副作用、第三方许可及费用需由部署者确认。

本地 MCP 示例可以配置 `command` 为本环境 Python 可执行文件，`args` 为 `examples/echo_mcp.py` 的路径，工具白名单为 `ping`。这只用于连通性测试，没有外部账号或业务信息。

## 上下文与用量保护

- `AGENT_HISTORY_TURNS=8`：发送最近 8 个完整历史轮次，完整会话仍保留在数据库。历史图片改为提示文字，需要再次分析时重新上传。
- `AGENT_MAX_INPUT_BYTES=64000`：每次模型请求的指令、输入和已加载工具定义的序列化 UTF-8 字节预算；超额时按完整历史轮次移除，当前轮仍超额则停止并提示拆分。它是本地大小保护，不是精确 token 数；当前图片的 base64 也计入，过大图片需要缩小后上传。
- `AGENT_MAX_TOOL_OUTPUT_CHARS=8000`：每次请求前限制单条工具返回，超长结果用合法 JSON 标注 `truncated` 和预览，提示模型缩小查询或分页。覆盖 MCP、技能、附件及搜索结果，不修改数据库中的原始结果。
- `AGENT_MAX_OUTPUT_TOKENS=4096`：每次模型调用的输出上限。
- `AGENT_MAX_RUN_INPUT_BYTES=256000`：单个用户任务内多次模型调用的累计输入预算，避免工具循环持续发送大上下文；`AGENT_MAX_TURNS=12` 仍限制调用轮次。
- 技能目录仅提供名称和简短说明；完整技能按用户选择或 `load_skill` 加载。
- 每个任务记录模型请求次数、累计上下文字节、裁剪次数及服务返回的输入/输出 token，页面显示请求次数和 token 用量。服务未返回用量时明确标注，不能把本地字节数当成计费 token。历史任务没有补算用量。

修改环境配置或更新代码后重启后端；前端需重新构建。上下文限额会影响可见历史及长文任务，可按实际模型和预算调整。
